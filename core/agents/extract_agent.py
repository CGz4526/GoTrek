import re
from core.agents.base_agent import BaseAgent


class ExtractAgent(BaseAgent):
    """识题agent：从面经文本中精确提取每一道独立的面试题。

    相比纯正则解析，LLM能理解章节结构（如 2.1/3.1 二级编号）、过滤噪音文字，
    并自动判断题目类型（bagua/project/algorithm）和细分分类（redis/mysql等）。
    当传入用户项目列表时，可判断每道题与哪些项目相关，输出 matched_project_ids。
    LLM不可用时降级为正则解析（支持二级编号）。
    """

    def extract(self, text: str, projects: list = None) -> list:
        """从面经文本中提取面试题。

        Args:
            text: 面经原始文本
            projects: 用户已有项目列表，每个project包含
                      id/name/tech_stack/project_type/description。
                      若提供，LLM会判断每道题与哪些项目相关，
                      在结果中加入 matched_project_ids 字段(项目ID列表)。

        Returns:
            题目列表，每项格式：
            {"content": str, "question_type": str, "category": str,
             "difficulty": int, "matched_project_ids": list}
        """
        try:
            result = self._extract_with_llm(text, projects)
            if result:
                return result
            return self._regex_fallback_extract(text)
        except Exception as e:
            print(f"ExtractAgent LLM error: {e}")
            return self._regex_fallback_extract(text)

    def _extract_with_llm(self, text: str, projects: list = None) -> list:
        system = (
            "你是一个专业的面试题提取助手（识题agent）。"
            "你的任务是从面试面经文本中精确提取出每一道独立的面试题。"
            "注意：1) 文本可能包含章节标题（如'二 项目'、'三 八股'）和编号（如2.1、3.1），"
            "这些都是题目分隔符，不是题目本身。"
            "2) 文本可能包含非题目内容（如互动数据、作者信息、输入框提示等噪音），必须过滤掉。"
            "3) 每道题应独立完整，不要把多道题合并。"
            "4) 准确判断每道题的类型（bagua=八股题/project=项目题/algorithm=算法题）和细分分类。"
            "5) 【最重要】题目改写补全：面经中的题目经常存在主语缺失、省略上下文的情况"
            "（如'锁的是什么东西'缺少'Redis分布式'前缀，'怎么防止超卖'缺少'秒杀场景下'前缀）。"
            "你必须根据上下文、章节标题、前后题目等信息，对每道题进行改写补全，"
            "使每道题单独拿出来都能看懂在问什么。补全时保持原意，不要改变问题方向。"
        )

        project_section = ""
        if projects:
            project_lines = []
            for p in projects:
                pid = p.get("id")
                pname = p.get("name", "")
                ptype = p.get("project_type", "")
                pstack = p.get("tech_stack", [])
                if isinstance(pstack, list):
                    pstack = ", ".join(pstack)
                pdesc = p.get("description", "")
                project_lines.append(
                    f"- 项目ID:{pid} | 名称:{pname} | 类型:{ptype} | 技术栈:{pstack} | 描述:{pdesc}"
                )
            project_section = (
                "\n\n用户已有项目列表：\n" + "\n".join(project_lines) +
                "\n请判断每道题与哪个/哪些项目相关，在结果中加入 matched_project_ids 字段"
                "（项目ID列表，与项目无关时为空列表[]）。"
            )

        prompt = f"""请从以下面经文本中提取所有面试题，返回JSON数组。

面经文本：
{text}{project_section}

分类规则：
- question_type: "project"（关于项目设计、实现、优化）、"bagua"（技术原理、机制、概念）、"algorithm"（算法、数据结构、复杂度）
- category: redis/mysql/java/multithreading/collection/network/os/design_pattern/spring/distributed/project/algorithm/other

返回格式（JSON数组，不要包含其他文字）：
[
  {{"content": "题目完整内容", "question_type": "bagua", "category": "redis", "difficulty": 2, "answer": "简短答案", "matched_project_ids": []}}
]

要求：
1. 提取每一道独立题目，不要遗漏
2. 章节标题（如"二 项目"、"三 八股"）不是题目，不要提取
3. 过滤掉互动数据、作者信息等噪音
4. difficulty范围1-5
5. 支持识别二级编号（如2.1、3.1）作为题目分隔
6. 【关键】题目改写补全：每道题的content必须是完整的、可独立理解的问题。
   - 如果原题缺少主语或上下文，根据章节标题和前后文补全（如"锁的是什么东西"→"秒杀系统中Redis分布式锁锁的是什么资源"）
   - 如果原题有省略，补全为完整问句（如"怎么防止超卖"→"秒杀场景下如何防止商品超卖"）
   - 保持原意不变，只做补全，不改变问题方向
   - 每道题单独拿出来都应该能看懂在问什么
7. 【关键】为每道题生成答案(answer字段)：
   - 答案总字数严格控制在200字以内（含标点）
   - 像面试时口头回答面试官一样：精简、直接、不废话，不要"这个问题需要..."等元叙述
   - 可以分成2-3个小段（用空行分隔），每段聚焦一个要点；不要一整段挤满
   - 必要时可用"1. 2. 3."编号分点，但每点写完整短句，不要每点一个词搞得碎
   - 第一句直接给结论/定义，后面展开核心原理或关键点，不要铺陈背景
   - 涉及对比可用简洁表格，涉及具体API可给一行核心代码；不要给完整代码
   - 答案要专业准确，像资深工程师精炼的回答"""


        content = self._chat(system, prompt, temperature=0.1)
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
                "difficulty": q.get("difficulty", 2),
                "answer": (q.get("answer") or "").strip(),
                "matched_project_ids": matched_ids
            })
        return cleaned

    def _regex_fallback_extract(self, text: str) -> list:
        """LLM不可用时的正则兜底解析（支持二级编号 2.1/3.1 等）。"""
        text = text.replace('\r', '\n')
        questions = []
        # 匹配 2.1、3.1、1. 这种编号
        pattern = r'(?:^|\n)\s*(?:\d+\.\d+\s*[、.\s]\s*|\d+\s*\.\s*|\d+\s*、\s*|【\d+】\s*|\(\d+\)\s*|第\d+[题问]\s*)\s*(.*?)(?=\n\s*\d+\.\d+\s*[、.\s]|\n\s*\d+\s*\.|\n\s*\d+\s*、|\n\s*【\d+】|\n\s*\(\d+\)|\n\s*第\d+[题问]|\n\n|\Z)'
        matches = re.findall(pattern, text, re.DOTALL)
        for m in matches:
            m = m.strip()
            if len(m) > 5 and not m.startswith(('#', '互动', '作者', '底部', '点赞', '收藏', '评论')):
                questions.append({
                    "content": m,
                    "question_type": "bagua",
                    "category": "other",
                    "difficulty": 2,
                    "matched_project_ids": []
                })
        return questions
