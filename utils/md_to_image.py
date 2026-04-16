"""
Markdown → 图片渲染

将总结 Markdown 渲染为精美的暗色主题卡片图片。
使用 playwright 进行渲染。
"""

import asyncio
import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
_LOGO_PATH = os.path.join(_ASSETS_DIR, "logo.ico")
_FONTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")

# Playwright 浏览器实例缓存
_browser = None
_lock = None


def _get_lock():
    """获取线程锁"""
    global _lock
    if _lock is None:
        import threading
        _lock = threading.Lock()
    return _lock


# 卡片左边框的颜色循环 (蓝、绿、紫、橙、青、粉)
CARD_COLORS = [
    ('#0066FF', 'rgba(0,102,255,.10)'),     # 知乎蓝
    ('#34d399', 'rgba(52,211,153,.10)'),
    ('#a78bfa', 'rgba(167,139,250,.10)'),
    ('#fb923c', 'rgba(251,146,60,.10)'),
    ('#22d3ee', 'rgba(34,211,238,.10)'),
    ('#f472b6', 'rgba(244,114,182,.10)'),
]


async def _get_browser():
    """获取或创建浏览器实例（线程安全）"""
    global _browser
    with _get_lock():
        if _browser is None:
            try:
                from playwright.async_api import async_playwright
                playwright = await async_playwright().start()
                _browser = await playwright.chromium.launch()
            except Exception as e:
                logger.error(f"启动浏览器失败: {e}")
                raise
    return _browser


def _wrap_sections_in_cards(html: str) -> str:
    """将 HTML 按 h2 标题拆分为独立卡片，每个卡片使用不同的左边框颜色"""
    parts = re.split(r'(<h2[^>]*>.*?</h2>)', html, flags=re.DOTALL | re.IGNORECASE)

    if len(parts) <= 1:
        return f'<div class="card card-0">{html}</div>'

    result = []
    card_idx = 0

    before_first_h2 = parts[0].strip()
    if before_first_h2:
        result.append(f'<div class="card-intro">{before_first_h2}</div>')

    i = 1
    while i < len(parts):
        h2_tag = parts[i] if i < len(parts) else ''
        content = parts[i + 1] if i + 1 < len(parts) else ''
        color_idx = card_idx % len(CARD_COLORS)
        border_color, bg_color = CARD_COLORS[color_idx]

        result.append(
            f'<div class="card card-{color_idx}" '
            f'style="border-left-color:{border_color};background:{bg_color}">'
            f'{h2_tag}{content}</div>'
        )
        card_idx += 1
        i += 2

    return '\n'.join(result)


def _build_full_html(body_html: str, logo_data_uri: Optional[str], title_text: str = '', footer_time: str = '') -> str:
    """构建完整的 HTML"""

    # Logo HTML
    logo_html = ""
    if logo_data_uri:
        logo_html = f'<img class="flogo" src="{logo_data_uri}" alt="">'

    return f'''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{
  font-family:'Microsoft YaHei','PingFang SC','Noto Sans SC','Hiragino Sans GB',sans-serif;
  background:#1a1b2e;
  color:#c9cedc;
  width:1400px;
  line-height:1.85;
  font-size:15px;
  padding: 0;
}}

/* ── 顶部 Header ── */
.header{{
  background:linear-gradient(135deg,#1a1f3a 0%,#1e2444 30%,#1a2744 70%,#1a1f3a 100%);
  padding:40px 56px 32px;
  border-bottom:2px solid rgba(0,102,255,.25);
  position:relative;
  overflow:hidden;
  text-align:center;
}}
.header::before{{
  content:'';position:absolute;top:0;left:0;right:0;bottom:0;
  background:radial-gradient(ellipse at 70% 0%,rgba(0,102,255,.12) 0%,transparent 55%),
             radial-gradient(ellipse at 30% 100%,rgba(96,165,250,.10) 0%,transparent 55%);
  pointer-events:none;
}}
.header h1{{
  position:relative;z-index:1;
  font-size:28px;font-weight:800;color:#f1f5f9;margin:0 auto;
  line-height:1.4;letter-spacing:.5px;
  background:linear-gradient(90deg,#e2e8f0 0%,#60a5fa 50%,#c4b5fd 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  background-clip:text;
  max-width:90%;
}}
.header-line{{
  position:relative;z-index:1;
  width:80px;height:3px;margin:14px auto 0;
  background:linear-gradient(90deg,#0066FF,#60a5fa);
  border-radius:2px;
}}

/* ── 内容区 — 双栏网格 ── */
.content{{
  padding:28px 40px 20px;
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:20px;
  align-items:start;
}}

/* ── 卡片通用 ── */
.card,.card-intro{{
  background:rgba(30,33,64,.65);
  border-radius:12px;
  border:1px solid rgba(148,163,184,.08);
  border-left:4px solid #0066FF;
  padding:20px 24px;
  box-shadow:0 2px 8px rgba(0,0,0,.2);
}}
.card-intro{{
  grid-column:1 / -1;
  border-left-color:#a5f3c4;
  background:rgba(52,211,153,.06);
}}
.card-full{{
  grid-column:1 / -1;
}}

/* ── 标题 ── */
h1{{font-size:22px;font-weight:700;color:#e2e8f0;margin-bottom:12px}}
h2{{
  font-size:16px;font-weight:700;color:#e2e8f0;
  margin:-20px -24px 14px;
  padding:12px 24px 10px;
  border-radius:12px 12px 0 0;
  background:rgba(0,0,0,.18);
  border-bottom:1px solid rgba(148,163,184,.08);
  display:flex;align-items:center;gap:8px;
  letter-spacing:.3px;
}}
h2::before{{
  content:'';display:inline-block;width:8px;height:8px;border-radius:50%;
  background:currentColor;opacity:.6;flex-shrink:0;
}}
h3{{font-size:15px;font-weight:700;color:#93c5fd;margin-top:16px;margin-bottom:8px;
    padding-left:12px;border-left:3px solid rgba(0,102,255,.4)}}
h4,h5,h6{{font-size:14px;font-weight:600;color:#c4b5fd;margin-top:12px;margin-bottom:6px}}

/* ── 文本 ── */
p{{margin-bottom:10px;text-align:justify;word-break:break-word;font-size:14px}}
strong{{color:#f9a8d4;font-weight:700}}
em{{color:#67e8f9;font-style:italic}}

/* ── 列表 ── */
ul,ol{{margin-bottom:10px;padding-left:20px}}
li{{margin-bottom:5px;line-height:1.7;padding-left:4px;font-size:14px}}
li::marker{{color:#0066FF;font-weight:700}}

/* ── 引用块 ── */
blockquote{{
  background:rgba(0,102,255,.06);
  border-left:3px solid #0066FF;
  border-radius:0 10px 10px 0;
  padding:12px 18px;
  margin:12px 0;
  color:#a5b4fc;
  box-shadow:0 2px 6px rgba(0,102,255,.06);
}}
blockquote p{{margin-bottom:4px}}

/* ── 代码 ── */
code{{background:rgba(248,113,113,.1);color:#fca5a5;padding:2px 6px;border-radius:6px;
      font-size:13px;font-family:'Consolas','Monaco',monospace}}
pre{{background:#12132a;color:#e2e8f0;padding:12px 16px;border-radius:10px;margin:10px 0;
     font-size:13px;line-height:1.5;border:1px solid rgba(148,163,184,.1);
     box-shadow:inset 0 1px 4px rgba(0,0,0,.3);overflow-x:auto}}
pre code{{background:transparent;color:inherit;padding:0}}

/* ── 分隔线 ── */
hr{{border:none;height:1px;
    background:linear-gradient(to right,transparent,rgba(148,163,184,.2),transparent);
    margin:16px 0}}

/* ── 表格 ── */
table{{width:100%;border-collapse:collapse;margin:10px 0;border-radius:8px;overflow:hidden}}
th{{background:rgba(0,102,255,.12);color:#93c5fd;font-weight:700;padding:8px 12px;
    text-align:left;border-bottom:2px solid rgba(0,102,255,.2);font-size:14px}}
td{{padding:6px 12px;border-bottom:1px solid rgba(148,163,184,.08);font-size:14px}}
tr:nth-child(even) td{{background:rgba(148,163,184,.03)}}

/* ── Footer ── */
.footer{{
  padding:14px 40px;
  border-top:1px solid rgba(148,163,184,.1);
  display:flex;align-items:center;justify-content:space-between;
  background:rgba(0,0,0,.1);
}}
.footer .flogo{{width:22px;height:22px;border-radius:6px;object-fit:cover;opacity:.7}}
.footer .flogo-e{{font-size:16px;opacity:.7}}
.ftxt{{font-size:11px;color:#64748b;letter-spacing:.8px;font-family:'Consolas',monospace}}
.ftxt .br{{color:#94a3b8;font-weight:700}}
.ftime{{font-size:11px;color:#4a5568;letter-spacing:.5px;font-family:'Consolas',monospace}}
</style></head>
<body>
<div class="header">
  <h1>{title_text}</h1>
  <div class="header-line"></div>
</div>
<div class="content">
{body_html}
</div>
<div class="footer">
  <div class="ftxt">Powered by <span class="br">zhihuSummary+</span> · AI 知乎总结助手</div>
  <div class="ftime">{footer_time}</div>
</div>
</body></html>'''


def _extract_title(html: str) -> tuple:
    """提取 h1 标题文本，并从 body 中移除。格式化为 '标题 —— 作者'"""
    m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL | re.IGNORECASE)
    if m:
        title_text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        html = html[:m.start()] + html[m.end():]
        # 移除紧跟 h1 后面的重复标题段落
        clean_title = re.sub(r'[📑📝🎬🎥\s]', '', title_text)
        if clean_title:
            dup_pattern = r'<p[^>]*>[^<]*' + re.escape(clean_title[:20]) + r'[^<]*</p>'
            html = re.sub(dup_pattern, '', html, count=1)
        # 将 " - 作者" 格式化为 " —— 作者"
        if ' - ' in title_text:
            parts = title_text.rsplit(' - ', 1)
            title_text = f"{parts[0]} —— {parts[1]}"
        return title_text, html
    return 'AI 知乎总结', html


def _get_logo_data_uri() -> Optional[str]:
    """获取 logo 的 data URI"""
    if os.path.exists(_LOGO_PATH):
        try:
            import base64
            with open(_LOGO_PATH, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode()
            return f"data:image/png;base64,{b64}"
        except Exception:
            pass
    return None


async def _render_note_image_async(markdown_text: str, output_path: str, width: int = 1400) -> Optional[str]:
    """异步渲染图片"""
    try:
        import markdown as md
    except ImportError as e:
        logger.error(f"缺少 markdown 依赖: {e}")
        return None

    try:
        import time as _time
        from datetime import datetime
        render_start = _time.time()

        # Markdown → HTML
        html_body = md.markdown(
            markdown_text,
            extensions=['tables', 'fenced_code', 'nl2br'],
        )

        # 提取标题
        title_text, html_body = _extract_title(html_body)

        # 将 h2 章节包裹为卡片
        html_body = _wrap_sections_in_cards(html_body)

        # 获取 logo
        logo_uri = _get_logo_data_uri()

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 构建完整 HTML
        full_html = _build_full_html(html_body, logo_uri, title_text, now_str)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # 使用 playwright 渲染
        browser = await _get_browser()
        page = await browser.new_page(viewport={'width': width, 'height': 1080})

        # 设置内容
        await page.set_content(full_html, wait_until='networkidle')

        # 等待页面完全渲染
        await page.wait_for_timeout(500)

        # 获取页面实际高度
        body_height = await page.evaluate('() => document.body.scrollHeight')

        # 调整 viewport 高度
        await page.set_viewport_size({'width': width, 'height': body_height})

        # 截图
        await page.screenshot(path=output_path, full_page=False)

        await page.close()

        if os.path.exists(output_path):
            render_secs = round(_time.time() - render_start, 1)
            logger.info(f"总结图片已生成: {output_path} ({os.path.getsize(output_path)} bytes, 渲染{render_secs}s)")
            return output_path
        else:
            logger.error("playwright 未生成文件")
            return None

    except Exception as e:
        logger.error(f"渲染总结图片失败: {e}", exc_info=True)
        return None


def render_note_image(
    markdown_text: str,
    output_path: str,
    width: int = 1400,
) -> Optional[str]:
    """
    将 Markdown 渲染为 PNG 图片。

    :param markdown_text: Markdown 文本
    :param output_path: 输出图片路径
    :param width: 图片宽度
    :return: 成功返回图片路径，失败返回 None
    """
    try:
        # 检查是否有正在运行的事件循环
        try:
            loop = asyncio.get_running_loop()
            # 如果有正在运行的循环，创建任务
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    _render_note_image_async(markdown_text, output_path, width)
                )
                return future.result()
        except RuntimeError:
            # 没有运行中的循环，直接运行
            return asyncio.run(_render_note_image_async(markdown_text, output_path, width))
    except Exception as e:
        logger.error(f"渲染总结图片失败: {e}", exc_info=True)
        return None
