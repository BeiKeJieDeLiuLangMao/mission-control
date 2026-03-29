"""
Intelligent Recall API — POST /api/v2/recall

三阶段并发召回：Query Analysis → Parallel Assembly → Merge/Rank/Format。
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.memory.services.recall_orchestrator import recall

logger = logging.getLogger(__name__)

router = APIRouter(tags=["memory-recall"])


class RecallRequest(BaseModel):
    """召回请求。"""

    user_id: str = Field(..., min_length=1, description="User identifier")
    query: str = Field(..., min_length=1, description="Search query")
    agent_id: Optional[str] = Field(None, description="Filter by agent_id")
    context_budget_tokens: Optional[int] = Field(
        None, ge=100, le=10000, description="Max tokens for context (default 2000)"
    )
    timeout_ms: Optional[int] = Field(
        None, ge=1000, le=30000, description="Total timeout in ms (default 5000)"
    )


class RecallResponse(BaseModel):
    """召回响应。"""

    context_text: str = Field(..., description="Formatted context text for agent injection")
    sources: list[dict[str, Any]] = Field(default_factory=list, description="Per-source summaries")
    query_analysis: dict[str, Any] = Field(
        default_factory=dict, description="Query intent/entities/complexity"
    )
    timing: dict[str, Any] = Field(default_factory=dict, description="Per-stage timing in ms")


@router.post("/recall", response_model=RecallResponse)
async def recall_endpoint(request: RecallRequest) -> RecallResponse:
    """智能并发召回。

    三阶段：
    1. Query Analysis (regex, <100ms)
    2. Parallel Context Assembly (Qdrant + Neo4j + corrections, per-source timeout)
    3. Merge + Rank + Format (memory, <100ms)
    """
    result = await recall(
        query=request.query,
        user_id=request.user_id,
        agent_id=request.agent_id,
        context_budget_tokens=request.context_budget_tokens,
        timeout_ms=request.timeout_ms,
    )

    return RecallResponse(
        context_text=result.context_text,
        sources=result.sources,
        query_analysis=result.query_analysis,
        timing=result.timing,
    )
