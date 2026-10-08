from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


class AuthTokenError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class VerifiedToken:
    subject: str
    email: str | None
    claims: dict[str, Any]


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except Exception as exc:  # pragma: no cover - defensive parser guard
        raise AuthTokenError("malformed_token", "Token is not valid base64url.") from exc


def _json_part(value: str) -> dict[str, Any]:
    try:
        decoded = json.loads(_b64url_decode(value))
    except json.JSONDecodeError as exc:
        raise AuthTokenError("malformed_token", "Token JSON is malformed.") from exc
    if not isinstance(decoded, dict):
        raise AuthTokenError("malformed_token", "Token payload is malformed.")
    return decoded


def _constant_time_hs256(token_head: str, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode("utf-8"), token_head.encode("ascii"), hashlib.sha256).digest()
    actual = _b64url_decode(signature)
    return hmac.compare_digest(expected, actual)


def _audience_matches(claim: Any, expected: str | None) -> bool:
    if not expected:
        return True
    if isinstance(claim, str):
        return claim == expected
    if isinstance(claim, list):
        return expected in {str(item) for item in claim}
    return False


def verify_supabase_jwt(
    token: str,
    *,
    secret: str,
    expected_issuer: str | None,
    expected_audience: str | None,
    now: datetime | None = None,
) -> VerifiedToken:
    parts = token.split(".")
    if len(parts) != 3:
        raise AuthTokenError("malformed_token", "Token must have three JWT segments.")

    header = _json_part(parts[0])
    payload = _json_part(parts[1])
    algorithm = header.get("alg")
    if algorithm != "HS256":
        raise AuthTokenError("unsupported_algorithm", "Only HS256 Supabase JWTs are supported by this deployment path.")

    if not _constant_time_hs256(f"{parts[0]}.{parts[1]}", parts[2], secret):
        raise AuthTokenError("invalid_signature", "Token signature is invalid.")

    current = int((now or datetime.now(UTC)).timestamp())
    expires_at = payload.get("exp")
    if not isinstance(expires_at, int) or expires_at <= current:
        raise AuthTokenError("expired_token", "Token has expired.")

    not_before = payload.get("nbf")
    if isinstance(not_before, int) and not_before > current:
        raise AuthTokenError("not_yet_valid", "Token is not valid yet.")

    issuer = payload.get("iss")
    if expected_issuer and issuer != expected_issuer:
        raise AuthTokenError("invalid_issuer", "Token issuer is invalid.")

    if not _audience_matches(payload.get("aud"), expected_audience):
        raise AuthTokenError("invalid_audience", "Token audience is invalid.")

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise AuthTokenError("missing_subject", "Token subject is missing.")

    email = payload.get("email")
    return VerifiedToken(subject=subject, email=email if isinstance(email, str) else None, claims=payload)
