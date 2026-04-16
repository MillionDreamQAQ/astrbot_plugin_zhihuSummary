"""
总结生成服务

编排：获取内容 → HTML→Markdown → 构建 Prompt → LLM → 后处理
支持长文本的截断和 Map-Reduce 两种策略。
"""

from typing import Optional

from astrbot.api import logger

from utils.html_to_text import (
    html_to_markdown,
    html_to_plain_text,
    estimate_char_count,
)

from gpt.prompt_builder import (
    build_answer_prompt,
    build_article_prompt,
    build_map_chunk_prompt,
    build_map_merge_prompt,
)

from .zhihu_api import fetch_content


class SummaryService:
    """知乎内容总结服务"""

    def __init__(self, cookie_str: str):
        self.cookie_str = cookie_str

    async def generate_summary(
        self,
        content_type: str,
        content_id: str,
        llm_ask_func,
        style: str = "professional",
        max_length: int = 4000,
        long_text_strategy: str = "truncate",
        long_text_threshold: int = 15000,
    ) -> Optional[str]:
        """
        生成知乎内容总结。

        :param content_type: "answer" | "article" | "question"
        :param content_id: 内容 ID
        :param llm_ask_func: async (prompt: str) -> str
        :param style: 总结风格
        :param max_length: 总结最大字符数
        :param long_text_strategy: "truncate" | "map_reduce"
        :param long_text_threshold: 长文本阈值
        :return: Markdown 总结文本
        """
        # 1. 获取内容
        logger.info(f"获取知乎内容: type={content_type}, id={content_id}")
        content_data = await fetch_content(content_type, content_id, self.cookie_str)

        if not content_data:
            return None

        # 2. HTML → Markdown
        content_html = content_data.get("content_html", "")
        if content_html:
            content_text = html_to_markdown(content_html)
            if not content_text:
                content_text = html_to_plain_text(content_html)
        else:
            content_text = ""

        if not content_text:
            return "❌ 无法提取内容文本"

        content_data["content_text"] = content_text
        char_count = estimate_char_count(content_text)
        logger.info(f"内容提取完成: {char_count} 字符")

        # 3. 判断是否需要长文本处理
        if char_count > long_text_threshold:
            if long_text_strategy == "map_reduce":
                logger.info(f"长文本({char_count}字)，使用 Map-Reduce 策略")
                markdown = await self._summarize_map_reduce(
                    content_data, style, llm_ask_func
                )
            else:
                logger.info(f"长文本({char_count}字)，截断到 {long_text_threshold} 字")
                content_data["content_text"] = (
                    content_text[:long_text_threshold]
                    + "\n\n...(内容过长，已截断，完整内容请查看原文)"
                )
                markdown = await self._summarize_direct(
                    content_data, style, llm_ask_func
                )
        else:
            markdown = await self._summarize_direct(content_data, style, llm_ask_func)

        if not markdown:
            return "❌ LLM 生成总结失败"

        # 4. 截断过长内容
        if len(markdown) > max_length:
            markdown = markdown[:max_length] + "\n\n...(内容过长，已截断)"

        return markdown

    async def _summarize_direct(
        self,
        content_data: dict,
        style: str,
        llm_ask_func,
    ) -> Optional[str]:
        """直接总结：单次 LLM 调用"""
        ctype = content_data.get("type", "answer")
        title = content_data.get("title", "")
        author = content_data.get("author_name", "")
        voteup = content_data.get("voteup_count", 0)
        text = content_data.get("content_text", "")

        if ctype == "article":
            prompt = build_article_prompt(
                title=title,
                author_name=author,
                voteup_count=voteup,
                content_text=text,
                style=style,
            )
        else:
            prompt = build_answer_prompt(
                question_title=title,
                author_name=author,
                voteup_count=voteup,
                content_text=text,
                style=style,
            )

        logger.info("调用 LLM 生成总结...")
        return await llm_ask_func(prompt)

    async def _summarize_map_reduce(
        self,
        content_data: dict,
        style: str,
        llm_ask_func,
    ) -> Optional[str]:
        """Map-Reduce 总结：分段总结后合并"""
        text = content_data.get("content_text", "")
        title = content_data.get("title", "")
        author = content_data.get("author_name", "")

        # 1. 分段
        chunks = self._split_text(text, chunk_size=3000)
        logger.info(f"文本分为 {len(chunks)} 个片段")

        # 2. Map: 逐段总结
        chunk_summaries = []
        for i, chunk in enumerate(chunks):
            prompt = build_map_chunk_prompt(
                source_title=title,
                chunk_text=chunk,
                chunk_index=i + 1,
                total_chunks=len(chunks),
            )
            summary = await llm_ask_func(prompt)
            if summary and not summary.startswith("❌"):
                chunk_summaries.append(summary)
            else:
                logger.warning(f"片段 {i+1} 总结失败，跳过")

        if not chunk_summaries:
            return "❌ 所有分段总结均失败"

        # 3. Reduce: 合并
        merge_prompt = build_map_merge_prompt(
            title=title,
            author_name=author,
            chunk_summaries=chunk_summaries,
            style=style,
        )

        logger.info(f"合并 {len(chunk_summaries)} 个分段总结...")
        return await llm_ask_func(merge_prompt)

    @staticmethod
    def _split_text(text: str, chunk_size: int = 3000) -> list:
        """
        按段落边界分段文本。

        :param text: 完整文本
        :param chunk_size: 目标分片大小（字符数）
        :return: 文本片段列表
        """
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 > chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = para
            else:
                current_chunk += "\n\n" + para if current_chunk else para

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks
