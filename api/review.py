from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import os
from dotenv import load_dotenv

from db.models import Question, User, QuestionWeight, AnswerRecord
from db.schemas import ReviewStart, ReviewSubmit, ReviewProgress, QuestionResponse
from db.database import get_db
from api.auth import get_current_user
from core.weight_manager import (
    mark_question_reviewed,
    mark_question_confused,
    get_weighted_questions,
    get_question_weight,
    add_review_question
)

load_dotenv()

_review_agent = None


def _get_review_agent():
    global _review_agent
    if _review_agent is None and os.getenv("DEEPSEEK_API_KEY"):
        from core.agents.review_agent import ReviewAgent
        _review_agent = ReviewAgent()
    return _review_agent


router = APIRouter(prefix="/api/review", tags=["review"])

review_session = {}


@router.post("/start")
def start_review(
    review: ReviewStart,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    weighted_questions = get_weighted_questions(current_user.id, db, review.count)
    
    if not weighted_questions:
        questions = db.query(Question).filter(
            Question.user_id == current_user.id
        ).order_by(Question.created_at.desc()).limit(review.count).all()
        
        for q in questions:
            add_review_question(current_user.id, q.id, db)
        
        weighted_questions = get_weighted_questions(current_user.id, db, review.count)
    
    review_data = {
        "questions": [q[0].id for q in weighted_questions],
        "current_index": 0,
        "total_reviewed": 0,
        "correct_count": 0,
        "confused_count": 0,
        "start_time": datetime.utcnow()
    }
    
    session_id = f"{current_user.id}_{datetime.utcnow().timestamp()}"
    review_session[session_id] = review_data
    
    first_question_id = weighted_questions[0][0].id if weighted_questions else None
    
    if first_question_id:
        question = db.query(Question).filter(Question.id == first_question_id).first()
        weight = get_question_weight(current_user.id, first_question_id, db)
        
        return {
            "session_id": session_id,
            "total_count": len(review_data["questions"]),
            "current_index": 0,
            "question": QuestionResponse(
                id=question.id,
                content=question.content,
                question_type=question.question_type,
                category=question.category,
                source=question.source,
                answer=question.answer or "",
                difficulty=question.difficulty,
                created_at=question.created_at,
                weight=weight
            ),
            "is_weighted": weight > 0
        }
    
    return {"session_id": session_id, "message": "No questions available for review"}


@router.get("/next")
def get_next_question(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if session_id not in review_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review session not found"
        )
    
    session = review_session[session_id]
    
    if session["current_index"] >= len(session["questions"]):
        return {"message": "Review completed", "session_id": session_id}
    
    question_id = session["questions"][session["current_index"]]
    question = db.query(Question).filter(Question.id == question_id).first()
    
    if not question:
        session["current_index"] += 1
        return get_next_question(session_id, db, current_user)
    
    weight = get_question_weight(current_user.id, question_id, db)
    
    return {
        "session_id": session_id,
        "total_count": len(session["questions"]),
        "current_index": session["current_index"],
        "question": QuestionResponse(
            id=question.id,
            content=question.content,
            question_type=question.question_type,
            category=question.category,
            source=question.source,
            answer=question.answer or "",
            difficulty=question.difficulty,
            created_at=question.created_at,
            weight=weight
        ),
        "is_weighted": weight > 0
    }


@router.post("/submit")
def submit_review_answer(
    session_id: str,
    submit: ReviewSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if session_id not in review_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review session not found"
        )
    
    session = review_session[session_id]

    # 使用复习agent评估答案
    question = db.query(Question).filter(Question.id == submit.question_id).first()
    is_correct = False
    score = 0
    feedback = ""

    agent = _get_review_agent()
    if agent and submit.user_answer and len(submit.user_answer.strip()) > 5:
        try:
            result = agent.evaluate_answer(
                question.content if question else "",
                submit.user_answer,
                question.answer if question and question.answer else None
            )
            is_correct = result.get("is_correct", False)
            score = result.get("score", 0)
            feedback = result.get("feedback", "")
        except Exception as e:
            print(f"ReviewAgent error: {e}")
            is_correct = len(submit.user_answer) > 20
            score = 60 if is_correct else 0
    elif submit.user_answer and len(submit.user_answer.strip()) > 10:
        is_correct = True
        score = 70

    mark_question_reviewed(current_user.id, submit.question_id, is_correct, db)

    if submit.is_confused:
        mark_question_confused(current_user.id, submit.question_id, db)
        session["confused_count"] += 1

    if is_correct:
        session["correct_count"] += 1

    session["total_reviewed"] += 1
    session["current_index"] += 1

    answer_record = AnswerRecord(
        user_id=current_user.id,
        question_id=submit.question_id,
        user_answer=submit.user_answer,
        is_correct=is_correct,
        score=score
    )
    db.add(answer_record)
    db.commit()

    return {
        "session_id": session_id,
        "total_reviewed": session["total_reviewed"],
        "correct_count": session["correct_count"],
        "confused_count": session["confused_count"],
        "is_correct": is_correct,
        "score": score,
        "feedback": feedback,
        "message": "Answer submitted successfully"
    }


@router.get("/progress", response_model=ReviewProgress)
def get_review_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    total_reviewed = db.query(AnswerRecord).filter(
        AnswerRecord.user_id == current_user.id
    ).count()
    
    correct_count = db.query(AnswerRecord).filter(
        AnswerRecord.user_id == current_user.id,
        AnswerRecord.is_correct == True
    ).count()
    
    confused_count = db.query(QuestionWeight).filter(
        QuestionWeight.user_id == current_user.id,
        QuestionWeight.confused_count > 0
    ).count()
    
    weight_records = db.query(QuestionWeight).filter(
        QuestionWeight.user_id == current_user.id
    ).all()
    
    weight_distribution = {}
    for record in weight_records:
        weight_range = f"{(record.weight // 10) * 10}-{(record.weight // 10) * 10 + 9}"
        weight_distribution[weight_range] = weight_distribution.get(weight_range, 0) + 1
    
    return ReviewProgress(
        total_reviewed=total_reviewed,
        correct_count=correct_count,
        confused_count=confused_count,
        current_weight_distribution=weight_distribution
    )


@router.get("/weighted-questions")
def get_weighted_review_questions(
    limit: Optional[int] = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    weighted_questions = get_weighted_questions(current_user.id, db, limit)
    
    questions = []
    for q, w in weighted_questions:
        questions.append({
            "question": QuestionResponse(
                id=q.id,
                content=q.content,
                question_type=q.question_type,
                category=q.category,
                source=q.source,
                answer=q.answer or "",
                difficulty=q.difficulty,
                created_at=q.created_at,
                weight=w.weight
            ),
            "weight_info": {
                "weight": w.weight,
                "confused_count": w.confused_count,
                "review_count": w.review_count,
                "last_review_time": w.last_review_time
            }
        })
    
    return questions