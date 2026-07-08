import requests
import json
import re
from typing import Optional


class DeepSeekClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.deepseek.com/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def _chat(self, system: str, user: str, temperature: float = 0.3, timeout: int = 90) -> str:
        """统一的聊天接口调用"""
        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            "temperature": temperature
        }
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self.headers,
            json=data,
            timeout=timeout
        )
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        raise RuntimeError(f"LLM API error {response.status_code}: {response.text}")

    def extract_questions(self, text: str) -> list:
        """识题agent：从面经文本中精确提取每一道面试题，返回结构化题目列表。

        相比正则解析，LLM能理解章节结构（如 2.1/3.1 二级编号）、过滤噪音文字，
        并自动判断题目类型和细分分类。
        """
        system = (
            "你是一个专业的面试题提取助手（识题agent）。"
            "你的任务是从面试面经文本中精确提取出每一道独立的面试题。"
            "注意：1) 文本可能包含章节标题（如'二 项目'、'三 八股'）和编号（如2.1、3.1），这些都是题目分隔符，不是题目本身。"
            "2) 文本可能包含非题目内容（如互动数据、作者信息、输入框提示等噪音），必须过滤掉。"
            "3) 每道题应独立完整，不要把多道题合并。"
            "4) 准确判断每道题的类型（bagua=八股题/project=项目题/algorithm=算法题）和细分分类。"
        )
        prompt = f"""请从以下面经文本中提取所有面试题，返回JSON数组。

面经文本：
{text}

分类规则：
- question_type: "project"（关于项目设计、实现、优化）、"bagua"（技术原理、机制、概念）、"algorithm"（算法、数据结构、复杂度）
- category: redis/mysql/java/multithreading/collection/network/os/design_pattern/spring/distributed/project/algorithm/other

返回格式（JSON数组，不要包含其他文字）：
[
  {{"content": "题目完整内容", "question_type": "bagua", "category": "redis", "difficulty": 2}}
]

要求：
1. 提取每一道独立题目，不要遗漏
2. 章节标题（如"二 项目"、"三 八股"）不是题目，不要提取
3. 过滤掉互动数据、作者信息等噪音
4. difficulty范围1-5"""

        try:
            content = self._chat(system, prompt, temperature=0.1)
            start = content.find('[')
            end = content.rfind(']') + 1
            if start == -1 or end == 0:
                return self._regex_fallback_extract(text)
            questions = json.loads(content[start:end])
            cleaned = []
            for q in questions:
                c = (q.get("content") or "").strip()
                if len(c) < 3:
                    continue
                cleaned.append({
                    "content": c,
                    "question_type": q.get("question_type", "bagua"),
                    "category": q.get("category", "other"),
                    "difficulty": q.get("difficulty", 2)
                })
            return cleaned if cleaned else self._regex_fallback_extract(text)
        except Exception as e:
            print(f"Extract questions LLM error: {e}")
            return self._regex_fallback_extract(text)

    def _regex_fallback_extract(self, text: str) -> list:
        """LLM不可用时的正则兜底解析（支持二级编号 2.1/3.1 等）"""
        text = text.replace('\r', '\n')
        questions = []
        # 匹配 2.1、3.1、1. 这种编号
        pattern = r'(?:^|\n)\s*(?:\d+\.\d+\s*[、.\s]\s*|\d+\s*\.\s*|\d+\s*、\s*|【\d+】\s*|\(\d+\)\s*|第\d+[题问]\s*)\s*(.*?)(?=\n\s*\d+\.\d+\s*[、.\s]|\n\s*\d+\s*\.|\n\s*\d+\s*、|\n\s*【\d+】|\n\s*\(\d+\)|\n\s*第\d+[题问]|\n\n|\Z)'
        matches = re.findall(pattern, text, re.DOTALL)
        for m in matches:
            m = m.strip()
            if len(m) > 5 and not m.startswith(('#', '互动', '作者', '底部', '点赞', '收藏', '评论')):
                questions.append({"content": m, "question_type": "bagua", "category": "other", "difficulty": 2})
        return questions

    def generate_questions(self, topic: str, count: int = 5, project_info: Optional[str] = None) -> list:
        prompt = f"""你是一个资深的后端/agent开发面试官。请根据以下主题生成{count}道面试题：
        
主题：{topic}

{"项目信息：" + project_info if project_info else ""}

要求：
1. 题目类型包括：八股题、项目题、算法题
2. 难度适中，适合2-3年经验的后端开发工程师
3. 每道题需要包含：题干、类型（bagua/project/algorithm）、分类（如redis/mysql/java等）
4. 返回格式为JSON数组，不要包含其他文字

示例格式：
[
    {{
        "content": "Redis的持久化机制是什么？",
        "question_type": "bagua",
        "category": "redis",
        "difficulty": 2,
        "answer": "Redis有两种持久化机制..."
    }}
]"""
        
        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "你是一个专业的技术面试官，擅长生成高质量的后端开发面试题。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=data,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                try:
                    start = content.find('[')
                    end = content.rfind(']') + 1
                    json_str = content[start:end]
                    return json.loads(json_str)
                except:
                    return self._parse_fallback(content)
            else:
                return []
        except Exception as e:
            print(f"LLM API Error: {e}")
            return []
    
    def generate_answer(self, question: str, project_info: Optional[str] = None) -> str:
        prompt = f"""请详细解答以下面试题：

题目：{question}

{"相关项目背景：" + project_info if project_info else ""}

要求：
1. 回答要详细、准确、专业
2. 如果是代码题，需要给出代码示例
3. 包含关键知识点和最佳实践
4. 语言简洁明了，适合面试场景"""
        
        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "你是一个资深的后端开发工程师，擅长解答各类技术问题。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.5
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=data,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                return "无法生成答案，请稍后重试。"
        except Exception as e:
            print(f"LLM API Error: {e}")
            return "生成答案时出错，请稍后重试。"
    
    def analyze_project(self, project_description: str) -> dict:
        prompt = f"""请分析以下项目描述，提取关键信息：

项目描述：{project_description}

请提取：
1. 项目名称
2. 技术栈（列出所有用到的技术）
3. 项目类型（如：秒杀系统、电商平台、社交系统等）
4. 核心功能模块
5. 可能被问到的面试问题方向

返回格式为JSON：
{{
    "name": "项目名称",
    "tech_stack": ["技术1", "技术2"],
    "project_type": "类型",
    "core_modules": ["模块1", "模块2"],
    "question_topics": ["话题1", "话题2"]
}}"""
        
        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "你是一个资深的技术架构师，擅长分析项目并提取关键信息。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=data,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                try:
                    start = content.find('{')
                    end = content.rfind('}') + 1
                    json_str = content[start:end]
                    return json.loads(json_str)
                except:
                    return {}
            else:
                return {}
        except Exception as e:
            print(f"LLM API Error: {e}")
            return {}
    
    def _parse_fallback(self, content: str) -> list:
        lines = content.split('\n')
        questions = []
        current_question = ""
        
        for line in lines:
            if line.strip().startswith(('1.', '2.', '3.', '4.', '5.', '- ', '• ')):
                if current_question:
                    questions.append({
                        "content": current_question.strip(),
                        "question_type": "bagua",
                        "category": "other",
                        "difficulty": 2,
                        "answer": ""
                    })
                current_question = line.strip()[2:] if line.strip()[1] == '.' else line.strip()[1:]
            else:
                current_question += " " + line.strip()
        
        if current_question:
            questions.append({
                "content": current_question.strip(),
                "question_type": "bagua",
                "category": "other",
                "difficulty": 2,
                "answer": ""
            })
        
        return questions[:5]