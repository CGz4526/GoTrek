from utils.pdf_parser import extract_text_from_pdf, extract_project_descriptions, parse_project_from_description
from utils.text_utils import extract_keywords
from db.models import Project, Question
from sqlalchemy.orm import Session


def analyze_resume_projects(resume_path: str, user_id: int, db: Session) -> list:
    if resume_path.endswith('.pdf'):
        resume_text = extract_text_from_pdf(resume_path)
    else:
        with open(resume_path, 'r', encoding='utf-8') as f:
            resume_text = f.read()
    
    if not resume_text:
        return []
    
    project_descriptions = extract_project_descriptions(resume_text)
    
    projects = []
    for desc in project_descriptions:
        parsed_project = parse_project_from_description(desc)
        
        if not parsed_project['name']:
            parsed_project['name'] = f"项目{len(projects) + 1}"
        
        project = Project(
            user_id=user_id,
            name=parsed_project['name'],
            description=parsed_project['description'],
            tech_stack=parsed_project['tech_stack'],
            project_type=parsed_project['project_type'],
            domain_tags=parsed_project['domain_tags']
        )
        
        db.add(project)
        projects.append(project)
    
    db.commit()
    
    for p in projects:
        db.refresh(p)
        match_questions_for_project(p, user_id, db)
    
    return projects


def analyze_project_description(description: str, user_id: int, db: Session) -> Project:
    parsed_project = parse_project_from_description(description)
    
    if not parsed_project['name']:
        parsed_project['name'] = "未命名项目"
    
    project = Project(
        user_id=user_id,
        name=parsed_project['name'],
        description=parsed_project['description'],
        tech_stack=parsed_project['tech_stack'],
        project_type=parsed_project['project_type'],
        domain_tags=parsed_project['domain_tags']
    )
    
    db.add(project)
    db.commit()
    db.refresh(project)
    
    match_questions_for_project(project, user_id, db)
    
    return project


def match_questions_for_project(project: Project, user_id: int, db: Session):
    from core.matcher import match_question_to_project
    
    questions = db.query(Question).filter(
        Question.user_id == user_id
    ).all()
    
    for question in questions:
        match_question_to_project(question, project, db)