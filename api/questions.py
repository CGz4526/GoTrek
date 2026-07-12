from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Response, Body
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from db.models import Question, User, QuestionWeight
from db.schemas import QuestionResponse, QuestionUpload, QuestionMarkConfused, QuestionCreate
from db.database import get_db
from api.auth import get_current_user
from core.parser import parse_interview_text
from core.weight_manager import mark_question_confused, get_question_weight, mark_question_vague, get_question_vague_count

router = APIRouter(prefix="/api/questions", tags=["questions"])


@router.post("/", response_model=QuestionResponse)
def create_question(
    question: QuestionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """手动添加单道题目到题库。自动去重，重复题返回已存在的题目。"""
    from core.dedup import find_duplicate

    content = question.content.strip()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="题目内容不能为空"
        )

    dup = find_duplicate(content, current_user.id, db)
    if dup is not None:
        weight = get_question_weight(current_user.id, dup.id, db)
        return QuestionResponse(
            id=dup.id,
            content=dup.content,
            question_type=dup.question_type,
            category=dup.category or '',
            source=dup.source or '',
            answer=dup.answer or '',
            difficulty=dup.difficulty,
            starred=bool(dup.starred),
            created_at=dup.created_at,
            weight=weight
        )

    new_q = Question(
        user_id=current_user.id,
        content=content,
        question_type=question.question_type or 'bagua',
        category=question.category or 'other',
        source=question.source or 'manual',
        answer=question.answer or '',
        difficulty=question.difficulty or 3,
    )
    db.add(new_q)
    db.commit()
    db.refresh(new_q)

    weight = get_question_weight(current_user.id, new_q.id, db)
    return QuestionResponse(
        id=new_q.id,
        content=new_q.content,
        question_type=new_q.question_type,
        category=new_q.category or '',
        source=new_q.source or '',
        answer=new_q.answer or '',
        difficulty=new_q.difficulty,
        starred=bool(new_q.starred),
        created_at=new_q.created_at,
        weight=weight
    )


@router.post("/solve")
def solve_question(
    body: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """解题接口：用户提出问题，agent解答，同时改写优化为题面，
    默认自动存入题库（高权重，标记为用户生疏的题，优先复习）。

    Args:
        question: 用户的原始问题
        auto_save: 是否自动存入题库，默认 True

    Returns:
        dict: 含 answer / refined_question / category / question_type / difficulty / saved（是否已存）/ question_id（已存则返回id）
    """
    from core.agents.solve_agent import SolveAgent
    from core.dedup import find_duplicate

    question = (body.get("question") or "").strip()
    auto_save = bool(body.get("auto_save", True))

    if len(question) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="问题不能为空"
        )

    agent = SolveAgent()
    result = agent.solve(question)
    answer = result.get("answer", "")
    refined = result.get("refined_question", question)
    category = result.get("category", "other")
    q_type = result.get("question_type", "bagua")
    difficulty = result.get("difficulty", 3)

    saved = False
    question_id = None
    duplicate_of_id = None

    if auto_save and answer and len(answer) > 5:
        dup = find_duplicate(refined, current_user.id, db)
        if dup is not None:
            if not dup.answer and answer:
                dup.answer = answer
                db.commit()
            saved = True
            question_id = dup.id
            duplicate_of_id = dup.id
        else:
            from db.models import Question, QuestionWeight
            new_q = Question(
                user_id=current_user.id,
                content=refined,
                question_type=q_type,
                category=category,
                source='solve_agent',
                answer=answer,
                difficulty=difficulty,
            )
            db.add(new_q)
            db.flush()

            weight_record = QuestionWeight(
                user_id=current_user.id,
                question_id=new_q.id,
                weight=30,
                review_count=0,
                confused_count=1,
            )
            db.add(weight_record)
            db.commit()
            db.refresh(new_q)

            saved = True
            question_id = new_q.id

    return {
        "answer": answer,
        "refined_question": refined,
        "category": category,
        "question_type": q_type,
        "difficulty": difficulty,
        "saved": saved,
        "question_id": question_id,
        "duplicate_of_id": duplicate_of_id,
    }


@router.post("/upload", response_model=List[QuestionResponse])
def upload_questions(upload: QuestionUpload, response: Response, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not upload.text or len(upload.text.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text content is too short"
        )

    questions, skipped = parse_interview_text(upload.text, current_user.id, db)

    # 去重统计：parser 返回 (题目列表, 被跳过的重复题统计)
    if skipped:
        response.headers["X-Skipped-Duplicates"] = str(len(skipped))

    resp = []
    for q in questions:
        weight = get_question_weight(current_user.id, q.id, db)
        resp.append(QuestionResponse(
            id=q.id,
            content=q.content,
            question_type=q.question_type,
            category=q.category,
            source=q.source,
            answer=q.answer or "",
            difficulty=q.difficulty,
            starred=bool(q.starred),
            created_at=q.created_at,
            weight=weight
        ))

    return resp


@router.post("/ocr")
async def ocr_image(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    """从上传的图片提取文字。返回提取的文字内容，前端可编辑后提交解析。"""
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="请上传图片文件")
    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片不能超过10MB")
    try:
        from core.ocr import extract_text_from_bytes
        text = extract_text_from_bytes(image_bytes)
    except ImportError:
        raise HTTPException(status_code=500, detail="OCR模块未安装，请运行 pip install paddleocr paddlepaddle")
    if not text.strip():
        raise HTTPException(status_code=422, detail="未能从图片中识别到文字，请换一张更清晰的图片")
    return {"text": text}


@router.get("/", response_model=List[QuestionResponse])
def get_questions(
    question_type: Optional[str] = None,
    category: Optional[str] = None,
    difficulty: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Question).filter(Question.user_id == current_user.id)

    if question_type:
        query = query.filter(Question.question_type == question_type)
    if category:
        query = query.filter(Question.category == category)
    if difficulty:
        query = query.filter(Question.difficulty == difficulty)

    questions = query.order_by(
        Question.starred.desc(),
        Question.created_at.desc()
    ).all()

    response = []
    for q in questions:
        weight = get_question_weight(current_user.id, q.id, db)
        vague_count = get_question_vague_count(current_user.id, q.id, db)
        response.append(QuestionResponse(
            id=q.id,
            content=q.content,
            question_type=q.question_type,
            category=q.category,
            source=q.source,
            answer=q.answer or "",
            difficulty=q.difficulty,
            starred=bool(q.starred),
            created_at=q.created_at,
            weight=weight,
            vague_count=vague_count
        ))

    response.sort(key=lambda x: (-x.vague_count, -x.starred, x.created_at), reverse=False)

    return response


@router.get("/{question_id}", response_model=QuestionResponse)
def get_question(question_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    question = db.query(Question).filter(
        Question.id == question_id,
        Question.user_id == current_user.id
    ).first()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )

    weight = get_question_weight(current_user.id, question.id, db)

    return QuestionResponse(
        id=question.id,
        content=question.content,
        question_type=question.question_type,
        category=question.category,
        source=question.source,
        answer=question.answer or "",
        difficulty=question.difficulty,
        starred=bool(question.starred),
        created_at=question.created_at,
        weight=weight
    )


@router.post("/{question_id}/mark-confused")
def mark_confused(question_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    question = db.query(Question).filter(
        Question.id == question_id,
        Question.user_id == current_user.id
    ).first()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )

    mark_question_confused(current_user.id, question_id, db)

    return {"message": "Question marked as confused", "question_id": question_id}


@router.post("/{question_id}/mark-vague")
def mark_vague(question_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """标记为模糊题目。每次点击模糊次数+1，权重+5。
    模糊次数越多排序越靠前。"""
    question = db.query(Question).filter(
        Question.id == question_id,
        Question.user_id == current_user.id
    ).first()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )

    mark_question_vague(current_user.id, question_id, db)
    vague_count = get_question_vague_count(current_user.id, question_id, db)

    return {
        "message": "Question marked as vague",
        "question_id": question_id,
        "vague_count": vague_count
    }


@router.post("/{question_id}/star")
def toggle_star(question_id: int, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    """切换题目的星标状态。星标题目在题库中置顶显示。"""
    question = db.query(Question).filter(
        Question.id == question_id,
        Question.user_id == current_user.id
    ).first()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )

    question.starred = not bool(question.starred)
    db.commit()
    db.refresh(question)

    return {
        "question_id": question_id,
        "starred": bool(question.starred)
    }


@router.put("/{question_id}", response_model=QuestionResponse)
def update_question(
    question_id: int,
    content: Optional[str] = None,
    question_type: Optional[str] = None,
    category: Optional[str] = None,
    answer: Optional[str] = None,
    difficulty: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    question = db.query(Question).filter(
        Question.id == question_id,
        Question.user_id == current_user.id
    ).first()
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )
    
    if content:
        question.content = content
    if question_type:
        question.question_type = question_type
    if category:
        question.category = category
    if answer:
        question.answer = answer
    if difficulty:
        question.difficulty = difficulty
    
    db.commit()
    db.refresh(question)
    
    weight = get_question_weight(current_user.id, question.id, db)
    
    return QuestionResponse(
        id=question.id,
        content=question.content,
        question_type=question.question_type,
        category=question.category,
        source=question.source,
        answer=question.answer or "",
        difficulty=question.difficulty,
        starred=bool(question.starred),
        created_at=question.created_at,
        weight=weight
    )


@router.delete("/{question_id}")
def delete_question(question_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    question = db.query(Question).filter(
        Question.id == question_id,
        Question.user_id == current_user.id
    ).first()
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )
    
    db.query(QuestionWeight).filter(
        QuestionWeight.question_id == question_id
    ).delete()
    
    db.query(QuestionProject).filter(
        QuestionProject.question_id == question_id
    ).delete()
    
    db.query(AnswerRecord).filter(
        AnswerRecord.question_id == question_id
    ).delete()
    
    db.delete(question)
    db.commit()
    
    return {"message": "Question deleted successfully"}