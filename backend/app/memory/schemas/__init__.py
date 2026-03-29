"""
Memory schemas for v2 API.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class TurnStoreRequest(BaseModel):
    """Turn 存储请求"""

    user_id: str = Field(..., min_length=1, description="用户标识")
    session_id: str = Field(..., min_length=1, description="会话 ID")
    agent_id: str = Field(..., min_length=1, description="Agent 标识")
    messages: List[dict] = Field(..., min_length=1, description="对话消息 [{role, content}]")
    source: str = Field(..., min_length=1, description="调用来源")


class TurnStoreResponse(BaseModel):
    """Turn 存储响应 - 只返回成功/失败"""

    success: bool
    turn_id: Optional[str] = None
    message: Optional[str] = None


class MemoryItem(BaseModel):
    """记忆条目"""

    id: str
    content: str = Field(..., description="记忆内容")
    memory_type: str = Field(..., description="fact/summary/task_fact/correction/procedure")
    score: Optional[float] = Field(None, description="向量搜索相似度分数")
    memory_subtype: Optional[str] = Field(
        None, description="goal/outcome/correction/procedure/decision"
    )
    task_segment_id: Optional[str] = None
    turn_id: Optional[str] = None
    agent_id: Optional[str] = None
    source: Optional[str] = None
    session_id: Optional[str] = None
    categories: List[str] = Field(default_factory=list)
    created_at: Optional[str] = None


class MemorySearchResponse(BaseModel):
    """记忆搜索响应"""

    items: List[MemoryItem]
    total: int


class MemoryListResponse(BaseModel):
    """记忆列表响应"""

    items: List[MemoryItem]
    total: int
    page: int
    size: int


class TaskSegmentItem(BaseModel):
    """任务分段条目"""

    id: str
    session_id: str
    user_id: str
    agent_id: str
    goal: str
    status: str = "unknown"
    outcome: Optional[str] = None
    task_type: Optional[str] = None
    turn_ids: List[str] = Field(default_factory=list)
    first_turn_at: Optional[str] = None
    last_turn_at: Optional[str] = None
    segmentation_confidence: float = 0.0
    event_time: Optional[str] = None
    created_at: Optional[str] = None
