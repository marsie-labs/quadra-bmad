from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, field_validator


class QuadrantType(str, Enum):
    IS = "IS"
    IS_NOT = "IS_NOT"
    DOES = "DOES"
    DOES_NOT = "DOES_NOT"


class SessionCreate(BaseModel):
    project_name: str

    @field_validator("project_name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("project_name must not be blank")
        return v


class QuadrantOut(BaseModel):
    id: UUID
    canvas_id: UUID
    type: QuadrantType
    created_at: datetime


class CanvasState(BaseModel):
    canvas_id: UUID
    workspace_id: UUID
    is_active: bool
    quadrants: list[QuadrantOut]


class SessionResponse(BaseModel):
    session_id: UUID
    access_token: UUID
    access_url: str
    project_name: str
    canvas: CanvasState


class CardCreate(BaseModel):
    quadrant_id: UUID
    content: str = ""
    order_index: int = 0
    author_id: str | None = None


class CardUpdate(BaseModel):
    content: str | None = None
    quadrant_id: UUID | None = None
    order_index: int | None = None


class CardOut(BaseModel):
    id: UUID
    quadrant_id: UUID
    content: str
    order_index: int
    author_id: str | None
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime
