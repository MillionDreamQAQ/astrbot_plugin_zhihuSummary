"""
知乎 URL 解析工具

检测文本中的知乎链接，提取内容类型和 ID。
支持：回答、文章（专栏）、问题（取高赞回答）。
"""

import re
from typing import Optional

# ── URL 正则模式 ──

# 回答: https://www.zhihu.com/question/123456/answer/789012
_ANSWER_PATTERN = re.compile(r"https?://(?:www\.)?zhihu\.com/question/\d+/answer/(\d+)")

# 文章（专栏）: https://zhuanlan.zhihu.com/p/123456
_ARTICLE_PATTERN = re.compile(r"https?://zhuanlan\.zhihu\.com/p/(\d+)")

# 问题（无指定回答）: https://www.zhihu.com/question/123456
_QUESTION_PATTERN = re.compile(
    r"https?://(?:www\.)?zhihu\.com/question/(\d+)(?:/(?:\?|$|\S))?", re.IGNORECASE
)

# 通用知乎域名检测
_ZHIHU_DOMAIN = re.compile(r"zhihu\.com|zhuanlan\.zhihu\.com")

# 短链接: https://zhi.hu/xxx 或 link.zhihu.com/?target=...
_SHORT_LINK_PATTERN = re.compile(
    r"https?://zhi\.hu/\S+|https?://link\.zhihu\.com/\?target=\S+"
)

# 提取所有 URL
_URL_EXTRACT = re.compile(r'https?://[^\s<>"\]]+')


def detect_zhihu_url(text: str) -> Optional[tuple]:
    """
    检测文本中的知乎链接，返回 (content_type, content_id)。

    :param text: 可能包含 URL 的文本
    :return: ("answer"|"article"|"question", id_str) 或 None
    """
    # 先尝试直接匹配
    result = _match_known_patterns(text)
    if result:
        return result

    # 尝试提取 URL 后匹配
    urls = _URL_EXTRACT.findall(text)
    for url in urls:
        if _ZHIHU_DOMAIN.search(url):
            result = _match_known_patterns(url)
            if result:
                return result

    return None


def _match_known_patterns(text: str) -> Optional[tuple]:
    """按优先级匹配已知 URL 模式"""
    # 1. 回答（最具体，优先匹配）
    m = _ANSWER_PATTERN.search(text)
    if m:
        return ("answer", m.group(1))

    # 2. 文章（专栏）
    m = _ARTICLE_PATTERN.search(text)
    if m:
        return ("article", m.group(1))

    # 3. 问题（不带 answer 路径）
    #    需要排除已经匹配到 answer 的情况
    m = _QUESTION_PATTERN.search(text)
    if m and not _ANSWER_PATTERN.search(text):
        return ("question", m.group(1))

    return None


def extract_answer_id(url: str) -> Optional[str]:
    """从 URL 提取回答 ID"""
    m = _ANSWER_PATTERN.search(url)
    return m.group(1) if m else None


def extract_article_id(url: str) -> Optional[str]:
    """从 URL 提取文章 ID"""
    m = _ARTICLE_PATTERN.search(url)
    return m.group(1) if m else None


def extract_question_id(url: str) -> Optional[str]:
    """从 URL 提取问题 ID"""
    m = _QUESTION_PATTERN.search(url)
    return m.group(1) if m else None


def is_short_link(url: str) -> bool:
    """是否为知乎短链接"""
    return bool(_SHORT_LINK_PATTERN.match(url))
