"""
知乎内容获取测试脚本

用法:
  python test_fetch.py <知乎链接> [Cookie字符串]

Cookie 获取方法:
  1. 在浏览器登录 zhihu.com
  2. F12 → Network → 刷新页面 → 点击任意 zhihu.com 请求
  3. Request Headers 中找到 Cookie，复制完整值

示例:
  python test_fetch.py https://www.zhihu.com/question/647634521/answer/3423456789
  python test_fetch.py https://zhuanlan.zhihu.com/p/123456 "your_cookie"
"""

import asyncio
import sys
import json
import os

# 将项目根目录加入 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.url_parser import detect_zhihu_url
from services.zhihu_api import fetch_content
from utils.html_to_text import html_to_markdown, html_to_plain_text, estimate_char_count


async def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    url = sys.argv[1].strip()
    cookie = sys.argv[2].strip() if len(sys.argv) > 2 else ""

    # 1. 解析 URL
    print("=" * 60)
    print(f"输入链接: {url}")
    print(f"Cookie:   {'已提供' if cookie else '未提供（部分内容可能无法获取）'}")
    print("=" * 60)

    result = detect_zhihu_url(url)
    if not result:
        print("❌ 无法识别该链接为知乎链接")
        sys.exit(1)

    content_type, content_id = result
    print(f"\n✅ 识别成功:")
    print(f"   类型: {content_type}")
    print(f"   ID:   {content_id}")

    # 2. 获取内容
    print(f"\n⏳ 正在获取内容...")
    data = await fetch_content(content_type, content_id, cookie)

    if not data:
        print("❌ 获取失败")
        if not cookie:
            print("💡 提示: 未提供 Cookie，请尝试:")
            print("   python test_fetch.py <链接> <cookie值>")
        sys.exit(1)

    # 3. 输出原始数据
    print(f"\n{'=' * 60}")
    print("📋 原始数据:")
    print(f"{'=' * 60}")
    display = {k: v for k, v in data.items() if k != "content_html"}
    print(json.dumps(display, ensure_ascii=False, indent=2))

    # 4. HTML → Markdown 转换
    content_html = data.get("content_html", "")
    if content_html:
        md_text = html_to_markdown(content_html)
        plain_text = html_to_plain_text(content_html)

        print(f"\n{'=' * 60}")
        print(f"📝 Markdown 内容 ({estimate_char_count(md_text)} 字符):")
        print(f"{'=' * 60}")
        print(md_text[:3000])
        if len(md_text) > 3000:
            print(f"\n... (共 {len(md_text)} 字符，仅显示前 3000)")

        print(f"\n{'=' * 60}")
        print(f"📊 统计:")
        print(f"   HTML 长度:    {len(content_html)} 字符")
        print(f"   Markdown 长度: {len(md_text)} 字符")
        print(f"   纯文本长度:   {len(plain_text)} 字符")
        print(f"   估算字符数:   {estimate_char_count(md_text)}")
    else:
        print("\n⚠️ content_html 为空")

    # 5. 保存完整结果到文件
    output_dir = os.path.join(os.path.dirname(__file__), "test_output")
    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, f"{content_type}_{content_id}.json")
    with open(output_file, "w", encoding="utf-8") as f:
        save_data = dict(data)
        if content_html:
            save_data["content_markdown"] = html_to_markdown(content_html)
        json.dump(save_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 完整结果已保存到: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
