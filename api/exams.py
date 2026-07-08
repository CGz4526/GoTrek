from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
import random
import os
from datetime import datetime
from dotenv import load_dotenv

from db.models import Question, Project, User, QuestionProject, QuestionWeight
from db.schemas import ExamGenerate, QuestionResponse
from db.database import get_db
from api.auth import get_current_user
from core.weight_manager import get_question_weight
from core.agents.exam_agent import ExamAgent

load_dotenv()

router = APIRouter(prefix="/api/exams", tags=["exams"])

_exam_agent = None


def _get_exam_agent():
    global _exam_agent
    if _exam_agent is not None:
        return _exam_agent
    if os.getenv("DEEPSEEK_API_KEY"):
        _exam_agent = ExamAgent()
    return _exam_agent


def _q_to_dict(q, weight=0, source_type="library"):
    """把Question模型/生成dict转成统一dict格式"""
    return {
        "id": q.id if hasattr(q, 'id') else (q.get('id', 0) or 0),
        "content": q.content if hasattr(q, 'content') else q.get('content', ''),
        "question_type": q.question_type if hasattr(q, 'question_type') else q.get('question_type', 'bagua'),
        "category": q.category if hasattr(q, 'category') else q.get('category', 'other'),
        "source": (q.source if hasattr(q, 'source') else q.get('source', 'generated')) or 'generated',
        "answer": (q.answer if hasattr(q, 'answer') else q.get('answer', '')) or '',
        "difficulty": q.difficulty if hasattr(q, 'difficulty') else q.get('difficulty', 2),
        "created_at": (q.created_at if hasattr(q, 'created_at') else q.get('created_at')) or datetime.utcnow(),
        "weight": weight,
        "source_type": source_type,
    }


@router.post("/generate")
def generate_exam(
    exam: ExamGenerate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if exam.mode not in ['project', 'bagua', 'mixed']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mode must be 'project', 'bagua', or 'mixed'"
        )

    count = exam.count or 10
    library_questions = []
    generated_questions = []
    project_info = None

    # 收集项目信息
    if exam.project_id:
        project = db.query(Project).filter(
            Project.id == exam.project_id,
            Project.user_id == current_user.id
        ).first()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        project_info = {
            "id": project.id,
            "name": project.name,
            "tech_stack": project.tech_stack or [],
            "project_type": project.project_type or "other",
            "description": project.description or "",
        }

    # 1. 从题库中取相关题目（作为一部分）
    if exam.mode == 'project' or exam.mode == 'mixed':
        if exam.project_id:
            # 取该项目关联的题
            project_questions = db.query(QuestionProject).filter(
                QuestionProject.project_id == exam.project_id
            ).order_by(QuestionProject.match_score.desc()).limit(count).all()
            for qa in project_questions:
                weight = get_question_weight(current_user.id, qa.question_id, db)
                library_questions.append(_q_to_dict(qa.question, weight, "library"))
        else:
            # 取所有项目类型题
            qs = db.query(Question).filter(
                Question.user_id == current_user.id,
                Question.question_type == 'project'
            ).order_by(Question.difficulty.desc()).limit(count).all()
            for q in qs:
                weight = get_question_weight(current_user.id, q.id, db)
                library_questions.append(_q_to_dict(q, weight, "library"))

    if exam.mode == 'bagua' or exam.mode == 'mixed':
        query = db.query(Question).filter(
            Question.user_id == current_user.id,
            Question.question_type == 'bagua'
        )
        if exam.category:
            query = query.filter(Question.category == exam.category)
        qs = query.order_by(Question.difficulty.desc()).limit(count).all()
        for q in qs:
            weight = get_question_weight(current_user.id, q.id, db)
            library_questions.append(_q_to_dict(q, weight, "library"))

    # 2. 调用ExamAgent生成新题目（基于项目或主题）
    agent = _get_exam_agent()
    if agent is not None:
        # 收集已有题目供agent参考（避免重复）
        existing_for_agent = [
            {"content": q["content"], "question_type": q["question_type"], "category": q["category"]}
            for q in library_questions[:15]
        ]
        try:
            topic = exam.category or ""
            generated = agent.generate(
                topic=topic,
                count=count,
                project_info=project_info,
                existing_questions=existing_for_agent
            )
            for g in generated:
                # 给生成的题一个临时负id（前端区分用）
                g["id"] = -(hash(g["content"]) % 100000)
                g["weight"] = 0
                g["source_type"] = "generated"
                g["created_at"] = datetime.utcnow()
                generated_questions.append(g)
        except Exception as e:
            print(f"ExamAgent failed: {e}")

    # 3. 合并：优先agent生成的题（更针对项目），再用题库题补充
    all_questions = generated_questions + library_questions
    all_questions = all_questions[:count]

    # 如果agent生成失败且题库也没题，尝试用通用模板兜底
    if not all_questions:
        all_questions = _fallback_templates(count, exam.category, project_info)

    # 项目模式不打乱顺序（保持递进逻辑），其他模式可以打乱
    if exam.mode == 'bagua' and not project_info:
        random.shuffle(all_questions)

    return {
        "id": hash(tuple(q.get("id", 0) for q in all_questions)),
        "mode": exam.mode,
        "project_id": exam.project_id,
        "category": exam.category,
        "questions": all_questions,
        "generated_count": len(generated_questions),
        "library_count": len([q for q in all_questions if q.get("source_type") == "library"]),
        "generated_at": datetime.utcnow()
    }


def _fallback_templates(count, category, project_info):
    """LLM不可用时的兜底模板"""
    templates = {
        'redis': [
            "请简述Redis的持久化机制，RDB和AOF的区别是什么？",
            "Redis的缓存雪崩、缓存击穿、缓存穿透分别是什么？如何解决？",
            "Redis的主从复制原理是什么？哨兵模式的作用是什么？",
        ],
        'mysql': [
            "MySQL的索引类型有哪些？B+树索引的特点是什么？",
            "MySQL的事务隔离级别有哪些？各自解决了什么问题？",
            "MySQL的锁机制有哪些？行锁和表锁的区别是什么？",
        ],
        'distributed': [
            "分布式锁有哪些实现方式？各自的优缺点是什么？",
            "分布式事务如何解决？常见的方案有哪些？",
            "CAP定理是什么？BASE理论如何应对？",
        ],
    }
    result = []
    if project_info:
        result.append({
            "id": -1,
            "content": f"请介绍一下「{project_info['name']}」项目的整体架构设计",
            "question_type": "project",
            "category": "project",
            "source": "fallback",
            "answer": "",
            "difficulty": 3,
            "weight": 0,
            "source_type": "generated",
            "created_at": datetime.utcnow(),
        })
    cat = category or 'redis'
    for i, t in enumerate(templates.get(cat, templates['redis'])):
        if len(result) >= count:
            break
        result.append({
            "id": -(i + 2),
            "content": t,
            "question_type": "bagua",
            "category": cat,
            "source": "fallback",
            "answer": "",
            "difficulty": 3,
            "weight": 0,
            "source_type": "generated",
            "created_at": datetime.utcnow(),
        })
    return result[:count]


@router.post("/generate/auto")
def generate_auto_exam(
    project_id: Optional[int] = None,
    category: Optional[str] = None,
    count: Optional[int] = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """兼容旧接口：自动生成"""
    return generate_exam(
        ExamGenerate(mode='mixed', project_id=project_id, category=category, count=count),
        db=db, current_user=current_user
    )
