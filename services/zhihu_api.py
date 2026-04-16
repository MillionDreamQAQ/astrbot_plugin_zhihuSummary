"""
知乎 API 客户端

通过知乎非官方 API 获取回答和文章内容。
支持限流和错误处理。
"""

import asyncio
import time
from typing import Optional

import aiohttp

from astrbot.api import logger

# ── 常量 ──

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)

ZHIHU_API_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.zhihu.com",
    "Origin": "https://www.zhihu.com",
}

# ── 限流 ──

_LAST_REQUEST_TIME: float = 0.0
_RATE_LOCK = asyncio.Lock()
_MIN_INTERVAL: float = 0.3  # 请求间隔 ≥ 300ms


async def _rate_limit():
    """确保请求间隔 ≥ 0.3 秒"""
    global _LAST_REQUEST_TIME
    async with _RATE_LOCK:
        now = time.monotonic()
        elapsed = now - _LAST_REQUEST_TIME
        if elapsed < _MIN_INTERVAL:
            await asyncio.sleep(_MIN_INTERVAL - elapsed)
        _LAST_REQUEST_TIME = time.monotonic()


def _build_headers(z_c0: str) -> dict:
    """构建带 Cookie 的请求头"""
    headers = dict(ZHIHU_API_HEADERS)
    if z_c0:
        headers["Cookie"] = f"z_c0={z_c0}"
    return headers


async def _do_request(url: str, z_c0: str, params: Optional[dict] = None) -> Optional[dict]:
    """
    发起知乎 API 请求，返回 JSON 或 None。

    处理 401/403/404/429 等状态码。
    """
    await _rate_limit()
    headers = _build_headers(z_c0)

    try:
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.get(url, params=params, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()

                if resp.status in (401, 403):
                    logger.warning(f"知乎 API 认证失败 (HTTP {resp.status})，Cookie 可能已失效")
                    return None

                if resp.status == 404:
                    logger.warning(f"知乎内容不存在 (HTTP 404)")
                    return None

                if resp.status == 429:
                    logger.warning("知乎 API 限流 (HTTP 429)，等待 2 秒后重试")
                    await asyncio.sleep(2)
                    async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as retry_session:
                        async with retry_session.get(url, params=params, headers=headers) as retry_resp:
                            if retry_resp.status == 200:
                                return await retry_resp.json()
                            logger.warning(f"知乎 API 重试失败 (HTTP {retry_resp.status})")
                            return None

                logger.warning(f"知乎 API 请求失败: HTTP {resp.status}")
                return None

    except asyncio.TimeoutError:
        logger.error("知乎 API 请求超时")
        return None
    except Exception as e:
        logger.error(f"知乎 API 请求异常: {e}")
        return None


# ── 内容获取函数 ──

async def fetch_answer(answer_id: str, z_c0: str) -> Optional[dict]:
    """
    获取知乎回答详情。

    :return: 标准化 dict 或 None
    """
    url = f"https://www.zhihu.com/api/v4/answers/{answer_id}"
    params = {
        "include": (
            "content,voteup_count,comment_count,"
            "author.name,author.avatar_url,author.headline,"
            "question.id,question.title,question.detail"
        ),
    }

    data = await _do_request(url, z_c0, params)
    if not data:
        return None

    try:
        author = data.get("author", {})
        question = data.get("question", {})
        return {
            "type": "answer",
            "id": str(data.get("id", answer_id)),
            "title": question.get("title", "未知问题"),
            "content_html": data.get("content", ""),
            "author_name": author.get("name", "匿名用户"),
            "author_avatar": author.get("avatar_url", ""),
            "voteup_count": data.get("voteup_count", 0),
            "comment_count": data.get("comment_count", 0),
            "source_url": f"https://www.zhihu.com/question/{question.get('id', '')}/answer/{answer_id}",
        }
    except Exception as e:
        logger.error(f"解析知乎回答数据失败: {e}")
        return None


async def fetch_article(article_id: str, z_c0: str) -> Optional[dict]:
    """
    获取知乎专栏文章详情。

    :return: 标准化 dict 或 None
    """
    url = f"https://api.zhihu.com/articles/{article_id}"

    data = await _do_request(url, z_c0)
    if not data:
        # 尝试备用端点
        url = f"https://www.zhihu.com/api/v4/articles/{article_id}"
        data = await _do_request(url, z_c0)
        if not data:
            return None

    try:
        author = data.get("author", {})
        column = data.get("column", {})
        return {
            "type": "article",
            "id": str(data.get("id", article_id)),
            "title": data.get("title", "未知文章"),
            "content_html": data.get("content", ""),
            "author_name": author.get("name", "匿名用户"),
            "author_avatar": author.get("avatar_url", ""),
            "voteup_count": data.get("voteup_count", 0),
            "comment_count": data.get("comment_count", 0),
            "column_name": column.get("name", "") if column else "",
            "source_url": f"https://zhuanlan.zhihu.com/p/{article_id}",
        }
    except Exception as e:
        logger.error(f"解析知乎文章数据失败: {e}")
        return None


async def fetch_question_top_answer(question_id: str, z_c0: str) -> Optional[dict]:
    """
    获取问题下的默认排序第一个回答（通常是高赞回答）。

    :return: 标准化 dict 或 None
    """
    url = f"https://www.zhihu.com/api/v4/questions/{question_id}/answers"
    params = {
        "limit": "1",
        "sort_by": "default",
        "include": (
            "content,voteup_count,comment_count,"
            "author.name,author.avatar_url,author.headline,"
            "question.id,question.title"
        ),
    }

    data = await _do_request(url, z_c0, params)
    if not data:
        return None

    try:
        answers = data.get("data", [])
        if not answers:
            logger.info(f"知乎问题 {question_id} 暂无回答")
            return None

        answer = answers[0]
        author = answer.get("author", {})
        question = answer.get("question", {})
        return {
            "type": "answer",
            "id": str(answer.get("id", "")),
            "title": question.get("title", "未知问题"),
            "content_html": answer.get("content", ""),
            "author_name": author.get("name", "匿名用户"),
            "author_avatar": author.get("avatar_url", ""),
            "voteup_count": answer.get("voteup_count", 0),
            "comment_count": answer.get("comment_count", 0),
            "source_url": (
                f"https://www.zhihu.com/question/{question_id}"
                f"/answer/{answer.get('id', '')}"
            ),
        }
    except Exception as e:
        logger.error(f"解析知乎问题回答数据失败: {e}")
        return None


async def fetch_content(
    content_type: str,
    content_id: str,
    z_c0: str,
) -> Optional[dict]:
    """
    统一内容获取入口。

    :param content_type: "answer" | "article" | "question"
    :param content_id: 内容 ID
    :param z_c0: 知乎 z_c0 Cookie 值
    :return: 标准化内容 dict 或 None
    """
    if not z_c0:
        logger.warning("未配置知乎 Cookie z_c0")
        return None

    if content_type == "answer":
        return await fetch_answer(content_id, z_c0)
    elif content_type == "article":
        return await fetch_article(content_id, z_c0)
    elif content_type == "question":
        return await fetch_question_top_answer(content_id, z_c0)
    else:
        logger.warning(f"不支持的内容类型: {content_type}")
        return None
