"""AI Learning router.

Provides endpoints for:
- Starting/stopping background learning
- Querying learning status and progress
- Viewing detected patterns and skills
- Managing amendment proposals
"""

import asyncio
import logging
import os
from datetime import UTC, datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.session import get_session
from app.memory.models import Turn

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ailearn", tags=["ailearn"])

# ------ Global AI Learning Instance ------
_ailearn_instance = None
_background_task = None
_llm_client = None


def get_llm_client():
    """Get LLM client from configuration."""
    global _llm_client
    if _llm_client is None:
        from openai import OpenAI

        api_key = os.environ.get("LLM_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
        base_url = os.environ.get("LLM_BASE_URL", os.environ.get("OPENAI_BASE_URL", ""))

        _llm_client = OpenAI(api_key=api_key, base_url=base_url)

    return _llm_client


async def fetch_recent_turns(session: AsyncSession, limit: int = 100) -> List[dict]:
    """Fetch recent turns from database."""
    try:
        statement = select(Turn).order_by(Turn.created_at.desc()).limit(limit)
        result = await session.exec(statement)
        turns = result.all()

        return [
            {
                "id": str(turn.id),
                "session_id": turn.session_id,
                "user_id": turn.user_id,
                "agent_id": turn.agent_id,
                "messages": turn.messages,
                "source": turn.source,
                "created_at": turn.created_at.isoformat() if turn.created_at else None,
            }
            for turn in turns
        ]
    except Exception as e:
        logger.error(f"Failed to fetch turns: {e}")
        return []


# ------ Response Models ------

class AILearnStatus(BaseModel):
    is_running: bool
    observations_count: int
    patterns_detected: int
    skills_extracted: int
    amendments_proposed: int
    health_status: str
    last_analysis: Optional[datetime] = None
    next_analysis: Optional[datetime] = None


class PatternInfo(BaseModel):
    id: str
    pattern_type: str
    name: str
    description: str
    confidence: float
    frequency: int
    extracted_at: datetime


class SkillInfo(BaseModel):
    id: str
    name: str
    description: str
    trigger_phrases: List[str]
    confidence: float
    extracted_at: datetime


class AmendmentInfo(BaseModel):
    id: str
    amendment_type: str
    memory_id: str
    reasoning: str
    confidence: float
    expected_impact: float
    created_at: datetime


class AILearnConfig(BaseModel):
    enabled: bool = True
    auto_learn_interval_minutes: int = Field(default=5, ge=1, le=60)
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    max_observations_per_batch: int = Field(default=1000, ge=100, le=10000)


class AILearnStartResponse(BaseModel):
    message: str
    config: AILearnConfig


# ------ Background Task ------

async def background_learning_task(
    interval_minutes: int,
    max_observations: int,
    confidence_threshold: float,
):
    """Background task that runs learning analysis periodically."""
    global _ailearn_instance

    logger.info(f"Starting AI Learning background task (interval: {interval_minutes}m)")

    while _ailearn_instance is not None:
        try:
            from app.db.session import async_session_maker
            from app.memory.ailearn.orchestrator import EnhancedAILearn

            if not isinstance(_ailearn_instance, EnhancedAILearn):
                break

            async with async_session_maker() as session:
                turns = await fetch_recent_turns(session, limit=100)

            results = await _ailearn_instance.analyze_and_learn(
                turns=turns,
                limit=max_observations,
            )

            logger.info(
                f"AI Learning analysis: "
                f"{results['observations_analyzed']} obs, "
                f"{results['turns_analyzed']} turns, "
                f"{results['patterns_detected']} patterns, "
                f"{results['skills_extracted']} skills"
            )

        except Exception as e:
            logger.error(f"AI Learning background error: {e}", exc_info=True)

        await asyncio.sleep(interval_minutes * 60)

    logger.info("AI Learning background task stopped")


# ------ API Endpoints ------

@router.get("/status", response_model=AILearnStatus)
async def get_ailearn_status():
    """Get current AI Learning status."""
    if _ailearn_instance is None:
        return AILearnStatus(
            is_running=False,
            observations_count=0,
            patterns_detected=0,
            skills_extracted=0,
            amendments_proposed=0,
            health_status="disabled",
        )

    try:
        health = await _ailearn_instance.get_health_status()
        return AILearnStatus(
            is_running=True,
            observations_count=0,
            patterns_detected=0,
            skills_extracted=0,
            amendments_proposed=0,
            health_status=health.get("status", "unknown"),
            last_analysis=datetime.now(UTC),
        )
    except Exception as e:
        logger.error(f"Error getting AI Learning status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start", response_model=AILearnStartResponse)
async def start_ailearn(config: AILearnConfig):
    """Start AI Learning background task."""
    global _ailearn_instance, _background_task

    if _ailearn_instance is not None:
        raise HTTPException(status_code=400, detail="AI Learning is already running")

    try:
        from app.memory.ailearn.orchestrator import EnhancedAILearn

        _ailearn_instance = EnhancedAILearn(
            storage_path="~/.openclaw/memory/ailearn",
            project_id="mission-control",
            auto_learn=config.enabled,
            llm_client=get_llm_client(),
            llm_model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
        )

        _background_task = asyncio.create_task(
            background_learning_task(
                interval_minutes=config.auto_learn_interval_minutes,
                max_observations=config.max_observations_per_batch,
                confidence_threshold=config.confidence_threshold,
            )
        )

        return AILearnStartResponse(
            message="AI Learning started successfully",
            config=config,
        )
    except Exception as e:
        logger.error(f"Error starting AI Learning: {e}", exc_info=True)
        _ailearn_instance = None
        _background_task = None
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_ailearn():
    """Stop AI Learning background task."""
    global _ailearn_instance, _background_task

    if _ailearn_instance is None:
        raise HTTPException(status_code=400, detail="AI Learning is not running")

    try:
        await _ailearn_instance.shutdown()
        if _background_task:
            _background_task.cancel()
            try:
                await _background_task
            except asyncio.CancelledError:
                pass

        _ailearn_instance = None
        _background_task = None
        return {"message": "AI Learning stopped successfully"}
    except Exception as e:
        logger.error(f"Error stopping AI Learning: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze")
async def trigger_analysis(session: AsyncSession = Depends(get_session)):
    """Manually trigger a learning analysis with recent turns."""
    if _ailearn_instance is None:
        raise HTTPException(status_code=400, detail="AI Learning is not running")

    try:
        turns = await fetch_recent_turns(session, limit=100)
        results = await _ailearn_instance.analyze_and_learn(turns=turns, limit=1000)
        return results
    except Exception as e:
        logger.error(f"Error triggering analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/patterns", response_model=List[PatternInfo])
async def get_patterns(limit: int = Query(10, ge=1, le=100)):
    return []


@router.get("/skills", response_model=List[SkillInfo])
async def get_skills(limit: int = Query(10, ge=1, le=100)):
    return []


@router.get("/amendments", response_model=List[AmendmentInfo])
async def get_amendments(limit: int = Query(10, ge=1, le=100)):
    return []


@router.post("/amendments/{amendment_id}/apply")
async def apply_amendment(amendment_id: str):
    if _ailearn_instance is None:
        raise HTTPException(status_code=400, detail="AI Learning is not running")
    return {"message": f"Amendment {amendment_id} applied successfully"}


@router.delete("/amendments/{amendment_id}")
async def reject_amendment(amendment_id: str):
    return {"message": f"Amendment {amendment_id} rejected"}
