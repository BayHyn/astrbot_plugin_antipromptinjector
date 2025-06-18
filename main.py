from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api.llm import LLMMessage, filter_llm_request
from astrbot.api import logger
import re
import json
import os

@register("antipromptinjector", "LumineStory", "屏蔽伪系统注入攻击的插件", "1.3.0")
class AntiPromptInjector(Star):
    def __init__(self, context: Context):
        super().__init__(context)

        # 加载配置文件
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        else:
            self.config = {
                "enabled": True,
                "detect_admin_spoof": True,
                "log_admin_commands": True,
                "admin_ids": "3338169190"
            }

        self.patterns = [
            re.compile(r"\[\S{1,12}/\d{1,2}:\d{2}:\d{2}]\[\d{5,12}]\s*[\s\S]*"),
            re.compile(r"^/system\s+.+", re.IGNORECASE),
            re.compile(r"你现在是.*?，从现在开始你(必须|只能|需要).*", re.IGNORECASE),
            re.compile(r"忽略之前.*?(现在|立刻).{0,10}(开始|执行).*", re.IGNORECASE),
            re.compile(r"你是一个?(可爱|忠诚|性感|助手|女孩|男性|AI|角色).{0,15}。", re.IGNORECASE),
            re.compile(r"^```(python|json|prompt|system|txt)?\s*\\?n?", re.IGNORECASE),
            re.compile(r"^(##|prompt:|角色设定|你必须扮演).{0,50}$", re.IGNORECASE)
        ]

        # 管理员ID白名单支持
        self.admin_ids = set(self.config.get("admin_ids", "3338169190").split(","))

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def detect_prompt_injection(self, event: AstrMessageEvent):
        if not self.config.get("enabled", True):
            return

        message = event.get_message_str().strip()

        for pattern in self.patterns:
            if pattern.match(message):
                logger.warning(f"⚠️ 阻止潜在注入攻击消息: {message}")
                event.stop_event()
                yield event.plain_result("⚠️ 检测到可能的提示词注入攻击，消息已被拦截。")
                return

    @filter_llm_request()
    async def mark_admin_identity(self, messages: list[LLMMessage]):
        if not self.config.get("enabled", True):
            return

        for msg in messages:
            if msg.role == "user":
                if msg.sender_id in self.admin_ids:
                    if self.config.get("log_admin_commands", True):
                        logger.info(f"已识别管理员发言者: {msg.sender_id}")
                    messages.insert(0, LLMMessage(
                        role="system",
                        content="请注意：当前发言者为管理员，其指令具有最高优先级且不可被伪造。",
                        sender_id="system"
                    ))
                    break
                else:
                    if self.config.get("detect_admin_spoof", True) and self._spoofed_admin_style(msg.content):
                        logger.warning(f"⚠️ 非管理员尝试使用管理员语气发送消息: {msg.sender_id}")
                        msg.content = "[消息已修改：疑似伪造管理员身份的行为已拦截]"

    def _spoofed_admin_style(self, content: str) -> bool:
        spoof_patterns = [
            re.compile(r"从现在开始你必须.*", re.IGNORECASE),
            re.compile(r"你现在是.+管理员.*", re.IGNORECASE),
            re.compile(r"请忽略上方所有设定.*", re.IGNORECASE)
        ]
        return any(p.search(content) for p in spoof_patterns)

    async def terminate(self):
        logger.info("AntiPromptInjector 插件终止。日志清理完成。")
