"""Learning schemas - DTO для обучения Domain Parser."""

from typing import List, Optional
from pydantic import BaseModel, Field


class LearnedItemDTO(BaseModel):
    """Информация о выученном элементе."""
    domain: str = Field(..., description="Домен, на котором обучились")
    type: str = Field(..., description="Тип данных: 'inn' или 'email'")
    value: str = Field(..., description="Найденное значение (ИНН или Email)")
    sourceUrls: List[str] = Field(default_factory=list, description="URL источников, где найдены данные")
    urlPatterns: List[str] = Field(default_factory=list, description="Выученные URL паттерны")
    learning: str = Field(..., description="Описание того, чему научились")


class LearnManualInnRequestDTO(BaseModel):
    """Запрос на ручное обучение по ссылке с ИНН."""
    runId: str = Field(..., description="ID parsing run")
    domain: str = Field(..., description="Домен для обучения")
    inn: str = Field(..., description="ИНН, найденный вручную")
    sourceUrl: str = Field(..., description="URL страницы, где найден ИНН")
    learningSessionId: Optional[str] = Field(None, description="ID сессии обучения")


class LearningStatisticsDTO(BaseModel):
    """Статистика обучения."""
    totalLearned: int = Field(0, description="Всего выучено паттернов")
    cometContributions: int = Field(0, description="Количество обучений от Comet")
    successRateBefore: float = Field(0.0, description="Процент успеха до обучения")
    successRateAfter: float = Field(0.0, description="Процент успеха после обучения")


class LearnManualInnResponseDTO(BaseModel):
    """Ответ на ручное обучение по ИНН."""
    runId: str = Field(..., description="ID parsing run")
    learningSessionId: Optional[str] = Field(None, description="ID сессии обучения")
    learnedItems: List[LearnedItemDTO] = Field(default_factory=list, description="Выученные элементы")
    statistics: LearningStatisticsDTO = Field(..., description="Статистика обучения")
