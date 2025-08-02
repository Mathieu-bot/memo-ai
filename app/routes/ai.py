from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any
import logging

from app.services.db import get_db
from app.services.ai_service import AIService
from app.models.course import Course as CourseModel
from app.models.quiz import Quiz as QuizModel
from app.models.question import Question as QuestionModel
from app.models.answer import Answer as AnswerModel

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])

@router.post("/generate-quiz/{course_id}", status_code=status.HTTP_201_CREATED)
def generate_quiz(course_id: int, num_questions: int = 5, db: Session = Depends(get_db)):
    course = db.query(CourseModel).filter(CourseModel.id == course_id).first()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    quiz_data = AIService.generate_quiz(
        course_title=course.title,
        course_description=course.description or "",
        num_questions=num_questions
    )

    db_quiz = QuizModel(
        title=quiz_data["title"],
        description=quiz_data["description"],
        course_id=course_id
    )
    db.add(db_quiz)
    db.flush()  # get quiz id

    for question_data in quiz_data["questions"]:
        db_question = QuestionModel(
            text=question_data["text"],
            explanation=question_data.get("explanation", ""),
            quiz_id=db_quiz.id
        )
        db.add(db_question)
        db.flush()

        for answer_data in question_data["answers"]:
            db_answer = AnswerModel(
                text=answer_data["text"],
                is_correct=answer_data["is_correct"],
                question_id=db_question.id
            )
            db.add(db_answer)

    db.commit()

    return {"message": "Quiz generated successfully", "quiz_id": db_quiz.id}