"""Tests for task priority validation, filtering, and sorting."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.api.tasks import (
    _priority_values,
    _task_list_statement,
)
from app.models.tasks import Task
from app.schemas.tasks import (
    ALLOWED_PRIORITIES,
    TaskCreate,
    TaskRead,
    TaskUpdate,
)

# -- Schema validation tests --


class TestTaskPrioritySchema:
    """Verify that priority validation enforces allowed values."""

    def test_allowed_priorities_match_literal(self) -> None:
        assert ALLOWED_PRIORITIES == {"urgent", "high", "medium", "low"}

    def test_create_default_priority_is_medium(self) -> None:
        task = TaskCreate(title="Test task")
        assert task.priority == "medium"

    @pytest.mark.parametrize("priority", ["urgent", "high", "medium", "low"])
    def test_create_accepts_valid_priorities(self, priority: str) -> None:
        task = TaskCreate(title="Test task", priority=priority)
        assert task.priority == priority

    def test_create_rejects_invalid_priority(self) -> None:
        with pytest.raises(ValidationError, match="priority"):
            TaskCreate(title="Test task", priority="critical")  # type: ignore[arg-type]

    def test_create_rejects_empty_string_priority(self) -> None:
        with pytest.raises(ValidationError, match="priority"):
            TaskCreate(title="Test task", priority="")  # type: ignore[arg-type]

    @pytest.mark.parametrize("priority", ["urgent", "high", "medium", "low"])
    def test_update_accepts_valid_priorities(self, priority: str) -> None:
        update = TaskUpdate(priority=priority)
        assert update.priority == priority

    def test_update_allows_none_priority(self) -> None:
        update = TaskUpdate()
        assert update.priority is None

    def test_update_rejects_invalid_priority(self) -> None:
        with pytest.raises(ValidationError, match="priority"):
            TaskUpdate(priority="critical")  # type: ignore[arg-type]


# -- Filter helper tests --


class TestPriorityValues:
    """Verify _priority_values parsing and validation."""

    def test_none_returns_empty(self) -> None:
        assert _priority_values(None) == []

    def test_empty_string_returns_empty(self) -> None:
        assert _priority_values("") == []

    def test_single_value(self) -> None:
        assert _priority_values("high") == ["high"]

    def test_comma_separated_values(self) -> None:
        result = _priority_values("urgent,high")
        assert result == ["urgent", "high"]

    def test_strips_whitespace(self) -> None:
        result = _priority_values(" high , medium ")
        assert result == ["high", "medium"]

    def test_rejects_invalid_value(self) -> None:
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _priority_values("critical")
        assert exc_info.value.status_code == 422
        assert "Unsupported task priority filter" in str(exc_info.value.detail)


# -- Statement builder tests --


class TestTaskListStatement:
    """Verify _task_list_statement applies priority filter and sort."""

    def test_no_priority_filter(self) -> None:
        stmt = _task_list_statement(
            board_id=uuid4(),
            status_filter=None,
            priority_filter=None,
            assigned_agent_id=None,
            unassigned=None,
            sort=None,
        )
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        # "urgent" only appears when a priority filter or sort is applied.
        assert "urgent" not in compiled

    def test_priority_filter_applied(self) -> None:
        stmt = _task_list_statement(
            board_id=uuid4(),
            status_filter=None,
            priority_filter="urgent,high",
            assigned_agent_id=None,
            unassigned=None,
            sort=None,
        )
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "priority" in compiled.lower()

    def test_priority_sort_applied(self) -> None:
        stmt = _task_list_statement(
            board_id=uuid4(),
            status_filter=None,
            priority_filter=None,
            assigned_agent_id=None,
            unassigned=None,
            sort="priority",
        )
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "CASE" in compiled.upper() or "case" in compiled.lower()

    def test_default_sort_is_created_at_desc(self) -> None:
        stmt = _task_list_statement(
            board_id=uuid4(),
            status_filter=None,
            priority_filter=None,
            assigned_agent_id=None,
            unassigned=None,
            sort=None,
        )
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "created_at" in compiled.lower()


# -- Model field tests --


class TestTaskModelPriority:
    """Verify the Task model has the priority field with correct default."""

    def test_default_priority(self) -> None:
        task = Task(board_id=uuid4(), title="Test")
        assert task.priority == "medium"

    @pytest.mark.parametrize("priority", ["urgent", "high", "medium", "low"])
    def test_accepts_all_priorities(self, priority: str) -> None:
        task = Task(board_id=uuid4(), title="Test", priority=priority)
        assert task.priority == priority


# -- TaskRead includes priority --


class TestTaskReadPriority:
    """Verify TaskRead and TaskCardRead include priority."""

    def test_task_read_includes_priority(self) -> None:
        from app.schemas.view_models import TaskCardRead

        assert "priority" in TaskRead.model_fields
        assert "priority" in TaskCardRead.model_fields
