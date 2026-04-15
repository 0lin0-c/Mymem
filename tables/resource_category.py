# 🔗 记忆来源关联表：记录原子化记忆与对话摘要的关系
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tables.base import Base


class ResourceCategory(Base):
    """记忆来源关联表

    记录原子化记忆（Category）与对话摘要（Resource）之间的关系：
    - 一条 Category 可能被多个 Resource 提及/更新
    - 一个 Resource 可能提取出多条 Category

    关联类型：
    - created: 该 Resource 首次创建了这个原子化记忆
    - updated: 该 Resource 更新了这个原子化记忆

    重复提及的处理：直接增加 Category.importance_score，不创建新的关联记录
    """

    __tablename__ = "resource_categories"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    resource_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("resources.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="对话摘要 ID",
    )
    category_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("categories.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="原子化记忆 ID",
    )
    relation_type: Mapped[str] = mapped_column(
        String(20),
        default="created",
        nullable=False,
        comment="关联类型：created/updated",
    )
    note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="关联说明（可选）",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # 关联关系
    resource: Mapped["Resource"] = relationship(
        "Resource",
        back_populates="resource_categories",
    )
    category: Mapped["Category"] = relationship(
        "Category",
        back_populates="resource_categories",
    )

    def __repr__(self) -> str:
        return f"<ResourceCategory(resource_id={self.resource_id}, category_id={self.category_id}, type={self.relation_type})>"
