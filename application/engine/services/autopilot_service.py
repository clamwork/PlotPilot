"""自动驾驶服务 - 全托管写作引擎的核心调度器

战役二：单线程同步状态机
- 状态：INIT → PLANNING → WRITING → ANALYZING → PLANNING → ...
- 持续规划：写完一幕再规划下一幕
- 伏笔账本：自动埋设和回收伏笔
- 异步扇出：图谱更新、文风计算等后台任务
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

from domain.novel.value_objects.novel_id import NovelId
from domain.novel.value_objects.chapter_id import ChapterId
from domain.novel.repositories.novel_repository import NovelRepository
from domain.novel.repositories.chapter_repository import ChapterRepository
from domain.novel.repositories.foreshadowing_repository import ForeshadowingRepository
from domain.ai.services.llm_service import LLMService, GenerationConfig
from domain.ai.value_objects.prompt import Prompt
from application.engine.services.background_task_service import (
    BackgroundTaskService,
    TaskType
)
from application.engine.services.context_builder import ContextBuilder

logger = logging.getLogger(__name__)


class AutopilotState(Enum):
    """自动驾驶状态"""
    IDLE = "idle"  # 空闲
    INIT_PLANNING = "init_planning"  # 初始化规划（第一幕）
    WRITING = "writing"  # 写作中
    ANALYZING = "analyzing"  # 分析中（异步扇出）
    CONTINUOUS_PLANNING = "continuous_planning"  # 持续规划（下一幕）
    COMPLETED = "completed"  # 完成
    ERROR = "error"  # 错误


class ActPlan:
    """幕级规划"""
    def __init__(self, act_number: int, title: str, chapters: List[str]):
        self.act_number = act_number
        self.title = title
        self.chapters = chapters  # 章节大纲列表
        self.completed = False


class AutopilotSession:
    """自动驾驶会话（状态容器）"""
    def __init__(self, novel_id: NovelId, target_acts: int = 3, chapters_per_act: int = 10):
        self.novel_id = novel_id
        self.target_acts = target_acts
        self.chapters_per_act = chapters_per_act

        # 状态机
        self.state = AutopilotState.IDLE
        self.current_act = 0
        self.current_chapter_in_act = 0

        # 规划数据
        self.acts: List[ActPlan] = []

        # 生成历史
        self.generated_chapters: List[Dict[str, Any]] = []

        # 统计
        self.total_words = 0
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None

    def get_current_chapter_number(self) -> int:
        """获取当前章节号（全局）"""
        return self.current_act * self.chapters_per_act + self.current_chapter_in_act + 1

    def advance_chapter(self):
        """推进到下一章"""
        self.current_chapter_in_act += 1
        if self.current_chapter_in_act >= self.chapters_per_act:
            # 完成当前幕
            if self.current_act < len(self.acts):
                self.acts[self.current_act].completed = True
            self.current_act += 1
            self.current_chapter_in_act = 0

    def is_act_completed(self) -> bool:
        """当前幕是否完成"""
        return self.current_chapter_in_act >= self.chapters_per_act

    def is_all_completed(self) -> bool:
        """是否全部完成"""
        return self.current_act >= self.target_acts


class AutopilotService:
    """自动驾驶服务

    核心职责：
    1. 状态机调度：管理 INIT → PLANNING → WRITING → ANALYZING 循环
    2. 持续规划：写完一幕触发下一幕规划
    3. 伏笔管理：自动埋设和回收伏笔
    4. 异步扇出：触发后台分析任务
    """

    def __init__(
        self,
        llm_service: LLMService,
        novel_repository: NovelRepository,
        chapter_repository: ChapterRepository,
        foreshadowing_repository: ForeshadowingRepository,
        context_builder: Optional[ContextBuilder] = None,
        background_task_service: Optional[BackgroundTaskService] = None,
    ):
        self.llm_service = llm_service
        self.novel_repository = novel_repository
        self.chapter_repository = chapter_repository
        self.foreshadowing_repository = foreshadowing_repository
        self.context_builder = context_builder
        self.background_task_service = background_task_service or BackgroundTaskService()

        # 当前会话（单例模式，后续可改为多会话）
        self.session: Optional[AutopilotSession] = None

    async def start_autopilot(
        self,
        novel_id: NovelId,
        target_acts: int = 3,
        chapters_per_act: int = 10
    ) -> AutopilotSession:
        """启动自动驾驶

        Args:
            novel_id: 小说 ID
            target_acts: 目标幕数（默认 3）
            chapters_per_act: 每幕章节数（默认 10）

        Returns:
            AutopilotSession: 会话对象
        """
        logger.info(f"启动自动驾驶：novel_id={novel_id}, target_acts={target_acts}, chapters_per_act={chapters_per_act}")

        # 创建会话
        self.session = AutopilotSession(novel_id, target_acts, chapters_per_act)
        self.session.started_at = datetime.now()
        self.session.state = AutopilotState.INIT_PLANNING

        # 执行状态机循环
        await self._run_state_machine()

        return self.session

    async def _run_state_machine(self):
        """运行状态机（单线程同步循环）"""
        while self.session.state not in [AutopilotState.COMPLETED, AutopilotState.ERROR]:
            try:
                if self.session.state == AutopilotState.INIT_PLANNING:
                    await self._handle_init_planning()

                elif self.session.state == AutopilotState.WRITING:
                    await self._handle_writing()

                elif self.session.state == AutopilotState.ANALYZING:
                    await self._handle_analyzing()

                elif self.session.state == AutopilotState.CONTINUOUS_PLANNING:
                    await self._handle_continuous_planning()

            except Exception as e:
                logger.error(f"状态机错误：{e}", exc_info=True)
                self.session.state = AutopilotState.ERROR
                raise

        # 完成
        if self.session.state == AutopilotState.COMPLETED:
            self.session.completed_at = datetime.now()
            logger.info(f"自动驾驶完成：总章节={len(self.session.generated_chapters)}, 总字数={self.session.total_words}")

    async def _handle_init_planning(self):
        """处理初始化规划（第一幕）"""
        logger.info("=" * 80)
        logger.info("阶段：初始化规划（第一幕）")
        logger.info("=" * 80)

        # 获取小说信息
        novel = await self.novel_repository.get_by_id(self.session.novel_id)
        if not novel:
            raise ValueError(f"小说不存在：{self.session.novel_id}")

        # 生成第一幕规划
        act_plan = await self._generate_act_plan(
            act_number=1,
            novel_premise=novel.premise or "一个关于命运与选择的奇幻故事",
            previous_acts=[]
        )

        self.session.acts.append(act_plan)
        logger.info(f"✓ 第一幕规划完成：{len(act_plan.chapters)} 个章节")

        # 转换状态
        self.session.state = AutopilotState.WRITING

    async def _handle_writing(self):
        """处理写作"""
        chapter_num = self.session.get_current_chapter_number()
        act_num = self.session.current_act + 1
        chapter_in_act = self.session.current_chapter_in_act + 1

        logger.info("=" * 80)
        logger.info(f"生成章节 {chapter_num} (第{act_num}幕 第{chapter_in_act}章)")
        logger.info("=" * 80)

        # 获取当前章节大纲
        current_act = self.session.acts[self.session.current_act]
        outline = current_act.chapters[self.session.current_chapter_in_act]

        # 生成章节内容（简化版，后续接入 context_builder）
        content = await self._generate_chapter_content(
            chapter_num=chapter_num,
            outline=outline,
            recent_chapters=self.session.generated_chapters[-3:]  # 最近 3 章
        )

        # 保存章节
        chapter_data = {
            "chapter_number": chapter_num,
            "act_number": act_num,
            "chapter_in_act": chapter_in_act,
            "outline": outline,
            "content": content,
            "word_count": len(content),
            "generated_at": datetime.now().isoformat()
        }
        self.session.generated_chapters.append(chapter_data)
        self.session.total_words += len(content)

        logger.info(f"✓ 章节 {chapter_num} 生成完成：{len(content)} 字")

        # 推进章节
        self.session.advance_chapter()

        # 判断下一步状态
        if self.session.is_all_completed():
            # 全部完成
            self.session.state = AutopilotState.COMPLETED
        elif self.session.is_act_completed():
            # 当前幕完成，需要持续规划
            self.session.state = AutopilotState.CONTINUOUS_PLANNING
        else:
            # 继续写作
            self.session.state = AutopilotState.ANALYZING  # 先分析再写下一章

    async def _handle_analyzing(self):
        """处理分析（异步扇出）"""
        chapter_num = self.session.get_current_chapter_number() - 1  # 刚生成的章节
        chapter_data = self.session.generated_chapters[-1]

        logger.info(f"异步扇出：章节 {chapter_num}")

        # 构造章节 ID（简化版）
        chapter_id = ChapterId(f"chapter_{chapter_num}")

        # 提交后台任务（不等待）
        self.background_task_service.submit_task(
            task_type=TaskType.GRAPH_UPDATE,
            novel_id=self.session.novel_id,
            chapter_id=chapter_id,
            payload={"content": chapter_data["content"]}
        )

        self.background_task_service.submit_task(
            task_type=TaskType.VOICE_ANALYSIS,
            novel_id=self.session.novel_id,
            chapter_id=chapter_id,
            payload={"content": chapter_data["content"]}
        )

        self.background_task_service.submit_task(
            task_type=TaskType.FORESHADOW_EXTRACT,
            novel_id=self.session.novel_id,
            chapter_id=chapter_id,
            payload={"content": chapter_data["content"]}
        )

        self.background_task_service.submit_task(
            task_type=TaskType.ENTITY_STATE_UPDATE,
            novel_id=self.session.novel_id,
            chapter_id=chapter_id,
            payload={"content": chapter_data["content"]}
        )

        # 获取任务统计
        stats = self.background_task_service.get_stats()
        logger.info(f"后台任务统计：{stats}")

        # 转换状态
        self.session.state = AutopilotState.WRITING

    async def _handle_continuous_planning(self):
        """处理持续规划（下一幕）"""
        next_act_num = self.session.current_act + 1

        logger.info("=" * 80)
        logger.info(f"持续规划：生成第 {next_act_num} 幕")
        logger.info("=" * 80)

        # 获取小说信息
        novel = await self.novel_repository.get_by_id(self.session.novel_id)

        # 生成下一幕规划
        act_plan = await self._generate_act_plan(
            act_number=next_act_num,
            novel_premise=novel.premise or "一个关于命运与选择的奇幻故事",
            previous_acts=self.session.acts
        )

        self.session.acts.append(act_plan)
        logger.info(f"✓ 第 {next_act_num} 幕规划完成：{len(act_plan.chapters)} 个章节")

        # 转换状态
        self.session.state = AutopilotState.WRITING

    async def _generate_act_plan(
        self,
        act_number: int,
        novel_premise: str,
        previous_acts: List[ActPlan]
    ) -> ActPlan:
        """生成幕级规划

        Args:
            act_number: 幕号
            novel_premise: 小说前提
            previous_acts: 之前的幕规划

        Returns:
            ActPlan: 幕级规划
        """
        # 构建上下文
        context = f"小说前提：{novel_premise}\n\n"

        if previous_acts:
            context += "已完成的幕：\n"
            for act in previous_acts:
                context += f"\n第{act.act_number}幕：{act.title}\n"
                for i, chapter in enumerate(act.chapters, 1):
                    context += f"  第{i}章：{chapter}\n"

        # 生成规划
        prompt = Prompt(
            system=f"""你是一位资深网文编剧，擅长三幕式结构。

当前任务：为第 {act_number} 幕生成 {self.session.chapters_per_act} 个章节大纲。

要求：
1. 每章大纲 50-80 字，包含：场景、冲突、转折
2. 章节之间有因果关系，不能跳跃
3. 标注伏笔埋设点【伏笔】和回收点
4. 符合三幕式结构：
   - 第一幕：建立世界观，引入冲突
   - 第二幕：冲突升级，主角成长
   - 第三幕：高潮对决，主题升华

输出格式：
第X章：标题** - 大纲内容（50-80字）。【伏笔：xxx】
""",
            user=f"""{context}

请生成第 {act_number} 幕的 {self.session.chapters_per_act} 个章节大纲："""
        )

        config = GenerationConfig(max_tokens=2000, temperature=0.8)
        result = await self.llm_service.generate(prompt, config)

        # 解析章节大纲
        chapters = self._parse_chapter_outlines(result.content)

        return ActPlan(
            act_number=act_number,
            title=f"第{act_number}幕",
            chapters=chapters
        )

    async def _generate_chapter_content(
        self,
        chapter_num: int,
        outline: str,
        recent_chapters: List[Dict[str, Any]]
    ) -> str:
        """生成章节内容（使用节拍放大器）

        Args:
            chapter_num: 章节号
            outline: 章节大纲
            recent_chapters: 最近章节

        Returns:
            str: 章节内容
        """
        # 使用节拍放大器拆分大纲
        if self.context_builder:
            beats = self.context_builder.magnify_outline_to_beats(outline, target_chapter_words=2500)
            logger.info(f"节拍放大器：拆分为 {len(beats)} 个节拍")
        else:
            # 降级：不使用节拍放大器
            beats = []

        # 构建上下文
        recent_context = ""
        if recent_chapters:
            recent_context = "\n【最近章节摘要】\n"
            for ch in recent_chapters:
                recent_context += f"第{ch['chapter_number']}章：{ch['content'][:200]}...\n\n"

        # 如果有节拍，逐节拍生成
        if beats:
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
                    user=f"""{recent_context}

【章节大纲】
{outline}

{beat_prompt_text}

开始撰写这个节拍："""
                )

                config = GenerationConfig(max_tokens=int(beat.target_words * 1.5), temperature=0.8)

                # 使用流式生成避免 502 超时
                beat_content = ""
                async for chunk in self.llm_service.stream_generate(prompt, config):
                    beat_content += chunk

                chapter_content += beat_content + "\n\n"
                logger.info(f"  节拍 {i+1}/{len(beats)} 完成：{len(beat_content)} 字")

            return chapter_content.strip()

        else:
            # 降级：不使用节拍放大器，直接生成
            prompt = Prompt(
                system="""你是一位资深网文作家，擅长写爽文。

写作要求：
1. 2000-2500 字（使用流式生成避免超时）
2. 必须有对话和人物互动
3. 保持人物性格一致
4. 如果有【伏笔】标记，自然地埋设伏笔
5. 增加感官细节：视觉、听觉、触觉、情绪
6. 节奏控制：不要一章推进太多剧情""",
                user=f"""{recent_context}

【本章大纲】
{outline}

开始撰写："""
            )

            config = GenerationConfig(max_tokens=3000, temperature=0.8)

            # 使用流式生成避免 502 超时
            content = ""
            async for chunk in self.llm_service.stream_generate(prompt, config):
                content += chunk

            return content

    def _parse_chapter_outlines(self, text: str) -> List[str]:
        """解析章节大纲

        Args:
            text: LLM 生成的文本

        Returns:
            List[str]: 章节大纲列表
        """
        lines = text.strip().split('\n')
        chapters = []

        for line in lines:
            line = line.strip()
            if line.startswith('第') and '章' in line:
                # 提取大纲内容
                if '**' in line:
                    # 格式：第X章：标题** - 大纲内容
                    parts = line.split('**', 1)
                    if len(parts) > 1:
                        outline = parts[1].strip().lstrip('- ').strip()
                        chapters.append(outline)
                else:
                    # 格式：第X章：大纲内容
                    parts = line.split('：', 1)
                    if len(parts) > 1:
                        outline = parts[1].strip()
                        chapters.append(outline)

        return chapters[:self.session.chapters_per_act]  # 限制数量
