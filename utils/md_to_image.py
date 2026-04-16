"""
Markdown → 图片渲染

将总结 Markdown 渲染为精美的暗色主题卡片图片。
使用 playwright 进行渲染。
"""

import asyncio
import logging
import os
import re
import threading
from typing import Optional

logger = logging.getLogger(__name__)

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
_LOGO_PATH = os.path.join(_ASSETS_DIR, "logo.ico")
_FONTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")

# 线程锁用于浏览器管理
_lock = threading.Lock()
_browser = None
_playwright = None


async def _get_browser():
    """获取或创建浏览器实例"""
    global _browser, _playwright

    with _lock:
        # 检查浏览器是否还连接
        if _browser is not None:
            try:
                # 测试连接是否有效
                if _browser.is_connected():
                    return _browser
            except Exception:
                logger.warning("浏览器连接已断开，重新创建")
                _browser = None

        # 创建新的浏览器实例
        if _browser is None:
            try:
                from playwright.async_api import async_playwright
                _playwright = await async_playwright().start()
                _browser = await _playwright.chromium.launch()
                logger.info("浏览器实例已创建")
            except Exception as e:
                logger.error(f"启动浏览器失败: {e}")
                raise

        return _browser


async def _render_note_image_async(markdown_text: str, output_path: str, width: int = 800) -> Optional[str]:
    """异步渲染图片"""
    browser = None
    page = None

    try:
        import markdown as md
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

        # 获取浏览器（带重试）
        max_retries = 3
        for attempt in range(max_retries):
            try:
                browser = await _get_browser()
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"获取浏览器失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                await asyncio.sleep(1)

        # 创建新页面
        page = await browser.new_page(
            viewport={'width': width, 'height': 2000},
            device_scale_factor=1
        )

        # 设置内容 - 使用更长的等待时间
        await page.set_content(full_html, wait_until='networkidle', timeout=30000)

        # 额外等待确保渲染完成
        await page.wait_for_timeout(300)

        # 获取精确的内容尺寸
        try:
            content_size = await page.evaluate('''() => {
                const body = document.body;
                const html = document.documentElement;

                // 获取实际内容宽度
                const contentWidth = Math.max(
                    body.scrollWidth,
                    body.offsetWidth,
                    html.scrollWidth,
                    html.offsetWidth
                );

                // 获取实际内容高度（footer底部）
                const footer = document.querySelector('.footer');
                let contentHeight;
                if (footer) {
                    contentHeight = footer.getBoundingClientRect().bottom + window.scrollY;
                } else {
                    contentHeight = Math.max(
                        body.scrollHeight,
                        body.offsetHeight,
                        html.scrollHeight,
                        html.offsetHeight
                    );
                }

                return { width: contentWidth, height: contentHeight };
            }''')
        except Exception as e:
            logger.warning(f"获取尺寸失败，使用默认值: {e}")
            content_size = {'width': width, 'height': 2000}

        # 转换为整数
        content_width = int(content_size['width'])
        content_height = int(content_size['height']) + 10

        # 设置 viewport
        await page.set_viewport_size({'width': content_width, 'height': content_height})

        # 截图（指定 clip 区域）
        await page.screenshot(
            path=output_path,
            clip={'x': 0, 'y': 0, 'width': content_width, 'height': content_height}
        )

        # 关闭页面
        await page.close()
        page = None

        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            render_secs = round(_time.time() - render_start, 1)
            logger.info(f"总结图片已生成: {output_path} ({file_size} bytes, {render_secs}s, 尺寸: {content_width}x{content_height})")
            return output_path
        else:
            logger.error("playwright 未生成文件")
            return None

    except Exception as e:
        logger.error(f"渲染总结图片失败: {e}", exc_info=True)

        # 清理页面
        if page is not None:
            try:
                await page.close()
            except Exception:
                pass

        return None


def _wrap_sections_in_cards(html: str) -> str:
    """将 HTML 按 h2 标题拆分为独立卡片"""
    parts = re.split(r'(<h2[^>]*>.*?</h2>)', html, flags=re.DOTALL | re.IGNORECASE)

    if len(parts) <= 1:
        return f'<div class="card">{html}</div>'

    result = []

    before_first_h2 = parts[0].strip()
    if before_first_h2:
        result.append(f'<div class="card-intro">{before_first_h2}</div>')

    i = 1
    while i < len(parts):
        h2_tag = parts[i] if i < len(parts) else ''
        content = parts[i + 1] if i + 1 < len(parts) else ''

        result.append(
            f'<div class="card">{h2_tag}{content}</div>'
        )
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
  background:#ffffff;
  color:#333333;
  width:800px;
  line-height:1.85;
  font-size:15px;
  padding: 0;
}}

/* ── 顶部 Header ── */
.header{{
  background:#f8f9fa;
  padding:30px 40px 24px;
  border-bottom:2px solid #e0e0e0;
  text-align:center;
}}
.header h1{{
  font-size:24px;font-weight:700;color:#333333;margin:0 auto;
  line-height:1.4;
  max-width:90%;
}}
.header-line{{
  width:60px;height:2px;margin:12px auto 0;
  background:#333333;
}}

/* ── 内容区 — 单列布局 ── */
.content{{
  padding:24px 40px 20px;
  display:block;
}}

/* ── 卡片通用 ── */
.card,.card-intro{{
  background:#ffffff;
  border-radius:8px;
  border:1px solid #e0e0e0;
  border-left:3px solid #333333;
  padding:18px 20px;
  margin-bottom:16px;
}}
.card-intro{{
  border-left-color:#666666;
  background:#f8f9fa;
}}

/* ── 标题 ── */
h1{{font-size:20px;font-weight:700;color:#333333;margin-bottom:12px}}
h2{{
  font-size:16px;font-weight:700;color:#333333;
  margin:-18px -20px 12px;
  padding:10px 20px 8px;
  background:#f8f9fa;
  border-bottom:1px solid #e0e0e0;
}}
h3{{font-size:15px;font-weight:700;color:#333333;margin-top:14px;margin-bottom:8px;
    padding-left:10px;border-left:3px solid #666666}}
h4,h5,h6{{font-size:14px;font-weight:600;color:#333333;margin-top:10px;margin-bottom:6px}}

/* ── 文本 ── */
p{{margin-bottom:10px;text-align:justify;word-break:break-word;font-size:14px;color:#333333}}
strong{{color:#000000;font-weight:700}}
em{{color:#555555;font-style:italic}}

/* ── 列表 ── */
ul,ol{{margin-bottom:10px;padding-left:24px}}
li{{margin-bottom:5px;line-height:1.7;font-size:14px;color:#333333}}
li::marker{{color:#666666;font-weight:700}}

/* ── 引用块 ── */
blockquote{{
  background:#f8f9fa;
  border-left:3px solid #666666;
  padding:12px 16px;
  margin:12px 0;
  color:#555555;
}}
blockquote p{{margin-bottom:4px}}

/* ── 代码 ── */
code{{background:#f0f0f0;color:#d32f2f;padding:2px 6px;border-radius:4px;
      font-size:13px;font-family:'Consolas','Monaco',monospace}}
pre{{background:#f5f5f5;color:#333333;padding:12px 16px;border-radius:6px;margin:10px 0;
     font-size:13px;line-height:1.5;border:1px solid #e0e0e0;overflow-x:auto}}
pre code{{background:transparent;color:inherit;padding:0}}

/* ── 分隔线 ── */
hr{{border:none;height:1px;
    background:#e0e0e0;
    margin:16px 0}}

/* ── 表格 ── */
table{{width:100%;border-collapse:collapse;margin:10px 0}}
th{{background:#f8f9fa;color:#333333;font-weight:700;padding:8px 12px;
    text-align:left;border-bottom:2px solid #e0e0e0;font-size:14px}}
td{{padding:6px 12px;border-bottom:1px solid #e0e0e0;font-size:14px;color:#333333}}
tr:nth-child(even) td{{background:#fafafa}}

/* ── Footer ── */
.footer{{
  padding:12px 40px;
  border-top:1px solid #e0e0e0;
  display:flex;align-items:center;justify-content:space-between;
  background:#f8f9fa;
}}
.footer .flogo{{width:20px;height:20px;object-fit:cover;opacity:0.6}}
.ftxt{{font-size:11px;color:#888888;letter-spacing:0.5px;font-family:'Consolas',monospace}}
.ftxt .br{{color:#333333;font-weight:600}}
.ftime{{font-size:11px;color:#888888;letter-spacing:0.5px;font-family:'Consolas',monospace}}
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


def render_note_image(
    markdown_text: str,
    output_path: str,
    width: int = 800,
) -> Optional[str]:
    """
    将 Markdown 渲染为 PNG 图片。

    :param markdown_text: Markdown 文本
    :param output_path: 输出图片路径
    :param width: 图片宽度
    :return: 成功返回图片路径，失败返回 None
    """
    try:
        # 在新线程中运行异步代码，避免事件循环冲突
        import concurrent.futures
        import threading

        result = [None]
        exception = [None]

        def run_in_thread():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result[0] = loop.run_until_complete(
                        _render_note_image_async(markdown_text, output_path, width)
                    )
                finally:
                    loop.close()
            except Exception as e:
                exception[0] = e

        thread = threading.Thread(target=run_in_thread)
        thread.start()
        thread.join(timeout=60)  # 60秒超时

        if exception[0]:
            raise exception[0]

        return result[0]

    except Exception as e:
        logger.error(f"渲染总结图片失败: {e}", exc_info=True)
        return None
