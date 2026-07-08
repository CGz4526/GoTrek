from core.agents.base_agent import BaseAgent


# project_type 关键词映射，用于将LLM返回的类型标准化
_PROJECT_TYPE_KEYWORDS = {
    "seckill": ["秒杀", "抢购", "flash sale"],
    "ecommerce": ["电商", "商城", "购物", "订单系统"],
    "social": ["社交", "社区", "即时通讯", "im", "朋友圈"],
    "cms": ["内容管理", "cms", "博客", "资讯", "门户"],
    "data": ["数据", "大数据", "数仓", "etl", "数据平台", "推荐系统"],
    "ai": ["ai", "人工智能", "机器学习", "深度学习", "llm", "agent", "智能"],
}

_VALID_PROJECT_TYPES = ("seckill", "ecommerce", "social", "cms", "data", "ai", "other")


class ProjectAgent(BaseAgent):
    """项目识别agent：分析项目描述并提取结构化信息。

    自动判断 project_type，映射到标准类型：
    seckill/ecommerce/social/cms/data/ai/other
    """

    def analyze(self, description: str) -> dict:
        """分析项目描述，提取结构化信息。

        Args:
            description: 项目描述文本

        Returns:
            dict: {
                "name": str,
                "tech_stack": list,
                "project_type": str (seckill/ecommerce/social/cms/data/ai/other),
                "core_modules": list,
                "question_topics": list
            }
        """
        try:
            result = self._analyze_with_llm(description)
            if result:
                result["project_type"] = self._normalize_project_type(result.get("project_type", ""))
                # 字段兜底
                result.setdefault("name", "未命名项目")
                result.setdefault("tech_stack", [])
                result.setdefault("core_modules", [])
                result.setdefault("question_topics", [])
                return result
            return self._fallback_analyze(description)
        except Exception as e:
            print(f"ProjectAgent LLM error: {e}")
            return self._fallback_analyze(description)

    def _analyze_with_llm(self, description: str) -> dict:
        system = (
            "你是一个资深的技术架构师，擅长从一段项目描述文字中自动识别项目信息。"
            "用户只会给你一段文字段落，你需要自己判断项目名称、类型、技术栈等所有信息。"
            "请严格按照JSON格式返回结果，不要包含其他文字。"
        )
        prompt = f"""请从以下文字段落中自动识别项目信息：

文字段落：
{description}

请自动识别并提取：
1. 项目名称(name) —— 根据描述内容自动总结一个简洁的项目名称（如"秒杀系统""博客平台"等）
2. 技术栈(tech_stack，字符串数组) —— 从描述中识别用到的技术
3. 项目类型(project_type，必须从以下选项中选择: seckill/ecommerce/social/cms/data/ai/other)
   - seckill: 秒杀/抢购系统
   - ecommerce: 电商/商城/订单系统
   - social: 社交/社区/即时通讯
   - cms: 内容管理/博客/资讯门户
   - data: 数据/大数据/数仓/推荐系统
   - ai: AI/智能/LLM/Agent相关
   - other: 其他
4. 核心功能模块(core_modules，字符串数组)
5. 可能被问到的面试问题方向(question_topics，字符串数组)

返回格式为JSON（不要包含其他文字）：
{{
    "name": "项目名称",
    "tech_stack": ["技术1", "技术2"],
    "project_type": "seckill",
    "core_modules": ["模块1", "模块2"],
    "question_topics": ["话题1", "话题2"]
}}"""

        content = self._chat(system, prompt, temperature=0.3)
        result = self._parse_json(content, '{', '}')
        if not isinstance(result, dict):
            return {}
        return result

    def _normalize_project_type(self, ptype: str) -> str:
        """将LLM返回的project_type标准化为受支持的类型。"""
        if not ptype or not isinstance(ptype, str):
            return "other"
        ptype_lower = ptype.strip().lower()
        if ptype_lower in _VALID_PROJECT_TYPES:
            return ptype_lower
        # 按关键词匹配
        for std_type, keywords in _PROJECT_TYPE_KEYWORDS.items():
            for kw in keywords:
                if kw in ptype_lower:
                    return std_type
        return "other"

    def _fallback_analyze(self, description: str) -> dict:
        """LLM失败时的简单兜底解析。"""
        return {
            "name": "未命名项目",
            "tech_stack": [],
            "project_type": "other",
            "core_modules": [],
            "question_topics": []
        }
