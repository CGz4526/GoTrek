from core.agents.base_agent import BaseAgent


class AnswerAgent(BaseAgent):
    """答案agent：为面试题生成详细答案，支持结合项目背景作答。"""

    def generate_answer(self, question: str, project_info: dict = None) -> str:
        """为题目生成详细答案。

        Args:
            question: 面试题目
            project_info: 项目背景信息dict(含 name/tech_stack/description 等)，
                          用于生成贴合项目实际场景的答案

        Returns:
            str: 详细答案文本
        """
        try:
            return self._generate_with_llm(question, project_info)
        except Exception as e:
            print(f"AnswerAgent LLM error: {e}")
            return "生成答案时出错，请稍后重试。"

    def _generate_with_llm(self, question: str, project_info: dict = None) -> str:
        system = "你是一个资深的后端开发工程师，擅长解答各类技术问题。"

        project_section = ""
        if project_info:
            pname = project_info.get("name", "")
            pstack = project_info.get("tech_stack", [])
            if isinstance(pstack, list):
                pstack = ", ".join(pstack)
            pdesc = project_info.get("description", "")
            project_section = (
                f"\n\n相关项目背景：\n- 项目名称:{pname}\n- 技术栈:{pstack}\n- 描述:{pdesc}\n"
                "请结合项目实际场景作答。"
            )

        prompt = f"""请详细解答以下面试题：

题目：{question}{project_section}

要求：
1. 答案总字数严格控制在200字以内（含标点）
2. 像面试时口头回答面试官一样：精简、直接、不废话，不要"这个问题需要..."等元叙述
3. 可以分成2-3个小段（用空行分隔），每段聚焦一个要点；不要一整段挤满
4. 必要时可用"1. 2. 3."编号分点，但每点写完整短句，不要每点一个词搞得碎
5. 第一句直接给结论/定义，后面展开核心原理或关键点，不要铺陈背景
6. 涉及对比可用简洁表格，涉及具体API可给一行核心代码；不要给完整代码
7. 答案要专业准确，像资深工程师精炼的回答"""

        content = self._chat(system, prompt, temperature=0.5, timeout=60)
        return content if content else "无法生成答案，请稍后重试。"
