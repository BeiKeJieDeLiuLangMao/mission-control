"""
Memory API 兼容路由。

将旧版 /api/v1/* 和 /api/v2/* 路径映射到新的 /memory/* 路由，
使现有的 OpenClaw 插件、Claude Code 插件和前端无需修改即可工作。
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.memory.internal_crud import (
    delete_memory,
    list_memories,
    search_memories,
)
from app.api.memory.adapter_turns import (
    create_turn,
    delete_turn,
    get_turn,
    list_turns,
)
from app.db.session import get_session
from app.memory.models import VectorMemory
from app.memory.schemas import TurnStoreRequest, TurnStoreResponse
from app.memory.services.client_factory import get_memory_client

logger = logging.getLogger(__name__)

# ============================================================
# v2 兼容路由（Claude Code 插件 + OpenClaw 插件使用）
# ============================================================

v2_turns = APIRouter(prefix="/api/v2/turns", tags=["compat-v2-turns"])
v2_memories = APIRouter(prefix="/api/v2/memories", tags=["compat-v2-memories"])


@v2_turns.post("/", response_model=TurnStoreResponse)
async def v2_create_turn(request: TurnStoreRequest, session: AsyncSession = Depends(get_session)):
    return await create_turn(request, session)


@v2_turns.get("/")
async def v2_list_turns(
    user_id: str = Query(...),
    session_id: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    return await list_turns(user_id, session_id, agent_id, status, limit, offset, session)


@v2_turns.get("/{turn_id}")
async def v2_get_turn(turn_id: str, session: AsyncSession = Depends(get_session)):
    return await get_turn(turn_id, session)


@v2_turns.delete("/{turn_id}")
async def v2_delete_turn(turn_id: str, session: AsyncSession = Depends(get_session)):
    return await delete_turn(turn_id, session)


@v2_memories.get("/")
async def v2_list_memories(
    user_id: str = Query(...),
    agent_id: Optional[str] = Query(None),
    memory_type: Optional[str] = Query(None),
    turn_id: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    return await list_memories(user_id, agent_id, memory_type, turn_id, limit, offset, session)


@v2_memories.get("/search")
async def v2_search_memories(
    user_id: str = Query(...),
    query: str = Query(...),
    agent_id: Optional[str] = Query(None),
    memory_type: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    return await search_memories(user_id, query, agent_id, memory_type, limit, session)


@v2_memories.delete("/{memory_id}")
async def v2_delete_memory(memory_id: str, session: AsyncSession = Depends(get_session)):
    return await delete_memory(memory_id, session)


# ============================================================
# v1 兼容路由（前端使用）
# ============================================================

v1_memories = APIRouter(prefix="/api/v1", tags=["compat-v1-memories"])


@v1_memories.get("/memories")
async def v1_list_memories(
    user_id: str = Query("yishu"),
    agent_id: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    return await list_memories(user_id, agent_id, None, None, limit, offset, session)


@v1_memories.get("/memories/search")
async def v1_search_memories(
    user_id: str = Query("yishu"),
    query: str = Query(...),
    agent_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    return await search_memories(user_id, query, agent_id, None, limit, session)


@v1_memories.delete("/memories/{memory_id}")
async def v1_delete_memory(memory_id: str, session: AsyncSession = Depends(get_session)):
    return await delete_memory(memory_id, session)


# v1 Turn 路由（OpenClaw 插件使用 /api/v1/turns/）
v1_turns = APIRouter(prefix="/api/v1", tags=["compat-v1-turns"])


@v1_turns.post("/turns/", response_model=TurnStoreResponse)
async def v1_create_turn(request: TurnStoreRequest, session: AsyncSession = Depends(get_session)):
    return await create_turn(request, session)


# ============================================================
# v1 Graph 路由（前端 MemoryGraph 组件使用）
# ============================================================

v1_graph = APIRouter(prefix="/api/v1", tags=["compat-v1-graph"])


class GraphRelation(BaseModel):
    source: str
    relationship: str
    target: str


class GraphResponse(BaseModel):
    relations: list[GraphRelation] = []
    total: int = 0


class GraphStats(BaseModel):
    nodes: int = 0
    relations: int = 0
    relation_types: dict[str, int] = {}


class GraphAgentItem(BaseModel):
    agent_id: str
    memory_count: int
    source: str = "unknown"


class GraphAgentsResponse(BaseModel):
    agents: list[GraphAgentItem] = []


@v1_graph.get("/graph", response_model=GraphResponse)
async def v1_get_graph(
    user_id: str = Query("yishu"),
    agent_id: Optional[str] = Query(None),
):
    """查询知识图谱关系"""
    memory_client = get_memory_client()
    if not memory_client or not getattr(memory_client, "enable_graph", False):
        return GraphResponse()

    try:
        graph = memory_client.graph

        # 查询 Neo4j 中的关系（支持 agent_id 过滤）
        if agent_id:
            query = """
            MATCH (s)-[r]->(t)
            WHERE s.user_id = $user_id AND s.agent_id = $agent_id
            RETURN s.name AS source, type(r) AS relationship, t.name AS target
            LIMIT 200
            """
            results = graph.graph.query(query, params={"user_id": user_id, "agent_id": agent_id})
        else:
            query = """
            MATCH (s)-[r]->(t)
            WHERE s.user_id = $user_id
            RETURN s.name AS source, type(r) AS relationship, t.name AS target
            LIMIT 200
            """
            results = graph.graph.query(query, params={"user_id": user_id})
        relations = [
            GraphRelation(
                source=str(r["source"] or "unknown"),
                relationship=str(r["relationship"] or "RELATED"),
                target=str(r["target"] or "unknown"),
            )
            for r in results
            if r.get("source") and r.get("target")
        ]
        return GraphResponse(relations=relations, total=len(relations))
    except Exception as e:
        logger.warning(f"Graph query failed: {e}")
        return GraphResponse()


@v1_graph.get("/graph/search", response_model=GraphResponse)
async def v1_graph_search(
    q: str = Query(""),
    user_id: str = Query("yishu"),
    agent_id: Optional[str] = Query(None),
):
    """搜索知识图谱"""
    memory_client = get_memory_client()
    if not memory_client or not getattr(memory_client, "enable_graph", False) or not q:
        return GraphResponse()

    try:
        filters = {"user_id": user_id}
        if agent_id:
            filters["agent_id"] = agent_id
        results = memory_client.graph.search(q, filters)
        relations = []
        for item in results:
            if isinstance(item, dict) and "source" in item:
                relations.append(
                    GraphRelation(
                        source=str(item.get("source", "unknown")),
                        relationship=str(item.get("relationship", "RELATED")),
                        target=str(item.get("target", "unknown")),
                    )
                )
        return GraphResponse(relations=relations, total=len(relations))
    except Exception as e:
        logger.warning(f"Graph search failed: {e}")
        return GraphResponse()


@v1_graph.get("/graph/stats", response_model=GraphStats)
async def v1_graph_stats(
    user_id: str = Query("yishu"),
    agent_id: Optional[str] = Query(None),
):
    """获取知识图谱统计"""
    memory_client = get_memory_client()
    if not memory_client or not getattr(memory_client, "enable_graph", False):
        return GraphStats()

    try:
        graph = memory_client.graph
        params: dict = {"user_id": user_id}
        agent_filter = ""
        if agent_id:
            agent_filter = " AND n.agent_id = $agent_id"
            params["agent_id"] = agent_id

        # 节点数
        node_result = graph.graph.query(
            f"MATCH (n) WHERE n.user_id = $user_id{agent_filter} RETURN count(n) AS cnt",
            params=params,
        )
        nodes = node_result[0]["cnt"] if node_result else 0

        # 关系数和类型
        rel_agent_filter = " AND s.agent_id = $agent_id" if agent_id else ""
        rel_result = graph.graph.query(
            f"MATCH (s)-[r]->(t) WHERE s.user_id = $user_id{rel_agent_filter} RETURN type(r) AS rel_type, count(*) AS cnt",
            params=params,
        )
        relation_types = {}
        total_relations = 0
        for row in rel_result:
            rt = str(row["rel_type"])
            cnt = int(row["cnt"])
            relation_types[rt] = cnt
            total_relations += cnt

        return GraphStats(nodes=nodes, relations=total_relations, relation_types=relation_types)
    except Exception as e:
        logger.warning(f"Graph stats failed: {e}")
        return GraphStats()


@v1_graph.get("/graph/agents", response_model=GraphAgentsResponse)
async def v1_graph_agents(
    user_id: str = Query("yishu"),
    session: AsyncSession = Depends(get_session),
):
    """获取有记忆的 agent 列表（从 vector_memories 聚合，带 source）"""
    try:
        # 按 agent_id 聚合，取最常见的 source 作为该 agent 的来源
        statement = (
            select(
                VectorMemory.agent_id,
                func.count().label("cnt"),
                VectorMemory.source,
            )
            .where(VectorMemory.user_id == user_id)
            .where(col(VectorMemory.agent_id).is_not(None))
            .group_by(VectorMemory.agent_id, VectorMemory.source)
            .order_by(func.count().desc())
        )
        result = await session.exec(statement)
        rows = result.all()

        # 合并同 agent_id 的不同 source 行，选 count 最大的 source
        agent_map: dict[str, dict] = {}
        for row in rows:
            aid = str(row[0])
            cnt = int(row[1])
            src = str(row[2]) if row[2] else "unknown"
            if not aid:
                continue
            if aid not in agent_map:
                agent_map[aid] = {
                    "agent_id": aid,
                    "memory_count": cnt,
                    "source": src,
                    "_max_cnt": cnt,
                }
            else:
                agent_map[aid]["memory_count"] += cnt
                if cnt > agent_map[aid]["_max_cnt"]:
                    agent_map[aid]["source"] = src
                    agent_map[aid]["_max_cnt"] = cnt

        agents = sorted(
            [
                GraphAgentItem(
                    agent_id=v["agent_id"],
                    memory_count=v["memory_count"],
                    source=v["source"],
                )
                for v in agent_map.values()
            ],
            key=lambda a: a.memory_count,
            reverse=True,
        )
        return GraphAgentsResponse(agents=agents)
    except Exception as e:
        logger.warning(f"Graph agents query failed: {e}")
        return GraphAgentsResponse()


# ============================================================
# v2 recall 路由
# ============================================================

from app.api.memory.intelligent_recall import router as v2_recall_inner

v2_recall = APIRouter(prefix="/api/v2", tags=["compat-v2-recall"])
v2_recall.include_router(v2_recall_inner)

# ============================================================
# 聚合路由器
# ============================================================

router = APIRouter()
router.include_router(v2_turns)
router.include_router(v2_memories)
router.include_router(v2_recall)
router.include_router(v1_turns)
router.include_router(v1_memories)
router.include_router(v1_graph)
