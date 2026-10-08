from __future__ import annotations

import base64
from datetime import datetime
import hashlib
import math
import re
from collections.abc import Iterator
from json import JSONDecodeError, dumps, loads
from uuid import uuid4

import httpx

from app.ai.types import (
    AIEmbeddingRequest,
    AIEmbeddingResponse,
    AIImageRequest,
    AIImageResponse,
    AIMessage,
    AIProviderError,
    AIRequest,
    AIResponse,
    AIStreamChunk,
    AIToolCall,
    AIUsageMetadata,
)
from app.ai.fake_intents import DeterministicAssistantFake


def _estimated_usage(request: AIRequest, text: str | None) -> AIUsageMetadata:
    input_chars = len(request.system_instruction) + sum(len(message.content) for message in request.messages)
    output_chars = len(text or "")
    input_tokens = max(1, input_chars // 4)
    output_tokens = max(1, output_chars // 4) if output_chars else 0
    return AIUsageMetadata(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        estimated=True,
    )


class FakeAIProvider:
    name = "fake"

    def __init__(self) -> None:
        self.assistant_fake = DeterministicAssistantFake()

    def complete(self, *, model: str, request: AIRequest) -> AIResponse:
        metadata = request.metadata
        if metadata.get("mode") == "response_composition":
            text = str(metadata.get("fake_response") or "Life OS has an update.")
            return AIResponse(text=text, provider=self.name, model=model, usage=_estimated_usage(request, text), finish_status="STOP")
        if metadata.get("mode") == "receipt_extraction":
            text = dumps(metadata.get("fake_response") or {
                "merchant": None,
                "transaction_at": None,
                "currency": "EUR",
                "subtotal": None,
                "tax": None,
                "total": None,
                "confidence": 0,
                "items": [],
            }, separators=(",", ":"))
            return AIResponse(text=text, provider=self.name, model=model, usage=_estimated_usage(request, text), finish_status="STOP")
        if metadata.get("mode") == "meal_intent":
            text = dumps(metadata.get("fake_response") or {}, separators=(",", ":"))
            return AIResponse(text=text, provider=self.name, model=model, usage=_estimated_usage(request, text), finish_status="STOP")
        if metadata.get("mode") == "memory_extraction":
            user_message = next((message.content for message in reversed(request.messages) if message.role == "user"), "")
            text = dumps({"candidates": self._memory_candidates(user_message)}, separators=(",", ":"))
            return AIResponse(
                text=text,
                provider=self.name,
                model=model,
                usage=_estimated_usage(request, text),
                finish_status="STOP",
            )
        if metadata.get("mode") == "finalize_tool_result":
            text = str(metadata.get("tool_result_message") or "Canonical Life OS data was loaded.")
            return AIResponse(
                text=text,
                provider=self.name,
                model=model,
                usage=_estimated_usage(request, text),
                finish_status="STOP",
            )
        user_message = next((message.content for message in reversed(request.messages) if message.role == "user"), "")
        now_value = metadata.get("now")
        now = datetime.fromisoformat(now_value) if isinstance(now_value, str) and now_value else None
        result = self.assistant_fake.complete_structured(
            role=metadata.get("assistant_role", "GENERAL_ASSISTANT"),
            context=metadata.get("context", {}),
            user_message=user_message,
            now=now,
            timezone=metadata.get("timezone", "Europe/Berlin"),
            model=model,
        )
        text = result.intent.model_dump_json()
        return AIResponse(
            text=text,
            provider=self.name,
            model=model,
            usage=_estimated_usage(request, text),
            finish_status="STOP",
        )

    def stream(self, *, model: str, request: AIRequest) -> Iterator[AIStreamChunk]:
        response = self.complete(model=model, request=request)
        chunks = request.metadata.get("fake_stream_chunks")
        if not isinstance(chunks, list) or not all(isinstance(item, str) for item in chunks):
            chunks = [response.text or ""]
        for item in chunks:
            if item:
                yield AIStreamChunk(text_delta=item, provider=self.name, model=model)
        yield AIStreamChunk(
            provider=self.name,
            model=model,
            done=True,
            usage=response.usage,
            finish_status=response.finish_status,
        )

    @staticmethod
    def _memory_candidates(message: str) -> list[dict]:
        cleaned = re.sub(r"\s+", " ", message.strip())
        cleaned = re.sub(r"^remember(?: that)?\s+", "", cleaned, flags=re.IGNORECASE)
        lowered = cleaned.lower()
        domain = "general"
        for candidate_domain, terms in {
            "kitchen": ("food", "meal", "cook", "eat", "breakfast", "lunch", "dinner", "olive", "spicy", "savory"),
            "fitness": ("workout", "exercise", "gym", "training", "run"),
            "learning": ("study", "learn", "exam", "course", "reading"),
            "planning": ("schedule", "calendar", "plan", "morning", "evening"),
        }.items():
            if any(term in lowered for term in terms):
                domain = candidate_domain
                break

        preference = re.search(
            r"\b(?:i|we)\s+(?:really\s+)?(don't like|do not like|dislike|hate|like|love|prefer)\s+(.+?)(?:[.!?]|$)",
            cleaned,
            re.IGNORECASE,
        )
        if preference:
            verb = preference.group(1).lower()
            subject = preference.group(2).strip(" .,;:!?")
            polarity = -1 if verb in {"don't like", "do not like", "dislike", "hate"} else 1
            key = re.sub(r"[^a-z0-9 ]+", " ", subject.lower())
            return [{
                "memory_type": "domain_preference" if domain != "general" else "preference",
                "domain": domain,
                "content": cleaned,
                "normalized_key": re.sub(r"\s+", " ", key).strip(),
                "polarity": polarity,
                "importance": 0.65,
                "explicit": True,
            }]

        routine = re.search(r"\b(?:(?:i|please)\s+)?(always|never)\s+(.+?)(?:[.!?]|$)", cleaned, re.IGNORECASE)
        if routine:
            polarity = -1 if routine.group(1).lower() == "never" else 1
            subject = routine.group(2).strip(" .,;:!?")
            key = re.sub(r"[^a-z0-9 ]+", " ", subject.lower())
            return [{
                "memory_type": "constraint_preference" if polarity < 0 else "routine_preference",
                "domain": domain,
                "content": cleaned,
                "normalized_key": re.sub(r"\s+", " ", key).strip(),
                "polarity": polarity,
                "importance": 0.78,
                "explicit": True,
            }]

        interaction = re.search(r"\b(keep (?:answers|responses).+|(?:don't|do not) ask.+?)(?:[.!?]|$)", cleaned, re.IGNORECASE)
        if interaction:
            content = interaction.group(1).strip()
            key = re.sub(r"[^a-z0-9 ]+", " ", content.lower())
            return [{
                "memory_type": "interaction_preference",
                "domain": "general",
                "content": cleaned,
                "normalized_key": re.sub(r"\s+", " ", key).strip(),
                "polarity": -1 if "not " in content.lower() or "don't" in content.lower() else 1,
                "importance": 0.72,
                "explicit": True,
            }]

        remembered = re.search(r"\bremember(?: that)?\s+(.+?)(?:[.!?]|$)", cleaned, re.IGNORECASE)
        if remembered:
            content = remembered.group(1).strip()
            key = re.sub(r"[^a-z0-9 ]+", " ", content.lower())
            return [{
                "memory_type": "personal_fact",
                "domain": domain,
                "content": content,
                "normalized_key": re.sub(r"\s+", " ", key).strip(),
                "polarity": 0,
                "importance": 0.7,
                "explicit": True,
            }]
        return []

    def embed(self, *, model: str, request: AIEmbeddingRequest) -> AIEmbeddingResponse:
        vectors = [self._vector(text, request.dimensions) for text in request.texts]
        input_tokens = sum(max(1, len(text) // 4) for text in request.texts)
        return AIEmbeddingResponse(
            vectors=vectors,
            provider=self.name,
            model=model,
            dimensions=request.dimensions,
            usage=AIUsageMetadata(input_tokens=input_tokens, total_tokens=input_tokens, estimated=True),
        )

    @staticmethod
    def _vector(text: str, dimensions: int) -> list[float]:
        vector = [0.0] * dimensions
        normalized = re.sub(r"[^a-z0-9 ]+", " ", text.lower())
        tokens = normalized.split()
        features = tokens + [normalized[index : index + 3] for index in range(max(0, len(normalized) - 2))]
        for feature in features:
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [round(value / norm, 8) for value in vector]

    def generate_image(self, *, model: str, request: AIImageRequest) -> AIImageResponse:
        pixel = base64.b64encode(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
            b"\x00\x00\x00\rIDAT\x08\xd7c\xf8\xcf\xc0\xf0\x1f\x00\x05\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82"
        ).decode("ascii")
        return AIImageResponse(data_base64=pixel, mime_type="image/png", provider=self.name, model=model, provider_metadata={"synthetic": True})


class OpenAIEmbeddingProvider:
    name = "openai"

    def __init__(self, *, api_key: str | None, timeout_seconds: int = 15, base_url: str = "https://api.openai.com/v1") -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.base_url = base_url.rstrip("/")

    def embed(self, *, model: str, request: AIEmbeddingRequest) -> AIEmbeddingResponse:
        if not self.api_key:
            raise AIProviderError("missing_api_key", "OpenAI embeddings are not configured.")
        try:
            response = httpx.post(
                f"{self.base_url}/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": model, "input": request.texts, "dimensions": request.dimensions, "encoding_format": "float"},
                timeout=request.timeout_seconds or self.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise AIProviderError("provider_timeout", "The embedding provider timed out.", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise AIProviderError("provider_unavailable", "The embedding provider is unavailable.", retryable=True) from exc
        if response.status_code == 429:
            raise AIProviderError("rate_limited", "The embedding provider rate limit was reached.", retryable=True)
        if response.status_code >= 500:
            raise AIProviderError("provider_unavailable", "The embedding provider is temporarily unavailable.", retryable=True)
        if response.status_code in {401, 403}:
            raise AIProviderError("invalid_api_key", "OpenAI rejected the saved API key.")
        if response.status_code >= 400:
            raise AIProviderError("provider_rejected", "The embedding provider rejected the request.")
        try:
            payload = response.json()
            rows = payload["data"]
            rows = sorted(rows, key=lambda item: item["index"])
            if [item["index"] for item in rows] != list(range(len(request.texts))):
                raise ValueError("unexpected embedding indices")
            vectors = [item["embedding"] for item in rows]
            if len(vectors) != len(request.texts) or any(
                len(vector) != request.dimensions or not all(math.isfinite(float(value)) for value in vector)
                for vector in vectors
            ):
                raise ValueError("unexpected vector shape")
            vectors = [self._normalize_vector(vector) for vector in vectors]
            raw_usage = payload.get("usage") or {}
            input_tokens = int(raw_usage.get("prompt_tokens") or 0)
        except (JSONDecodeError, KeyError, TypeError, ValueError, IndexError) as exc:
            raise AIProviderError("malformed_provider_response", "The embedding provider returned an unexpected vector response.") from exc
        estimated = input_tokens == 0
        if estimated:
            input_tokens = sum(max(1, len(text) // 4) for text in request.texts)
        return AIEmbeddingResponse(
            vectors=vectors,
            provider=self.name,
            model=model,
            dimensions=request.dimensions,
            usage=AIUsageMetadata(input_tokens=input_tokens, total_tokens=input_tokens, estimated=estimated),
            provider_metadata={"batch_size": len(vectors)},
        )

    @staticmethod
    def _normalize_vector(vector: list[float]) -> list[float]:
        values = [float(value) for value in vector]
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]


class GeminiProvider:
    name = "gemini"

    def __init__(self, *, api_key: str | None, timeout_seconds: int = 15, base_url: str = "https://generativelanguage.googleapis.com/v1beta") -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.base_url = base_url.rstrip("/")

    def complete(self, *, model: str, request: AIRequest) -> AIResponse:
        if not self.api_key:
            raise AIProviderError("missing_api_key", "Gemini is not configured. Add GEMINI_API_KEY on the backend.")

        body = self._request_body(request)
        url = f"{self.base_url}/models/{model}:generateContent"
        try:
            response = httpx.post(
                url,
                headers={"x-goog-api-key": self.api_key},
                json=body,
                timeout=request.timeout_seconds or self.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise AIProviderError("provider_timeout", "The AI provider timed out.", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise AIProviderError("provider_unavailable", "The AI provider is unavailable.", retryable=True) from exc

        if response.status_code == 429:
            raise AIProviderError("rate_limited", "The AI provider rate limit was reached.", retryable=True)
        if response.status_code >= 500:
            raise AIProviderError("provider_unavailable", "The AI provider is temporarily unavailable.", retryable=True)
        if response.status_code in {401, 403}:
            raise AIProviderError("invalid_api_key", "Gemini rejected the saved API key.")
        if response.status_code >= 400:
            raise AIProviderError("provider_rejected", "The AI provider rejected the request.")

        try:
            payload = response.json()
        except JSONDecodeError as exc:
            raise AIProviderError("malformed_provider_response", "The AI provider returned an invalid response.") from exc
        return self._normalize(model, request, payload)

    def stream(self, *, model: str, request: AIRequest) -> Iterator[AIStreamChunk]:
        if not self.api_key:
            raise AIProviderError("missing_api_key", "Gemini is not configured. Add GEMINI_API_KEY on the backend.")
        url = f"{self.base_url}/models/{model}:streamGenerateContent"
        usage = AIUsageMetadata()
        finish_status: str | None = None
        try:
            with httpx.stream(
                "POST",
                url,
                headers={"x-goog-api-key": self.api_key},
                params={"alt": "sse"},
                json=self._request_body(request),
                timeout=request.timeout_seconds or self.timeout_seconds,
            ) as response:
                if response.status_code == 429:
                    raise AIProviderError("rate_limited", "The AI provider rate limit was reached.", retryable=True)
                if response.status_code >= 500:
                    raise AIProviderError("provider_unavailable", "The AI provider is temporarily unavailable.", retryable=True)
                if response.status_code in {401, 403}:
                    raise AIProviderError("invalid_api_key", "Gemini rejected the saved API key.")
                if response.status_code >= 400:
                    raise AIProviderError("provider_rejected", "The AI provider rejected the request.")
                for line in response.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    try:
                        payload = loads(line[5:].strip())
                        if not payload.get("candidates") and payload.get("usageMetadata"):
                            raw_usage = payload["usageMetadata"]
                            usage = AIUsageMetadata(
                                input_tokens=int(raw_usage.get("promptTokenCount") or 0),
                                output_tokens=int(raw_usage.get("candidatesTokenCount") or 0),
                                total_tokens=int(raw_usage.get("totalTokenCount") or 0),
                            )
                            continue
                        normalized = self._normalize(model, request, payload)
                    except (JSONDecodeError, AIProviderError) as exc:
                        if isinstance(exc, AIProviderError):
                            raise
                        raise AIProviderError("malformed_provider_response", "The AI provider returned an invalid stream chunk.") from exc
                    if normalized.text:
                        yield AIStreamChunk(text_delta=normalized.text, provider=self.name, model=model)
                    usage = normalized.usage
                    finish_status = normalized.finish_status or finish_status
        except httpx.TimeoutException as exc:
            raise AIProviderError("provider_timeout", "The AI provider timed out.", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise AIProviderError("provider_unavailable", "The AI provider is unavailable.", retryable=True) from exc
        yield AIStreamChunk(provider=self.name, model=model, done=True, usage=usage, finish_status=finish_status)

    def embed(self, *, model: str, request: AIEmbeddingRequest) -> AIEmbeddingResponse:
        if not self.api_key:
            raise AIProviderError("missing_api_key", "Gemini is not configured. Add GEMINI_API_KEY on the backend.")
        model_name = model if model.startswith("models/") else f"models/{model}"
        requests: list[dict] = []
        for text in request.texts:
            item: dict = {
                "model": model_name,
                "content": {"parts": [{"text": text}]},
                "embedContentConfig": {"outputDimensionality": request.dimensions},
            }
            if "embedding-2" not in model:
                item["embedContentConfig"]["taskType"] = request.task_type
            requests.append(item)
        try:
            response = httpx.post(
                f"{self.base_url}/{model_name}:batchEmbedContents",
                headers={"x-goog-api-key": self.api_key},
                json={"requests": requests},
                timeout=request.timeout_seconds or self.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise AIProviderError("provider_timeout", "The embedding provider timed out.", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise AIProviderError("provider_unavailable", "The embedding provider is unavailable.", retryable=True) from exc
        if response.status_code == 429:
            raise AIProviderError("rate_limited", "The embedding provider rate limit was reached.", retryable=True)
        if response.status_code >= 500:
            raise AIProviderError("provider_unavailable", "The embedding provider is temporarily unavailable.", retryable=True)
        if response.status_code in {401, 403}:
            raise AIProviderError("invalid_api_key", "Gemini rejected the saved API key.")
        if response.status_code >= 400:
            raise AIProviderError("provider_rejected", "The embedding provider rejected the request.")
        try:
            payload = response.json()
            vectors = [item["values"] for item in payload.get("embeddings") or []]
            if len(vectors) != len(request.texts) or any(
                not isinstance(vector, list)
                or len(vector) != request.dimensions
                or not all(math.isfinite(float(value)) for value in vector)
                for vector in vectors
            ):
                raise ValueError("unexpected vector shape")
            vectors = [self._normalize_vector([float(value) for value in vector]) for vector in vectors]
        except (JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise AIProviderError("malformed_provider_response", "The embedding provider returned an invalid response.") from exc
        raw_usage = payload.get("usageMetadata") or {}
        input_tokens = int(raw_usage.get("inputTokenCount") or raw_usage.get("promptTokenCount") or 0)
        estimated = input_tokens == 0
        if estimated:
            input_tokens = sum(max(1, len(text) // 4) for text in request.texts)
        return AIEmbeddingResponse(
            vectors=vectors,
            provider=self.name,
            model=model,
            dimensions=request.dimensions,
            usage=AIUsageMetadata(input_tokens=input_tokens, total_tokens=input_tokens, estimated=estimated),
            provider_metadata={"batch_size": len(vectors)},
        )

    def generate_image(self, *, model: str, request: AIImageRequest) -> AIImageResponse:
        if not self.api_key:
            raise AIProviderError("missing_api_key", "Gemini image generation is not configured.")
        body = {
            "contents": [{"role": "user", "parts": [{"text": request.prompt}]}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"], "imageConfig": {"aspectRatio": request.aspect_ratio}},
        }
        try:
            response = httpx.post(
                f"{self.base_url}/models/{model}:generateContent",
                headers={"x-goog-api-key": self.api_key},
                json=body,
                timeout=request.timeout_seconds or self.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise AIProviderError("provider_timeout", "The image provider timed out.", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise AIProviderError("provider_unavailable", "The image provider is unavailable.", retryable=True) from exc
        if response.status_code in {401, 403}:
            raise AIProviderError("invalid_api_key", "Gemini rejected the saved API key.")
        if response.status_code >= 400:
            raise AIProviderError("provider_rejected", "The image provider rejected the request.", retryable=response.status_code >= 500)
        try:
            payload = response.json()
            parts = payload["candidates"][0]["content"]["parts"]
            inline = next(part.get("inlineData") or part.get("inline_data") for part in parts if part.get("inlineData") or part.get("inline_data"))
            data = inline["data"]
            mime_type = inline.get("mimeType") or inline.get("mime_type") or request.mime_type
        except (JSONDecodeError, KeyError, IndexError, StopIteration, TypeError) as exc:
            raise AIProviderError("malformed_provider_response", "The image provider returned no usable image.") from exc
        raw_usage = payload.get("usageMetadata") or {}
        usage = AIUsageMetadata(
            input_tokens=int(raw_usage.get("promptTokenCount") or 0),
            output_tokens=int(raw_usage.get("candidatesTokenCount") or 0),
            total_tokens=int(raw_usage.get("totalTokenCount") or 0),
        )
        return AIImageResponse(data_base64=data, mime_type=mime_type, provider=self.name, model=model, usage=usage)

    @staticmethod
    def _normalize_vector(vector: list[float]) -> list[float]:
        norm = math.sqrt(sum(float(value) * float(value) for value in vector)) or 1.0
        return [float(value) / norm for value in vector]

    def _request_body(self, request: AIRequest) -> dict:
        contents: list[dict] = []
        for message in request.messages:
            role = "model" if message.role == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": message.content}]})
        if request.attachments:
            if not contents:
                contents.append({"role": "user", "parts": []})
            for attachment in request.attachments:
                contents[-1]["parts"].append({"inlineData": {"mimeType": attachment.mime_type, "data": attachment.data_base64}})
        body: dict = {
            "systemInstruction": {"parts": [{"text": request.system_instruction}]},
            "contents": contents,
            "generationConfig": {},
        }
        if request.temperature is not None:
            body["generationConfig"]["temperature"] = request.temperature
        if request.response_schema is not None:
            body["generationConfig"].update({"responseMimeType": "application/json", "responseJsonSchema": request.response_schema})
        if request.tools:
            body["tools"] = [{"functionDeclarations": [
                {"name": tool.name, "description": tool.description, "parametersJsonSchema": tool.parameters}
                for tool in request.tools
            ]}]
        return body

    def _normalize(self, model: str, request: AIRequest, payload: dict) -> AIResponse:
        candidates = payload.get("candidates") or []
        if not candidates:
            raise AIProviderError("malformed_provider_response", "The AI provider returned no response candidate.")
        candidate = candidates[0]
        parts = ((candidate.get("content") or {}).get("parts") or [])
        text_parts: list[str] = []
        tool_calls: list[AIToolCall] = []
        for part in parts:
            if isinstance(part.get("text"), str):
                text_parts.append(part["text"])
            function_call = part.get("functionCall")
            if function_call:
                tool_calls.append(AIToolCall(id=str(uuid4()), name=function_call.get("name", ""), arguments=function_call.get("args") or {}))
        raw_usage = payload.get("usageMetadata") or {}
        usage = AIUsageMetadata(
            input_tokens=int(raw_usage.get("promptTokenCount") or 0),
            output_tokens=int(raw_usage.get("candidatesTokenCount") or 0),
            cached_tokens=int(raw_usage.get("cachedContentTokenCount") or 0),
            total_tokens=int(raw_usage.get("totalTokenCount") or 0),
            estimated=False,
        )
        if usage.total_tokens == 0:
            usage = _estimated_usage(request, "\n".join(text_parts))
        return AIResponse(
            text="\n".join(text_parts).strip() or None,
            tool_calls=tool_calls,
            provider=self.name,
            model=model,
            usage=usage,
            finish_status=candidate.get("finishReason"),
            provider_metadata={"prompt_feedback": payload.get("promptFeedback")},
        )
