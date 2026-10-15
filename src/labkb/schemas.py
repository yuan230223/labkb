from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=3000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=800)
    history: list[Message] = Field(default_factory=list, max_length=12)
    top_k: int = Field(default=4, ge=1, le=6)

    @field_validator("message")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("问题不能为空")
        return value.strip()


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=800)
    top_k: int = Field(default=4, ge=1, le=6)
