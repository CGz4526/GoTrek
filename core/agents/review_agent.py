from core.agents.base_agent import BaseAgent


class ReviewAgent(BaseAgent):
    """复习agent：评估用户答案的质量，给出分数、反馈和关键得分点。"""

    def evaluate_answer(self, question: str, user_answer: str, correct_answer: str = None) -> dict:
        """评估用户答案。

        Args:
            question: 面试题目
            user_answer: 用户的答案
            correct_answer: 标准答案（可选）。若无则直接根据专业知识
                            评估用户答案的质量和正确性。

        Returns:
            dict: {
                "is_correct": bool,
                "score": int (0-100),
                "feedback": str (指出不足和改进建议),
                "key_points": list
            }
        """
        try:
            result = self._evaluate_with_llm(question, user_answer, correct_answer)
            if result:
                return result
            return self._fallback_evaluate(user_answer)
        except Exception as e:
            print(f"ReviewAgent LLM error: {e}")
            return self._fallback_evaluate(user_answer)

    def _evaluate_with_llm(self, question: str, user_answer: str, correct_answer: str = None) -> dict:
        system = (
            "你是一个严格的技术面试官，负责评估候选人的面试答案。"
            "请严格按照JSON格式返回评估结果，不要包含其他文字。"
        )

        if correct_answer:
            correct_section = (
                f"\n\n标准答案：\n{correct_answer}\n"
                "请将用户答案与标准答案对比评估。"
            )
        else:
            correct_section = (
                "\n\n（无标准答案，请根据你的专业知识直接评估用户答案的质量和正确性。）"
            )

        prompt = f"""请评估以下面试题的用户答案：

题目：{question}

用户答案：
{user_answer}{correct_section}

评估要求：
1. 判断答案是否正确(is_correct: true/false)
2. 给出0-100的分数(score)
3. 指出用户答案的不足和改进建议(feedback)
4. 列出该题的关键得分点(key_points，字符串数组)

返回格式为JSON（不要包含其他文字）：
{{
    "is_correct": true,
    "score": 85,
    "feedback": "评估反馈...",
    "key_points": ["关键点1", "关键点2"]
}}"""

        content = self._chat(system, prompt, temperature=0.3, timeout=60)
        result = self._parse_json(content, '{', '}')
        if not isinstance(result, dict):
            return {}

        # 字段校验与默认值
        score = result.get("score", 0)
        try:
            score = int(score)
        except (ValueError, TypeError):
            score = 0
        score = max(0, min(100, score))

        is_correct = result.get("is_correct", score >= 60)
        if not isinstance(is_correct, bool):
            is_correct = bool(is_correct)

        key_points = result.get("key_points", [])
        if not isinstance(key_points, list):
            key_points = []

        feedback = result.get("feedback", "")
        if not isinstance(feedback, str):
            feedback = str(feedback)

        return {
            "is_correct": is_correct,
            "score": score,
            "feedback": feedback,
            "key_points": key_points
        }

    def _fallback_evaluate(self, user_answer: str) -> dict:
        """LLM失败时的简单兜底评估。"""
        if not user_answer or not user_answer.strip():
            return {
                "is_correct": False,
                "score": 0,
                "feedback": "未提供答案。",
                "key_points": []
            }
        return {
            "is_correct": False,
            "score": 50,
            "feedback": "评估服务暂不可用，无法给出详细反馈。请稍后重试。",
            "key_points": []
        }
