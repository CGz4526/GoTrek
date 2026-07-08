import json
from core.agents.base_agent import BaseAgent


class SolveAgent(BaseAgent):
    """解题agent：用户提出技术问题，agent给出解答，
    同时从用户问题中提炼、改写为标准面试题，方便存入题库。

    返回结构：
    {
        "answer": "精简答案（200字以内，口头回答风格）",
        "refined_question": "改写优化后的标准面试题",
        "category": "所属技术分类，如 mysql/redis/distributed 等",
        "question_type": "bagua 或 project 或 algorithm",
        "difficulty": 1-5 难度
    }
    """

    def solve(self, user_question: str) -> dict:
        """解答用户问题并改写为标准面试题。

        Args:
            user_question: 用户的原始问题（可能口语化、不规范）

        Returns:
            dict: 含 answer / refined_question / category / question_type / difficulty
        """
        try:
            result = self._generate_with_llm(user_question)
            return result
        except Exception as e:
            print(f"SolveAgent error: {e}")
            return {
                "answer": "解答时出错，请稍后重试。",
                "refined_question": user_question,
                "category": "other",
                "question_type": "bagua",
                "difficulty": 3,
            }

    def _generate_with_llm(self, user_question: str) -> dict:
        system = (
            "你是一位资深后端技术面试官，同时也是优秀的技术答疑者。\n"
            "你需要做两件事：\n"
            "1. 用精简的方式解答用户的问题（像面试口头回答一样）\n"
            "2. 把用户的原始问题改写优化为一道标准的、规范的面试题\n\n"
            "请用 JSON 格式返回，不要输出多余文字。"
        )

        prompt = f"""用户的问题：{user_question}

请按以下 JSON 格式返回：
{{
    "answer": "精简答案（200字以内，2-3小段，像面试口头回答，不要有元叙述和铺垫）",
    "refined_question": "改写后的标准面试题（一句话，专业规范，去掉口语化表达，适合作为题库题目）",
    "category": "技术分类，如 mysql、redis、distributed、algorithm、network、os、java、python、go、system_design 等，用英文小写",
    "question_type": "bagua 或 project 或 algorithm",
    "difficulty": 难度等级 1-5 的整数，1最简单5最难
}}

要求：
- answer 严格 200 字以内，2-3 小段（用空行分隔），直接给结论再展开
- refined_question 要是一个完整的、规范的面试题问句，不要口语化用词
- category 从常见后端分类中选，尽量精确
- difficulty 客观评估，3为中等"""

        content = self._chat(system, prompt, temperature=0.5, timeout=60)
        parsed = self._parse_json(content, start_char='{', end_char='}')

        if parsed and isinstance(parsed, dict):
            return {
                "answer": parsed.get("answer", "").strip(),
                "refined_question": parsed.get("refined_question", user_question).strip(),
                "category": parsed.get("category", "other").strip().lower(),
                "question_type": parsed.get("question_type", "bagua").strip().lower(),
                "difficulty": min(5, max(1, int(parsed.get("difficulty", 3)))),
            }

        return {
            "answer": content.strip() if content else "无法生成答案，请稍后重试。",
            "refined_question": user_question,
            "category": "other",
            "question_type": "bagua",
            "difficulty": 3,
        }
