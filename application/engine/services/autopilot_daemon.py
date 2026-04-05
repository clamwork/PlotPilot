"""自动驾驶守护进程 - 全托管写作引擎的心跳

核心设计：
1. 死循环轮询数据库，捞出所有 autopilot_status=RUNNING 的小说
2. 根据 current_stage 执行对应的状态机逻辑
3. 状态持久化到数据库，进程重启可恢复

战术植入点：
- ACT_PLANNING：插入缓冲章（日常/装逼/过渡）
- WRITING：节拍放大器（拆分为 4 个 500 字 Beat）
"""
import time
import logging
import asyncio
from typing import List, Optional

from domain.novel.entities.novel import Novel, NovelStage, AutopilotStatus
from domain.novel.value_objects.novel_id import NovelId
from domain.novel.repositories.novel_repository import NovelRepository
from domain.ai.services.llm_service import LLMService, GenerationConfig
from domain.ai.value_objects.prompt import Prompt
from application.engine.services.context_builder import ContextBuilder
from application.engine.services.background_task_service import BackgroundTaskService, TaskType
from domain.novel.value_objects.chapter_id import ChapterId

logger = logging.getLogger(__name__)


class AutopilotDaemon:
    """自动驾驶守护进程

    职责：
    1. 轮询数据库，处理所有 RUNNING 状态的小说
    2. 状态机调度：MACRO_PLANNING → ACT_PLANNING → WRITING → AUDITING
    3. 错误处理：捕获异常，标记为 ERROR 状态
    """

    def __init__(
        self,
        novel_repository: NovelRepository,
        llm_service: LLMService,
        context_builder: ContextBuilder,
        background_task_service: BackgroundTaskService,
        poll_interval: int = 5,  # 轮询间隔（秒）
    ):
        self.novel_repository = novel_repository
        self.llm_service = llm_service
        self.context_builder = context_builder
        self.background_task_service = background_task_service
        self.poll_interval = poll_interval

    def run_forever(self):
        """守护进程主循环"""
        logger.info("🚀 Autopilot Daemon Started...")

        while True:
            try:
                # 1. 捞出所有处于 RUNNING 状态的小说
                active_novels = self._get_active_novels()

                if active_novels:
                    logger.info(f"发现 {len(active_novels)} 个活跃小说")

                for novel in active_novels:
                    asyncio.run(self._process_novel(novel))

            except Exception as e:
                logger.error(f"Daemon 级别异常: {e}", exc_info=True)

            # 基础轮询间隔，避免打满 CPU
            time.sleep(self.poll_interval)

    def _get_active_novels(self) -> List[Novel]:
        """获取所有活跃小说

        Returns:
            List[Novel]: 活跃小说列表
        """
        return self.novel_repository.find_by_autopilot_status(AutopilotStatus.RUNNING.value)

    async def _process_novel(self, novel: Novel):
        """处理单个小说

        Args:
            novel: 小说对象
        """
        try:
            logger.info(f"[{novel.novel_id}] 当前阶段: {novel.current_stage.value}")

            if novel.current_stage == NovelStage.MACRO_PLANNING:
                await self._handle_macro_planning(novel)

            elif novel.current_stage == NovelStage.ACT_PLANNING:
                await self._handle_act_planning(novel)

            elif novel.current_stage == NovelStage.WRITING:
                await self._handle_writing(novel)

            elif novel.current_stage == NovelStage.AUDITING:
                await self._handle_auditing(novel)

            # 持久化状态
            self.novel_repository.save(novel)

        except Exception as e:
            logger.error(f"[{novel.novel_id}] 坠机，挂起排查: {str(e)}", exc_info=True)
            novel.autopilot_status = AutopilotStatus.ERROR
            self.novel_repository.save(novel)

    async def _handle_macro_planning(self, novel: Novel):
        """处理宏观规划（规划部/卷/幕）

        Args:
            novel: 小说对象
        """
        logger.info(f"[{novel.novel_id}] 执行宏观规划...")

        # TODO: 实现宏观规划逻辑
        # 1. 生成 3 幕结构
        # 2. 每幕 10 章
        # 3. 保存到数据库

        # 转换状态
        novel.current_stage = NovelStage.ACT_PLANNING

    async def _handle_act_planning(self, novel: Novel):
        """处理幕级规划（插入缓冲章策略）

        💡 战术植入点 1：日常/装逼缓冲池

        策略：
        1. 检测上一幕的类型（高潮战斗 vs 日常过渡）
        2. 如果上一幕是"大高潮"，强制插入 1-2 章缓冲章
        3. 缓冲章类型：
           - 战后休整：主角疗伤、盘点收获
           - 日常互动：与配角闲聊、展示战利品
           - 装逼打脸：路人震惊主角实力

        Args:
            novel: 小说对象
        """
        logger.info(f"[{novel.novel_id}] 执行幕级规划 (注入缓冲章策略)...")

        # 检测是否需要插入缓冲章
        needs_buffer = self._needs_buffer_chapters(novel)

        if needs_buffer:
            logger.info(f"[{novel.novel_id}] 检测到需要缓冲章，插入 2 章过渡")

        # 生成章节大纲
        prompt = Prompt(
            system=f"""你是一位资深网文编剧，擅长三幕式结构。

当前任务：为第 {novel.current_act + 1} 幕生成 10 个章节大纲。

{'【重要】上一幕是高潮战斗，本幕前 2 章必须是缓冲章：' if needs_buffer else ''}
{'1. 第1章：战后休整/疗伤/盘点收获（日常向，轻松氛围）' if needs_buffer else ''}
{'2. 第2章：装逼打脸/路人震惊/展示战利品（爽点密集）' if needs_buffer else ''}
{'3. 第3章开始：正式推进主线剧情' if needs_buffer else ''}

要求：
1. 每章大纲 50-80 字，包含：场景、冲突、转折
2. 章节之间有因果关系，不能跳跃
3. 标注伏笔埋设点【伏笔】和回收点
4. 符合三幕式结构

输出格式：
第X章：标题** - 大纲内容（50-80字）。【伏笔：xxx】
""",
            user=f"""小说前提：{novel.premise}

请生成第 {novel.current_act + 1} 幕的 10 个章节大纲："""
        )

        config = GenerationConfig(max_tokens=2000, temperature=0.8)
        result = await self.llm_service.generate(
            prompt.to_string(),
            max_tokens=config.max_tokens,
            temperature=config.temperature
        )

        # TODO: 解析并保存章节大纲
        logger.info(f"[{novel.novel_id}] 幕级规划完成")

        # 转换状态
        novel.current_stage = NovelStage.WRITING

    async def _handle_writing(self, novel: Novel):
        """处理写作（节拍放大器）

        💡 战术植入点 2：微观节拍放大器

        策略：
        1. 获取当前章节大纲
        2. 使用 context_builder.magnify_outline_to_beats() 拆分为 4 个节拍
        3. 逐节拍流式生成，每个节拍 500-800 字
        4. 拼接成完整章节（2000-2500 字）

        Args:
            novel: 小说对象
        """
        chapter_num = novel.current_act * 10 + novel.current_chapter_in_act + 1

        logger.info(f"[{novel.novel_id}] 写作中 (通过节拍放大器) - 章节 {chapter_num}")

        # TODO: 获取章节大纲
        outline = "林羽发现真相，和苏晴争吵"  # 占位

        # 使用节拍放大器拆分大纲
        beats = self.context_builder.magnify_outline_to_beats(outline, target_chapter_words=2500)
        logger.info(f"[{novel.novel_id}] 节拍放大器：拆分为 {len(beats)} 个节拍")

        # 逐节拍生成
        chapter_content = ""
        for i, beat in enumerate(beats):
            beat_prompt_text = self.context_builder.build_beat_prompt(beat, i, len(beats))

            prompt = Prompt(
                system="""你是一位资深网文作家，擅长写爽文。

写作要求：
1. 严格按照节拍要求的字数和聚焦点写作
2. 必须有对话和人物互动
3. 保持人物性格一致
4. 增加感官细节：视觉、听觉、触觉、情绪
5. 节奏控制：不要一章推进太多剧情
6. 这是章节的一部分，不要写章节标题""",
                user=f"""【章节大纲】
{outline}

{beat_prompt_text}

开始撰写这个节拍："""
            )

            config = GenerationConfig(max_tokens=int(beat.target_words * 1.5), temperature=0.8)

            # 使用流式生成避免 502 超时
            beat_content = ""
            async for chunk in self.llm_service.stream_generate(
                prompt,
                max_tokens=config.max_tokens,
                temperature=config.temperature
            ):
                beat_content += chunk

            chapter_content += beat_content + "\n\n"
            logger.info(f"[{novel.novel_id}]   节拍 {i+1}/{len(beats)} 完成：{len(beat_content)} 字")

        # TODO: 保存章节到数据库
        logger.info(f"[{novel.novel_id}] 章节 {chapter_num} 生成完成：{len(chapter_content)} 字")

        # 推进章节
        novel.current_chapter_in_act += 1
        if novel.current_chapter_in_act >= 10:
            # 当前幕完成
            novel.current_act += 1
            novel.current_chapter_in_act = 0

        # 转换状态
        novel.current_stage = NovelStage.AUDITING

    async def _handle_auditing(self, novel: Novel):
        """处理审计（异步扇出）

        Args:
            novel: 小说对象
        """
        chapter_num = novel.current_act * 10 + novel.current_chapter_in_act
        logger.info(f"[{novel.novel_id}] 审计与落账 - 章节 {chapter_num}")

        # 构造章节 ID
        chapter_id = ChapterId(f"chapter_{chapter_num}")

        # 提交后台任务（不等待）
        self.background_task_service.submit_task(
            task_type=TaskType.GRAPH_UPDATE,
            novel_id=novel.novel_id,
            chapter_id=chapter_id,
            payload={"content": ""}  # TODO: 传入实际内容
        )

        self.background_task_service.submit_task(
            task_type=TaskType.VOICE_ANALYSIS,
            novel_id=novel.novel_id,
            chapter_id=chapter_id,
            payload={"content": ""}
        )

        self.background_task_service.submit_task(
            task_type=TaskType.FORESHADOW_EXTRACT,
            novel_id=novel.novel_id,
            chapter_id=chapter_id,
            payload={"content": ""}
        )

        # 状态流转判断
        if self._needs_new_act(novel):
            novel.current_stage = NovelStage.ACT_PLANNING
        else:
            novel.current_stage = NovelStage.WRITING

    def _needs_buffer_chapters(self, novel: Novel) -> bool:
        """判断是否需要插入缓冲章

        策略：
        1. 如果是第一幕，不需要缓冲章
        2. 如果上一幕最后一章包含"战斗"、"对决"、"高潮"等关键词，需要缓冲章

        Args:
            novel: 小说对象

        Returns:
            bool: 是否需要缓冲章
        """
        if novel.current_act == 0:
            # 第一幕，不需要缓冲章
            return False

        # TODO: 检查上一幕最后一章的类型
        # 简化版：每隔一幕插入缓冲章
        return novel.current_act % 2 == 1

    def _needs_new_act(self, novel: Novel) -> bool:
        """判断是否需要规划新的幕

        Args:
            novel: 小说对象

        Returns:
            bool: 是否需要新幕
        """
        # 当前幕的章节是否已经全部写完
        return novel.current_chapter_in_act >= 10
