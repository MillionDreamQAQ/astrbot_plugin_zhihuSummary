"""
Prompt 组装逻辑

根据内容类型、风格和配置组装最终的 LLM Prompt。
"""

from .prompt import (
    ANSWER_PROMPT,
    ARTICLE_PROMPT,
    STYLE_CONCISE,
    STYLE_DETAILED,
    STYLE_PROFESSIONAL,
    AI_SUMMARY_FOOTER,
    MAP_CHUNK_PROMPT,
    MAP_MERGE_PROMPT,
)

NOTE_STYLES = {
    "concise": STYLE_CONCISE,
    "detailed": STYLE_DETAILED,
    "professional": STYLE_PROFESSIONAL,
}


def build_answer_prompt(
    question_title: str,
    author_name: str,
    voteup_count: int,
    content_text: str,
    style: str = "professional",
    enable_ai_summary: bool = True,
) -> str:
    """
    构建知乎回答总结 Prompt。

    :param question_title: 问题标题
    :param author_name: 回答者名称
    :param voteup_count: 赞同数
    :param content_text: 回答内容（Markdown）
    :param style: 总结风格
    :param enable_ai_summary: 是否添加 AI 点评
    :return: 完整 Prompt
    """
    extra = ""
    if style in NOTE_STYLES:
        extra += "\n" + NOTE_STYLES[style]
    if enable_ai_summary:
        extra += AI_SUMMARY_FOOTER

    return ANSWER_PROMPT.format(
        question_title=question_title,
        author_name=author_name,
        voteup_count=voteup_count,
        content_text=content_text,
        extra_instructions=extra,
    )


def build_article_prompt(
    title: str,
    author_name: str,
    voteup_count: int,
    content_text: str,
    style: str = "detailed",
    enable_ai_summary: bool = True,
) -> str:
    """
    构建知乎文章总结 Prompt。

    :param title: 文章标题
    :param author_name: 作者名称
    :param voteup_count: 赞同数
    :param content_text: 文章内容（Markdown）
    :param style: 总结风格
    :param enable_ai_summary: 是否添加 AI 点评
    :return: 完整 Prompt
    """
    extra = ""
    if style in NOTE_STYLES:
        extra += "\n" + NOTE_STYLES[style]
    if enable_ai_summary:
        extra += AI_SUMMARY_FOOTER

    return ARTICLE_PROMPT.format(
        title=title,
        author_name=author_name,
        voteup_count=voteup_count,
        content_text=content_text,
        extra_instructions=extra,
    )


def build_map_chunk_prompt(
    source_title: str,
    chunk_text: str,
    chunk_index: int,
    total_chunks: int,
) -> str:
    """
    构建 Map-Reduce 中单段总结的 Prompt。
    """
    return MAP_CHUNK_PROMPT.format(
        source_title=source_title,
        chunk_text=chunk_text,
        chunk_index=chunk_index,
        total_chunks=total_chunks,
    )


def build_map_merge_prompt(
    title: str,
    author_name: str,
    chunk_summaries: list,
    style: str = "professional",
    enable_ai_summary: bool = True,
) -> str:
    """
    构建 Map-Reduce 合并 Prompt。
    """
    summaries_text = "\n\n---\n\n".join(
        f"### 片段 {i+1}\n{s}" for i, s in enumerate(chunk_summaries)
    )

    style_instruction = ""
    if style in NOTE_STYLES:
        style_instruction = NOTE_STYLES[style]

    ai_summary_instruction = ""
    if enable_ai_summary:
        ai_summary_instruction = AI_SUMMARY_FOOTER

    return MAP_MERGE_PROMPT.format(
        title=title,
        author_name=author_name,
        chunk_summaries=summaries_text,
        style_instruction=style_instruction,
        ai_summary_instruction=ai_summary_instruction,
    )
