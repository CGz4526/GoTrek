from core.agents.base_agent import BaseAgent


class ExamAgent(BaseAgent):
    """出题agent：根据所选项目和技术栈智能生成面试题。

    不止使用题库中的题，会根据项目描述生成针对项目的递进式问题，
    以及针对项目技术栈生成相关八股题。问题层层递进、有逻辑。
    每道题同时生成简短答案。
    """

    def generate(self, topic: str, count: int = 5, project_info: dict = None,
                 existing_questions: list = None) -> list:
        """根据主题/项目生成面试题。

        Args:
            topic: 面试主题（用于bagua模式）
            count: 生成题目数量
            project_info: 项目信息dict(含 id/name/tech_stack/project_type/description 等)，
                          用于生成项目相关题目
            existing_questions: 题库中已有的题目列表，用于补充和避免重复

        Returns:
            题目列表，每项格式：
            {"content": str, "question_type": str, "category": str,
             "difficulty": int, "answer": str, "matched_project_ids": list,
             "source": str}  # source="generated" 表示agent新生成，"library" 表示取自题库
        """
        try:
            result = self._generate_with_llm(topic, count, project_info, existing_questions)
            if result:
                return result
            return []
        except Exception as e:
            print(f"ExamAgent LLM error: {e}")
            return []

    def _generate_with_llm(self, topic: str, count: int, project_info: dict,
                           existing_questions: list = None) -> list:
        system = (
            "你是一位资深的技术面试官，擅长根据候选人的项目背景设计有逻辑、层层递进的面试题。"
            "你的提问风格像真实面试：先从项目整体设计问起，再深入到具体技术决策、难点攻坚、"
            "最后延伸到相关八股原理。问题之间有承接关系，不是孤立罗列。"
            "请严格按JSON数组格式返回，不要包含其他文字。"
        )

        project_section = ""
        matched_pid = []
        if project_info:
            pid = project_info.get("id")
            if pid:
                matched_pid = [pid]
            pname = project_info.get("name", "")
            pstack = project_info.get("tech_stack", [])
            if isinstance(pstack, list):
                pstack = ", ".join(pstack)
            ptype = project_info.get("project_type", "")
            pdesc = project_info.get("description", "")
            project_section = (
                f"\n\n【项目信息】\n- 名称: {pname}\n- 类型: {ptype}\n"
                f"- 技术栈: {pstack}\n- 描述: {pdesc}\n"
            )

        library_section = ""
        if existing_questions:
            lib_items = []
            for q in existing_questions[:15]:  # 最多给15条参考
                lib_items.append(
                    f"  - [{q.get('question_type','?')}/{q.get('category','?')}] {q.get('content','')[:80]}"
                )
            library_section = (
                "\n\n【题库已有相关题目（可选用，但不要重复）】\n"
                + "\n".join(lib_items) + "\n"
            )

        has_project = bool(project_info)
        if has_project:
            mode_desc = (
                "本次出题模式：项目深度面试。\n"
                "1. 约60%的题目针对该项目：先问整体架构设计→再问某个模块/技术选型理由→"
                "再问难点攻坚（如高并发、一致性、性能瓶颈）→最后问可能的优化方向或扩展性。\n"
                "2. 约40%的题目针对项目技术栈相关的八股原理：从该项目用到的技术中提炼核心知识点提问，"
                "如项目用了Redis就问Redis持久化/分布式锁/缓存穿透等。\n"
                "3. 问题要层层递进：前一个问题的答案可以作为后一个问题的前提，"
                "形成 \"项目→原理→深挖\" 的逻辑链。"
            )
        else:
            mode_desc = (
                f"本次出题模式：八股题面试，主题：{topic or '后端开发通用'}。\n"
                "1. 围绕该主题的核心知识点设计问题，覆盖原理、对比、场景应用。\n"
                "2. 问题之间有逻辑承接，如 \"是什么→为什么→怎么用→如何优化\"。"
            )

        project_id_value = matched_pid[0] if matched_pid else None
        matched_ids_instruction = (
            f"如果该题针对项目，matched_project_ids 设为 [{project_id_value}]；"
            f"否则设为 []" if project_id_value
            else "matched_project_ids 一律设为 []"
        )

        prompt = f"""请为候选人设计 {count} 道面试题。

{mode_desc}{project_section}{library_section}

输出要求：
1. 严格返回JSON数组，不要包含markdown代码块或任何其他文字
2. 每道题包含字段：
   - content: 完整题目（如果针对项目，要在题目中体现项目背景）
   - question_type: "project"（项目题）或 "bagua"（八股题）或 "algorithm"（算法题）
   - category: redis/mysql/java/multithreading/collection/network/os/design_pattern/spring/distributed/project/algorithm/other
   - difficulty: 1-5
   - answer: 答案（总字数严格200字以内，像面试时口头回答面试官一样精简直接，可分2-3小段或用1.2.3编号分点，第一句给结论，不要废话和元叙述）
   - matched_project_ids: {matched_ids_instruction}
   - source: "generated"
3. 题目顺序按面试逻辑排列（递进式），不要按类型分组
4. 不要与题库已有题目重复
5. 答案要专业准确，涉及对比可用简洁表格

示例格式：
[
  {{
    "content": "请介绍一下你这个秒杀项目的整体架构设计",
    "question_type": "project",
    "category": "project",
    "difficulty": 3,
    "answer": "秒杀系统采用分层架构：前端CDN+限流，网关层防刷，应用层Redis预扣库存，数据库做最终一致性保证。\n\n核心链路是用户下单→网关校验→Redis原子扣减→MQ异步创建订单→消费者落库，把高并发拦截在Redis层。\n\n通过Redisson分布式锁防超卖，RocketMQ削峰填谷。",
    "matched_project_ids": [{project_id_value if project_id_value else ''}],
    "source": "generated"
  }}
]"""

        content = self._chat(system, prompt, temperature=0.7, timeout=60)
        questions = self._parse_json(content, '[', ']')
        if not isinstance(questions, list):
            return []

        cleaned = []
        for q in questions:
            if not isinstance(q, dict):
                continue
            c = (q.get("content") or "").strip()
            if len(c) < 3:
                continue
            matched_ids = q.get("matched_project_ids", [])
            if not isinstance(matched_ids, list):
                matched_ids = []
            cleaned.append({
                "content": c,
                "question_type": q.get("question_type", "bagua"),
                "category": q.get("category", "other"),
                "difficulty": int(q.get("difficulty", 2) or 2),
                "answer": (q.get("answer") or "").strip(),
                "matched_project_ids": matched_ids,
                "source": "generated"
            })
        return cleaned
