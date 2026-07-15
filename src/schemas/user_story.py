"""Schemas para User Stories extraídas de transcripciones."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Priority(str, Enum):
    CRITICAL = "Highest"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class UserStory(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., description="Como [rol], quiero [acción] para [beneficio]")
    acceptance_criteria: list[str] = Field(
        ...,
        min_length=1,
        description="Formato Gherkin: Given/When/Then",
    )
    priority: Priority = Priority.MEDIUM
    story_points: Optional[int] = Field(None, ge=1, le=13)
    labels: list[str] = Field(default_factory=list)
    epic_link: Optional[str] = None
    extracted_from_file_id: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    extracted_at: datetime = Field(default_factory=datetime.now)

    @field_validator("story_points")
    @classmethod
    def validate_fibonacci(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v not in {1, 2, 3, 5, 8, 13}:
            raise ValueError(f"Story points debe ser Fibonacci (1,2,3,5,8,13). Recibido: {v}")
        return v

    @field_validator("acceptance_criteria")
    @classmethod
    def validate_ac(cls, v: list[str]) -> list[str]:
        for ac in v:
            if len(ac.strip()) < 10:
                raise ValueError(f"AC demasiado corto: '{ac}'")
        return [ac.strip() for ac in v]

    @field_validator("labels", mode="before")
    @classmethod
    def sanitize_labels(cls, v: list[str]) -> list[str]:
        if not v:
            return []
        # Jira no permite espacios en las etiquetas
        return [label.strip().replace(" ", "-") for label in v]

    @property
    def jira_description(self) -> str:
        acs = "\n".join(f"- {ac}" for ac in self.acceptance_criteria)
        return (
            f"{self.description}\n\n"
            f"*Criterios de Aceptación:*\n{acs}\n\n"
            f"_Extraído automáticamente · Confianza: {self.confidence_score:.0%}_"
        )


class ExtractionResult(BaseModel):
    file_id: str
    file_name: str
    user_stories: list[UserStory]
    extraction_warnings: list[str] = Field(default_factory=list)
    total_tokens_used: int = 0
