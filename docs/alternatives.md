# 同类项目与兼容范围

查询日期：2026 年 10 月 26 日。GitHub 上已有类似项目，本项目并非唯一的汉化方案。

| 项目 | 主要方式 | 查到的维护与兼容证据 |
| --- | --- | --- |
| [xqnode/codex-zh-CN](https://github.com/xqnode/codex-zh-CN) | Windows 桌面语言包、菜单和资源补丁；Store 版使用可写副本 | 仓库最近推送为 2026-06-04。README 提醒客户端更新后重装补丁；没有据此确认 26.1021 兼容性 |
| [LinYiXin123/claude-code-zh-toolkit](https://github.com/LinYiXin123/claude-code-zh-toolkit) | Windows 便携版显示层与技能列表中文增强 | 仓库最近推送为 2026-05-04；README 明确依赖便携版目录结构，不同前端版本可能需要适配 |
| [pluscodex888/codex-plusplus-release](https://github.com/pluscodex888/codex-plusplus-release) | 预编译汉化增强版，也包含模型、账号与更新功能 | 2026-10-20 发布的 v2.1.3 说明客户端沿用 26.911.7940；不能因此认定已适配截图中的 26.1021 |
| [chen0416ccc-cpu/codex-windows-fast-patch-skill](https://github.com/chen0416ccc-cpu/codex-windows-fast-patch-skill) | 供智能体使用的诊断与修复 Skill，包含语言重置修复 | 最近推送为 2026-10-24；README 明确说明适用性取决于版本和文件内容，并非适用于所有版本的一键安装器 |

“最近有更新”不等于“已经验证最新版兼容”。以上为仓库说明与发布信息的核对，没有安装这些项目或执行其脚本。

## 本项目当前支持什么

- 已验证的安装包：`OpenAI.Codex 26.1021.3705.0`。
- 使用者提供的版本截图：`ChatGPT / Powered by Codex & OWL 26.1021.31345`，发布日期 2026-10-24。
- 复用当前版本自带中文词典；按资源内容匹配，不依赖固定的界面文件哈希名称。
- 未来更新后可以重新生成副本，但文件格式、启动器或消息结构改变时仍可能需要适配。
- 不承诺支持每一个“最新版本”，也不把独立 ChatGPT 桌面客户端与该 Codex / OWL 程序混为同一兼容目标。

## 证据来源

- 各项目 README 与 GitHub 仓库 `pushed_at`。
- [Codex 汉化增强版 v2.1.3 发布说明](https://github.com/pluscodex888/codex-plusplus-release/releases/tag/v2.1.3)。
- 本仓库 README 中的四张实际效果截图。
