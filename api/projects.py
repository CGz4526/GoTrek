from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
import os

from db.models import Project, User, QuestionProject
from db.schemas import ProjectResponse, ProjectCreate
from db.database import get_db
from api.auth import get_current_user
from core.project_analyzer import analyze_resume_projects, analyze_project_description
from core.weight_manager import get_question_weight

router = APIRouter(prefix="/api/projects", tags=["projects"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload", response_model=List[ProjectResponse])
def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not file.filename.endswith(('.pdf', '.txt')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF and TXT files are supported"
        )
    
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, 'wb') as f:
        f.write(file.file.read())
    
    projects = analyze_resume_projects(file_path, current_user.id, db)
    
    os.remove(file_path)
    
    return projects


@router.post("/", response_model=ProjectResponse)
def create_project(
    project: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not project.name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project name is required"
        )

    new_project = Project(
        user_id=current_user.id,
        name=project.name,
        description=project.description,
        tech_stack=project.tech_stack or [],
        project_type=project.project_type or 'other',
        domain_tags=project.domain_tags or []
    )

    db.add(new_project)
    db.commit()
    db.refresh(new_project)

    from core.project_analyzer import match_questions_for_project
    match_questions_for_project(new_project, current_user.id, db)

    return new_project


@router.post("/auto-recognize")
def auto_recognize_project(
    description: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """用户只需上传一段项目描述文字，项目识别agent自动识别名称、类型、技术栈等全部信息"""
    import os
    from dotenv import load_dotenv
    load_dotenv()

    if not description or len(description.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="项目描述太短，请至少输入10个字符"
        )

    from core.agents.project_agent import ProjectAgent
    agent = ProjectAgent() if os.getenv("DEEPSEEK_API_KEY") else None
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LLM服务未配置"
        )

    analysis = agent.analyze(description)

    # 用识别结果创建项目
    new_project = Project(
        user_id=current_user.id,
        name=analysis.get("name", "未命名项目"),
        description=description,
        tech_stack=analysis.get("tech_stack", []),
        project_type=analysis.get("project_type", "other"),
        domain_tags=analysis.get("core_modules", [])
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)

    from core.project_analyzer import match_questions_for_project
    match_questions_for_project(new_project, current_user.id, db)

    return {
        "id": new_project.id,
        "name": new_project.name,
        "description": new_project.description,
        "tech_stack": new_project.tech_stack,
        "project_type": new_project.project_type,
        "core_modules": analysis.get("core_modules", []),
        "question_topics": analysis.get("question_topics", []),
        "message": "项目识别成功"
    }


@router.get("/", response_model=List[ProjectResponse])
def get_projects(
    project_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Project).filter(Project.user_id == current_user.id)
    
    if project_type:
        query = query.filter(Project.project_type == project_type)
    
    projects = query.order_by(Project.created_at.desc()).all()
    
    return projects


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    name: Optional[str] = None,
    description: Optional[str] = None,
    tech_stack: Optional[List[str]] = None,
    project_type: Optional[str] = None,
    domain_tags: Optional[List[str]] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    if name:
        project.name = name
    if description:
        project.description = description
    if tech_stack:
        project.tech_stack = tech_stack
    if project_type:
        project.project_type = project_type
    if domain_tags:
        project.domain_tags = domain_tags
    
    db.commit()
    db.refresh(project)
    
    from core.project_analyzer import match_questions_for_project
    match_questions_for_project(project, current_user.id, db)
    
    return project


@router.delete("/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    db.delete(project)
    db.commit()
    
    return {"message": "Project deleted successfully"}


@router.get("/{project_id}/questions")
def get_project_questions(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    question_adaptations = db.query(QuestionProject).filter(
        QuestionProject.project_id == project_id
    ).order_by(QuestionProject.match_score.desc()).all()
    
    from db.schemas import QuestionResponse
    
    questions = []
    for qa in question_adaptations:
        weight = get_question_weight(current_user.id, qa.question_id, db)
        questions.append({
            "question": QuestionResponse(
                id=qa.question.id,
                content=qa.adapted_content or qa.question.content,
                question_type=qa.question.question_type,
                category=qa.question.category,
                source=qa.question.source,
                answer=qa.question.answer or "",
                difficulty=qa.question.difficulty,
                created_at=qa.question.created_at,
                weight=weight
            ),
            "match_score": qa.match_score
        })
    
    return {"project_id": project_id, "project_name": project.name, "questions": questions}