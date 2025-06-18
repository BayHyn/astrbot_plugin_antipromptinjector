from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api import AstrBotConfig # 导入 AstrBotConfig

import re
import json
import os

WHITELIST_PATH = "data/antiprompt_admin_whitelist.json"

# 修改 load_whitelist 函数，使其可以接收 initial_admin_id 和 initial_whitelist
def load_whitelist(initial_admin_id: str = "3338169190", initial_whitelist: list = None):
    """
    加载白名单数据。如果文件不存在，则创建默认数据。
    :param initial_admin_id: 初始管理员ID，当文件不存在时使用。
    :param initial_whitelist: 初始白名单列表，当文件不存在时使用。
    """
    if initial_whitelist is None:
        initial_whitelist = [initial_admin_id] # 默认白名单包含管理员ID

    try:
        with open(WHITELIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            # 确保加载的数据结构完整，如果缺少admin_id或whitelist，使用初始值
            if "admin_id" not in data:
                data["admin_id"] = initial_admin_id
            if "whitelist" not in data:
                data["whitelist"] = initial_whitelist
            return data
    except FileNotFoundError:
        logger.info(f"白名单文件 {WHITELIST_PATH} 不存在，将创建默认白名单。")
        default_data = {"admin_id": initial_admin_id, "whitelist": initial_whitelist}
        save_whitelist(default_data)
        return default_data
    except json.JSONDecodeError:
        logger.error(f"白名单文件 {WHITELIST_PATH} 内容无法解析为JSON，将创建新的默认白名单。")
        default_data = {"admin_id": initial_admin_id, "whitelist": initial_whitelist}
        save_whitelist(default_data)
        return default_data
    except Exception as e:
        logger.error(f"加载白名单文件时发生未知错误: {e}，将创建新的默认白名单。")
        default_data = {"admin_id": initial_admin_id, "whitelist": initial_whitelist}
        save_whitelist(default_data)
        return default_data


def save_whitelist(data):
    """
    保存白名单数据到文件。
    :param data: 要保存的白名单数据字典。
    """
    os.makedirs(os.path.dirname(WHITELIST_PATH), exist_ok=True)
    with open(WHITELIST_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@register("antipromptinjector", "LumineStory", "屏蔽伪系统注入攻击插件", "1.0.1")
class AntiPromptInjector(Star):
    # 修改 __init__ 方法以接收 config 参数
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config # 将传入的 config 保存为实例属性
        
        # 从配置中获取插件启用状态，默认为 True
        self.plugin_enabled = self.config.get("enabled", True)
        
        # 从配置中获取初始管理员ID和白名单，用于 load_whitelist
        # 这些值只在首次创建 antiprompt_admin_whitelist.json 时生效
        self.initial_admin_id = self.config.get("initial_admin_id", "3338169190")
        self.initial_whitelist = self.config.get("initial_whitelist", ["3338169190"])


        self.patterns = [
            # 带时间戳+ID的聊天记录伪注入
            re.compile(r"\[\d{2}:\d{2}:\d{2}\].*?\[\d{5,12}\].*"),
            # 简易注入格式 [角色/时间][ID]
            re.compile(r"\[\S{1,12}/\d{1,2}:\d{2}:\d{2}\]\[\d{5,12}\]"),
            # 让Bot复述/重复内容
            re.compile(r"重复我(刚才|说的话|内容).*", re.IGNORECASE),
            # 已设置X为管理员 注入
            re.compile(r".*?已设置.*?为管理员.*", re.IGNORECASE),
            # 输出系统内部想法
            re.compile(r"(告诉我|输出|显示).*你的(记忆|内部|思考|模型).*", re.IGNORECASE),
            # 角色设定注入
            re.compile(r"你现在是.*角色.*", re.IGNORECASE),
            # 强制角色属性注入（可爱、性感等）
            re.compile(r"你是一个?(可爱|忠诚|性感|助手|女孩|男性|AI|角色).{0,15}。", re.IGNORECASE),
            # 忽略之前所有设定
            re.compile(r"忽略之前.*?(现在|立刻).*(开始|执行).*", re.IGNORECASE),
            # 伪系统命令
            re.compile(r"^/system\s+.+", re.IGNORECASE),
            # prompt: 指令、角色设定等代码注入
            re.compile(r"^(##|prompt:|角色设定|你必须扮演).{0,50}$", re.IGNORECASE),
            # 代码块开头
            re.compile(r"^```(python|json|prompt|system|txt)", re.IGNORECASE),
        ]

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def detect_prompt_injection(self, event: AstrMessageEvent):
        # 使用从 config 中读取的插件启用状态
        if not self.plugin_enabled:
            return
        
        # 在加载白名单时传入初始配置，确保文件不存在时使用 config 中的值
        wl = load_whitelist(self.initial_admin_id, self.initial_whitelist)
        if event.get_sender_id() in wl.get("whitelist", []):
            return
        m = event.get_message_str().strip()
        for p in self.patterns:
            if p.search(m):
                logger.warning(f"⚠️ 拦截注入消息: {m}")
                event.stop_event()
                yield event.plain_result("⚠️ 检测到可能的注入攻击，消息已被拦截。")
                return

    @filter.on_llm_request()
    async def mark_admin_identity(self, event: AstrMessageEvent, req):
        # 使用从 config 中读取的插件启用状态
        if not self.plugin_enabled:
            return

        # 在加载白名单时传入初始配置
        wl = load_whitelist(self.initial_admin_id, self.initial_whitelist)
        # 获取消息列表（适配不同版本）
        messages = None
        if hasattr(req, "get_messages"):
            messages = req.get_messages()
        elif hasattr(req, "messages"):
            messages = req.messages
        if not isinstance(messages, list):
            logger.warning("ProviderRequest 无消息列表，跳过管理员标记")
            return

        for msg in messages:
            if getattr(msg, "role", None) == "user":
                sid = getattr(msg, "sender_id", None)
                content = getattr(msg, "content", "")
                # 管理员优先
                if sid in wl.get("whitelist", []):
                    messages.insert(0, type(msg)(
                        role="system",
                        content="⚠️ 注意：当前发言者为管理员，其指令优先级最高。",
                        sender_id="system"
                    ))
                    break
                # 伪管理员语言
                for pat in [
                    re.compile(r"从现在开始你必须"),
                    re.compile(r"你现在是.*管理员"),
                    re.compile(r"请忽略上方所有设定"),
                    re.compile(r"重复我说的话"),
                ]:
                    if pat.search(content):
                        logger.warning(f"⚠️ 拦截伪管理员语气: {sid}")
                        msg.content = "[⚠️ 消息已修改：疑似伪装管理员行为已拦截]"
                        break

    @filter.command("添加防注入白名单ID")
    async def cmd_add_wl(self, event: AstrMessageEvent, target_id: str):
        # 在加载白名单时传入初始配置
        data = load_whitelist(self.initial_admin_id, self.initial_whitelist)
        if event.get_sender_id() != data["admin_id"]:
            yield event.plain_result("❌ 权限不足，只有管理员可操作。")
            return
        if target_id not in data["whitelist"]:
            data["whitelist"].append(target_id)
            save_whitelist(data)
            yield event.plain_result(f"✅ {target_id} 已添加至白名单。")
        else:
            yield event.plain_result(f"⚠️ {target_id} 已在白名单内。")

    @filter.command("移除防注入白名单ID")
    async def cmd_remove_wl(self, event: AstrMessageEvent, target_id: str):
        # 在加载白名单时传入初始配置
        data = load_whitelist(self.initial_admin_id, self.initial_whitelist)
        if event.get_sender_id() != data["admin_id"]:
            yield event.plain_result("❌ 权限不足，只有管理员可操作。")
            return
        if target_id in data["whitelist"]:
            data["whitelist"].remove(target_id)
            save_whitelist(data)
            yield event.plain_result(f"✅ {target_id} 已从白名单移除。")
        else:
            yield event.plain_result(f"⚠️ {target_id} 不在白名单中。")

    @filter.command("查看防注入白名单")
    async def cmd_view_wl(self, event: AstrMessageEvent):
        # 在加载白名单时传入初始配置
        data = load_whitelist(self.initial_admin_id, self.initial_whitelist)
        ids = "\n".join(data["whitelist"])
        yield event.plain_result(f"当前白名单用户：\n{ids}")

    @filter.command("设置管理员ID") # 新增的命令
    async def cmd_set_admin_id(self, event: AstrMessageEvent, new_admin_id: str):
        """
        设置插件的管理员用户ID。
        只有当前的管理员才能执行此命令。
        :param new_admin_id: 新的管理员用户ID
        """
        data = load_whitelist(self.initial_admin_id, self.initial_whitelist)
        current_admin_id = data["admin_id"]

        if event.get_sender_id() != current_admin_id:
            yield event.plain_result("❌ 权限不足，只有当前管理员可操作此命令。")
            return

        if new_admin_id == current_admin_id:
            yield event.plain_result("⚠️ 新的管理员ID与当前管理员ID相同，无需更改。")
            return

        data["admin_id"] = new_admin_id
        save_whitelist(data)
        logger.info(f"管理员ID已从 {current_admin_id} 更改为 {new_admin_id}。")
        yield event.plain_result(f"✅ 管理员ID已成功更改为：{new_admin_id}。")

    @filter.command("注入拦截帮助")
    async def cmd_help(self, event: AstrMessageEvent):
        msg = (
            "🛡️ 注入拦截插件命令：\n"
            "/添加防注入白名单ID <ID>\n"
            "/移除防注入白名单ID <ID>\n"
            "/查看防注入白名单\n"
            "/设置管理员ID <新ID>\n" # 更新帮助信息
            "/注入拦截帮助\n"
        )
        yield event.plain_result(msg)

    async def terminate(self):
        """
        插件终止时调用，用于清理资源。
        """
        logger.info("AntiPromptInjector 插件已终止。")
