# 🧠 原子化记忆表：存储从对话中提取的原子化信息
from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.config import settings
from tables.base import Base


class Category(Base):
    """原子化记忆表

    存储从对话摘要中提取的原子化信息。
    每条记录属于一个固定的分类（核心自我/情景时间轴/语义知识库/社交关系图谱/动态分类1/动态分类2）。
    每条信息有独立的重要性评分。

    与 Resource 的关系：
    - 通过 resource_categories 关联表记录来源
    - 一条 Category 可能被多个 Resource 提及/更新
    """

    __tablename__ = "categories"

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
    category_name: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
        comment="归属的分类名（核心自我/情景时间轴/语义知识库/社交关系图谱/动态分类）",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="原子化的记忆内容（一条独立的信息）",
    )
    content_vector: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dimensions),
        nullable=True,
        comment="记忆内容的向量嵌入，用于 Category 层向量检索",
    )
    importance_score: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
        comment="该条信息的重要性评分 (1-10)",
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
    user: Mapped["User"] = relationship("User", back_populates="categories")
    resource_categories: Mapped[list["ResourceCategory"]] = relationship(
        "ResourceCategory",
        back_populates="category",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Category(id={self.id}, category={self.category_name}, content={self.content[:30]}...)>"
