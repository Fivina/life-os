"""Compatibility exports for the provider-independent AI boundary."""

from app.ai.types import (
    AICapability,
    AIMessage,
    AIProvider,
    AIProviderError,
    AIRequest,
    AIResponse,
    AIToolCall,
    AIToolDefinition,
    AIUsageMetadata,
)

__all__ = [
    "AICapability",
    "AIMessage",
    "AIProvider",
    "AIProviderError",
    "AIRequest",
    "AIResponse",
    "AIToolCall",
    "AIToolDefinition",
    "AIUsageMetadata",
]
