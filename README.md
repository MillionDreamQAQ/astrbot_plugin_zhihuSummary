# zhihuSummary 知乎总结 | AstrBot 插件

发送知乎回答/文章链接，自动生成 AI 结构化总结。

## 功能

- **知乎总结**：发送知乎链接，自动抓取内容并通过 LLM 生成结构化总结
- **多类型支持**：回答、专栏文章、问题（自动取高赞回答）
- **自动识别**：开启后自动检测群聊中的知乎链接并生成总结
- **精美渲染**：总结可渲染为暗色主题卡片图片（需 wkhtmltopdf）
- **长文本处理**：支持截断和 Map-Reduce 分段总结两种策略
- **多种 LLM**：支持 AstrBot 内置 LLM 或自定义 OpenAI 兼容 API
- **访问控制**：黑名单/白名单模式控制群聊使用权限

## 安装

### 前置依赖

- [AstrBot](https://github.com/Soulter/AstrBot) v3.5+
- [wkhtmltopdf](https://wkhtmltopdf.org/)（图片渲染模式需要）

### 安装插件

1. 在 AstrBot 管理面板的插件市场中搜索 `zhihuSummary` 安装
2. 或手动将本项目克隆到 AstrBot 的插件目录：

```bash
git clone https://github.com/MillionDreamQAQ/astrbot_plugin_zhihuSummary.git
```

### 安装 Python 依赖

```bash
pip install -r requirements.txt
```

## 配置

安装插件后，在 AstrBot 管理面板的插件设置中进行配置。

### 必填配置

| 配置项 | 说明 |
|--------|------|
| **zhihu_cookie_z_c0** | 知乎 Cookie `z_c0` 值 |

#### 如何获取 z_c0

1. 在浏览器中登录 [知乎](https://www.zhihu.com)
2. 按 `F12` 打开开发者工具
3. 切换到 `Application` → `Cookies` → `https://www.zhihu.com`
4. 找到 `z_c0`，复制其值填入插件配置

### 可选配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| llm_provider | `astrbot` | LLM 提供者：`astrbot`（内置）或 `openai_compatible` |
| llm_api_base | - | OpenAI 兼容 API 地址 |
| llm_api_key | - | OpenAI 兼容 API 密钥 |
| llm_model | `gpt-4o-mini` | 模型名称 |
| enable_auto_detect | `false` | 自动识别知乎链接 |
| output_image | `true` | 图片模式发送（需 wkhtmltopdf） |
| note_style | `professional` | 总结风格：`concise` / `detailed` / `professional` |
| max_note_length | `4000` | 总结最大字符数 |
| long_text_strategy | `truncate` | 长文本策略：`truncate` / `map_reduce` |
| long_text_threshold | `15000` | 长文本阈值（字符数） |
| processing_timeout | `120` | 处理超时（秒） |
| access_mode | `blacklist` | 群聊控制：`blacklist` / `whitelist` |
| group_list | - | 群号列表（逗号分隔） |

## 使用

### 命令

| 命令 | 别名 | 说明 |
|------|------|------|
| `/知乎总结 <链接>` | `zhsummary`、`总结知乎`、`知乎` | 生成知乎内容总结 |
| `/知乎帮助` | `zhihu_help` | 查看帮助信息和当前配置 |
| `/知乎识别开关` | `zhihu_detect_toggle` | 切换自动识别开关 |

### 支持的链接格式

```
回答：https://www.zhihu.com/question/123456/answer/789012
文章：https://zhuanlan.zhihu.com/p/123456
问题：https://www.zhihu.com/question/123456（自动取高赞回答）
```

### 使用示例

```
/知乎总结 https://www.zhihu.com/question/647634521/answer/3423456789
```

开启自动识别后，在群聊中直接发送知乎链接即可触发总结。

## 总结风格

| 风格 | 说明 |
|------|------|
| `concise` | 简洁模式 — 仅核心要点，5-8 个要点 |
| `detailed` | 详细模式 — 完整记录，保留示例和数据 |
| `professional` | 专业模式 — 结构化分析，深度总结（默认） |

## 项目结构

```
astrbot_plugin_zhihuSummary/
├── main.py                   # 插件主类
├── services/
│   ├── zhihu_api.py          # 知乎 API 客户端
│   └── summary_service.py    # 总结编排服务
├── gpt/
│   ├── prompt.py             # Prompt 模板
│   └── prompt_builder.py     # Prompt 组装
├── utils/
│   ├── url_parser.py         # URL 检测与解析
│   ├── html_to_text.py       # HTML → Markdown 转换
│   └── md_to_image.py        # Markdown → 图片渲染
├── _conf_schema.json         # 配置 Schema
└── metadata.yaml             # 插件元数据
```

## 常见问题

**Q: 提示 "Cookie 已失效" 怎么办？**

A: 知乎的 `z_c0` Cookie 会过期，重新从浏览器获取并更新配置即可。

**Q: 部分长文章总结不完整？**

A: 可以将 `long_text_strategy` 改为 `map_reduce`，会分段总结后再合并，更完整但耗时更长。也可以调高 `long_text_threshold`。

**Q: 图片渲染失败？**

A: 需要安装 [wkhtmltopdf](https://wkhtmltopdf.org/) 并确保其在系统 PATH 中。或将 `output_image` 关闭，使用纯文本模式。

## 鸣谢

本项目参考了 [storyAura/astrbot_plugin_biliVideo](https://github.com/storyAura/astrbot_plugin_biliVideo)（B站视频总结插件）的架构设计，复用了其图片渲染模块、LLM 调度模式和插件框架集成方案。感谢原作者的开源贡献。

## License

[MIT](LICENSE)
