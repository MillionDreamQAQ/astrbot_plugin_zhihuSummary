"""
知乎 HTML → Markdown 转换工具

将知乎 API 返回的 HTML 内容转换为干净的 Markdown 文本。
使用 stdlib html.parser，不引入额外依赖。
"""

import re
from html.parser import HTMLParser

class ZhihuHTMLToMarkdown(HTMLParser):
    """知乎 HTML 转 Markdown 解析器"""

    def __init__(self):
        super().__init__()
        self._output: list[str] = []
        self._tag_stack: list[str] = []
        self._list_depth = 0
        self._list_counter: list[int] = []
        self._in_pre = False
        self._in_code = False
        self._in_blockquote = False
        self._in_link = False
        self._link_href = ""
        self._link_text = ""
        self._in_heading = False
        self._heading_level = 0
        self._in_math = False
        self._skip_tag = False

    def reset(self):
        super().reset()
        self._output = []
        self._tag_stack = []
        self._list_depth = 0
        self._list_counter = []
        self._in_pre = False
        self._in_code = False
        self._in_blockquote = False
        self._in_link = False
        self._link_href = ""
        self._link_text = ""
        self._in_heading = False
        self._heading_level = 0
        self._in_math = False
        self._skip_tag = False

    def handle_starttag(self, tag: str, attrs: list):
        attr_dict = dict(attrs)
        classes = attr_dict.get("class", "").split()

        if tag in ("script", "style", "noscript", "svg"):
            self._skip_tag = True
            return

        self._tag_stack.append(tag)

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._in_heading = True
            self._heading_level = int(tag[1])
            self._emit("\n\n" + "#" * self._heading_level + " ")

        elif tag == "p":
            self._emit("\n\n")

        elif tag == "br":
            self._emit("\n")

        elif tag == "hr":
            self._emit("\n\n---\n\n")

        elif tag in ("strong", "b"):
            self._emit("**")

        elif tag in ("em", "i"):
            self._emit("*")

        elif tag == "a":
            self._in_link = True
            self._link_href = attr_dict.get("href", "")
            self._link_text = ""

        elif tag == "img":
            # 知乎 LaTeX 公式: <img class="Formula" alt="...">
            if "Formula" in classes or "ztext-gif" in classes:
                alt = attr_dict.get("alt", "")
                src = attr_dict.get("src", "")
                if alt and ("\\" in alt or "$" in alt or "_" in alt):
                    # 可能是 LaTeX
                    self._emit(f" ${alt}$ ")
                # 增加 src 的有效性校验
                elif src and not src.strip().startswith(("<svg", "data:image/svg")):
                    self._emit(f"!{alt} [<sup>2</sup>]({src})")
            else:
                alt = attr_dict.get("alt", "")
                src = attr_dict.get("data-original") or attr_dict.get("src", "")
                if src:
                    self._emit(f"![{alt}]({src})")

        elif tag == "figure":
            self._emit("\n\n")

        elif tag == "figcaption":
            self._emit("\n> ")

        elif tag == "ul":
            self._list_depth += 1
            self._list_counter.append(0)
            self._emit("\n")

        elif tag == "ol":
            self._list_depth += 1
            self._list_counter.append(1)
            self._emit("\n")

        elif tag == "li":
            indent = "  " * (self._list_depth - 1)
            if self._list_counter:
                # 检查父标签是否为 ol
                parent_ol = len(self._tag_stack) >= 2 and self._tag_stack[-2] == "ol"
                if parent_ol and self._list_counter:
                    self._list_counter[-1] += 1
                    self._emit(f"\n{indent}{self._list_counter[-1]}. ")
                else:
                    self._emit(f"\n{indent}- ")

        elif tag == "blockquote":
            self._in_blockquote = True
            self._emit("\n\n> ")

        elif tag == "pre":
            self._in_pre = True
            self._emit("\n\n```\n")

        elif tag == "code":
            if not self._in_pre:
                self._in_code = True
                self._emit("`")

        elif tag == "span":
            # 知乎数学公式
            if "ztext-math" in classes:
                self._in_math = True

        elif tag in ("sup",):
            self._emit("^")

        elif tag in ("sub",):
            self._emit("~")

        elif tag == "table":
            self._emit("\n\n")

        elif tag in ("thead", "tbody"):
            pass

        elif tag == "tr":
            self._emit("\n| ")

        elif tag in ("th", "td"):
            pass

    def handle_endtag(self, tag: str):
        if self._skip_tag:
            if tag in ("script", "style", "noscript", "svg"):
                self._skip_tag = False
            return

        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._in_heading = False

        elif tag == "p":
            self._emit("\n")

        elif tag in ("strong", "b"):
            self._emit("**")

        elif tag in ("em", "i"):
            self._emit("*")

        elif tag == "a":
            self._in_link = False
            text = self._link_text.strip()
            href = self._link_href
            if href and text:
                # 内部链接简化
                if "zhihu.com" in href:
                    self._emit(f"[{text}]({href})")
                else:
                    self._emit(f"[{text}]({href})")
            elif text:
                self._emit(text)

        elif tag == "figure":
            self._emit("\n\n")

        elif tag == "figcaption":
            self._emit("\n")

        elif tag == "ul":
            self._list_depth = max(0, self._list_depth - 1)
            if self._list_counter:
                self._list_counter.pop()
            self._emit("\n")

        elif tag == "ol":
            self._list_depth = max(0, self._list_depth - 1)
            if self._list_counter:
                self._list_counter.pop()
            self._emit("\n")

        elif tag == "li":
            pass

        elif tag == "blockquote":
            self._in_blockquote = False
            self._emit("\n\n")

        elif tag == "pre":
            self._in_pre = False
            self._emit("\n```\n")

        elif tag == "code":
            if self._in_code:
                self._in_code = False
                self._emit("`")

        elif tag == "span":
            self._in_math = False

    def handle_data(self, data: str):
        if self._skip_tag:
            return

        if self._in_math:
            # LaTeX 公式内容
            self._emit(f"${data.strip()}$")
            return

        if self._in_link:
            self._link_text += data
            return

        if self._in_blockquote:
            # 引用块内换行需要加 > 前缀
            data = data.replace("\n", "\n> ")

        self._emit(data)

    def handle_entityref(self, name: str):
        entities = {
            "amp": "&",
            "lt": "<",
            "gt": ">",
            "quot": '"',
            "apos": "'",
            "nbsp": " ",
            "mdash": "—",
            "ndash": "–",
            "hellip": "…",
            "laquo": "«",
            "raquo": "»",
        }
        self._emit(entities.get(name, f"&{name};"))

    def handle_charref(self, name: str):
        try:
            if name.startswith("x") or name.startswith("X"):
                char = chr(int(name[1:], 16))
            else:
                char = chr(int(name))
            self._emit(char)
        except (ValueError, OverflowError):
            self._emit(f"&#{name};")

    def _emit(self, text: str):
        self._output.append(text)

    def get_markdown(self) -> str:
        """获取转换后的 Markdown 文本"""
        result = "".join(self._output)
        # 清理多余空行
        result = re.sub(r"\n{3,}", "\n\n", result)
        # 清理行首尾空白
        lines = result.split("\n")
        lines = [line.rstrip() for line in lines]
        result = "\n".join(lines)
        return result.strip()


def html_to_markdown(html_content: str) -> str:
    """
    将知乎 HTML 内容转换为 Markdown。

    :param html_content: 知乎 API 返回的 HTML 字符串
    :return: 干净的 Markdown 文本
    """
    if not html_content:
        return ""

    parser = ZhihuHTMLToMarkdown()
    parser.feed(html_content)
    return parser.get_markdown()


def html_to_plain_text(html_content: str) -> str:
    """
    简化版：去除所有 HTML 标签，保留纯文本。

    作为 html_to_markdown 的后备方案。
    """
    if not html_content:
        return ""

    # 移除标签
    text = re.sub(r"<[^>]+>", "", html_content)
    # 处理 HTML 实体
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    text = text.replace("&nbsp;", " ")
    # 清理空白
    text = re.sub(r"\s+", " ", text).strip()
    return text


def estimate_char_count(text: str) -> int:
    """估算文本字符数（CJK 字符算 1 个）"""
    return len(text)
