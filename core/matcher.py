from db.models import QuestionProject, Question, Project
from sqlalchemy.orm import Session
import re


def calculate_project_similarity(project1: Project, project2: Project) -> float:
    tech_similarity = 0.0
    if project1.tech_stack and project2.tech_stack:
        common_tech = set(project1.tech_stack) & set(project2.tech_stack)
        all_tech = set(project1.tech_stack) | set(project2.tech_stack)
        tech_similarity = len(common_tech) / len(all_tech) if all_tech else 0.0
    
    type_similarity = 1.0 if project1.project_type == project2.project_type else 0.0
    
    tag_similarity = 0.0
    if project1.domain_tags and project2.domain_tags:
        common_tags = set(project1.domain_tags) & set(project2.domain_tags)
        all_tags = set(project1.domain_tags) | set(project2.domain_tags)
        tag_similarity = len(common_tags) / len(all_tags) if all_tags else 0.0
    
    description_similarity = calculate_text_similarity(
        project1.description or "", 
        project2.description or ""
    )
    
    return 0.3 * tech_similarity + 0.3 * type_similarity + 0.2 * tag_similarity + 0.2 * description_similarity


def calculate_text_similarity(text1: str, text2: str) -> float:
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if not words1 and not words2:
        return 0.0
    
    common = words1 & words2
    return len(common) / max(len(words1), len(words2))


def match_question_to_project(question: Question, project: Project, db: Session):
    original_project = question.original_project
    
    if original_project:
        similarity = calculate_project_similarity(original_project, project)
    else:
        similarity = estimate_question_project_match(question, project)
    
    if similarity >= 0.3:
        existing_adaptation = db.query(QuestionProject).filter(
            QuestionProject.question_id == question.id,
            QuestionProject.project_id == project.id
        ).first()
        
        if existing_adaptation:
            existing_adaptation.match_score = similarity
            existing_adaptation.adapted_content = adapt_question_to_project(question, project)
        else:
            adaptation = QuestionProject(
                question_id=question.id,
                project_id=project.id,
                match_score=similarity,
                adapted_content=adapt_question_to_project(question, project)
            )
            db.add(adaptation)
        
        db.commit()


def estimate_question_project_match(question: Question, project: Project) -> float:
    score = 0.0
    
    if project.project_type and project.project_type in question.content:
        score += 0.3
    
    if project.tech_stack:
        tech_in_question = sum(1 for tech in project.tech_stack if tech.lower() in question.content.lower())
        score += 0.4 * (tech_in_question / max(len(project.tech_stack), 1))
    
    if project.domain_tags:
        tag_in_question = sum(1 for tag in project.domain_tags if tag in question.content)
        score += 0.3 * (tag_in_question / max(len(project.domain_tags), 1))
    
    return score


def adapt_question_to_project(question: Question, project: Project) -> str:
    adapted = question.content
    
    type_mappings = {
        'seckill': ['秒杀平台', '秒杀系统', '抢购系统'],
        'ecommerce': ['电商平台', '电商系统', '购物商城'],
        'social': ['社交平台', '社交系统', '社区系统'],
        'cms': ['内容管理系统', '博客系统', '新闻系统'],
        'crm': ['客户管理系统', '销售管理系统'],
        'data': ['数据分析系统', '大数据平台'],
        'ai': ['人工智能系统', '推荐系统'],
    }
    
    if project.project_type in type_mappings:
        for keyword in type_mappings[project.project_type]:
            if keyword in adapted:
                adapted = adapted.replace(keyword, project.name)
    
    return adapted


def match_projects_for_question(question: Question, user_id: int, db: Session):
    projects = db.query(Project).filter(Project.user_id == user_id).all()
    
    for project in projects:
        match_question_to_project(question, project, db)