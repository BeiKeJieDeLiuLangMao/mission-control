"""
Task Segmenter: 将 session 中的 turns 按任务边界分组。

支持两种模式：
1. 启发式分段（默认）：基于时间间隔、信号词、agent_id 变化
2. LLM 增强分段（可选）：TASK_SEGMENTER_USE_LLM=true
"""

from __future__ import annotations

import logging
import re
from datetime import timedelta
from typing import TYPE_CHECKING

from app.memory.models import TaskSegment, Turn
from app.memory.services.client_factory import get_memory_client

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# 任务切换信号词 (中英文)
_TASK_SWITCH_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"接下来|换个|下一个|新任务|另外|还有一个", re.IGNORECASE),
    re.compile(r"next task|new task|switch to|moving on|let'?s move", re.IGNORECASE),
    re.compile(r"^/\w+", re.MULTILINE),  # slash command 通常表示新意图
]

# 时间间隔阈值（30 分钟）
_TIME_GAP_THRESHOLD = timedelta(minutes=30)


def _extract_user_text(turn: Turn) -> str:
    """从 turn 的 messages 中提取用户消息文本。"""
    parts: list[str] = []
    for msg in turn.messages:
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
    return "\n".join(parts)


def _has_task_switch_signal(text: str) -> bool:
    """检测文本是否包含任务切换信号词。"""
    return any(p.search(text) for p in _TASK_SWITCH_PATTERNS)


def _summarize_goal(turns: list[Turn]) -> str:
    """从 turn 组的第一条用户消息提取简短目标描述。"""
    for turn in turns:
        text = _extract_user_text(turn)
        if text.strip():
            # 取前 200 字符作为目标
            return text.strip()[:200]
    return "Unknown task"


def segment_turns_heuristic(turns: list[Turn]) -> list[TaskSegment]:
    """启发式任务分段。

    分段规则（按优先级）：
    1. agent_id 变化 → 新任务
    2. 时间间隔 > 30min → 新任务
    3. 用户消息包含任务切换信号词 → 新任务

    Args:
        turns: 同一 session 的 turns，按 created_at 升序排列

    Returns:
        TaskSegment 列表（未持久化，需要调用方写入 DB）
    """
    if not turns:
        return []

    segments: list[TaskSegment] = []
    current_group: list[Turn] = [turns[0]]

    for i in range(1, len(turns)):
        prev = turns[i - 1]
        curr = turns[i]
        should_split = False

        # Rule 1: agent_id 变化
        if curr.agent_id != prev.agent_id:
            should_split = True

        # Rule 2: 时间间隔
        if curr.created_at and prev.created_at:
            gap = curr.created_at - prev.created_at
            if gap > _TIME_GAP_THRESHOLD:
                should_split = True

        # Rule 3: 信号词
        if not should_split:
            user_text = _extract_user_text(curr)
            if user_text and _has_task_switch_signal(user_text):
                should_split = True

        if should_split:
            segments.append(_build_segment(current_group))
            current_group = [curr]
        else:
            current_group.append(curr)

    # 最后一组
    if current_group:
        segments.append(_build_segment(current_group))

    return segments


def _build_segment(turns: list[Turn]) -> TaskSegment:
    """从 turn 组构建 TaskSegment。"""
    first = turns[0]
    last = turns[-1]

    return TaskSegment(
        session_id=first.session_id,
        user_id=first.user_id,
        agent_id=first.agent_id,
        goal=_summarize_goal(turns),
        status="unknown",
        turn_ids=[str(t.id) for t in turns],
        first_turn_at=first.created_at,
        last_turn_at=last.created_at,
        segmentation_confidence=0.6,  # 启发式的基础置信度
        event_time=first.created_at,
    )


async def segment_turns_llm(turns: list[Turn]) -> list[TaskSegment]:
    """LLM 增强任务分段（可选）。

    将 session 的 turn 摘要发给 LLM，请求输出结构化的任务边界。
    失败时回退到启发式分段。
    """
    memory_client = get_memory_client()
    if not memory_client:
        logger.warning("Memory client unavailable, falling back to heuristic segmentation")
        return segment_turns_heuristic(turns)

    try:
        # 构建摘要文本
        summary_lines: list[str] = []
        for i, turn in enumerate(turns):
            user_text = _extract_user_text(turn)
            if user_text:
                preview = user_text[:150].replace("\n", " ")
                ts = turn.created_at.isoformat() if turn.created_at else "?"
                summary_lines.append(f"[Turn {i}, {ts}, agent={turn.agent_id}] {preview}")

        if not summary_lines:
            return segment_turns_heuristic(turns)

        # TODO: Send summary_lines to LLM for structured task boundary extraction
        # For now, fall back to heuristic
        logger.info("LLM task segmentation not yet fully implemented, using heuristic")
        return segment_turns_heuristic(turns)

    except Exception as e:
        logger.warning(f"LLM segmentation failed, falling back to heuristic: {e}")
        return segment_turns_heuristic(turns)
