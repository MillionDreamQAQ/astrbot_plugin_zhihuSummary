"""
Markdown 转纯净文本工具

将 Markdown 格式转换为 QQ 友好的纯净文本格式。
"""
import re


def markdown_to_plain(text: str) -> str:
    """
    将 Markdown 转换为 QQ 友好的纯净文本。

    转换规则：
    - # H1 -> ═════ H1 ═════
    - ## H2 -> 【H2】
    - ### H3 -> ▶ H3
    - **加粗** -> 『加粗』
    - *斜体* -> 斜体
    - > 引用 -> ┃ 引用
    - - 列表 -> • 列表

    :param text: Markdown 文本
    :return: 纯净文本
    """
    if not text:
        return text

    lines = text.split("\n")
    result = []

    in_code_block = False
    code_block_fence = None

    for line in lines:
        # 检测代码块开始/结束
        if line.strip().startswith("```"):
            if not in_code_block:
                in_code_block = True
                code_block_fence = "```"
            else:
                in_code_block = False
                code_block_fence = None
            result.append("")  # 空行代替代码块分隔符
            continue

        # 代码块内不处理
        if in_code_block:
            result.append(line)
            continue

        # 处理一级标题 # H1
        h1_match = re.match(r"^#\s+(.+)$", line)
        if h1_match:
            title = h1_match.group(1).strip()
            result.append(f"═════ {title} ═════")
            continue

        # 处理二级标题 ## H2
        h2_match = re.match(r"^##\s+(.+)$", line)
        if h2_match:
            title = h2_match.group(1).strip()
            result.append(f"【{title}】")
            continue

        # 处理三级标题 ### H3
        h3_match = re.match(r"^###\s+(.+)$", line)
        if h3_match:
            title = h3_match.group(1).strip()
            result.append(f"▶ {title}")
            continue

        # 处理引用块 > 引用
        if line.strip().startswith(">"):
            content = re.sub(r"^>\s*", "", line).strip()
            result.append(f"┃ {content}")
            continue

        # 处理无序列表 - 列表
        unordered_match = re.match(r"^[\-\*]\s+(.+)$", line)
        if unordered_match:
            content = unordered_match.group(1).strip()
            result.append(f"• {content}")
            continue

        # 处理有序列表 1. 列表
        ordered_match = re.match(r"^\d+\.\s+(.+)$", line)
        if ordered_match:
            content = ordered_match.group(1).strip()
            result.append(f"{ordered_match.group(0)}")
            continue

        # 处理行内格式
        line = _process_inline_formats(line)

        result.append(line)

    return "\n".join(result)


def _process_inline_formats(line: str) -> str:
    """处理行内 Markdown 格式"""
    # 处理加粗 **text** 或 __text__
    line = re.sub(r"\*\*(.+?)\*\*", r"『\1』", line)
    line = re.sub(r"__(.+?)__", r"『\1』", line)

    # 处理斜体 *text* 或 _text_ （先处理加粗，避免冲突）
    line = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", line)
    line = re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", r"\1", line)

    # 处理内联代码 `code`
    line = re.sub(r"`(.+?)`", r"\1", line)

    # 处理链接 [text](url) -> text
    line = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", line)

    # 处理图片 ![alt](url) -> [图片]
    line = re.sub(r"!\[.+?\]\(.+?\)", "[图片]", line)

    return line
