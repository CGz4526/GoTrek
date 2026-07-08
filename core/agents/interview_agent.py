import os
import json
import requests
from typing import List, Optional


class InterviewAgent:
    """模拟面试官 agent：以面试官身份与候选人进行多轮对话。

    根据候选人选择的项目，进行递进式、有逻辑的提问：
    - 开场：简短寒暄 + 第一个项目相关问题
    - 过程：根据候选人回答给出简短反馈并追问/延伸/切换话题
    - 结束：候选人主动结束或问够约定题数
    所有对话历史由调用方传入，agent 仅负责生成下一条面试官回复。
    """

    def __init__(self):
        self.api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        self.base_url = "https://api.deepseek.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def available(self) -> bool:
        return bool(self.api_key)

    def _build_system_prompt(self, project_info: Optional[dict], position: str,
                             question_count: int) -> str:
        project_section = ""
        if project_info:
            pname = project_info.get("name", "")
            ptype = project_info.get("project_type", "")
            pstack = project_info.get("tech_stack", [])
            if isinstance(pstack, list):
                pstack = "、".join(pstack)
            pdesc = project_info.get("description", "")
            project_section = (
                f"\n\n候选人简历项目信息：\n"
                f"- 项目名称：{pname}\n"
                f"- 项目类型：{ptype}\n"
                f"- 技术栈：{pstack}\n"
                f"- 项目描述：{pdesc}\n"
            )

        return (
            "你是一位资深的" + position + "面试官，正在进行一场1对1的技术模拟面试。\n"
            "面试风格要求：\n"
            "1. 像真实面试一样自然对话，不要像出题机器。\n"
            "2. 每次只问一个问题，问题要基于候选人上一个回答深入或自然延伸。\n"
            "3. 提问递进式：整体架构→技术选型理由→具体难点攻坚→优化方向→相关八股原理。\n"
            "4. 在追问前，先用1-2句简短评价候选人的回答（说对/有遗漏/方向偏了），再提下一个问题。\n"
            "5. 如果候选人回答偏离太远，礼貌引导回主题；如果候选人不会，简要给思路后换话题。\n"
            "6. 围绕候选人选择的项目展开，约60%项目相关问题，40%项目技术栈相关八股原理。\n"
            "7. 不要一次输出多个问题，不要列要点式提问，保持口语化面试感。\n"
            "8. 当候选人明确表达结束意图（如\"结束\"\"面试结束\"\"不面了\"），"
            "或已问够" + str(question_count) + "个问题左右时，"
            "给出简短总结评价并说\"本次面试结束\"，评价要包含优点和可改进点。\n"
            "9. 你的回复就是面试官说的原话，不要加\"面试官：\"前缀，不要输出JSON。"
            + project_section
        )

    def chat(self, history: List[dict], project_info: Optional[dict],
             position: str = "后端开发", question_count: int = 8) -> dict:
        """生成面试官的下一条回复。

        Args:
            history: 对话历史，每项 {"role": "interviewer"/"candidate", "content": str}
            project_info: 项目信息 dict（可选）
            position: 面试岗位
            question_count: 计划面试题数（达到后引导结束）

        Returns:
            {"content": str, "should_end": bool}
        """
        if not self.available():
            return {
                "content": "（LLM服务未配置，无法进行模拟面试）",
                "should_end": True
            }

        system = self._build_system_prompt(project_info, position, question_count)

        # 将历史转为 DeepSeek messages 格式
        messages = [{"role": "system", "content": system}]

        # 开场提示：如果历史为空，让面试官开始
        if not history:
            messages.append({
                "role": "user",
                "content": "面试现在开始，请以面试官身份开场并问第一个问题。"
            })
        else:
            for msg in history:
                role = msg.get("role")
                content = msg.get("content", "")
                if role == "interviewer":
                    messages.append({"role": "assistant", "content": content})
                else:
                    messages.append({"role": "user", "content": content})
            # 提示生成下一条
            messages.append({
                "role": "user",
                "content": "（请以面试官身份回复，只说面试官的话）"
            })

        data = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 600
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=data,
                timeout=60
            )
            if response.status_code != 200:
                return {
                    "content": f"（面试官暂时离线，请稍后重试。状态码 {response.status_code}）",
                    "should_end": False
                }
            content = response.json()['choices'][0]['message']['content'].strip()
            # 简单判断是否结束
            end_keywords = ["本次面试结束", "面试结束", "本次模拟面试结束"]
            should_end = any(kw in content for kw in end_keywords)
            return {"content": content, "should_end": should_end}
        except Exception as e:
            print(f"InterviewAgent error: {e}")
            return {
                "content": "（面试官网络异常，请稍后重试）",
                "should_end": False
            }
