"""
Memory models for Turn and VectorMemory storage.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlmodel import JSON, Field, SQLModel

from app.models.base import QueryModel


def get_current_utc_time() -> datetime:
    """Get current UTC time"""
    return datetime.now()


def generate_uuid_str() -> str:
    """Generate UUID as string"""
    return str(uuid4())


class Turn(QueryModel, table=True):
    """存储原始对话 turn（用户-模型的完整交互）"""

    __tablename__ = "turns"  # pyright: ignore[reportAssignmentType]

    id: str = Field(default_factory=generate_uuid_str, primary_key=True)
    session_id: str = Field(nullable=False, index=True)
    user_id: str = Field(nullable=False, index=True)
    agent_id: str = Field(nullable=False, index=True)  # 必填
    messages: list[dict] = Field(default_factory=list, sa_type=JSON, nullable=False)
    source: str = Field(nullable=False)  # 必填
    created_at: datetime = Field(default_factory=get_current_utc_time, index=True)
    processing_status: str = Field(
        default="pending", index=True
    )  # pending/processing/completed/failed


class VectorMemory(QueryModel, table=True):
    """冗余表：统一存储记忆（来自 Qdrant）"""

    __tablename__ = "vector_memories"  # pyright: ignore[reportAssignmentType]

    id: str = Field(default_factory=generate_uuid_str, primary_key=True)
    qdrant_id: str = Field(nullable=False, unique=True, index=True)  # Qdrant point ID
    user_id: str = Field(nullable=False, index=True)
    agent_id: str | None = Field(default=None, index=True)
    turn_id: str | None = Field(default=None, index=True)
    content: str = Field(nullable=False)
    memory_type: str = Field(
        nullable=False, index=True
    )  # fact/summary/task_fact/correction/procedure
    source: str | None = Field(default=None)
    task_segment_id: str | None = Field(default=None, index=True)
    memory_subtype: str | None = Field(
        default=None, index=True
    )  # goal/outcome/correction/procedure/decision
    created_at: datetime = Field(default_factory=get_current_utc_time, index=True)
    updated_at: datetime | None = Field(default=None)


class TaskSegment(QueryModel, table=True):
    """任务分段：将 session 中的 turns 按任务边界分组"""

    __tablename__ = "task_segments"  # pyright: ignore[reportAssignmentType]

    id: str = Field(default_factory=generate_uuid_str, primary_key=True)
    session_id: str = Field(nullable=False, index=True)
    user_id: str = Field(nullable=False, index=True)
    agent_id: str = Field(nullable=False)
    goal: str = Field(nullable=False)  # LLM/启发式提取的任务目标
    status: str = Field(default="unknown")  # succeeded/failed/abandoned/unknown
    outcome: str | None = Field(default=None)
    task_type: str | None = Field(default=None)  # bug_fix/feature/refactor/question/config
    turn_ids: list[str] = Field(default_factory=list, sa_type=JSON, nullable=False)
    first_turn_at: datetime = Field(nullable=False)
    last_turn_at: datetime = Field(nullable=False)
    segmentation_confidence: float = Field(default=0.0)
    event_time: datetime = Field(nullable=False)  # 双时态：事件发生时间
    ingestion_time: datetime = Field(default_factory=get_current_utc_time)
    created_at: datetime = Field(default_factory=get_current_utc_time)
