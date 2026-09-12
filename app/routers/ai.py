from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import get_course_or_404
from app.auth import current_user
from app.config import get_settings
from app.dependencies import get_db
from app.exceptions import AIServiceError
from app.limiter import limiter
from app.models import Answer as AnswerModel
from app.models import Question as QuestionModel
from app.models import Quiz as QuizModel
from app.models import User
from app.services.ai import QuizGenerator, get_ai_provider

router = APIRouter(prefix="/ai", tags=["ai"])
settings = get_settings()


def _validate_quiz_data(data) -> str | None:
    if not isinstance(data, dict):
        return "AI returned an invalid quiz structure"
    title = data.get("title")
    questions = data.get("questions")
    if (
        not isinstance(title, str)
        or not title.strip()
        or not isinstance(questions, list)
        or not questions
    ):
        return "AI returned an invalid quiz structure"
    for index, question in enumerate(questions):
        if (
            not isinstance(question, dict)
            or not isinstance(question.get("text"), str)
            or not question["text"].strip()
        ):
            return f"AI returned an invalid question at index {index}"
        answers = question.get("answers", [])
        if not isinstance(answers, list) or len(answers) < 2:
            return f"AI returned invalid answers for question {index + 1}"
        for answer in answers:
            if (
                not isinstance(answer, dict)
                or not isinstance(answer.get("text"), str)
                or not answer["text"].strip()
            ):
                return f"AI returned an invalid answer for question {index + 1}"
    return None


@router.post("/generate-quiz/{course_id}", status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_AI)
async def generate_quiz(
    request: Request,
    course_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
    num_questions: Annotated[int, Query(ge=1, le=25)] = 5,
):
    course = await get_course_or_404(db, user, course_id, write=True)

    provider = get_ai_provider()
    quiz_generator = QuizGenerator(provider)
    try:
        quiz_data = await quiz_generator.generate(
            title=course.title,
            description=course.description or "",
            num_questions=num_questions,
        )
    except AIServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI quiz generation failed",
        ) from exc

    validation_error = _validate_quiz_data(quiz_data)
    if validation_error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=validation_error,
        )

    db_quiz = QuizModel(
        title=quiz_data["title"],
        description=quiz_data.get("description"),
        course_id=course_id,
    )
    db.add(db_quiz)
    await db.flush()

    for question_data in quiz_data["questions"]:
        db_question = QuestionModel(
            text=question_data["text"],
            explanation=question_data.get("explanation", ""),
            quiz_id=db_quiz.id,
        )
        db.add(db_question)
        await db.flush()

        for answer_data in question_data["answers"]:
            db_answer = AnswerModel(
                text=answer_data["text"],
                is_correct=answer_data.get("is_correct", False),
                question_id=db_question.id,
            )
            db.add(db_answer)

    await db.commit()
    return {"quiz_id": db_quiz.id}
