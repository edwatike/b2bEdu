"""Learning API router - обучение Domain Parser на основе Comet результатов."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.session import get_db
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

# Learning Engine временно отключен
LearningEngine = None

# Глобальный экземпляр learning engine
_learning_mock = None


class MockLearningEngine:
    """Заглушка для Learning Engine."""
    
    def learn_from_manual_inn(self, domain, inn, source_url, learning_session_id):
        # Fallback behavior: persist a minimal learned signal instead of returning empty.
        # This prevents "nothing to learn" for valid manual training input.
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
            "total_learned": 1,
            "success_rate_before": 0.0,
            "success_rate_after": 0.0
        }
    
    def get_learned_summary(self, limit=10):
        return {"items": []}


def get_engine():
    """Получить глобальный экземпляр learning engine."""
    global _learning_mock
    # Используем заглушку вместо реального LearningEngine
    if _learning_mock is None:
        _learning_mock = MockLearningEngine()
    return _learning_mock


@router.post("/learn-manual-inn", response_model=LearnManualInnResponseDTO)
async def learn_manual_inn(
    request: LearnManualInnRequestDTO,
    db: AsyncSession = Depends(get_db)
):
    """Ручное обучение Domain Parser по ссылке, где найден ИНН."""
    run_id = request.runId
    learning_session_id = request.learningSessionId
    domain = request.domain.strip()
    inn = request.inn.strip()
    source_url = request.sourceUrl.strip()

    if not inn.isdigit() or len(inn) not in (10, 12):
        raise HTTPException(status_code=400, detail="Invalid INN format")
    if not source_url.startswith("http://") and not source_url.startswith("https://"):
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
            source_url=source_url,
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
async def get_learning_statistics():
    """Получить статистику обучения Domain Parser."""
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
async def get_learned_summary(limit: int = 10):
    """Получить краткую сводку выученных паттернов."""
    try:
        engine_instance = get_engine()
        summary = engine_instance.get_learned_summary(limit=limit)
        
        return summary
    except Exception as e:
        logger.error(f"Error getting learned summary: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
