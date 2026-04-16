"""
zhihuSummary 知乎总结插件

发送知乎回答/文章链接，自动生成 AI 结构化总结。
"""

import asyncio
import os
import time

from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.star import Context, Star, StarTools
from astrbot.api.message_components import Plain, Image
from astrbot.api import logger

from .services.summary_service import SummaryService
from .utils.url_parser import detect_zhihu_url, _URL_EXTRACT
from .utils.md_to_image import render_note_image


class ZhihuSummaryPlugin(Star):
    """知乎总结插件"""

    def __init__(self, context: Context, config: dict):
        super().__init__(context)

        # 数据目录
        self.data_dir = str(StarTools.get_data_dir("astrbot_plugin_zhihuSummary"))
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(os.path.join(self.data_dir, "images"), exist_ok=True)

        # 配置
        self.config = config

        # Debug 模式
        self._debug_mode = bool(self.config.get("debug_mode", False))
        if self._debug_mode:
            logger.info("═══════════ [zhihuSummary] Debug 模式已启用 ═══════════")

        self._log("══════ [zhihuSummary] 插件初始化开始 ══════")

        # 知乎 Cookie
        self.z_c0 = str(self.config.get("zhihu_cookie_z_c0", "")).strip()
        self._log(f"Cookie 状态: {'已配置' if self.z_c0 else '未配置'}")

        # 总结服务
        self.summary_service = SummaryService(z_c0=self.z_c0)

        # LLM 配置
        self.llm_provider = self.config.get("llm_provider", "astrbot")
        self.llm_api_base = str(self.config.get("llm_api_base", "")).rstrip("/")
        self.llm_api_key = str(self.config.get("llm_api_key", ""))
        self.llm_model = str(self.config.get("llm_model", "gpt-4o-mini"))
        self._log(f"LLM Provider: {self.llm_provider}")

        # 总结配置
        self.note_style = self.config.get("note_style", "professional")
        self.max_note_length = int(self.config.get("max_note_length", 4000))
        self.long_text_strategy = self.config.get("long_text_strategy", "truncate")
        self.long_text_threshold = int(self.config.get("long_text_threshold", 15000))
        self.processing_timeout = int(self.config.get("processing_timeout", 120))

        # 自动识别
        self.enable_auto_detect = bool(self.config.get("enable_auto_detect", False))
        self._log(f"自动识别: {'启用' if self.enable_auto_detect else '禁用'}")

        # 群聊访问控制
        self.access_mode = self.config.get("access_mode", "blacklist")
        self.group_list = self._parse_list(str(self.config.get("group_list", "")))
        self._log(f"访问控制: mode={self.access_mode}, group_list={self.group_list}")

        self._log("══════ [zhihuSummary] 插件初始化完成 ══════")

        if self.z_c0:
            logger.info("zhihuSummary 插件已加载（知乎 Cookie 已配置）")
        else:
            logger.info("zhihuSummary 插件已加载（知乎 Cookie 未配置，请在插件设置中填写 z_c0）")

    # ==================== 工具方法 ====================

    def _log(self, msg: str):
        """Debug 日志"""
        if self._debug_mode:
            logger.info(f"[zhihuSummary/DBG] {msg}")

    @staticmethod
    def _parse_list(text: str) -> set:
        """解析逗号分隔的列表为 set"""
        if not text or not text.strip():
            return set()
        return {item.strip() for item in text.split(',') if item.strip()}

    def _check_access(self, event: AstrMessageEvent) -> bool:
        """检查群是否有权使用插件"""
        try:
            origin = getattr(event, 'unified_msg_origin', '') or ''
            self._log(f"[AccessCheck] mode={self.access_mode}, origin={origin}")

            if not self.group_list:
                return True

            if self.access_mode == 'whitelist':
                for gid in self.group_list:
                    if f':{gid}' in origin or origin.endswith(gid):
                        return True
                return False

            elif self.access_mode == 'blacklist':
                for gid in self.group_list:
                    if f':{gid}' in origin or origin.endswith(gid):
                        return False
                return True

        except Exception as e:
            logger.warning(f"访问控制检查异常: {e}")

        return True

    @staticmethod
    def _parse_args(message_str) -> str:
        """从消息中提取命令参数"""
        if not message_str:
            return ""
        parts = str(message_str).strip().split(maxsplit=1)
        return parts[1].strip() if len(parts) > 1 else ""

    def _render_and_get_chain(self, note_text: str):
        """
        将总结渲染为图片或返回纯文本。

        :return: list[Image] 或 str
        """
        if not self.config.get("output_image", True):
            self._log("[Render] 纯文本模式")
            return note_text

        img_filename = f"note_{int(time.time() * 1000)}.png"
        img_path = os.path.join(self.data_dir, "images", img_filename)

        self._log(f"[Render] 渲染图片: {img_path}")
        result = render_note_image(note_text, img_path)

        if result and os.path.exists(result):
            self._log(f"[Render] 成功: {os.path.getsize(result)} bytes")
            return [Image.fromFileSystem(result)]
        else:
            self._log("[Render] 渲染失败，回退纯文本")
            return note_text

    # ==================== 命令 ====================

    @filter.command("知乎帮助", alias={"zhihu_help", "知乎help"})
    async def help_cmd(self, event: AstrMessageEvent):
        """显示帮助信息"""
        cookie_status = "✅ 已配置" if self.z_c0 else "❌ 未配置"
        detect_status = "✅ 已开启" if self.enable_auto_detect else "❌ 已关闭"
        image_status = "✅ 图片模式" if self.config.get("output_image", True) else "📝 纯文本模式"

        help_text = f"""📖 **知乎总结插件 使用指南**

🔗 **基本用法：**
• `/知乎总结 <知乎链接>` — 生成总结
• `/知乎识别开关` — 切换自动识别

📋 **支持的链接类型：**
• 回答：zhihu.com/question/xxx/answer/xxx
• 文章：zhuanlan.zhihu.com/p/xxx
• 问题：zhihu.com/question/xxx（自动取高赞回答）

⚙️ **当前配置：**
• Cookie: {cookie_status}
• 自动识别: {detect_status}
• 输出格式: {image_status}
• 总结风格: {self.note_style}

💡 **提示：**
• Cookie 未配置时无法获取内容
• 从浏览器 Cookie 中复制 z_c0 值填入插件配置即可"""

        yield event.plain_result(help_text)

    @filter.command("知乎识别开关", alias={"zhihu_detect_toggle"})
    async def toggle_detect_cmd(self, event: AstrMessageEvent):
        """切换自动识别开关"""
        self.enable_auto_detect = not self.enable_auto_detect
        self.config["enable_auto_detect"] = self.enable_auto_detect
        status = "✅ 已开启" if self.enable_auto_detect else "❌ 已关闭"
        yield event.plain_result(f"知乎链接自动识别: {status}")

    @filter.command("知乎总结", alias={"zhsummary", "总结知乎", "知乎"})
    async def summarize_cmd(self, event: AstrMessageEvent):
        """手动总结知乎内容"""
        # 访问控制
        if not self._check_access(event):
            return

        # Cookie 检查
        if not self.z_c0:
            yield event.plain_result(
                "❌ 未配置知乎 Cookie，请在插件设置中填写 z_c0 值。\n"
                "💡 获取方法：登录知乎 → 浏览器 F12 → Application → Cookies → 复制 z_c0 的值"
            )
            return

        # 解析参数
        args = self._parse_args(event.message_str)

        # 尝试从参数中提取 URL
        url = args.strip()
        if not url:
            # 尝试从完整消息中提取
            full_text = event.message_str or ""
            urls = _URL_EXTRACT.findall(full_text)
            url = urls[0] if urls else ""

        if not url:
            yield event.plain_result(
                "❌ 请提供知乎链接\n"
                "用法: /知乎总结 <知乎链接>\n"
                "示例: /知乎总结 https://www.zhihu.com/question/123456/answer/789012"
            )
            return

        # 检测链接类型
        result = detect_zhihu_url(url)
        if not result:
            yield event.plain_result("❌ 无法识别该知乎链接，请检查链接格式")
            return

        content_type, content_id = result
        self._log(f"检测到知乎链接: type={content_type}, id={content_id}")

        # 生成总结
        yield event.plain_result("⏳ 正在获取知乎内容并生成总结，请稍候...")

        try:
            note = await asyncio.wait_for(
                self.summary_service.generate_summary(
                    content_type=content_type,
                    content_id=content_id,
                    llm_ask_func=self._ask_llm,
                    style=self.note_style,
                    max_length=self.max_note_length,
                    long_text_strategy=self.long_text_strategy,
                    long_text_threshold=self.long_text_threshold,
                ),
                timeout=self.processing_timeout,
            )
        except asyncio.TimeoutError:
            yield event.plain_result("❌ 总结生成超时，请稍后重试")
            return
        except Exception as e:
            logger.error(f"总结生成异常: {e}", exc_info=True)
            yield event.plain_result(f"❌ 总结生成失败: {str(e)}")
            return

        if not note:
            yield event.plain_result(
                "❌ 获取内容失败。可能原因：\n"
                "• Cookie 已失效，请更新 z_c0\n"
                "• 内容不存在或已被删除\n"
                "• 网络连接问题"
            )
            return

        if note.startswith("❌"):
            yield event.plain_result(note)
            return

        # 渲染输出
        rendered = self._render_and_get_chain(note)
        if isinstance(rendered, list):
            yield event.chain_result(rendered)
        else:
            yield event.plain_result(rendered)

    # ==================== 自动识别 ====================

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_all_message(self, event: AstrMessageEvent):
        """自动识别消息中的知乎链接"""
        if not self.enable_auto_detect:
            return

        # 跳过命令消息
        raw_msg = event.message_str or ""
        if raw_msg.strip().startswith("/"):
            return

        # 访问控制
        if not self._check_access(event):
            return

        # Cookie 检查
        if not self.z_c0:
            return

        # 检测知乎链接
        result = detect_zhihu_url(raw_msg)
        if not result:
            return

        content_type, content_id = result
        self._log(f"[AutoDetect] 检测到知乎链接: type={content_type}, id={content_id}")

        # 生成总结
        yield event.plain_result("⏳ 检测到知乎链接，正在生成总结...")

        try:
            note = await asyncio.wait_for(
                self.summary_service.generate_summary(
                    content_type=content_type,
                    content_id=content_id,
                    llm_ask_func=self._ask_llm,
                    style=self.note_style,
                    max_length=self.max_note_length,
                    long_text_strategy=self.long_text_strategy,
                    long_text_threshold=self.long_text_threshold,
                ),
                timeout=self.processing_timeout,
            )
        except asyncio.TimeoutError:
            yield event.plain_result("❌ 总结生成超时")
            return
        except Exception as e:
            logger.error(f"自动总结异常: {e}", exc_info=True)
            return

        if not note or note.startswith("❌"):
            return

        # 渲染输出
        rendered = self._render_and_get_chain(note)
        if isinstance(rendered, list):
            yield event.chain_result(rendered)
        else:
            yield event.plain_result(rendered)

    # ==================== LLM 调度 ====================

    async def _ask_llm(self, prompt: str) -> str:
        """根据配置调用 LLM"""
        if self.llm_provider == "openai_compatible":
            return await self._ask_llm_openai_compatible(prompt)
        return await self._ask_llm_astrbot(prompt)

    async def _ask_llm_astrbot(self, prompt: str) -> str:
        """调用 AstrBot 内置 LLM"""
        try:
            self._log(f"[AskLLM/AstrBot] prompt 长度={len(prompt)}")
            provider = self.context.get_using_provider()
            if not provider:
                return "❌ 未配置 LLM Provider"

            response = await provider.text_chat(
                prompt=prompt,
                session_id="zhihuSummary_plugin",
            )

            if hasattr(response, 'completion_text'):
                return response.completion_text
            elif isinstance(response, str):
                return response
            else:
                return str(response)

        except Exception as e:
            logger.error(f"LLM 调用失败 (AstrBot): {e}", exc_info=True)
            return f"❌ LLM 调用失败: {str(e)}"

    async def _ask_llm_openai_compatible(self, prompt: str) -> str:
        """调用 OpenAI 兼容 API"""
        try:
            if not self.llm_api_base or not self.llm_api_key:
                return "❌ 请先配置 llm_api_base 和 llm_api_key"

            self._log(f"[AskLLM/OpenAI] prompt 长度={len(prompt)}, model={self.llm_model}")
            url = f"{self.llm_api_base}/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.llm_api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": self.llm_model,
                "messages": [{"role": "user", "content": prompt}],
            }

            import aiohttp as _aiohttp
            timeout = _aiohttp.ClientTimeout(total=120)
            async with _aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.error(f"OpenAI 兼容 API 返回 HTTP {resp.status}: {body[:500]}")
                        return f"❌ LLM API 返回错误 (HTTP {resp.status})"

                    data = await resp.json()
                    content = data["choices"][0]["message"]["content"]
                    self._log(f"[AskLLM/OpenAI] 响应长度={len(content)}")
                    return content

        except Exception as e:
            logger.error(f"LLM 调用失败 (OpenAI Compatible): {e}", exc_info=True)
            return f"❌ LLM 调用失败: {str(e)}"

    # ==================== 生命周期 ====================

    async def terminate(self):
        """插件卸载"""
        logger.info("zhihuSummary 知乎总结插件已卸载")
