from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from dotenv import load_dotenv
import os

from db.models import User, Question, Project
from db.schemas import QuestionResponse
from db.database import get_db
from api.auth import get_current_user
from core.agents.exam_agent import ExamAgent
from core.agents.answer_agent import AnswerAgent
from core.agents.project_agent import ProjectAgent
from core.weight_manager import get_question_weight

load_dotenv()

_exam_agent = None
_answer_agent = None
_project_agent = None


def _get_exam_agent():
    global _exam_agent
    if _exam_agent is None and os.getenv("DEEPSEEK_API_KEY"):
        _exam_agent = ExamAgent()
    return _exam_agent


def _get_answer_agent():
    global _answer_agent
    if _answer_agent is None and os.getenv("DEEPSEEK_API_KEY"):
        _answer_agent = AnswerAgent()
    return _answer_agent


def _get_project_agent():
    global _project_agent
    if _project_agent is None and os.getenv("DEEPSEEK_API_KEY"):
        _project_agent = ProjectAgent()
    return _project_agent


router = APIRouter(prefix="/api/llm", tags=["llm"])


@router.post("/generate-questions")
def generate_questions_with_llm(
    topic: str,
    count: Optional[int] = 5,
    project_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    agent = _get_exam_agent()
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LLM service not configured"
        )

    project_info = ""
    if project_id:
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == current_user.id
        ).first()
        if project:
            project_info = f"名称：{project.name}\n描述：{project.description}\n技术栈：{project.tech_stack}"

    questions_data = agent.generate(topic, count, project_info)

    saved_questions = []
    for q_data in questions_data:
        question = Question(
            user_id=current_user.id,
            content=q_data.get("content", ""),
            question_type=q_data.get("question_type", "bagua"),
            category=q_data.get("category", "other"),
            source="AI生成",
            answer=q_data.get("answer", ""),
            difficulty=q_data.get("difficulty", 2)
        )
        db.add(question)
        saved_questions.append(question)

    db.commit()

    response = []
    for q in saved_questions:
        db.refresh(q)
        weight = get_question_weight(current_user.id, q.id, db)
        response.append(QuestionResponse(
            id=q.id,
            content=q.content,
            question_type=q.question_type,
            category=q.category,
            source=q.source,
            answer=q.answer or "",
            difficulty=q.difficulty,
            created_at=q.created_at,
            weight=weight
        ))

    return response


@router.post("/generate-answer/{question_id}")
def generate_answer_for_question(
    question_id: int,
    project_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    agent = _get_answer_agent()
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LLM service not configured"
        )

    question = db.query(Question).filter(
        Question.id == question_id,
        Question.user_id == current_user.id
    ).first()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )

    project_info = ""
    if project_id:
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == current_user.id
        ).first()
        if project:
            project_info = f"名称：{project.name}\n描述：{project.description}"

    answer = agent.generate_answer(question.content, project_info)

    question.answer = answer
    db.commit()

    weight = get_question_weight(current_user.id, question.id, db)

    return QuestionResponse(
        id=question.id,
        content=question.content,
        question_type=question.question_type,
        category=question.category,
        source=question.source,
        answer=question.answer,
        difficulty=question.difficulty,
        created_at=question.created_at,
        weight=weight
    )


@router.post("/analyze-project/{project_id}")
def analyze_project_with_llm(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    agent = _get_project_agent()
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LLM service not configured"
        )

    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    analysis = agent.analyze(project.description)

    return {
        "project_id": project_id,
        "project_name": project.name,
        "analysis": analysis
    }
