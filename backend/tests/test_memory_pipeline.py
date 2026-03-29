# ruff: noqa: INP001
"""Comprehensive unit tests for the MC Memory Worker pipeline.

Covers Phase 1-4 features:
1. detect_memory_type() — correction/procedure/fact classification
2. Task Segmenter — heuristic segmentation by time gap, agent change, signal words
3. Recall Orchestrator — query analysis, merge/rank, format with budget
4. Schema validation — MemoryItem, TaskSegmentItem, TaskSegmentDetail
5. extract_text_from_messages — string/block/mixed content extraction
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pytest

# Import app.models first to break the circular import chain
# (app.models.__init__ imports app.memory.models, and app.memory.models
#  imports app.models.base — importing app.models first resolves the cycle.)
import app.models  # noqa: F401

from app.memory.models import TaskSegment, Turn, VectorMemory
from app.memory.schemas import (
    MemoryItem,
    TaskSegmentDetail,
    TaskSegmentItem,
    TurnItem,
)
from app.memory.services.memory_worker import (
    _safe_content_str,
    detect_memory_type,
    extract_text_from_messages,
)
from app.memory.services.recall_orchestrator import (
    QueryAnalysis,
    RecallSource,
    _format_context,
    _merge_and_rank,
    analyze_query,
)
from app.memory.services.task_segmenter import (
    _has_task_switch_signal,
    segment_turns_heuristic,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_turn(
    messages: list[dict[str, Any]],
    session_id: str = "sess-1",
    user_id: str = "user-1",
    agent_id: str = "agent-1",
    source: str = "test",
    created_at: datetime | None = None,
    processing_status: str = "completed",
) -> Turn:
    """Create a Turn instance with sensible defaults for testing."""
    return Turn(
        session_id=session_id,
        user_id=user_id,
        agent_id=agent_id,
        messages=messages,
        source=source,
        created_at=created_at or datetime.now(),
        processing_status=processing_status,
    )


# ===========================================================================
# 1. detect_memory_type() unit tests
# ===========================================================================


class TestDetectMemoryType:
    """Tests for memory type detection: correction > procedure > fact."""

    def test_detect_correction_chinese(self):
        """Chinese correction patterns detected."""
        messages = [{"role": "user", "content": "不对，应该是 8000 端口"}]
        assert detect_memory_type(messages) == "correction"

    def test_detect_correction_chinese_wrong(self):
        """Chinese '错了' pattern."""
        messages = [{"role": "user", "content": "错了，不是这个文件"}]
        assert detect_memory_type(messages) == "correction"

    def test_detect_correction_english(self):
        """English correction pattern 'No, it should be'."""
        messages = [{"role": "user", "content": "No, it should be port 8080"}]
        assert detect_memory_type(messages) == "correction"

    def test_detect_correction_english_actually(self):
        """English 'actually...wrong' pattern."""
        messages = [{"role": "user", "content": "actually that's wrong, the path is /opt"}]
        assert detect_memory_type(messages) == "correction"

    def test_detect_procedure_chinese(self):
        """Chinese procedure patterns: 步骤, 第N步."""
        messages = [{"role": "user", "content": "步骤一：克隆仓库。第二步：安装依赖"}]
        assert detect_memory_type(messages) == "procedure"

    def test_detect_procedure_english(self):
        """English 'Step N' pattern."""
        messages = [{"role": "user", "content": "Step 1: clone. Step 2: install. Step 3: run"}]
        assert detect_memory_type(messages) == "procedure"

    def test_detect_fact_default(self):
        """Normal messages default to 'fact'."""
        messages = [{"role": "user", "content": "项目使用 Python 3.12"}]
        assert detect_memory_type(messages) == "fact"

    def test_detect_fact_simple_english(self):
        """Simple English statement is 'fact'."""
        messages = [{"role": "user", "content": "The project uses PostgreSQL as the database."}]
        assert detect_memory_type(messages) == "fact"

    def test_detect_ignores_assistant_messages(self):
        """Only user messages are checked for type detection."""
        messages = [
            {"role": "assistant", "content": "不对，我来纠正"},
            {"role": "user", "content": "好的"},
        ]
        assert detect_memory_type(messages) == "fact"

    def test_detect_empty_messages(self):
        """Empty message list returns 'fact'."""
        assert detect_memory_type([]) == "fact"

    def test_detect_correction_priority_over_procedure(self):
        """Correction takes priority when both patterns are present."""
        messages = [{"role": "user", "content": "不对，步骤应该是先装依赖再编译"}]
        assert detect_memory_type(messages) == "correction"

    def test_detect_with_content_blocks(self):
        """Handle ContentBlock[] format (list of dicts with 'type' and 'text')."""
        messages = [
            {
                "role": "user",
                "content": [{"type": "text", "text": "错了，不是这个文件"}],
            }
        ]
        assert detect_memory_type(messages) == "correction"

    def test_detect_multiple_user_messages(self):
        """Combines text from multiple user messages."""
        messages = [
            {"role": "user", "content": "这个配置有点问题"},
            {"role": "assistant", "content": "什么问题？"},
            {"role": "user", "content": "不对，端口应该是 3000"},
        ]
        assert detect_memory_type(messages) == "correction"

    def test_detect_no_user_messages(self):
        """No user messages returns 'fact' (empty user text)."""
        messages = [
            {"role": "assistant", "content": "Hello!"},
            {"role": "system", "content": "You are a helpful assistant."},
        ]
        assert detect_memory_type(messages) == "fact"

    def test_detect_procedure_first_then_finally(self):
        """English 'first...then...finally' pattern."""
        messages = [
            {"role": "user", "content": "first clone the repo, then install deps, finally run tests"}
        ]
        assert detect_memory_type(messages) == "procedure"


# ===========================================================================
# 2. Task Segmenter unit tests
# ===========================================================================


class TestHasTaskSwitchSignal:
    """Tests for _has_task_switch_signal() helper."""

    def test_chinese_signal_next(self):
        assert _has_task_switch_signal("接下来我们看另一个问题")

    def test_chinese_signal_new_task(self):
        assert _has_task_switch_signal("好，新任务：修复登录页面")

    def test_english_signal_next_task(self):
        assert _has_task_switch_signal("next task: implement the API")

    def test_english_signal_moving_on(self):
        assert _has_task_switch_signal("moving on to the database schema")

    def test_slash_command(self):
        assert _has_task_switch_signal("/plan implement new feature")

    def test_no_signal(self):
        assert not _has_task_switch_signal("项目使用 Python 3.12")

    def test_no_signal_english(self):
        assert not _has_task_switch_signal("The project uses PostgreSQL")


class TestSegmentTurnsHeuristic:
    """Tests for heuristic task segmentation."""

    def test_segmenter_time_gap(self):
        """30+ minute gap creates a new segment."""
        now = datetime.now()
        t1 = _make_turn(
            [{"role": "user", "content": "Task A work"}],
            created_at=now,
        )
        t2 = _make_turn(
            [{"role": "user", "content": "Task B work"}],
            created_at=now + timedelta(minutes=31),
        )
        segments = segment_turns_heuristic([t1, t2])
        assert len(segments) == 2
        assert str(t1.id) in segments[0].turn_ids
        assert str(t2.id) in segments[1].turn_ids

    def test_segmenter_no_time_gap(self):
        """Turns within 30 minutes stay in the same segment."""
        now = datetime.now()
        t1 = _make_turn(
            [{"role": "user", "content": "Part 1"}],
            created_at=now,
        )
        t2 = _make_turn(
            [{"role": "user", "content": "Part 2"}],
            created_at=now + timedelta(minutes=10),
        )
        segments = segment_turns_heuristic([t1, t2])
        assert len(segments) == 1
        assert len(segments[0].turn_ids) == 2

    def test_segmenter_agent_change(self):
        """Different agent_id creates a new segment."""
        now = datetime.now()
        t1 = _make_turn(
            [{"role": "user", "content": "Work with agent A"}],
            agent_id="agent-A",
            created_at=now,
        )
        t2 = _make_turn(
            [{"role": "user", "content": "Work with agent B"}],
            agent_id="agent-B",
            created_at=now + timedelta(minutes=1),
        )
        segments = segment_turns_heuristic([t1, t2])
        assert len(segments) == 2

    def test_segmenter_signal_words(self):
        """Task switch signal words create a new segment."""
        now = datetime.now()
        t1 = _make_turn(
            [{"role": "user", "content": "Fix the login bug"}],
            created_at=now,
        )
        t2 = _make_turn(
            [{"role": "user", "content": "接下来，我们做另一个功能"}],
            created_at=now + timedelta(minutes=2),
        )
        segments = segment_turns_heuristic([t1, t2])
        assert len(segments) == 2

    def test_segmenter_single_turn(self):
        """A single turn still creates one segment."""
        t1 = _make_turn([{"role": "user", "content": "Only turn"}])
        segments = segment_turns_heuristic([t1])
        assert len(segments) == 1
        assert segments[0].turn_ids == [str(t1.id)]

    def test_segmenter_no_turns(self):
        """Empty turns list returns empty segments."""
        segments = segment_turns_heuristic([])
        assert segments == []

    def test_segmenter_segment_fields(self):
        """Verify TaskSegment fields are populated correctly."""
        now = datetime.now()
        t1 = _make_turn(
            [{"role": "user", "content": "Implement auth"}],
            session_id="sess-42",
            user_id="user-7",
            agent_id="agent-X",
            created_at=now,
        )
        t2 = _make_turn(
            [{"role": "user", "content": "Add tests for auth"}],
            session_id="sess-42",
            user_id="user-7",
            agent_id="agent-X",
            created_at=now + timedelta(minutes=5),
        )
        segments = segment_turns_heuristic([t1, t2])
        assert len(segments) == 1
        seg = segments[0]
        assert seg.session_id == "sess-42"
        assert seg.user_id == "user-7"
        assert seg.agent_id == "agent-X"
        assert seg.first_turn_at == now
        assert seg.last_turn_at == now + timedelta(minutes=5)
        assert seg.segmentation_confidence == 0.6
        assert "Implement auth" in seg.goal

    def test_segmenter_multiple_splits(self):
        """Multiple split reasons produce correct number of segments."""
        now = datetime.now()
        turns = [
            _make_turn(
                [{"role": "user", "content": "Task 1"}],
                agent_id="a",
                created_at=now,
            ),
            _make_turn(
                [{"role": "user", "content": "Task 2"}],
                agent_id="b",  # agent change
                created_at=now + timedelta(minutes=1),
            ),
            _make_turn(
                [{"role": "user", "content": "Task 3"}],
                agent_id="b",
                created_at=now + timedelta(hours=1),  # time gap
            ),
        ]
        segments = segment_turns_heuristic(turns)
        assert len(segments) == 3


# ===========================================================================
# 3. Recall orchestrator unit tests
# ===========================================================================


class TestAnalyzeQuery:
    """Tests for analyze_query() rule-based intent/entity extraction."""

    def test_debug_intent(self):
        result = analyze_query("error in database connection")
        assert result.intent == "debug"

    def test_debug_intent_chinese(self):
        result = analyze_query("数据库连接报错了")
        assert result.intent == "debug"

    def test_question_intent(self):
        result = analyze_query("how to configure the database?")
        assert result.intent == "question"

    def test_question_intent_chinese(self):
        result = analyze_query("怎么配置数据库？")
        assert result.intent == "question"

    def test_task_intent(self):
        result = analyze_query("implement a new REST API for users")
        assert result.intent == "task"

    def test_config_intent(self):
        result = analyze_query("deploy the service with these env settings")
        assert result.intent == "config"

    def test_general_intent(self):
        result = analyze_query("hello world")
        assert result.intent == "general"

    def test_file_path_entity(self):
        result = analyze_query("check backend/app/main.py for errors")
        assert "backend/app/main.py" in result.entities

    def test_multiple_file_paths(self):
        result = analyze_query("compare backend/app/main.py and backend/app/core/config.py")
        assert len(result.entities) >= 2

    def test_error_message_extraction(self):
        result = analyze_query("I got Error: connection refused when starting the server")
        assert len(result.error_messages) >= 1

    def test_complexity_simple(self):
        result = analyze_query("fix the bug")
        assert result.complexity == "simple"

    def test_complexity_moderate(self):
        # >30 words makes it moderate
        long_query = " ".join(["word"] * 35)
        result = analyze_query(long_query)
        assert result.complexity == "moderate"

    def test_complexity_complex(self):
        # >100 words makes it complex
        long_query = " ".join(["word"] * 105)
        result = analyze_query(long_query)
        assert result.complexity == "complex"


class TestMergeAndRank:
    """Tests for _merge_and_rank(): dedup + priority-based sorting."""

    def test_correction_priority(self):
        """Corrections should rank higher than facts."""
        source_corrections = RecallSource(
            source_type="correction",
            items=[
                {
                    "content": "Port should be 8080 not 3000",
                    "score": 0.5,
                    "memory_type": "correction",
                }
            ],
        )
        source_facts = RecallSource(
            source_type="vector",
            items=[
                {
                    "content": "Project uses Python 3.12",
                    "score": 0.9,
                    "memory_type": "fact",
                }
            ],
        )
        merged = _merge_and_rank([source_corrections, source_facts])
        assert len(merged) == 2
        # Correction should be first (type priority 100 vs fact 20)
        assert merged[0]["memory_type"] == "correction"
        assert merged[1]["memory_type"] == "fact"

    def test_procedure_ranks_above_fact(self):
        """Procedures (priority 90) rank above facts (priority 20)."""
        sources = [
            RecallSource(
                source_type="vector",
                items=[
                    {"content": "A fact", "score": 0.9, "memory_type": "fact"},
                    {"content": "A procedure", "score": 0.5, "memory_type": "procedure"},
                ],
            )
        ]
        merged = _merge_and_rank(sources)
        assert merged[0]["memory_type"] == "procedure"

    def test_deduplication(self):
        """Duplicate content is removed."""
        source = RecallSource(
            source_type="vector",
            items=[
                {"content": "same content", "score": 0.9, "memory_type": "fact"},
                {"content": "same content", "score": 0.8, "memory_type": "fact"},
            ],
        )
        merged = _merge_and_rank([source])
        assert len(merged) == 1

    def test_empty_content_filtered(self):
        """Items with empty/whitespace content are excluded."""
        source = RecallSource(
            source_type="vector",
            items=[
                {"content": "", "score": 0.9, "memory_type": "fact"},
                {"content": "   ", "score": 0.8, "memory_type": "fact"},
                {"content": "real content", "score": 0.7, "memory_type": "fact"},
            ],
        )
        merged = _merge_and_rank([source])
        assert len(merged) == 1
        assert merged[0]["content"] == "real content"

    def test_multiple_sources(self):
        """Items from multiple sources are merged."""
        s1 = RecallSource(
            source_type="vector",
            items=[{"content": "vector result", "score": 0.8, "memory_type": "fact"}],
        )
        s2 = RecallSource(
            source_type="graph",
            items=[{"content": "graph result", "score": 0.5, "memory_type": "graph_relation"}],
        )
        s3 = RecallSource(
            source_type="correction",
            items=[{"content": "correction result", "score": 1.0, "memory_type": "correction"}],
        )
        merged = _merge_and_rank([s1, s2, s3])
        assert len(merged) == 3
        # correction first, then graph_relation (50), then fact (20)
        assert merged[0]["memory_type"] == "correction"

    def test_empty_sources(self):
        """Empty source list returns empty."""
        assert _merge_and_rank([]) == []

    def test_rank_score_computed(self):
        """Each merged item has a _rank_score."""
        source = RecallSource(
            source_type="vector",
            items=[{"content": "test", "score": 0.8, "memory_type": "fact"}],
        )
        merged = _merge_and_rank([source])
        assert "_rank_score" in merged[0]
        # fact priority=20, score 0.8 * 50 = 40, total = 60
        assert merged[0]["_rank_score"] == pytest.approx(60.0, abs=0.1)


class TestFormatContext:
    """Tests for _format_context(): token budget enforcement."""

    def test_correction_prefix(self):
        """Corrections get [CORRECTION] prefix."""
        items = [{"content": "Use port 8080", "memory_type": "correction"}]
        text = _format_context(items, budget_tokens=1000, analysis=QueryAnalysis())
        assert text.startswith("[CORRECTION]")

    def test_procedure_prefix(self):
        """Procedures get [PROCEDURE] prefix."""
        items = [{"content": "Step 1 do this", "memory_type": "procedure"}]
        text = _format_context(items, budget_tokens=1000, analysis=QueryAnalysis())
        assert text.startswith("[PROCEDURE]")

    def test_graph_prefix(self):
        """Graph relations get [GRAPH] prefix."""
        items = [{"content": "A -> relates -> B", "memory_type": "graph_relation"}]
        text = _format_context(items, budget_tokens=1000, analysis=QueryAnalysis())
        assert text.startswith("[GRAPH]")

    def test_fact_prefix(self):
        """Facts get '- ' prefix."""
        items = [{"content": "Uses Python 3.12", "memory_type": "fact"}]
        text = _format_context(items, budget_tokens=1000, analysis=QueryAnalysis())
        assert text.startswith("- ")

    def test_budget_truncation(self):
        """Context respects token budget by truncating items."""
        # budget_tokens=5 means budget_chars=20, very small
        items = [
            {"content": "A" * 100, "memory_type": "fact"},
            {"content": "B" * 100, "memory_type": "fact"},
        ]
        text = _format_context(items, budget_tokens=5, analysis=QueryAnalysis())
        # With 20 chars budget, at most one item (or none if "- " + 100 chars > 20)
        # "- " + "A"*100 = 102 chars > 20 budget, so nothing fits
        assert text == ""

    def test_budget_allows_items(self):
        """Budget large enough includes all items."""
        items = [
            {"content": "short", "memory_type": "fact"},
            {"content": "also short", "memory_type": "fact"},
        ]
        text = _format_context(items, budget_tokens=500, analysis=QueryAnalysis())
        assert "short" in text
        assert "also short" in text

    def test_empty_items(self):
        """Empty item list returns empty string."""
        text = _format_context([], budget_tokens=1000, analysis=QueryAnalysis())
        assert text == ""


# ===========================================================================
# 4. Schema validation tests
# ===========================================================================


class TestSchemaValidation:
    """Tests for Pydantic schema models."""

    def test_memory_item_fact(self):
        """MemoryItem accepts 'fact' memory_type."""
        item = MemoryItem(id="1", content="test", memory_type="fact")
        assert item.memory_type == "fact"

    def test_memory_item_correction(self):
        """MemoryItem accepts 'correction' memory_type."""
        item = MemoryItem(id="1", content="test", memory_type="correction")
        assert item.memory_type == "correction"

    def test_memory_item_procedure(self):
        """MemoryItem accepts 'procedure' memory_type."""
        item = MemoryItem(id="1", content="test", memory_type="procedure")
        assert item.memory_type == "procedure"

    def test_memory_item_summary(self):
        """MemoryItem accepts 'summary' memory_type."""
        item = MemoryItem(id="1", content="test", memory_type="summary")
        assert item.memory_type == "summary"

    def test_memory_item_task_fact(self):
        """MemoryItem accepts 'task_fact' memory_type."""
        item = MemoryItem(id="1", content="test", memory_type="task_fact")
        assert item.memory_type == "task_fact"

    def test_memory_item_optional_fields(self):
        """MemoryItem optional fields default correctly."""
        item = MemoryItem(id="1", content="test", memory_type="fact")
        assert item.score is None
        assert item.memory_subtype is None
        assert item.task_segment_id is None
        assert item.turn_id is None
        assert item.agent_id is None
        assert item.source is None
        assert item.session_id is None
        assert item.categories == []
        assert item.created_at is None

    def test_memory_item_full(self):
        """MemoryItem with all fields populated."""
        item = MemoryItem(
            id="mem-1",
            content="The project uses Python 3.12",
            memory_type="fact",
            score=0.95,
            memory_subtype="goal",
            task_segment_id="seg-1",
            turn_id="turn-1",
            agent_id="agent-1",
            source="claude-code",
            session_id="sess-1",
            categories=["tech", "config"],
            created_at="2024-01-01T00:00:00Z",
        )
        assert item.id == "mem-1"
        assert item.score == 0.95
        assert item.categories == ["tech", "config"]

    def test_task_segment_item_required_fields(self):
        """TaskSegmentItem has all required fields."""
        seg = TaskSegmentItem(
            id="seg-1",
            session_id="sess-1",
            user_id="user-1",
            agent_id="agent-1",
            goal="Implement auth",
        )
        assert seg.id == "seg-1"
        assert seg.status == "unknown"
        assert seg.turn_ids == []
        assert seg.segmentation_confidence == 0.0

    def test_task_segment_item_full(self):
        """TaskSegmentItem with all fields."""
        seg = TaskSegmentItem(
            id="seg-1",
            session_id="sess-1",
            user_id="user-1",
            agent_id="agent-1",
            goal="Fix login bug",
            status="succeeded",
            outcome="Bug fixed",
            task_type="bug_fix",
            turn_ids=["t1", "t2"],
            first_turn_at="2024-01-01T00:00:00Z",
            last_turn_at="2024-01-01T01:00:00Z",
            segmentation_confidence=0.8,
            event_time="2024-01-01T00:00:00Z",
            created_at="2024-01-01T00:00:00Z",
        )
        assert seg.status == "succeeded"
        assert seg.task_type == "bug_fix"
        assert len(seg.turn_ids) == 2

    def test_task_segment_detail_schema(self):
        """TaskSegmentDetail includes segment, turns, and memories."""
        seg_item = TaskSegmentItem(
            id="seg-1",
            session_id="sess-1",
            user_id="user-1",
            agent_id="agent-1",
            goal="Task goal",
        )
        turn_item = TurnItem(
            id="t-1",
            session_id="sess-1",
            user_id="user-1",
            agent_id="agent-1",
            source="test",
            processing_status="completed",
            message_count=3,
        )
        mem_item = MemoryItem(id="m-1", content="A memory", memory_type="fact")
        detail = TaskSegmentDetail(
            segment=seg_item,
            turns=[turn_item],
            memories=[mem_item],
        )
        assert detail.segment.id == "seg-1"
        assert len(detail.turns) == 1
        assert len(detail.memories) == 1
        assert detail.turns[0].message_count == 3
        assert detail.memories[0].content == "A memory"

    def test_task_segment_detail_empty_lists(self):
        """TaskSegmentDetail defaults to empty turns and memories."""
        seg_item = TaskSegmentItem(
            id="seg-1",
            session_id="sess-1",
            user_id="user-1",
            agent_id="agent-1",
            goal="Task",
        )
        detail = TaskSegmentDetail(segment=seg_item)
        assert detail.turns == []
        assert detail.memories == []


# ===========================================================================
# 5. extract_text_from_messages tests
# ===========================================================================


class TestExtractTextFromMessages:
    """Tests for extract_text_from_messages() and _safe_content_str()."""

    def test_extract_text_string_content(self):
        """String content extracted correctly."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        result = extract_text_from_messages(messages)
        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "Hello"}
        assert result[1] == {"role": "assistant", "content": "Hi there"}

    def test_extract_text_content_blocks(self):
        """ContentBlock[] with text, tool_use, and tool_result extracted."""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Let me check that."},
                    {"type": "tool_use", "name": "read_file", "input": {"path": "main.py"}},
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "content": "file contents here"},
                ],
            },
        ]
        result = extract_text_from_messages(messages)
        assert len(result) == 2
        assert "Let me check that." in result[0]["content"]
        assert "[Used tool: read_file]" in result[0]["content"]
        assert "[Tool result: file contents here]" in result[1]["content"]

    def test_extract_text_mixed(self):
        """Mix of string and block content."""
        messages = [
            {"role": "user", "content": "Please fix the bug"},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "I'll fix it."},
                    {"type": "tool_use", "name": "edit_file", "input": {}},
                ],
            },
        ]
        result = extract_text_from_messages(messages)
        assert len(result) == 2
        assert result[0]["content"] == "Please fix the bug"
        assert "I'll fix it." in result[1]["content"]

    def test_extract_empty_content_filtered(self):
        """Messages with empty/whitespace content are filtered out."""
        messages = [
            {"role": "user", "content": ""},
            {"role": "user", "content": "   "},
            {"role": "user", "content": "Real content"},
        ]
        result = extract_text_from_messages(messages)
        assert len(result) == 1
        assert result[0]["content"] == "Real content"

    def test_extract_tool_result_truncation(self):
        """Long tool_result content is truncated to 200 chars."""
        long_content = "x" * 500
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "content": long_content},
                ],
            },
        ]
        result = extract_text_from_messages(messages)
        assert len(result) == 1
        # _safe_content_str truncates tool_result to 200 chars + "..."
        assert "..." in result[0]["content"]
        # The total should be [Tool result: <200 chars>...]
        assert len(result[0]["content"]) < 250

    def test_extract_preserves_role(self):
        """Role is preserved correctly for all messages."""
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Help me"},
            {"role": "assistant", "content": "Sure"},
        ]
        result = extract_text_from_messages(messages)
        roles = [m["role"] for m in result]
        assert roles == ["system", "user", "assistant"]


# ===========================================================================
# 6. _safe_content_str tests (lower-level helper)
# ===========================================================================


class TestSafeContentStr:
    """Tests for _safe_content_str() which handles both str and block formats."""

    def test_string_content(self):
        assert _safe_content_str("hello") == "hello"

    def test_list_text_blocks(self):
        blocks = [
            {"type": "text", "text": "line 1"},
            {"type": "text", "text": "line 2"},
        ]
        result = _safe_content_str(blocks)
        assert "line 1" in result
        assert "line 2" in result

    def test_tool_use_block(self):
        blocks = [{"type": "tool_use", "name": "grep"}]
        result = _safe_content_str(blocks)
        assert "[Used tool: grep]" in result

    def test_tool_result_block(self):
        blocks = [{"type": "tool_result", "content": "output data"}]
        result = _safe_content_str(blocks)
        assert "[Tool result: output data]" in result

    def test_none_content(self):
        assert _safe_content_str(None) == ""

    def test_non_dict_blocks_skipped(self):
        """Non-dict items in list are skipped."""
        blocks = ["not a dict", {"type": "text", "text": "valid"}]
        result = _safe_content_str(blocks)
        assert result == "valid"

    def test_integer_content(self):
        """Integer content is stringified."""
        assert _safe_content_str(42) == "42"
