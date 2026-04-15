# 🪨 对话摘要表：存储对话粒度的综合摘要
from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.config import settings
from tables.base import Base


class Resource(Base):
    """对话摘要表

    存储对话粒度的综合摘要（如 5 轮对话的总结）。
    每条记录对应一次对话交互。
    原子化信息存储在 Category 表中，通过 resource_categories 关联表追踪来源。
    """

    __tablename__ = "resources"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    modality: Mapped[str] = mapped_column(
        String(50),
        default="text",
        nullable=False,
        comment="多模态扩展预留：text/image/audio",
    )
    raw_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="用户输入的原始文本（防篡改底稿）",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="对话的综合摘要（LLM 生成的客观描述）",
    )
    assistant_response: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="AI 助手的回复摘要",
    )
    description_vector: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dimensions),
        nullable=True,
        comment="综合摘要的向量，用于语义检索",
    )
    importance_score: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
        comment="对综合摘要的整体重要性评分 (1-10)",
    )
    access_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="被检索引用的次数，用于检索分数的访问加成",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间，用于检索分数的时间衰减计算",
    )

    # 关联关系
    user: Mapped["User"] = relationship("User", back_populates="resources")
    # 关联到从此摘要提取的原子化信息
    resource_categories: Mapped[list["ResourceCategory"]] = relationship(
        "ResourceCategory",
        back_populates="resource",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Resource(id={self.id}, modality={self.modality})>"
