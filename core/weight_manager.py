from db.models import QuestionWeight, Question
from sqlalchemy.orm import Session
from datetime import datetime, timedelta


def mark_question_confused(user_id: int, question_id: int, db: Session):
    weight_record = db.query(QuestionWeight).filter(
        QuestionWeight.user_id == user_id,
        QuestionWeight.question_id == question_id
    ).first()
    
    if weight_record:
        weight_record.weight += 20
        weight_record.confused_count += 1
        weight_record.last_review_time = datetime.utcnow()
    else:
        weight_record = QuestionWeight(
            user_id=user_id,
            question_id=question_id,
            weight=20,
            confused_count=1,
            last_review_time=datetime.utcnow()
        )
        db.add(weight_record)
    
    db.commit()


def mark_question_reviewed(user_id: int, question_id: int, is_correct: bool, db: Session):
    weight_record = db.query(QuestionWeight).filter(
        QuestionWeight.user_id == user_id,
        QuestionWeight.question_id == question_id
    ).first()
    
    if weight_record:
        weight_record.review_count += 1
        weight_record.last_review_time = datetime.utcnow()
        
        if is_correct:
            weight_record.weight = max(0, weight_record.weight - 10)
        else:
            weight_record.weight += 15
    else:
        weight = 15 if not is_correct else 0
        weight_record = QuestionWeight(
            user_id=user_id,
            question_id=question_id,
            weight=weight,
            review_count=1,
            last_review_time=datetime.utcnow()
        )
        db.add(weight_record)
    
    db.commit()


def add_review_question(user_id: int, question_id: int, db: Session):
    weight_record = db.query(QuestionWeight).filter(
        QuestionWeight.user_id == user_id,
        QuestionWeight.question_id == question_id
    ).first()
    
    if weight_record:
        weight_record.weight += 10
    else:
        weight_record = QuestionWeight(
            user_id=user_id,
            question_id=question_id,
            weight=10
        )
        db.add(weight_record)
    
    db.commit()


def apply_time_decay(user_id: int, db: Session):
    weight_records = db.query(QuestionWeight).filter(
        QuestionWeight.user_id == user_id
    ).all()
    
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    
    for record in weight_records:
        if record.last_review_time and record.last_review_time < seven_days_ago:
            record.weight = max(0, record.weight - 5)
    
    db.commit()


def get_weighted_questions(user_id: int, db: Session, limit: int = 10) -> list:
    apply_time_decay(user_id, db)
    
    weighted_questions = db.query(Question, QuestionWeight).join(
        QuestionWeight, Question.id == QuestionWeight.question_id
    ).filter(
        QuestionWeight.user_id == user_id
    ).order_by(QuestionWeight.weight.desc()).limit(limit).all()
    
    return [(q, w) for q, w in weighted_questions]


def get_question_weight(user_id: int, question_id: int, db: Session) -> int:
    weight_record = db.query(QuestionWeight).filter(
        QuestionWeight.user_id == user_id,
        QuestionWeight.question_id == question_id
    ).first()
    
    return weight_record.weight if weight_record else 0