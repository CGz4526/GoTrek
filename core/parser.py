from db.models import Question, Project, QuestionProject
from core.matcher import match_projects_for_question
from core.agents.extract_agent import ExtractAgent
from core.dedup import find_duplicate
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv

load_dotenv()

_extract_agent = None


def _get_extract_agent():
    """惰性初始化识题agent"""
    global _extract_agent
    if _extract_agent is not None:
        return _extract_agent
    if os.getenv("DEEPSEEK_API_KEY"):
        _extract_agent = ExtractAgent()
    return _extract_agent


def parse_interview_text(text: str, user_id: int, db: Session) -> list:
    """解析面经文本，使用识题agent提取题目并打上项目标签"""
    # 查询用户已有项目列表，用于项目标签匹配
    projects = db.query(Project).filter(Project.user_id == user_id).all()
    project_list = [
        {
            "id": p.id,
            "name": p.name,
            "tech_stack": p.tech_stack or [],
            "project_type": p.project_type or "other",
            "description": p.description or ""
        }
        for p in projects
    ]

    # 优先使用识题agent
    agent = _get_extract_agent()
    extracted = []
    if agent is not None:
        try:
            extracted = agent.extract(text, project_list)
        except Exception as e:
            print(f"ExtractAgent failed, fallback to regex: {e}")
            extracted = agent._regex_fallback_extract(text)

    # 降级：正则解析
    if not extracted:
        from utils.text_utils import split_text_into_questions
        from utils.classifier import classify_question
        raw_questions = split_text_into_questions(text)
        extracted = []
        for raw_q in raw_questions:
            classification = classify_question(raw_q)
            extracted.append({
                "content": raw_q,
                "question_type": classification['type'],
                "category": classification['category'],
                "difficulty": estimate_difficulty(raw_q),
                "matched_project_ids": []
            })

    parsed_questions = []
    skipped_duplicates = []
    for item in extracted:
        content = item.get("content", "").strip()
        if not content:
            continue

        # 去重：题库已存在相同/高度相似的题目时跳过，不再重复入库
        dup = find_duplicate(content, user_id, db)
        if dup is not None:
            skipped_duplicates.append({"content": content, "duplicate_of_id": dup.id})
            # 已存在的题目若本次解析有补全答案，则补到旧题上
            new_answer = item.get("answer", "")
            if new_answer and not dup.answer:
                dup.answer = new_answer
                # 旧题补了答案后加入返回列表，让前端能看到结果（而非空）
                parsed_questions.append(dup)
            continue

        question = Question(
            user_id=user_id,
            content=content,
            question_type=item.get("question_type", "bagua"),
            category=item.get("category", "other"),
            source='面经',
            answer=item.get("answer", ""),
            difficulty=int(item.get("difficulty", 2) or 2),
        )
        db.add(question)
        db.flush()  # 获取 question.id

        # 存储识题agent匹配的项目标签
        matched_ids = item.get("matched_project_ids", [])
        for pid in matched_ids:
            # 确保项目存在且属于该用户
            proj = db.query(Project).filter(
                Project.id == pid,
                Project.user_id == user_id
            ).first()
            if proj:
                qp = QuestionProject(
                    question_id=question.id,
                    project_id=pid,
                    match_score=0.85,
                    adapted_content=question.content
                )
                db.add(qp)

        parsed_questions.append(question)

    db.commit()

    for q in parsed_questions:
        db.refresh(q)
        # 同时使用传统匹配补充
        match_projects_for_question(q, user_id, db)

    # 返回 (题目列表, 被跳过的重复题统计)
    return parsed_questions, skipped_duplicates


def estimate_difficulty(text: str) -> int:
    length = len(text)

    difficulty = 1
    if length > 100:
        difficulty += 1
    if length > 200:
        difficulty += 1

    advanced_keywords = ['分布式', '高并发', '海量数据', '性能优化', '底层原理', '源码', '设计模式', '微服务']
    if any(k in text for k in advanced_keywords):
        difficulty += 1

    complex_keywords = ['一致性', '事务', '锁', '缓存', '消息队列', '算法']
    if sum(1 for k in complex_keywords if k in text) >= 2:
        difficulty += 1

    return min(difficulty, 5)
