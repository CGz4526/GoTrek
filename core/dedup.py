"""题目去重工具：在写入题库前检测相似题目，避免重复入库。

采用两层去重策略：
1. 精确匹配：规范化后（去除空白和标点）字符串完全相同 -> 视为重复
2. 相似度匹配：基于字符 bigram 的 Jaccard 相似度，阈值 >= 0.85 -> 视为重复
"""

import re
from typing import Optional

from db.models import Question
from sqlalchemy.orm import Session


# 中文标点 + 英文标点 + 空白
_PUNCT_RE = re.compile(r"[\s，。、；：！？“”‘’（）《》【】「」\"'.,;:!?\-—(){}\[\]…·]+")


def _normalize(text: str) -> str:
    """规范化文本：去掉所有标点和空白，统一转小写。"""
    if not text:
        return ""
    return _PUNCT_RE.sub("", text).lower()


def _char_bigrams(text: str) -> set:
    """生成字符 bigram 集合。"""
    if len(text) < 2:
        return {text} if text else set()
    return {text[i:i+2] for i in range(len(text) - 1)}


def _similarity(a: str, b: str) -> float:
    """计算两段文本的字符 bigram Jaccard 相似度（0-1）。"""
    if not a or not b:
        return 0.0
    sa, sb = _char_bigrams(a), _char_bigrams(b)
    if not sa or not sb:
        return 1.0 if a == b else 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def _is_similar(a: str, b: str, threshold: float = 0.8) -> bool:
    """判断两段规范化后的文本是否视为重复题目。

    采用两种判断的并集（满足其一即视为重复）：
    1. Jaccard bigram 相似度 >= threshold
    2. 较短文本完全包含在较长文本中（且短文本足够长 >= 6 字），
       用于捕捉"末尾多/少几个字"的同一题目变体
    """
    if not a or not b:
        return False
    if a == b:
        return True
    # 子串包含：题库题是新增题的子串，或新增题是题库题的子串
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    if len(short) >= 6 and short in long_:
        return True
    # Jaccard 相似度
    return _similarity(a, b) >= threshold


def find_duplicate(content: str, user_id: int, db: Session,
                   threshold: float = 0.8) -> Optional[Question]:
    """检查题库中是否已存在与给定题目内容相似（重复）的题目。

    Args:
        content: 待检测的题目内容
        user_id: 用户ID（仅在该用户题库范围内去重）
        db: 数据库会话
        threshold: 相似度阈值，>= 该值视为重复

    Returns:
        如果存在重复，返回已存在的 Question 对象；否则返回 None
    """
    norm = _normalize(content)
    if not norm:
        return None

    # 拉取该用户所有题库题目做对比（题库通常不大，单机够用）
    existing = db.query(Question).filter(Question.user_id == user_id).all()
    for q in existing:
        q_norm = _normalize(q.content or "")
        if not q_norm:
            continue
        # 短题（规范化后 < 6 字）只走精确匹配，避免误杀
        if len(norm) < 6 or len(q_norm) < 6:
            if q_norm == norm:
                return q
            continue
        if _is_similar(q_norm, norm, threshold):
            return q
    return None
