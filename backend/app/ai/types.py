from __future__ import annotations

from enum import Enum
from collections.abc import Iterator
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field


class AICapability(str, Enum):
    economy = "ECONOMY"
    fast = "FAST"
    reasoning = "REASONING"
    vision = "VISION"
    image = "IMAGE"
    embedding = "EMBEDDING"


CAPABILITY_RANK: dict[AICapability, int] = {
    AICapability.economy: 10,
    AICapability.fast: 20,
    AICapability.reasoning: 30,
    AICapability.vision: 40,
    AICapability.image: 50,
    AICapability.embedding: 60,
}


class AIMessage(BaseModel):
    role: str
    content: str


class AIBinaryInput(BaseModel):
    mime_type: str
    data_base64: str


class AIToolDefinition(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class AIToolCall(BaseModel):
    id: str | None = None
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class AIUsageMetadata(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    total_tokens: int = 0
    estimated: bool = False


class AIRequest(BaseModel):
    system_instruction: str
    messages: list[AIMessage]
    tools: list[AIToolDefinition] = Field(default_factory=list)
    response_schema: dict[str, Any] | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    timeout_seconds: int = Field(default=15, gt=0)
    cache_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    attachments: list[AIBinaryInput] = Field(default_factory=list, max_length=4)


class AIResponse(BaseModel):
    text: str | None = None
    tool_calls: list[AIToolCall] = Field(default_factory=list)
    provider: str
    model: str
    usage: AIUsageMetadata = Field(default_factory=AIUsageMetadata)
    finish_status: str | None = None
    cache_hit: bool = False
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class AIStreamChunk(BaseModel):
    text_delta: str = ""
    provider: str
    model: str
    done: bool = False
    usage: AIUsageMetadata = Field(default_factory=AIUsageMetadata)
    finish_status: str | None = None


class AIEmbeddingRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=100)
    task_type: Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY", "SEMANTIC_SIMILARITY"] = "SEMANTIC_SIMILARITY"
    dimensions: int = Field(default=768, ge=32, le=3072)
    timeout_seconds: int = Field(default=15, gt=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AIEmbeddingResponse(BaseModel):
    vectors: list[list[float]]
    provider: str
    model: str
    dimensions: int
    usage: AIUsageMetadata = Field(default_factory=AIUsageMetadata)
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class AIImageRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    mime_type: Literal["image/png", "image/jpeg", "image/webp"] = "image/png"
    aspect_ratio: str = "1:1"
    timeout_seconds: int = Field(default=45, gt=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AIImageResponse(BaseModel):
    data_base64: str
    mime_type: str
    provider: str
    model: str
    usage: AIUsageMetadata = Field(default_factory=AIUsageMetadata)
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class AIProviderError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


class AIProvider(Protocol):
    name: str

    def complete(self, *, model: str, request: AIRequest) -> AIResponse:
        ...

    def stream(self, *, model: str, request: AIRequest) -> Iterator[AIStreamChunk]:
        ...

    def embed(self, *, model: str, request: AIEmbeddingRequest) -> AIEmbeddingResponse:
        ...

    def generate_image(self, *, model: str, request: AIImageRequest) -> AIImageResponse:
        ...
