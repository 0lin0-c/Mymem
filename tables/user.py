# 👤 用户表：存储账号信息和全局人设
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tables.base import Base


class User(Base):
    """用户表

    系统的全局配置锚点，实现用户数据和人设的绝对物理隔离。
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    username: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="用户登录密码（存储哈希值）",
    )
    user_prompt_template: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="用户的全局客观画像（替代 USER.md）",
    )
    agent_persona_template: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="助手的性格、语气指令（替代 SOUL.md）",
    )
    # LLM 配置（用户级）
    llm_provider: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="LLM 提供商: openai/deepseek/qwen/glm/anthropic/custom",
    )
    llm_api_key: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="LLM API Key",
    )
    llm_base_url: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="LLM API Base URL",
    )
    llm_model: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="LLM 模型名称",
    )
    llm_warmed_up: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        comment="LLM 是否已预热",
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
    )

    # 关联关系
    categories: Mapped[list["Category"]] = relationship(
        "Category",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    resources: Mapped[list["Resource"]] = relationship(
        "Resource",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username})>"
