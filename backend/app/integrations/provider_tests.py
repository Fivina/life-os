"""Small explicit connectivity checks: no AI inference or banking activation."""
import json

import httpx


class IntegrationConnectionTester:
    def __init__(self, *, transport: httpx.BaseTransport | None = None):
        self.transport = transport

    def test(self, provider: str, secret: str, *, environment: str, client_id: str | None = None) -> str | None:
        """Return a fixed public error code or None; never expose provider text."""
        method = "GET"
        params = None
        body = None
        headers = {"Accept": "application/json"}
        if provider == "tmdb":
            url = "https://api.themoviedb.org/3/configuration"
            headers["Authorization"] = f"Bearer {secret}"
        elif provider == "api-football":
            url = "https://v3.football.api-sports.io/status"
            headers["x-apisports-key"] = secret
        elif provider == "usda":
            url = "https://api.nal.usda.gov/fdc/v1/foods/list"
            # Data.gov supports header authentication; keep the key out of URLs/logs.
            headers["X-Api-Key"] = secret
            params = {"pageSize": 1}
        elif provider == "plaid":
            if not client_id:
                return "client_id_required"
            host = "sandbox" if environment == "sandbox" else "production"
            url = f"https://{host}.plaid.com/institutions/get"
            method = "POST"
            headers.update({"PLAID-CLIENT-ID": client_id, "PLAID-SECRET": secret, "Plaid-Version": "2020-09-14"})
            body = {"count": 1, "offset": 0, "country_codes": ["US"]}
        elif provider == "openai":
            url = "https://api.openai.com/v1/models"
            headers["Authorization"] = f"Bearer {secret}"
        else:
            return "test_unavailable"
        try:
            with httpx.Client(transport=self.transport, timeout=httpx.Timeout(10.0, connect=5.0),
                              follow_redirects=False, trust_env=False) as client:
                with client.stream(method, url, headers=headers, params=params, json=body) as response:
                    if response.status_code in {401, 403}:
                        return "authentication_failed"
                    if response.status_code == 429:
                        return "rate_limited"
                    if response.status_code >= 500:
                        return "provider_unavailable"
                    if response.status_code != 200:
                        return "provider_rejected"
                    content = bytearray()
                    for chunk in response.iter_bytes():
                        content.extend(chunk)
                        if len(content) > 262144:
                            return "invalid_response"
                    payload = json.loads(content)
        except httpx.TimeoutException:
            return "timeout"
        except httpx.HTTPError:
            return "network_error"
        except (ValueError, UnicodeError):
            return "invalid_response"
        if provider == "usda":
            return None if isinstance(payload, list) else "invalid_response"
        if not isinstance(payload, dict):
            return "invalid_response"
        if provider == "api-football":
            if payload.get("errors"):
                return "provider_rejected"
            valid = isinstance(payload.get("response"), dict)
        elif provider == "tmdb":
            valid = isinstance(payload.get("images"), dict)
        elif provider == "plaid":
            valid = isinstance(payload.get("institutions"), list)
        else:
            valid = isinstance(payload.get("data"), list)
        return None if valid else "invalid_response"
