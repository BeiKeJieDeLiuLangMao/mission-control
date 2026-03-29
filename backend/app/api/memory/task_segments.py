"""
Task Segment API — 任务分段查询端点。

提供 TaskSegment 的列表、详情、统计查询。
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlmodel import col
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.session import get_session
from app.memory.models import TaskSegment, Turn, VectorMemory
from app.memory.schemas import (
    MemoryItem,
    TaskSegmentDetail,
    TaskSegmentItem,
    TaskSegmentListResponse,
    TaskSegmentStats,
    TurnItem,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory/tasks", tags=["memory-tasks"])


def _segment_to_item(seg: TaskSegment) -> TaskSegmentItem:
    """TaskSegment ORM → TaskSegmentItem schema."""
    return TaskSegmentItem(
        id=seg.id,
        session_id=seg.session_id,
        user_id=seg.user_id,
        agent_id=seg.agent_id,
        goal=seg.goal,
        status=seg.status,
        outcome=seg.outcome,
        task_type=seg.task_type,
        turn_ids=seg.turn_ids or [],
        first_turn_at=seg.first_turn_at.isoformat() if seg.first_turn_at else None,
        last_turn_at=seg.last_turn_at.isoformat() if seg.last_turn_at else None,
        segmentation_confidence=seg.segmentation_confidence,
        event_time=seg.event_time.isoformat() if seg.event_time else None,
        created_at=seg.created_at.isoformat() if seg.created_at else None,
    )


def _turn_to_item(turn: Turn) -> TurnItem:
    """Turn ORM → TurnItem schema."""
    return TurnItem(
        id=turn.id,
        session_id=turn.session_id,
        user_id=turn.user_id,
        agent_id=turn.agent_id,
        source=turn.source,
        processing_status=turn.processing_status,
        message_count=len(turn.messages) if turn.messages else 0,
        created_at=turn.created_at.isoformat() if turn.created_at else None,
    )


def _vm_to_memory_item(vm: VectorMemory) -> MemoryItem:
    """VectorMemory ORM → MemoryItem schema."""
    return MemoryItem(
        id=vm.id,
        content=vm.content,
        memory_type=vm.memory_type,
        memory_subtype=vm.memory_subtype,
        task_segment_id=vm.task_segment_id,
        turn_id=vm.turn_id,
        agent_id=vm.agent_id,
        source=vm.source,
        created_at=vm.created_at.isoformat() if vm.created_at else None,
    )


@router.get("/", response_model=TaskSegmentListResponse)
async def list_task_segments(
    user_id: str = Query(...),
    session_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    task_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    """列出任务分段。"""
    stmt = select(TaskSegment).where(col(TaskSegment.user_id) == user_id)

    if session_id:
        stmt = stmt.where(col(TaskSegment.session_id) == session_id)
    if status:
        stmt = stmt.where(col(TaskSegment.status) == status)
    if task_type:
        stmt = stmt.where(col(TaskSegment.task_type) == task_type)

    # Count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    count_result = await session.execute(count_stmt)
    total = count_result.scalar_one()

    # Paginate
    stmt = stmt.order_by(col(TaskSegment.created_at).desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    segments = result.scalars().all()

    return TaskSegmentListResponse(
        items=[_segment_to_item(s) for s in segments],
        total=total,
    )


@router.get("/stats", response_model=TaskSegmentStats)
async def get_task_segment_stats(
    user_id: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """获取任务分段统计。"""
    # Total
    total_stmt = (
        select(func.count()).select_from(TaskSegment).where(col(TaskSegment.user_id) == user_id)
    )
    total_result = await session.execute(total_stmt)
    total = total_result.scalar_one()

    # By status
    status_stmt = (
        select(TaskSegment.status, func.count().label("cnt"))
        .where(col(TaskSegment.user_id) == user_id)
        .group_by(TaskSegment.status)
    )
    status_result = await session.execute(status_stmt)
    by_status = {row[0]: row[1] for row in status_result.all()}

    # By task_type
    type_stmt = (
        select(TaskSegment.task_type, func.count().label("cnt"))
        .where(col(TaskSegment.user_id) == user_id)
        .where(col(TaskSegment.task_type).is_not(None))
        .group_by(TaskSegment.task_type)
    )
    type_result = await session.execute(type_stmt)
    by_task_type = {row[0]: row[1] for row in type_result.all()}

    return TaskSegmentStats(total=total, by_status=by_status, by_task_type=by_task_type)


@router.get("/{segment_id}", response_model=TaskSegmentDetail)
async def get_task_segment_detail(
    segment_id: str,
    session: AsyncSession = Depends(get_session),
):
    """获取单个任务分段详情，含关联 turns 和 memories。"""
    # Fetch segment
    stmt = select(TaskSegment).where(col(TaskSegment.id) == segment_id)
    result = await session.execute(stmt)
    segment = result.scalar_one_or_none()

    if not segment:
        raise HTTPException(status_code=404, detail="Task segment not found")

    segment_item = _segment_to_item(segment)

    # Fetch related turns
    turns: list[TurnItem] = []
    if segment.turn_ids:
        turns_stmt = select(Turn).where(col(Turn.id).in_(segment.turn_ids))
        turns_result = await session.execute(turns_stmt)
        turns = [_turn_to_item(t) for t in turns_result.scalars().all()]

    # Fetch related memories (via turn_ids)
    memories: list[MemoryItem] = []
    if segment.turn_ids:
        mem_stmt = select(VectorMemory).where(col(VectorMemory.turn_id).in_(segment.turn_ids))
        mem_result = await session.execute(mem_stmt)
        memories = [_vm_to_memory_item(vm) for vm in mem_result.scalars().all()]

    return TaskSegmentDetail(
        segment=segment_item,
        turns=turns,
        memories=memories,
    )
