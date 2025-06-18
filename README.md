# AntiPromptInjector 插件

这是一个用于 AstrBot 的插件，用于识别和拦截伪造系统指令（Prompt Injection），防止恶意用户伪造系统提示影响 LLM 的行为。

## 功能特性

- 拦截多种常见的注入攻击提示词（如伪装成 system、角色扮演设定等）
- 识别伪造管理员语气内容并替换
- 支持设置白名单用户（如 bot 拥有者）
- 支持指令管理白名单
- 插件启动时自动创建 JSON 存储文件（如不存在）

## 默认配置

初次启动时会在 `data/antiprompt_admin_whitelist.json` 自动创建：

```json
{
  "admin_id": "3338169190",
  "whitelist": ["3338169190"]
}
```

## 指令说明

- `/添加防注入白名单ID <ID>` - 添加指定用户 ID 到白名单（仅管理员）
- `/移除防注入白名单ID <ID>` - 移除指定 ID（仅管理员）
- `/查看防注入白名单` - 查看当前白名单列表
- `/注入拦截帮助` - 显示帮助信息


## 插件信息

- 插件名：antipromptinjector
- 作者：LumineStory
- 描述：屏蔽伪系统注入攻击的插件
- 版本：1.0.0

## 反馈问题

本插件托管在 GitHub 上：https://github.com/oyxning/astrbot_plugin_antipromptinjector  
如有建议或 Bug，欢迎提交 issue。
