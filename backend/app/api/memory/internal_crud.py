"""
Memory API router (v2).

简化的记忆 API：
- GET /: 列出记忆
- GET /search: 搜索记忆 (优先 Qdrant 向量搜索，SQL LIKE 作 fallback)
"""

import asyncio
import logging
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.session import get_session
from app.memory.models import VectorMemory
from app.memory.schemas import MemoryItem, MemoryListResponse, MemorySearchResponse
from app.memory.services.client_factory import get_memory_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory/memories", tags=["memory-memories"])


async def _vm_to_memory_item(vm: VectorMemory) -> MemoryItem:
    """将 VectorMemory 转换为 MemoryItem"""
    return MemoryItem(
        id=vm.qdrant_id,
        content=vm.content,
        memory_type=vm.memory_type,
        memory_subtype=vm.memory_subtype,
        task_segment_id=vm.task_segment_id,
        turn_id=vm.turn_id,
        agent_id=vm.agent_id,
        source=vm.source,
        created_at=vm.created_at.isoformat() if vm.created_at else None,
    )


@router.get("/", response_model=MemoryListResponse)
async def list_memories(
    user_id: str = Query(..., description="User identifier"),
    agent_id: Optional[str] = Query(None, description="Filter by agent_id"),
    memory_type: Optional[str] = Query(None, description="Filter by memory_type: summary or fact"),
    turn_id: Optional[str] = Query(None, description="Filter by turn_id"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    """列出记忆"""
    statement = select(VectorMemory).where(VectorMemory.user_id == user_id)

    if agent_id:
        statement = statement.where(VectorMemory.agent_id == agent_id)
    if memory_type:
        statement = statement.where(VectorMemory.memory_type == memory_type)
    if turn_id:
        statement = statement.where(VectorMemory.turn_id == turn_id)

    # Count total
    count_statement = statement
    total_result = await session.exec(count_statement)
    memories_list = total_result.all()
    total = len(memories_list)

    # Paginate
    statement = statement.order_by(col(VectorMemory.created_at).desc()).offset(offset).limit(limit)
    result = await session.exec(statement)
    results = result.all()

    return MemoryListResponse(
        items=[await _vm_to_memory_item(vm) for vm in results],
        total=total,
        page=(offset // limit) + 1 if limit > 0 else 1,
        size=limit,
    )


def _vector_search(
    query: str,
    user_id: str,
    agent_id: Optional[str],
    limit: int,
) -> list[dict[str, Any]]:
    """同步调用 mem0 Memory.search() 进行 Qdrant 向量搜索。

    此函数在 ThreadPoolExecutor 中运行，不阻塞 async 事件循环。
    """
    memory_client = get_memory_client()
    if not memory_client:
        raise RuntimeError("Memory client unavailable")

    response: dict[str, Any] = memory_client.search(
        query,
        user_id=user_id,
        agent_id=agent_id,
        limit=limit,
    )
    results: list[dict[str, Any]] = response.get("results", [])
    return results


def _mem0_result_to_memory_item(item: dict[str, Any]) -> MemoryItem:
    """将 mem0 search 结果映射为 MemoryItem schema。"""
    metadata: dict[str, Any] = item.get("metadata", {}) or {}
    return MemoryItem(
        id=str(item.get("id", "")),
        content=str(item.get("memory", "")),
        memory_type=str(metadata.get("memory_type", "fact")),
        score=item.get("score"),
        memory_subtype=metadata.get("memory_subtype"),
        task_segment_id=metadata.get("task_segment_id"),
        turn_id=metadata.get("turn_id"),
        agent_id=item.get("agent_id") or metadata.get("agent_id"),
        source=metadata.get("source"),
        created_at=item.get("created_at"),
    )


@router.get("/search", response_model=MemorySearchResponse)
async def search_memories(
    user_id: str = Query(..., description="User identifier"),
    query: str = Query(..., description="Search query"),
    agent_id: Optional[str] = Query(None, description="Filter by agent_id"),
    memory_type: Optional[str] = Query(None, description="Filter by memory_type"),
    limit: int = Query(10, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """
    搜索记忆（优先 Qdrant 向量搜索，SQL LIKE 作 fallback）
    """
    # 优先: Qdrant 向量语义搜索
    try:
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(
            None,
            _vector_search,
            query,
            user_id,
            agent_id,
            limit,
        )

        # memory_type 过滤（Qdrant 不直接支持按 metadata.memory_type 过滤）
        if memory_type:
            results = [
                r for r in results if r.get("metadata", {}).get("memory_type") == memory_type
            ]

        items = [_mem0_result_to_memory_item(r) for r in results[:limit]]
        return MemorySearchResponse(items=items, total=len(items))

    except Exception as e:
        logger.warning(f"Vector search failed, falling back to SQL LIKE: {e}")

    # Fallback: SQL 关键词子串匹配
    statement = select(VectorMemory).where(VectorMemory.user_id == user_id)

    if agent_id:
        statement = statement.where(VectorMemory.agent_id == agent_id)
    if memory_type:
        statement = statement.where(VectorMemory.memory_type == memory_type)

    statement = statement.where(col(VectorMemory.content).contains(query))

    count_statement = statement
    total_result = await session.exec(count_statement)
    memories_list = total_result.all()
    total = len(memories_list)

    statement = statement.order_by(col(VectorMemory.created_at).desc()).limit(limit)
    result = await session.exec(statement)
    results_db = result.all()

    return MemorySearchResponse(
        items=[await _vm_to_memory_item(vm) for vm in results_db],
        total=total,
    )


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str, session: Annotated[AsyncSession, Depends(get_session)]):
    """删除记忆"""
    statement = select(VectorMemory).where(VectorMemory.qdrant_id == memory_id)
    result = await session.exec(statement)
    vm = result.first()
    if not vm:
        raise HTTPException(status_code=404, detail="Memory not found")

    try:
        await session.delete(vm)
        await session.commit()
        return {"status": "deleted", "id": memory_id}
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to delete memory: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete memory: {e}")
