"""NVIDIA Nemotron via Nebius Token Factory (OpenAI-compatible API).

Every call is logged with model, latency and token usage, so the evidence
ledger can show exactly what the AI contributed.

Fail-safe: if NEBIUS_API_KEY is missing or the call fails, callers get None
and GovernGate continues with deterministic results only. AI output can add
explanation; it can never turn a failing verdict into a passing one.
"""

import json
import os
import time

import requests

BASE_URL = os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1")
# Fast model for routine calls, larger model for root cause. Both overridable.
FAST_MODEL = os.environ.get("NEMOTRON_FAST_MODEL", "nvidia/nemotron-3-super-120b-a12b")
REASONING_MODEL = os.environ.get("NEMOTRON_REASONING_MODEL", "nvidia/nemotron-3-ultra-550b-a55b")


class NemotronClient:
    def __init__(self, api_key=None, timeout=120):
        self.api_key = os.environ.get("NEBIUS_API_KEY") if api_key is None else api_key
        self.timeout = timeout
        self.calls = []          # provenance log for the evidence ledger
        self._model_ids = None

    @property
    def enabled(self):
        return bool(self.api_key)

    def _headers(self):
        return {"Authorization": "Bearer " + self.api_key, "Content-Type": "application/json"}

    def resolve_model(self, wanted):
        """Match the configured model against the live model list, ignoring case."""
        if self._model_ids is None:
            try:
                response = requests.get(BASE_URL + "/models", headers=self._headers(), timeout=30)
                response.raise_for_status()
                self._model_ids = [m["id"] for m in response.json().get("data", [])]
            except requests.RequestException:
                self._model_ids = []
        for model_id in self._model_ids:
            if model_id.lower() == wanted.lower():
                return model_id
        return wanted

    def complete_json(self, system, user, reasoning=False, max_tokens=1500):
        """Ask for a JSON object. Returns (dict or None, call record)."""
        if not self.enabled:
            record = {"status": "skipped", "reason": "NEBIUS_API_KEY not set"}
            self.calls.append(record)
            return None, record

        model = self.resolve_model(REASONING_MODEL if reasoning else FAST_MODEL)
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.1,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        started = time.time()
        record = {"model": model, "endpoint": BASE_URL}
        try:
            response = requests.post(BASE_URL + "/chat/completions", headers=self._headers(),
                                     json=payload, timeout=self.timeout)
            record["latency_seconds"] = round(time.time() - started, 2)
            response.raise_for_status()
            body = response.json()
            record["usage"] = body.get("usage", {})
            text = body["choices"][0]["message"]["content"]
            parsed = json.loads(text[text.find("{"): text.rfind("}") + 1])
            record["status"] = "ok"
            self.calls.append(record)
            return parsed, record
        except (requests.RequestException, KeyError, ValueError) as error:
            record["status"] = "error"
            record["error"] = str(error)[:200]
            record.setdefault("latency_seconds", round(time.time() - started, 2))
            self.calls.append(record)
            return None, record
