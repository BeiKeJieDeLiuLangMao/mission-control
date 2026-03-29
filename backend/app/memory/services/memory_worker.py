"""
记忆处理 Worker

后台轮询处理 pending turns：
1. 批量取出 N 条 pending turns（WORKER_BATCH_SIZE）
2. 按 session_id 分组，不同 session 并发处理，同 session 内保持顺序
3. 顺序执行: fact → summary → graph
4. session 内所有 pending turns 处理完后触发任务分段
"""

import asyncio
import logging
from collections import defaultdict

from sqlalchemy import func, select
from sqlmodel import col
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.db.session import async_session_maker
from app.memory.models import TaskSegment, Turn, VectorMemory
from app.memory.services.client_factory import get_memory_client

logger = logging.getLogger(__name__)


def _safe_content_str(content: object) -> str:
    """从 content 字段提取纯文本，兼容 str 和 ContentBlock[] 两种格式。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text":
                parts.append(block.get("text", ""))
            elif btype == "tool_use":
                parts.append(f"[Used tool: {block.get('name', 'unknown')}]")
            elif btype == "tool_result":
                result = str(block.get("content", ""))
                if len(result) > 200:
                    result = result[:200] + "..."
                parts.append(f"[Tool result: {result}]")
        return "\n".join(parts)
    return str(content) if content else ""


def extract_text_from_messages(messages: list[dict]) -> list[dict]:
    """将结构化消息 (含 tool_use/tool_result blocks) 转换为纯文本消息供 Memory 引擎使用。"""
    result: list[dict] = []
    for msg in messages:
        role = msg.get("role", "unknown")
        text = _safe_content_str(msg.get("content", ""))
        if text.strip():
            result.append({"role": role, "content": text})
    return result


async def process_fact_extraction(turn: Turn, db: AsyncSession) -> None:
    """从对话中提取关键事实"""
    try:
        memory_client = get_memory_client()
        if not memory_client:
            logger.warning(f"Memory client unavailable for turn {turn.id}")
            return

        metadata = {
            "source": turn.source,
            "turn_id": str(turn.id),
            "memory_type": "fact",
        }
        if turn.agent_id:
            metadata["agent_id"] = turn.agent_id

        # 调用 LLM 提取事实 (结构化消息转为纯文本)
        response = memory_client.add(
            messages=extract_text_from_messages(turn.messages),
            user_id=turn.user_id,
            agent_id=turn.agent_id,
            metadata=metadata,
            infer=True,
        )

        # 写入 vector_memories 表（跳过已存在的 qdrant_id 避免 UniqueViolation）
        results = response.get("results", [])
        inserted = 0
        for item in results:
            qdrant_id = item.get("id", "")
            if not qdrant_id:
                continue
            existing = await db.execute(
                select(VectorMemory).where(col(VectorMemory.qdrant_id) == qdrant_id).limit(1)
            )
            if existing.scalar_one_or_none():
                logger.debug(f"Skipping duplicate qdrant_id {qdrant_id} for turn {turn.id}")
                continue
            vm = VectorMemory(
                qdrant_id=qdrant_id,
                user_id=turn.user_id,
                agent_id=turn.agent_id,
                turn_id=str(turn.id),
                content=item.get("memory", item.get("text", "")),
                memory_type="fact",
                source=turn.source,
            )
            db.add(vm)
            inserted += 1

        await db.commit()
        logger.info(
            f"Fact extraction completed for turn {turn.id}, "
            f"extracted {len(results)} facts, inserted {inserted}"
        )

    except Exception as e:
        logger.error(f"Fact extraction failed for turn {turn.id}: {e}")
        await db.rollback()


async def process_summary_generation(turn: Turn, db: AsyncSession) -> None:
    """生成对话摘要"""
    try:
        memory_client = get_memory_client()
        if not memory_client:
            logger.warning(f"Memory client unavailable for turn {turn.id}")
            return

        # 构建摘要文本
        summary_text = _build_summary_text(turn.messages)
        if not summary_text:
            logger.info(f"No summary text for turn {turn.id}")
            return

        metadata = {
            "source": turn.source,
            "turn_id": str(turn.id),
            "memory_type": "summary",
        }
        if turn.agent_id:
            metadata["agent_id"] = turn.agent_id

        # 存储摘要（不经过 LLM 提取）
        response = memory_client.add(
            messages=[{"role": "user", "content": summary_text}],
            user_id=turn.user_id,
            agent_id=turn.agent_id,
            metadata=metadata,
            infer=False,
        )

        # 写入 vector_memories 表（跳过已存在的 qdrant_id 避免 UniqueViolation）
        results = response.get("results", [])
        inserted = 0
        for item in results:
            qdrant_id = item.get("id", "")
            if not qdrant_id:
                continue
            existing = await db.execute(
                select(VectorMemory).where(col(VectorMemory.qdrant_id) == qdrant_id).limit(1)
            )
            if existing.scalar_one_or_none():
                logger.debug(f"Skipping duplicate qdrant_id {qdrant_id} for turn {turn.id}")
                continue
            vm = VectorMemory(
                qdrant_id=qdrant_id,
                user_id=turn.user_id,
                agent_id=turn.agent_id,
                turn_id=str(turn.id),
                content=item.get("memory", item.get("text", "")),
                memory_type="summary",
                source=turn.source,
            )
            db.add(vm)
            inserted += 1

        await db.commit()
        logger.info(f"Summary generation completed for turn {turn.id}, inserted {inserted}")

    except Exception as e:
        logger.error(f"Summary generation failed for turn {turn.id}: {e}")
        await db.rollback()


def _build_summary_text(messages: list) -> str:
    """构建对话摘要文本，兼容 str 和 ContentBlock[] 两种 content 格式。"""
    if not messages:
        return ""

    lines = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = _safe_content_str(msg.get("content", ""))
        if content:
            lines.append(f"{role}: {content}")

    return "\n".join(lines)


async def process_graph_build(turn: Turn, db: AsyncSession) -> None:
    """构建知识图谱

    注意：当 Neo4j 启用时，Memory.add() 在 fact extraction 阶段已自动并行写入图数据库。
    此步骤仅做状态确认日志。
    """
    try:
        memory_client = get_memory_client()
        if not memory_client:
            return

        if getattr(memory_client, "enable_graph", False):
            logger.info(
                f"Graph build for turn {turn.id}: handled by Memory.add() during fact extraction"
            )
        else:
            logger.debug(f"Graph store not enabled, skipping graph build for turn {turn.id}")

    except Exception as e:
        logger.error(f"Graph build check failed for turn {turn.id}: {e}")


async def process_turn(db: AsyncSession, turn: Turn) -> bool:
    """处理单个 turn：顺序执行 fact → summary → graph"""
    try:
        # 更新状态为 processing
        turn.processing_status = "processing"
        await db.commit()

        # 1. 提取事实
        await process_fact_extraction(turn, db)

        # 2. 生成摘要
        await process_summary_generation(turn, db)

        # 3. 构建图谱
        await process_graph_build(turn, db)

        # 更新状态为 completed
        turn.processing_status = "completed"
        await db.commit()

        logger.info(f"Turn {turn.id} processing completed")
        return True

    except Exception as e:
        logger.error(f"Turn {turn.id} processing failed: {e}")
        turn.processing_status = "failed"
        await db.commit()
        return False


async def _process_session_turns(session_id: str, turns: list[Turn]) -> None:
    """处理同一 session 的 turns（顺序执行，保持 created_at 升序）。

    每个 turn 使用独立的 DB session，避免跨 turn 事务冲突。
    所有 turns 处理完后触发任务分段。
    """
    for turn in turns:
        async with async_session_maker() as db:
            try:
                # 重新从 DB 加载 turn（独立 session）
                stmt = select(Turn).where(col(Turn.id) == turn.id)
                result = await db.execute(stmt)
                fresh_turn = result.scalar_one_or_none()
                if not fresh_turn or fresh_turn.processing_status != "pending":
                    continue

                logger.info(f"Processing turn {fresh_turn.id} (session={session_id})")
                await process_turn(db, fresh_turn)
            except Exception as e:
                logger.error(f"Failed to process turn {turn.id} in session {session_id}: {e}")

    # Session 级后处理：任务分段
    await process_session_segmentation(session_id)


async def process_session_segmentation(session_id: str) -> None:
    """Session 级任务分段。

    检查 session 是否还有 pending turns，如果没有则运行 TaskSegmenter。
    """
    from app.memory.services.task_segmenter import segment_turns_heuristic, segment_turns_llm

    async with async_session_maker() as db:
        try:
            # 检查是否还有 pending turns
            pending_stmt = (
                select(func.count())
                .select_from(Turn)
                .where(col(Turn.session_id) == session_id, col(Turn.processing_status) == "pending")
            )
            pending_result = await db.execute(pending_stmt)
            pending_count = pending_result.scalar_one()

            if pending_count > 0:
                logger.debug(
                    f"Session {session_id} still has {pending_count} pending turns, "
                    "skipping segmentation"
                )
                return

            # 取出 session 的所有 completed turns
            turns_stmt = (
                select(Turn)
                .where(
                    col(Turn.session_id) == session_id, col(Turn.processing_status) == "completed"
                )
                .order_by(col(Turn.created_at).asc())
            )
            turns_result = await db.execute(turns_stmt)
            completed_turns = list(turns_result.scalars().all())

            if len(completed_turns) < 2:
                logger.debug(f"Session {session_id} has <2 completed turns, skipping segmentation")
                return

            # 检查是否已有 TaskSegment（避免重复分段）
            existing_stmt = (
                select(func.count())
                .select_from(TaskSegment)
                .where(col(TaskSegment.session_id) == session_id)
            )
            existing_result = await db.execute(existing_stmt)
            existing_count = existing_result.scalar_one()

            if existing_count > 0:
                logger.debug(
                    f"Session {session_id} already has {existing_count} segments, skipping"
                )
                return

            # 运行分段
            if settings.task_segmenter_use_llm:
                segments = await segment_turns_llm(completed_turns)
            else:
                segments = segment_turns_heuristic(completed_turns)

            # 持久化
            for seg in segments:
                db.add(seg)

            await db.commit()
            logger.info(
                f"Task segmentation completed for session {session_id}: "
                f"{len(segments)} segments from {len(completed_turns)} turns"
            )

        except Exception as e:
            logger.error(f"Session segmentation failed for {session_id}: {e}")
            await db.rollback()


async def run_worker_cycle() -> None:
    """单次 Worker 轮询：批量取 pending turns，按 session 分组并发处理。"""
    batch_size = settings.worker_batch_size
    max_concurrent = settings.worker_max_concurrent_sessions

    async with async_session_maker() as db:
        try:
            # 批量取出 N 条 pending turns（按 created_at 升序）
            statement = (
                select(Turn)
                .where(col(Turn.processing_status) == "pending")
                .order_by(col(Turn.created_at).asc())
                .limit(batch_size)
            )
            result = await db.execute(statement)
            turns = list(result.scalars().all())

            if not turns:
                logger.debug("No pending turns found")
                return

            logger.info(f"Fetched {len(turns)} pending turns for processing")

            # 按 session_id 分组
            session_groups: dict[str, list[Turn]] = defaultdict(list)
            for turn in turns:
                session_groups[turn.session_id].append(turn)

            # 同 session 内按 created_at 排序（应该已经排好，但确保）
            for sid in session_groups:
                session_groups[sid].sort(key=lambda t: t.created_at)

            # 并发处理不同 session（限制并发数）
            semaphore = asyncio.Semaphore(max_concurrent)

            async def _limited_process(sid: str, session_turns: list[Turn]) -> None:
                async with semaphore:
                    await _process_session_turns(sid, session_turns)

            tasks = [
                _limited_process(sid, session_turns)
                for sid, session_turns in session_groups.items()
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

            logger.info(
                f"Worker cycle completed: {len(turns)} turns across "
                f"{len(session_groups)} sessions"
            )

        except Exception as e:
            logger.error(f"Worker cycle failed: {e}", exc_info=True)


async def start_worker() -> None:
    """启动 Worker 循环"""
    logger.info("Memory worker started")
    while True:
        try:
            await run_worker_cycle()
        except Exception as e:
            logger.error(f"Worker error: {e}")

        await asyncio.sleep(5)  # 5 秒轮询


def start_worker_in_background() -> None:
    """在后台线程中启动 worker"""
    import threading

    def run() -> None:
        asyncio.run(start_worker())

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    logger.info("Memory worker thread started")
