"""SQLite Novel Repository 实现"""
import logging
from typing import Optional, List
from datetime import datetime
from domain.novel.entities.novel import Novel, AutopilotStatus, NovelStage
from domain.novel.value_objects.novel_id import NovelId
from domain.novel.repositories.novel_repository import NovelRepository
from infrastructure.persistence.database.connection import DatabaseConnection

logger = logging.getLogger(__name__)


class SqliteNovelRepository(NovelRepository):
    """SQLite Novel Repository 实现"""

    def __init__(self, db: DatabaseConnection):
        self.db = db

    def save(self, novel: Novel) -> None:
        """保存小说"""
        sql = """
            INSERT INTO novels (id, title, slug, author, target_chapters, premise, autopilot_status, current_stage, current_act, current_chapter_in_act, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                slug = excluded.slug,
                author = excluded.author,
                target_chapters = excluded.target_chapters,
                premise = excluded.premise,
                autopilot_status = excluded.autopilot_status,
                current_stage = excluded.current_stage,
                current_act = excluded.current_act,
                current_chapter_in_act = excluded.current_chapter_in_act,
                updated_at = excluded.updated_at
        """
        now = datetime.utcnow().isoformat()
        novel_id = novel.novel_id.value if hasattr(novel, 'novel_id') else novel.id
        slug = novel_id  # 使用 novel_id 作为唯一 slug
        premise = getattr(novel, 'premise', '')
        author = getattr(novel, 'author', '未知作者')
        autopilot_status = getattr(novel, 'autopilot_status', 'stopped')
        current_stage = getattr(novel, 'current_stage', 'planning')
        current_act = getattr(novel, 'current_act', 0)
        current_chapter_in_act = getattr(novel, 'current_chapter_in_act', 0)

        self.db.execute(sql, (
            novel_id,
            novel.title,
            slug,
            author,
            novel.target_chapters,
            premise,
            autopilot_status,
            current_stage,
            current_act,
            current_chapter_in_act,
            now,
            now
        ))
        self.db.get_connection().commit()

    async def async_save(self, novel: Novel) -> None:
        """异步保存小说（守护进程使用）"""
        # SQLite 是同步的，直接调用 save
        self.save(novel)

    def get_by_id(self, novel_id: NovelId) -> Optional[Novel]:
        """根据 ID 获取小说"""
        sql = "SELECT * FROM novels WHERE id = ?"
        row = self.db.fetch_one(sql, (novel_id.value,))

        if not row:
            return None

        # 转换枚举类型
        autopilot_status = AutopilotStatus(row.get('autopilot_status', 'idle'))
        current_stage = NovelStage(row.get('current_stage', 'macro_planning'))

        return Novel(
            id=novel_id,
            title=row['title'],
            author=row.get('author', '未知作者'),
            target_chapters=row['target_chapters'],
            premise=row.get('premise', ''),
            autopilot_status=autopilot_status,
            current_stage=current_stage,
            current_act=row.get('current_act', 0),
            current_chapter_in_act=row.get('current_chapter_in_act', 0)
        )

    def get_by_slug(self, slug: str) -> Optional[Novel]:
        """根据 slug 获取小说"""
        sql = "SELECT * FROM novels WHERE slug = ?"
        row = self.db.fetch_one(sql, (slug,))

        if not row:
            return None

        from domain.novel.value_objects.novel_id import NovelId

        # 转换枚举类型
        autopilot_status = AutopilotStatus(row.get('autopilot_status', 'idle'))
        current_stage = NovelStage(row.get('current_stage', 'macro_planning'))

        return Novel(
            id=NovelId(row['id']),
            title=row['title'],
            author=row.get('author', '未知作者'),
            target_chapters=row['target_chapters'],
            premise=row.get('premise', ''),
            autopilot_status=autopilot_status,
            current_stage=current_stage,
            current_act=row.get('current_act', 0),
            current_chapter_in_act=row.get('current_chapter_in_act', 0)
        )

    def list_all(self) -> List[Novel]:
        """列出所有小说"""
        sql = "SELECT * FROM novels ORDER BY created_at DESC"
        rows = self.db.fetch_all(sql)

        from domain.novel.value_objects.novel_id import NovelId
        return [
            Novel(
                id=NovelId(row['id']),
                title=row['title'],
                author=row.get('author', '未知作者'),
                target_chapters=row['target_chapters'],
                premise=row.get('premise', ''),
                autopilot_status=AutopilotStatus(row.get('autopilot_status', 'idle')),
                current_stage=NovelStage(row.get('current_stage', 'macro_planning')),
                current_act=row.get('current_act', 0),
                current_chapter_in_act=row.get('current_chapter_in_act', 0)
            )
            for row in rows
        ]

    def find_by_autopilot_status(self, status: str) -> List[Novel]:
        """根据自动驾驶状态查找小说列表"""
        sql = "SELECT * FROM novels WHERE autopilot_status = ? ORDER BY updated_at DESC"
        rows = self.db.fetch_all(sql, (status,))

        from domain.novel.value_objects.novel_id import NovelId
        return [
            Novel(
                id=NovelId(row['id']),
                title=row['title'],
                author=row.get('author', '未知作者'),
                target_chapters=row['target_chapters'],
                premise=row.get('premise', ''),
                autopilot_status=AutopilotStatus(row.get('autopilot_status', 'idle')),
                current_stage=NovelStage(row.get('current_stage', 'macro_planning')),
                current_act=row.get('current_act', 0),
                current_chapter_in_act=row.get('current_chapter_in_act', 0)
            )
            for row in rows
        ]

    def delete(self, novel_id: NovelId) -> None:
        """删除小说（级联删除所有关联数据）"""
        sql = "DELETE FROM novels WHERE id = ?"
        self.db.execute(sql, (novel_id.value,))
        self.db.get_connection().commit()
        logger.info(f"Deleted novel: {novel_id.value}")

    def exists(self, novel_id: NovelId) -> bool:
        """检查小说是否存在"""
        sql = "SELECT 1 FROM novels WHERE id = ? LIMIT 1"
        row = self.db.fetch_one(sql, (novel_id.value,))
        return row is not None
