import os
import json
from core.llm_client import DeepSeekClient


class BaseAgent:
    """所有agent的基础类，封装LLM客户端的初始化与调用、JSON解析等通用能力。

    所有具体agent（识题/项目/出题/答案/复习）均继承此类，
    通过 _get_client() 获取LLM客户端，通过 _chat() 调用LLM，
    通过 _parse_json() 解析LLM返回内容中的JSON片段。
    """

    def __init__(self):
        # 每个agent在初始化时获取LLM客户端
        self.client = self._get_client()

    def _get_client(self) -> DeepSeekClient:
        """从环境变量读取DEEPSEEK_API_KEY并初始化DeepSeekClient。"""
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        return DeepSeekClient(api_key)

    def _chat(self, system: str, user: str, temperature: float = 0.3, timeout: int = 90) -> str:
        """统一的LLM聊天接口，委托给DeepSeekClient。

        Args:
            system: system prompt
            user: user prompt
            temperature: 采样温度
            timeout: 请求超时时间(秒)

        Returns:
            LLM返回的文本内容

        Raises:
            RuntimeError: 当LLM接口返回非200状态码时
        """
        return self.client._chat(system, user, temperature=temperature, timeout=timeout)

    def _parse_json(self, content: str, start_char: str = '[', end_char: str = ']'):
        """从LLM返回内容中解析JSON片段。

        自动定位第一个 start_char 与最后一个 end_char 之间的内容并解析为JSON对象。
        具备容错处理：定位失败或解析失败时返回 None，不抛出异常。

        Args:
            content: LLM返回的原始文本
            start_char: JSON起始字符，默认为 '[' (数组)
            end_char: JSON结束字符，默认为 ']' (数组)

        Returns:
            解析后的Python对象(list/dict)；解析失败返回 None
        """
        try:
            start = content.find(start_char)
            end = content.rfind(end_char) + 1
            if start == -1 or end == 0:
                return None
            return json.loads(content[start:end])
        except Exception as e:
            print(f"JSON parse error: {e}")
            return None
