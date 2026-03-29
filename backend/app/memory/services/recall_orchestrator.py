"""
智能并发召回编排器。

三阶段召回：
1. Query Analysis — 规则式意图/实体提取 (<100ms)
2. Parallel Context Assembly — Qdrant + Neo4j + corrections 并发 (per-source timeout)
3. Merge + Rank + Format — 去重排序截断 (<100ms)
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


def _get_memory_client():  # type: ignore[no-untyped-def]
    """Lazy import to avoid circular import."""
    from app.memory.services.client_factory import get_memory_client

    return get_memory_client()

# --- Stage 1: Query Analysis ---

# 文件路径模式
_FILE_PATH_RE = re.compile(
    r"(?:^|[\s\"'`(])("
    r"(?:[a-zA-Z]:)?(?:[/\\][\w.\-]+)+\.\w+"  # /path/to/file.ext or C:\path
    r"|(?:[\w.\-]+[/\\])+[\w.\-]+\.\w+"  # relative/path/to/file.ext
    r"|[\w.\-]+\.(?:py|ts|tsx|js|jsx|rs|go|java|md|sh|yaml|yml|json|toml)"  # file.ext
    r")",
    re.MULTILINE,
)

# 错误消息模式
_ERROR_RE = re.compile(
    r"(?:Error|Exception|Traceback|FAILED|panic|fatal)[\s:].{10,200}",
    re.IGNORECASE,
)

# 意图分类关键词
_INTENT_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "debug": [
        re.compile(r"error|bug|fix|crash|fail|broken|不工作|报错|崩溃|异常", re.I),
    ],
    "question": [
        re.compile(r"what|how|why|where|when|是什么|怎么|为什么|哪里|如何", re.I),
    ],
    "task": [
        re.compile(r"implement|add|create|build|write|实现|添加|创建|编写|新增", re.I),
    ],
    "config": [
        re.compile(r"config|setting|env|deploy|安装|配置|部署|环境", re.I),
    ],
}


@dataclass
class QueryAnalysis:
    """查询分析结果。"""

    intent: str = "general"  # debug/question/task/config/general
    entities: list[str] = field(default_factory=list)  # 文件路径、函数名等
    error_messages: list[str] = field(default_factory=list)
    complexity: str = "simple"  # simple/moderate/complex


def analyze_query(query: str) -> QueryAnalysis:
    """规则式查询分析，无 LLM 调用。<100ms。"""
    result = QueryAnalysis()

    # 提取文件路径
    for m in _FILE_PATH_RE.finditer(query):
        path = m.group(1).strip()
        if path and path not in result.entities:
            result.entities.append(path)

    # 提取错误消息
    for m in _ERROR_RE.finditer(query):
        err = m.group(0).strip()
        if err and err not in result.error_messages:
            result.error_messages.append(err[:200])

    # 意图分类（第一个匹配的）
    for intent, patterns in _INTENT_PATTERNS.items():
        if any(p.search(query) for p in patterns):
            result.intent = intent
            break

    # 复杂度评估
    word_count = len(query.split())
    if word_count > 100 or len(result.entities) > 3:
        result.complexity = "complex"
    elif word_count > 30 or len(result.entities) > 1:
        result.complexity = "moderate"

    return result


# --- Stage 2: Parallel Context Assembly ---


@dataclass
class RecallSource:
    """单个召回来源的结果。"""

    source_type: str  # "vector" / "graph" / "correction"
    items: list[dict[str, Any]] = field(default_factory=list)
    duration_ms: float = 0.0
    error: Optional[str] = None


async def _search_vector(
    query: str,
    user_id: str,
    agent_id: Optional[str],
    limit: int,
    timeout_ms: int,
) -> RecallSource:
    """Qdrant 向量语义搜索。"""
    start = time.monotonic()
    source = RecallSource(source_type="vector")
    try:
        memory_client = _get_memory_client()
        if not memory_client:
            source.error = "Memory client unavailable"
            return source

        loop = asyncio.get_running_loop()
        response: dict[str, Any] = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: memory_client.search(
                    query, user_id=user_id, agent_id=agent_id, limit=limit
                ),
            ),
            timeout=timeout_ms / 1000.0,
        )
        results = response.get("results", [])
        for item in results:
            metadata = item.get("metadata", {}) or {}
            source.items.append(
                {
                    "content": str(item.get("memory", "")),
                    "score": item.get("score", 0.0),
                    "memory_type": str(metadata.get("memory_type", "fact")),
                    "source_type": "vector",
                    "id": str(item.get("id", "")),
                    "agent_id": item.get("agent_id") or metadata.get("agent_id"),
                    "created_at": item.get("created_at"),
                }
            )
    except asyncio.TimeoutError:
        source.error = f"Vector search timed out after {timeout_ms}ms"
        logger.warning(source.error)
    except Exception as e:
        source.error = str(e)
        logger.warning(f"Vector search failed: {e}")
    finally:
        source.duration_ms = (time.monotonic() - start) * 1000
    return source


async def _search_graph(
    query: str,
    user_id: str,
    agent_id: Optional[str],
    limit: int,
    timeout_ms: int,
) -> RecallSource:
    """Neo4j 图遍历搜索。"""
    start = time.monotonic()
    source = RecallSource(source_type="graph")
    try:
        memory_client = _get_memory_client()
        if not memory_client or not getattr(memory_client, "enable_graph", False):
            source.error = "Graph not enabled"
            return source

        loop = asyncio.get_running_loop()
        results = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: memory_client.search(
                    query,
                    user_id=user_id,
                    agent_id=agent_id,
                    limit=limit,
                ),
            ),
            timeout=timeout_ms / 1000.0,
        )
        # Graph results come from the "relations" key in mem0 search response
        relations = results.get("relations", [])
        for rel in relations:
            content = f"{rel.get('source', '')} → {rel.get('relationship', '')} → {rel.get('destination', '')}"
            source.items.append(
                {
                    "content": content,
                    "score": 0.5,  # Graph results don't have similarity scores
                    "memory_type": "graph_relation",
                    "source_type": "graph",
                }
            )
    except asyncio.TimeoutError:
        source.error = f"Graph search timed out after {timeout_ms}ms"
        logger.warning(source.error)
    except Exception as e:
        source.error = str(e)
        logger.warning(f"Graph search failed: {e}")
    finally:
        source.duration_ms = (time.monotonic() - start) * 1000
    return source


async def _search_corrections(
    query: str,
    user_id: str,
    agent_id: Optional[str],
    limit: int,
    timeout_ms: int,
) -> RecallSource:
    """查询 correction 类型记忆。"""
    start = time.monotonic()
    source = RecallSource(source_type="correction")
    try:
        memory_client = _get_memory_client()
        if not memory_client:
            source.error = "Memory client unavailable"
            return source

        loop = asyncio.get_running_loop()
        response: dict[str, Any] = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: memory_client.search(
                    query,
                    user_id=user_id,
                    agent_id=agent_id,
                    limit=limit,
                    filters={"memory_type": "correction"},
                ),
            ),
            timeout=timeout_ms / 1000.0,
        )
        results = response.get("results", [])
        for item in results:
            source.items.append(
                {
                    "content": str(item.get("memory", "")),
                    "score": item.get("score", 0.0),
                    "memory_type": "correction",
                    "source_type": "correction",
                    "id": str(item.get("id", "")),
                    "created_at": item.get("created_at"),
                }
            )
    except asyncio.TimeoutError:
        source.error = f"Correction search timed out after {timeout_ms}ms"
        logger.warning(source.error)
    except Exception as e:
        source.error = str(e)
        logger.warning(f"Correction search failed: {e}")
    finally:
        source.duration_ms = (time.monotonic() - start) * 1000
    return source


# --- Stage 3: Merge + Rank + Format ---

# 优先级权重（越高越优先）
_TYPE_PRIORITY: dict[str, int] = {
    "correction": 100,
    "procedure": 90,
    "graph_relation": 50,
    "summary": 30,
    "fact": 20,
    "task_fact": 25,
}


def _content_hash(content: str) -> str:
    """内容哈希用于去重。"""
    return hashlib.md5(content.strip().lower().encode()).hexdigest()


def _merge_and_rank(sources: list[RecallSource]) -> list[dict[str, Any]]:
    """合并所有来源结果，去重并按优先级排序。"""
    seen_hashes: set[str] = set()
    merged: list[dict[str, Any]] = []

    for source in sources:
        for item in source.items:
            content = item.get("content", "")
            if not content.strip():
                continue
            h = _content_hash(content)
            if h in seen_hashes:
                continue
            seen_hashes.add(h)

            # 计算综合分数：类型优先级 + 向量相似度
            type_priority = _TYPE_PRIORITY.get(item.get("memory_type", "fact"), 10)
            vector_score = item.get("score", 0.0) or 0.0
            item["_rank_score"] = type_priority + vector_score * 50
            merged.append(item)

    merged.sort(key=lambda x: x.get("_rank_score", 0), reverse=True)
    return merged


def _format_context(
    items: list[dict[str, Any]],
    budget_tokens: int,
    analysis: QueryAnalysis,
) -> str:
    """将排序后的结果格式化为纯文本，按 token budget 截断。"""
    # 粗略估算：1 token ≈ 4 chars (中英混合)
    budget_chars = budget_tokens * 4
    lines: list[str] = []
    used_chars = 0

    for item in items:
        content = item.get("content", "").strip()
        memory_type = item.get("memory_type", "fact")

        # 格式化单条
        if memory_type == "correction":
            line = f"[CORRECTION] {content}"
        elif memory_type == "graph_relation":
            line = f"[GRAPH] {content}"
        elif memory_type == "procedure":
            line = f"[PROCEDURE] {content}"
        else:
            line = f"- {content}"

        if used_chars + len(line) > budget_chars:
            break
        lines.append(line)
        used_chars += len(line) + 1  # +1 for newline

    return "\n".join(lines)


# --- Public API ---


@dataclass
class RecallResult:
    """召回结果。"""

    context_text: str
    sources: list[dict[str, Any]]
    query_analysis: dict[str, Any]
    timing: dict[str, Any]


async def recall(
    query: str,
    user_id: str,
    agent_id: Optional[str] = None,
    context_budget_tokens: Optional[int] = None,
    timeout_ms: Optional[int] = None,
) -> RecallResult:
    """智能并发召回入口。

    三阶段：Query Analysis → Parallel Assembly → Merge/Rank/Format。
    """
    total_start = time.monotonic()

    budget = context_budget_tokens or settings.recall_default_budget_tokens
    vector_timeout = settings.recall_vector_timeout_ms
    graph_timeout = settings.recall_graph_timeout_ms
    correction_timeout = min(vector_timeout, 2000)

    # Stage 1: Query Analysis
    analysis = analyze_query(query)

    # Stage 2: Parallel Context Assembly
    vector_task = _search_vector(query, user_id, agent_id, limit=20, timeout_ms=vector_timeout)
    graph_task = _search_graph(query, user_id, agent_id, limit=10, timeout_ms=graph_timeout)
    correction_task = _search_corrections(
        query, user_id, agent_id, limit=5, timeout_ms=correction_timeout
    )

    results = await asyncio.gather(vector_task, graph_task, correction_task, return_exceptions=True)

    # 收集成功的 sources（异常转为空 RecallSource）
    sources: list[RecallSource] = []
    for r in results:
        if isinstance(r, RecallSource):
            sources.append(r)
        elif isinstance(r, Exception):
            logger.error(f"Recall source failed: {r}")
            sources.append(RecallSource(source_type="unknown", error=str(r)))

    # Stage 3: Merge + Rank + Format
    merged = _merge_and_rank(sources)
    context_text = _format_context(merged, budget, analysis)

    total_ms = (time.monotonic() - total_start) * 1000

    # 构建 sources 摘要
    source_summaries = []
    for s in sources:
        source_summaries.append(
            {
                "type": s.source_type,
                "count": len(s.items),
                "duration_ms": round(s.duration_ms, 1),
                "error": s.error,
            }
        )

    return RecallResult(
        context_text=context_text,
        sources=source_summaries,
        query_analysis={
            "intent": analysis.intent,
            "entities": analysis.entities,
            "error_messages": analysis.error_messages,
            "complexity": analysis.complexity,
        },
        timing={
            "total_ms": round(total_ms, 1),
            "vector_ms": round(
                next((s.duration_ms for s in sources if s.source_type == "vector"), 0), 1
            ),
            "graph_ms": round(
                next((s.duration_ms for s in sources if s.source_type == "graph"), 0), 1
            ),
            "correction_ms": round(
                next((s.duration_ms for s in sources if s.source_type == "correction"), 0),
                1,
            ),
        },
    )
