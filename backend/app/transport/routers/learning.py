"""Learning API router - обучение Domain Parser на основе Comet результатов."""

import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.session import get_db
from app.transport.routers.auth import get_current_user
from app.utils.authz import require_moderator
from app.transport.schemas.learning import (
    LearningStatisticsDTO,
    LearnedItemDTO,
    LearnManualInnRequestDTO,
    LearnManualInnResponseDTO
)
from app.usecases import get_parsing_run
import json
import os
import sys

router = APIRouter()
logger = logging.getLogger(__name__)

# Добавляем путь к domain_info_parser в sys.path
domain_parser_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "domain_info_parser")
if domain_parser_path not in sys.path:
    sys.path.insert(0, domain_parser_path)

# Try to import real LearningEngine; fall back to mock if unavailable.
try:
    from learning_engine import LearningEngine as _RealLearningEngine
    logger.info("LearningEngine imported successfully from domain_info_parser")
except ImportError:
    _RealLearningEngine = None
    logger.warning("LearningEngine not available — using MockLearningEngine")

# Глобальный экземпляр learning engine
_learning_instance = None


class MockLearningEngine:
    """Заглушка для Learning Engine (используется если реальный недоступен)."""
    
    def learn_from_manual_inn(self, domain, inn, source_url, learning_session_id):
        from urllib.parse import urlparse
        parsed = urlparse(source_url or "")
        path = (parsed.path or "/").strip() or "/"
        host = (parsed.netloc or domain or "").strip().lower()
        return {
            "learned_items": [
                {
                    "type": "inn",
                    "value": str(inn),
                    "source_urls": [str(source_url)],
                    "url_patterns": [f"{host}{path}"],
                    "learning": f"Ручное обучение: ИНН {inn} подтвержден на {host}{path}",
                }
            ]
        }
    
    def get_statistics(self):
        return {
            "total_learned": 0,
            "success_rate_before": 0.0,
            "success_rate_after": 0.0
        }
    
    def get_learned_summary(self, limit=10):
        return {"items": []}


def get_engine():
    """Получить глобальный экземпляр learning engine (реальный или mock)."""
    global _learning_instance
    if _learning_instance is None:
        if _RealLearningEngine is not None:
            try:
                _learning_instance = _RealLearningEngine()
                logger.info("Using real LearningEngine (patterns_file=%s)", _learning_instance.patterns_file)
            except Exception as e:
                logger.warning("Failed to init real LearningEngine: %s — using mock", e)
                _learning_instance = MockLearningEngine()
        else:
            _learning_instance = MockLearningEngine()
    return _learning_instance


@router.post("/learn-manual-inn", response_model=LearnManualInnResponseDTO)
async def learn_manual_inn(
    request: LearnManualInnRequestDTO,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Ручное обучение Domain Parser по ссылке, где найден ИНН."""
    require_moderator(current_user)
    run_id = request.runId
    learning_session_id = request.learningSessionId
    domain = request.domain.strip()
    inn = request.inn.strip()
    source_url = (request.sourceUrl or "").strip()
    source_urls = request.sourceUrls or []

    if not inn.isdigit() or len(inn) not in (10, 12):
        raise HTTPException(status_code=400, detail="Invalid INN format")

    urls: List[str] = []
    for u in (source_urls or []):
        if not u:
            continue
        us = str(u).strip()
        if not us:
            continue
        urls.append(us)
    if not urls and source_url:
        urls = [source_url]
    if not urls:
        raise HTTPException(status_code=400, detail="Invalid sourceUrl")
    for u in urls:
        if not u.startswith("http://") and not u.startswith("https://"):
            raise HTTPException(status_code=400, detail="Invalid sourceUrl")

    try:
        parsing_run = await get_parsing_run.execute(db=db, run_id=run_id)
        if not parsing_run:
            raise HTTPException(status_code=404, detail="Parsing run not found")

        engine_instance = get_engine()
        learned_items = []

        learned = engine_instance.learn_from_manual_inn(
            domain=domain,
            inn=inn,
            source_url=urls[0] if urls else "",
            source_urls=urls,
            learning_session_id=learning_session_id
        )

        if learned.get("learned_items"):
            for item in learned["learned_items"]:
                learned_items.append(LearnedItemDTO(
                    domain=domain,
                    type=item["type"],
                    value=item["value"],
                    sourceUrls=item["source_urls"],
                    urlPatterns=item["url_patterns"],
                    learning=item["learning"]
                ))

        stats = engine_instance.get_statistics()

        return LearnManualInnResponseDTO(
            runId=run_id,
            learningSessionId=learning_session_id,
            learnedItems=learned_items,
            statistics=LearningStatisticsDTO(
                totalLearned=stats["total_learned"],
                successRateBefore=stats["success_rate_before"],
                successRateAfter=stats["success_rate_after"]
            )
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in learn_manual_inn: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/statistics", response_model=LearningStatisticsDTO)
async def get_learning_statistics(
    current_user: dict = Depends(get_current_user),
):
    """Получить статистику обучения Domain Parser."""
    require_moderator(current_user)
    try:
        engine_instance = get_engine()
        stats = engine_instance.get_statistics()
        
        return LearningStatisticsDTO(
            totalLearned=stats["total_learned"],
            successRateBefore=stats["success_rate_before"],
            successRateAfter=stats["success_rate_after"]
        )
    except Exception as e:
        logger.error(f"Error getting learning statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/learned-summary")
async def get_learned_summary(
    limit: int = 10,
    current_user: dict = Depends(get_current_user),
):
    """Получить краткую сводку выученных паттернов."""
    require_moderator(current_user)
    try:
        engine_instance = get_engine()
        summary = engine_instance.get_learned_summary(limit=limit)
        
        return summary
    except Exception as e:
        logger.error(f"Error getting learned summary: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
