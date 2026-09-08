from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.exceptions import AIServiceError, NotFoundError
from app.models import Answer as AnswerModel
from app.models import Course as CourseModel
from app.models import Question as QuestionModel
from app.models import Quiz as QuizModel
from app.services.ai import QuizGenerator, get_ai_provider

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/generate-quiz/{course_id}", status_code=status.HTTP_201_CREATED)
async def generate_quiz(
    course_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    num_questions: int = 5,
):
    course_result = await db.execute(
        select(CourseModel).where(CourseModel.id == course_id)
    )
    course = course_result.scalar_one_or_none()
    if course is None:
        raise NotFoundError("Course", course_id)

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

    if not quiz_data.get("title") or not quiz_data.get("questions"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI returned an invalid quiz structure",
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

        for answer_data in question_data.get("answers", []):
            db_answer = AnswerModel(
                text=answer_data["text"],
                is_correct=answer_data.get("is_correct", False),
                question_id=db_question.id,
            )
            db.add(db_answer)

    await db.commit()
    return {"quiz_id": db_quiz.id}
