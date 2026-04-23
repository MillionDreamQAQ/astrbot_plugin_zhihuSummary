"""
知乎总结插件完整功能测试脚本

测试完整流程: URL解析 → 内容获取 → Markdown转换 → LLM总结 → 图片渲染

用法:
  python test_fetch.py <知乎链接>

配置参数在代码顶部的 CONFIG 字典中修改
"""

import asyncio
import sys
import json
import os
import time
from typing import Optional

# 将项目根目录加入 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.url_parser import detect_zhihu_url
from services.zhihu_api import fetch_content
from utils.html_to_text import html_to_markdown, estimate_char_count
from utils.md_to_image import render_note_image


# ==================== 配置区域 ====================
CONFIG = {
    # 知乎 Cookie (必需)
    "zhihu_cookie": "Hm_lvt_98beee57fd2ef70ccdd5ca52b9740c49=1745572087,1746494955,1746579932,1747190982; _xsrf=eL1JiCrpIAD8gv5Kzoy2HI7Z3abaLt34; _zap=b5c90ece-3662-470f-904a-12715c7d2738; d_c0=y1QUlh765BuPTu3euZKctAHP79210fwDX60=|1772002856; q_c1=e8a6c44eff424abeb5fb26758a0a8367|1772003014000|1772003014000; z_c0=2|1:0|10:1775036282|4:z_c0|92:Mi4xU1B1U0F3QUFBQURMVkJTV0h2cmtHeVlBQUFCZ0FsVk5raUczYWdBN3UybDJEZ1FXLXUzaUdVeTZvMzNBOFMzZjR3|0df074291fe3c440487263b720a162758d40bfcfe22035bd7bf6072754b9ae02; __zse_ck=005_bSwuJ5xiNO2H2Yd7LxNigbkX1upNysKPZ46f0e==/kzpX4FwlhaKo33s5NvoLwOgQsRDk8obw/p40li8K26KMBGywY2=Dtzyz7ER1Qg0Hhv0VI0LIoWlwmFlRxeibqT=-c+6U1hUhmSnZ78G4KJRG5w2CIZSfNX4X+v62PqFJYuejvGPeQTD6iJFUOxorjEWkXwesyN23xp6+PkOn4h1eV1Ey0gzoV6S8hvOjVO2UkqmCPPTgEbsGi/6/muC6pRR/; BEC=f23896b358f7577445de7dd8602ca4bf; SESSIONID=9j9v4Mn9UTVEgnCDhnSLkDDVl3HLaec43hlLbjIIlV6",

    # LLM 配置
    "llm_provider": "openai_compatible",  # astrbot 或 openai_compatible
    "llm_api_base": "https://api.xiaomimimo.com/v1",
    "llm_api_key": "sk-ccxt0oyzk8pkmgsk629i9zglybo83ssjcofkz9xtpgmnetjj",
    "llm_model": "mimo-v2-pro",

    # 总结配置
    "note_style": "professional",  # concise, detailed, professional
    "max_note_length": 4000,
    "long_text_strategy": "truncate",  # truncate, map_reduce
    "long_text_threshold": 15000,

    # 图片配置
    "output_image": True,  # 是否生成图片
    "image_width": 1400,

    # 测试用的模拟总结 (当没有 LLM API 时使用)
    "use_mock_summary": False,
    "mock_summary": """# 测试标题 —— 测试作者

## 核心观点

这是一个测试总结，用于验证图片渲染功能是否正常工作。

## 主要内容

- 测试要点1: 内容获取功能
- 测试要点2: Markdown转换功能
- 测试要点3: 图片渲染功能

## 结论

weasyprint 渲染效果良好。
""",
}
# ====================================================


def load_config_from_env():
    """从环境变量加载配置"""
    env_vars = [
        "ZHIHU_COOKIE", "LLM_API_BASE", "LLM_API_KEY", "LLM_MODEL"
    ]
    for var in env_vars:
        key = var.lower()
        if os.getenv(var):
            if key == "zhihu_cookie":
                CONFIG["zhihu_cookie"] = os.getenv(var)
            elif key == "llm_api_base":
                CONFIG["llm_api_base"] = os.getenv(var)
            elif key == "llm_api_key":
                CONFIG["llm_api_key"] = os.getenv(var)
            elif key == "llm_model":
                CONFIG["llm_model"] = os.getenv(var)


async def call_llm_openai(prompt: str, config: dict) -> str:
    """调用 OpenAI 兼容 API"""
    import aiohttp

    url = f"{config['llm_api_base'].rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['llm_api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config["llm_model"],
        "messages": [{"role": "user", "content": prompt}],
    }

    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise Exception(f"API 返回 HTTP {resp.status}: {body[:500]}")
            data = await resp.json()
            return data["choices"][0]["message"]["content"]


def build_prompt(content_type: str, title: str, author: str, markdown_text: str, style: str) -> str:
    """构建 LLM 提示词"""
    style_prompts = {
        "concise": "简洁精炼，突出核心观点，控制在200字以内",
        "detailed": "详细全面，保留重要细节和例子",
        "professional": "专业结构化，使用清晰的层级和要点",
    }

    style_desc = style_prompts.get(style, style_prompts["professional"])

    if content_type == "answer":
        prompt = f"""你是一个专业的内容总结助手。请阅读以下知乎回答，生成结构化总结。

**标题**: {title}
**作者**: {author}
**要求**: {style_desc}

**回答内容**:
{markdown_text}

请按以下格式输出总结（使用 Markdown 格式）:

# {title} —— {author}

## 核心观点
[一句话概括回答的核心观点]

## 主要内容
[列出回答的主要论点和内容]

## 结论
[总结回答的结论或建议]

## 关键亮点
[列出回答中的亮点或独特观点]"""
    else:  # article
        prompt = f"""你是一个专业的内容总结助手。请阅读以下知乎文章，生成结构化总结。

**标题**: {title}
**作者**: {author}
**要求**: {style_desc}

**文章内容**:
{markdown_text}

请按以下格式输出总结（使用 Markdown 格式）:

# {title} —— {author}

## 核心观点
[一句话概括文章的核心观点]

## 主要内容
[列出文章的主要章节和内容]

## 结论
[总结文章的结论或建议]

## 关键亮点
[列出文章中的亮点或独特观点]"""

    return prompt


async def generate_summary(content_type: str, title: str, author: str,
                          markdown_text: str, config: dict) -> Optional[str]:
    """生成总结"""
    if config["use_mock_summary"]:
        print("\n📝 使用模拟总结...")
        return config["mock_summary"]

    if config["llm_provider"] == "astrbot":
        print("\n⚠️ AstrBot LLM 需要在 AstrBot 环境中运行，测试脚本不支持")
        print("💡 请设置 llm_provider='openai_compatible' 并配置 API")
        return None

    print(f"\n📝 正在调用 LLM 生成总结 (模型: {config['llm_model']})...")

    prompt = build_prompt(content_type, title, author, markdown_text, config["note_style"])
    print(f"   Prompt 长度: {len(prompt)} 字符")

    try:
        summary = await call_llm_openai(prompt, config)
        print(f"   总结长度: {len(summary)} 字符")
        return summary
    except Exception as e:
        print(f"❌ LLM 调用失败: {e}")
        return None


async def main():
    load_config_from_env()

    if len(sys.argv) < 2:
        print(__doc__)
        print("\n当前配置:")
        print(json.dumps({k: v if k != 'zhihu_cookie' else ('*' * 10 if v else '')
                         for k, v in CONFIG.items()}, ensure_ascii=False, indent=2))
        sys.exit(1)

    url = sys.argv[1].strip()

    # 1. 解析 URL
    print("=" * 60)
    print("🔗 步骤 1: URL 解析")
    print("=" * 60)
    print(f"输入链接: {url}")

    result = detect_zhihu_url(url)
    if not result:
        print("❌ 无法识别该链接为知乎链接")
        sys.exit(1)

    content_type, content_id = result
    print(f"✅ 识别成功: 类型={content_type}, ID={content_id}")

    # 2. 获取内容
    print(f"\n{'=' * 60}")
    print("📥 步骤 2: 获取知乎内容")
    print("=" * 60)

    cookie = CONFIG["zhihu_cookie"]
    print(f"Cookie: {'已配置' if cookie else '❌ 未配置'}")

    if not cookie:
        print("⚠️ 警告: 未配置 Cookie，部分内容可能无法获取")
        print("💡 请在 CONFIG 中设置 zhihu_cookie 或设置环境变量 ZHIHU_COOKIE")

    data = await fetch_content(content_type, content_id, cookie)

    if not data:
        print("❌ 获取失败")
        if not cookie:
            print("💡 提示: 未提供 Cookie 可能导致获取失败")
        sys.exit(1)

    print(f"✅ 获取成功:")
    print(f"   标题: {data.get('title', 'N/A')}")
    print(f"   作者: {data.get('author', 'N/A')}")
    print(f"   内容长度: {len(data.get('content_html', ''))} 字符")

    # 3. HTML → Markdown 转换
    print(f"\n{'=' * 60}")
    print("📝 步骤 3: HTML → Markdown 转换")
    print("=" * 60)

    content_html = data.get("content_html", "")
    if not content_html:
        print("⚠️ content_html 为空")
        sys.exit(1)

    md_text = html_to_markdown(content_html)
    char_count = estimate_char_count(md_text)
    print(f"✅ 转换成功:")
    print(f"   Markdown 长度: {len(md_text)} 字符")
    print(f"   估算字符数: {char_count}")

    # 截断过长文本
    if len(md_text) > CONFIG["long_text_threshold"] and CONFIG["long_text_strategy"] == "truncate":
        md_text = md_text[:CONFIG["long_text_threshold"]]
        print(f"⚠️ 文本过长，已截断到 {CONFIG['long_text_threshold']} 字符")

    # 4. LLM 生成总结
    print(f"\n{'=' * 60}")
    print("🤖 步骤 4: LLM 生成总结")
    print("=" * 60)

    summary = await generate_summary(
        content_type,
        data.get('title', 'N/A'),
        data.get('author', 'N/A'),
        md_text,
        CONFIG
    )

    if not summary:
        print("❌ 总结生成失败")
        print("💡 提示: 可以设置 use_mock_summary=True 测试图片渲染功能")
        sys.exit(1)

    print(f"\n📄 总结内容预览 (前 500 字符):")
    print("-" * 60)
    print(summary[:500])
    if len(summary) > 500:
        print(f"... (共 {len(summary)} 字符)")
    print("-" * 60)

    # 5. 图片渲染
    if CONFIG["output_image"]:
        print(f"\n{'=' * 60}")
        print("🎨 步骤 5: 图片渲染")
        print("=" * 60)

        output_dir = os.path.join(os.path.dirname(__file__), "test_output")
        os.makedirs(output_dir, exist_ok=True)

        timestamp = int(time.time() * 1000)
        output_path = os.path.join(output_dir, f"summary_{timestamp}.png")

        print(f"正在渲染图片...")
        result_path = render_note_image(summary, output_path, CONFIG["image_width"])

        if result_path:
            file_size = os.path.getsize(result_path)
            print(f"✅ 图片生成成功!")
            print(f"   路径: {result_path}")
            print(f"   大小: {file_size} bytes")
        else:
            print(f"❌ 图片生成失败")
            print("💡 请检查 weasyprint 是否正确安装")
            sys.exit(1)

    # 6. 保存总结文本
    output_dir = os.path.join(os.path.dirname(__file__), "test_output")
    os.makedirs(output_dir, exist_ok=True)

    timestamp = int(time.time() * 1000)
    summary_file = os.path.join(output_dir, f"summary_{timestamp}.md")
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write(summary)

    print(f"\n📁 总结文本已保存到: {summary_file}")

    print(f"\n{'=' * 60}")
    print("✅ 测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
