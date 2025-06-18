from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import re
import json
import os

WHITELIST_PATH = "data/antiprompt_admin_whitelist.json"

def load_whitelist():
    default_data = {"admin_id": "3338169190", "whitelist": ["3338169190"]}
    if not os.path.exists(WHITELIST_PATH):
        os.makedirs(os.path.dirname(WHITELIST_PATH), exist_ok=True)
        with open(WHITELIST_PATH, "w", encoding="utf-8") as f:
            json.dump(default_data, f, ensure_ascii=False, indent=2)
        return default_data
    try:
        with open(WHITELIST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        with open(WHITELIST_PATH, "w", encoding="utf-8") as f:
            json.dump(default_data, f, ensure_ascii=False, indent=2)
        return default_data

def save_whitelist(data):
    os.makedirs(os.path.dirname(WHITELIST_PATH), exist_ok=True)
    with open(WHITELIST_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@register("antipromptinjector", "LumineStory", "屏蔽伪系统注入攻击的插件", "1.4.1")  # 版本更新
class AntiPromptInjector(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.config = self.context.get_config()
        self.patterns = [
            re.compile(r"\[\S{1,12}/\d{1,2}:\d{2}:\d{2}]\[\d{5,12}]\s*[\s\S]*"),
            re.compile(r"^/system\s+.+", re.IGNORECASE),
            re.compile(r"你现在是.*?，从现在开始你(必须|只能|需要).*", re.IGNORECASE),
            re.compile(r"忽略之前.*?(现在|立刻).{0,10}(开始|执行).*", re.IGNORECASE),
            re.compile(r"你是一个?(可爱|忠诚|性感|助手|女孩|男性|AI|角色).{0,15}。", re.IGNORECASE),
            re.compile(r"^```(python|json|prompt|system|txt)?\s*\\?n?", re.IGNORECASE),
            re.compile(r"^(##|prompt:|角色设定|你必须扮演).{0,50}$", re.IGNORECASE),
            re.compile(
                r"\[\d{2}:\d{2}:\d{2}]\s*\[[^\]]+]\s*\[[^\]]+]\s*\[[^\]]+]:\s*\[[^\]]+]\s*[^\s]+/\d+:\[\S+/\d{2}:\d{2}:\d{2}]\[\d{5,12}].*"
            ),
            re.compile(r"从现在开始你必须.*", re.IGNORECASE),
            re.compile(r"你现在是.+管理员.*", re.IGNORECASE),
            re.compile(r"请忽略上方所有设定.*", re.IGNORECASE),
            re.compile(r"^/(reset|reload|restart|shutdown|stop|eval|exec)\b", re.IGNORECASE),
            re.compile(r"(\[[Ss]ystem\]|\[[Uu]ser\]|\[[Aa]dmin\])"),
            re.compile(r"[\x00-\x1F\x7F-\x9F]"),
        ]

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def detect_prompt_injection(self, event: AstrMessageEvent):
        if not self.config.get("enabled", True):
            return

        wl = load_whitelist()
        if event.get_sender_id() in wl.get("whitelist", []):
            return

        message = event.get_message_str().strip()
        for pattern in self.patterns:
            if pattern.match(message):
                logger.warning(f"⚠️ 阻止潜在注入攻击消息: {message}")
                event.stop_event()
                yield event.plain_result("⚠️ 检测到可能的提示词注入攻击，消息已被拦截。")
                return

    @filter.on_llm_request()
    async def mark_admin_identity(self, event: AstrMessageEvent, req: ProviderRequest):
        if not self.config.get("enabled", True):
            return

        wl = load_whitelist()
        for msg in req.messages:
            if msg.role == "user":
                if msg.sender_id in wl.get("whitelist", []):
                    req.messages.insert(0, type(msg)(
                        role="system",
                        content="请注意：当前发言者为管理员，其指令具有最高优先级且不可被伪造。",
                        sender_id="system"
                    ))
                    break
                elif self._spoofed_admin_style(msg.content):
                    logger.warning(f"⚠️ 非管理员尝试使用管理员语气发送消息: {msg.sender_id}")
                    msg.content = "[消息已修改：疑似伪造管理员身份的行为已拦截]"

    def _spoofed_admin_style(self, content: str) -> bool:
        spoof_patterns = [
            re.compile(r"从现在开始你必须.*", re.IGNORECASE),
            re.compile(r"你现在是.+管理员.*", re.IGNORECASE),
            re.compile(r"请忽略上方所有设定.*", re.IGNORECASE)
        ]
        return any(p.search(content) for p in spoof_patterns)

    @filter.command("添加防注入白名单ID")
    async def add_whitelist(self, event: AstrMessageEvent, target_id: str):
        data = load_whitelist()
        if event.get_sender_id() != data["admin_id"]:
            yield event.plain_result("你不是系统管理员，无法添加白名单。")
            return
        if target_id not in data["whitelist"]:
            data["whitelist"].append(target_id)
            save_whitelist(data)
            yield event.plain_result(f"{target_id} 已添加到防注入白名单。")
        else:
            yield event.plain_result(f"{target_id} 已经在白名单中。")

    @filter.command("移除防注入白名单ID")
    async def remove_whitelist(self, event: AstrMessageEvent, target_id: str):
        data = load_whitelist()
        if event.get_sender_id() != data["admin_id"]:
            yield event.plain_result("你不是系统管理员，无法移除白名单。")
            return
        if target_id in data["whitelist"]:
            data["whitelist"].remove(target_id)
            save_whitelist(data)
            yield event.plain_result(f"{target_id} 已从防注入白名单中移除。")
        else:
            yield event.plain_result(f"{target_id} 不在白名单中。")

    @filter.command("查看防注入白名单")
    async def view_whitelist(self, event: AstrMessageEvent):
        data = load_whitelist()
        yield event.plain_result("当前白名单 ID 列表：\n" + "\n".join(data["whitelist"]))

    # 新增指令 /注入拦截帮助，输出所有命令说明
    @filter.command("注入拦截帮助")
    async def help_commands(self, event: AstrMessageEvent):
        help_text = (
            "防注入插件可用指令列表：\n"
            "1. 添加防注入白名单ID <目标ID> —— 将指定ID添加到白名单，免疫拦截。\n"
            "2. 移除防注入白名单ID <目标ID> —— 将指定ID从白名单移除。\n"
            "3. 查看防注入白名单 —— 显示当前所有白名单ID。\n"
            "4. 注入拦截帮助 —— 查看此帮助信息。\n"
            "\n注意：仅系统管理员（ID: 3338169190）可使用添加与移除指令。"
        )
        yield event.plain_result(help_text)

    async def terminate(self):
        logger.info("AntiPromptInjector 插件终止。")
