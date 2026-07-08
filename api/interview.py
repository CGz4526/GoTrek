from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import re

from db.models import InterviewSession, InterviewMessage, Project, User
from db.schemas import (
    InterviewStartRequest, InterviewChatRequest,
    InterviewMessageOut, InterviewSessionOut, InterviewChatResponse
)
from db.database import get_db
from api.auth import get_current_user
from core.agents.interview_agent import InterviewAgent

router = APIRouter(prefix="/api/interview", tags=["interview"])

_interview_agent = None


def _get_interview_agent() -> InterviewAgent:
    global _interview_agent
    if _interview_agent is None:
        _interview_agent = InterviewAgent()
    return _interview_agent


def _project_info(project: Project) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "tech_stack": project.tech_stack or [],
        "project_type": project.project_type or "other",
        "description": project.description or "",
    }


def _session_to_out(s: InterviewSession) -> dict:
    last_msg = s.messages[-1].content[:120] if s.messages else None
    return {
        "id": s.id,
        "project_id": s.project_id,
        "project_name": s.project_name,
        "position": s.position,
        "status": s.status,
        "created_at": s.created_at,
        "updated_at": s.updated_at,
        "message_count": len(s.messages),
        "last_message": last_msg,
    }


# 注意：/sessions 必须在 /{session_id} 之前定义，避免被当作 session_id
@router.get("/sessions", response_model=List[InterviewSessionOut])
def list_sessions(db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    sessions = db.query(InterviewSession).filter(
        InterviewSession.user_id == current_user.id
    ).order_by(InterviewSession.updated_at.desc()).all()
    return [_session_to_out(s) for s in sessions]


@router.post("/start", response_model=InterviewChatResponse)
def start_session(req: InterviewStartRequest,
                  db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    """开启一场模拟面试：选择项目后，面试官生成第一个问题。"""
    project = None
    project_name = None
    project_info = None
    if req.project_id:
        project = db.query(Project).filter(
            Project.id == req.project_id,
            Project.user_id == current_user.id
        ).first()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Project not found")
        project_name = project.name
        project_info = _project_info(project)

    # 创建会话
    session = InterviewSession(
        user_id=current_user.id,
        project_id=req.project_id,
        project_name=project_name,
        position=req.position or "后端开发",
        status="active"
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # 调用 agent 生成开场问题
    agent = _get_interview_agent()
    result = agent.chat(
        history=[],
        project_info=project_info,
        position=session.position,
        question_count=8
    )

    # 保存面试官消息
    msg = InterviewMessage(
        session_id=session.id,
        role="interviewer",
        content=result["content"]
    )
    db.add(msg)
    session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(msg)

    return InterviewChatResponse(
        session_id=session.id,
        role="interviewer",
        content=result["content"],
        should_end=result.get("should_end", False)
    )


@router.post("/{session_id}/chat", response_model=InterviewChatResponse)
def chat(session_id: int, req: InterviewChatRequest,
         db: Session = Depends(get_db),
         current_user: User = Depends(get_current_user)):
    """候选人回复，面试官生成下一条回复。"""
    session = db.query(InterviewSession).filter(
        InterviewSession.id == session_id,
        InterviewSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Interview session not found")
    if session.status == "ended":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="该面试会话已结束")

    user_msg = (req.message or "").strip()
    if not user_msg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="消息不能为空")

    # 保存候选人消息
    db.add(InterviewMessage(
        session_id=session.id,
        role="candidate",
        content=user_msg
    ))
    db.commit()

    # 收集历史（含刚保存的候选人消息）
    msgs = db.query(InterviewMessage).filter(
        InterviewMessage.session_id == session.id
    ).order_by(InterviewMessage.id.asc()).all()
    history = [{"role": m.role, "content": m.content} for m in msgs]

    # 准备项目信息
    project_info = None
    if session.project_id:
        project = db.query(Project).filter(
            Project.id == session.project_id
        ).first()
        if project:
            project_info = _project_info(project)

    agent = _get_interview_agent()
    result = agent.chat(
        history=history,
        project_info=project_info,
        position=session.position,
        question_count=8
    )

    # 保存面试官回复
    db.add(InterviewMessage(
        session_id=session.id,
        role="interviewer",
        content=result["content"]
    ))
    session.updated_at = datetime.utcnow()
    if result.get("should_end"):
        session.status = "ended"
    db.commit()

    return InterviewChatResponse(
        session_id=session.id,
        role="interviewer",
        content=result["content"],
        should_end=result.get("should_end", False)
    )


@router.get("/{session_id}/history", response_model=List[InterviewMessageOut])
def get_history(session_id: int,
                db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    session = db.query(InterviewSession).filter(
        InterviewSession.id == session_id,
        InterviewSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Interview session not found")
    return session.messages


@router.post("/{session_id}/end")
def end_session(session_id: int,
                db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    session = db.query(InterviewSession).filter(
        InterviewSession.id == session_id,
        InterviewSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Interview session not found")
    session.status = "ended"
    session.updated_at = datetime.utcnow()
    db.commit()
    return {"session_id": session_id, "status": "ended"}


@router.delete("/{session_id}")
def delete_session(session_id: int,
                   db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    session = db.query(InterviewSession).filter(
        InterviewSession.id == session_id,
        InterviewSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Interview session not found")
    db.delete(session)
    db.commit()
    return {"session_id": session_id, "deleted": True}


@router.post("/{session_id}/extract")
def extract_questions_to_library(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """从面试会话中提取面试官的问题并存入题库。
    自动识别问题句，去掉寒暄/评价/总结，已有重复的跳过。"""
    session = db.query(InterviewSession).filter(
        InterviewSession.id == session_id,
        InterviewSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Interview session not found")

    from db.models import Question
    from core.dedup import find_duplicate

    msgs = db.query(InterviewMessage).filter(
        InterviewMessage.session_id == session_id
    ).order_by(InterviewMessage.id.asc()).all()

    questions_added = []
    questions_skipped = 0

    for msg in msgs:
        if msg.role != 'interviewer':
            continue
        q_text = _extract_question(msg.content)
        if not q_text or len(q_text) < 5:
            continue

        # 去重
        dup = find_duplicate(q_text, current_user.id, db)
        if dup is not None:
            questions_skipped += 1
            continue

        # 确定题型和分类
        q_type = 'project' if session.project_id else 'bagua'
        category = 'project' if session.project_id else 'interview'

        question = Question(
            user_id=current_user.id,
            content=q_text,
            question_type=q_type,
            category=category,
            difficulty=3,
            answer='',
            source='interview_' + str(session.id)
        )
        db.add(question)
        db.flush()

        # 如果有关联项目，也添加到项目关联
        if session.project_id:
            from db.models import QuestionProject
            db.add(QuestionProject(
                question_id=question.id,
                project_id=session.project_id,
                match_score=0.8,
                adapted_content=q_text
            ))

        questions_added.append({
            "id": question.id,
            "content": q_text
        })

    db.commit()
    return {
        "added": len(questions_added),
        "skipped": questions_skipped,
        "questions": questions_added
    }


def _extract_question(text: str) -> str:
    """从面试官的一段话中提取核心问题句。"""
    if not text:
        return ''
    lines = text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # 含问号，且不是纯寒暄
        if '？' in line or '?' in line:
            if any(kw in line for kw in ['你好', '哈喽', '嗨', '欢迎', '今天', '我们']):
                # 混合问候+问题的长句，如果有问号仍可能是问题
                if len(line) > 20:
                    # 取问号后面那句
                    idx = max(line.rfind('？'), line.rfind('?'))
                    if idx > 0:
                        first_part = line[:idx+1].strip()
                        if len(first_part) > 5:
                            return _clean_question(first_part)
                    return _clean_question(line)
                continue
            return _clean_question(line)
        # 祈使句："请..."、"说一下..."、"谈谈..."
        if re.match(r'^(请|说一下|谈谈|聊聊|说说|讲一下|解释一下|介绍一下|分析一下|说明一下|对比一下|你怎么看|如何看待)', line):
            return _clean_question(line)
        # "我想问你..." / "我的问题是..."
        if any(kw in line for kw in ['想问你', '问题是', '考考你', '想了解']):
            return _clean_question(line)
    # 如果没找到明确的问题句，返回整段（如果较短且不像寒暄）
    if len(lines) <= 2 and 8 <= len(text) <= 120:
        if not any(kw in text for kw in ['你好', '结束', '总结', '不错', '感谢', '辛苦了', '加油']):
            return _clean_question(text)
    return ''


def _clean_question(text: str) -> str:
    cleaned = text.strip()
    # 去掉前缀的"那"、"好的"、"嗯"等过渡词
    cleaned = re.sub(r'^(那|好的|好|嗯|啊|哦|那好|行|行那|好，那)，?\s*', '', cleaned)
    # 去掉结尾的语气词和重复标点
    cleaned = re.sub(r'[？?\s]+$', '？', cleaned)
    return cleaned.strip()
