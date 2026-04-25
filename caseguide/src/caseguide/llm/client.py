"""OpenAI-compatible chat-completions client.

Stdlib-only on purpose — a thin synchronous ``urllib`` POST keeps the
dependency surface flat and matches the one-shot, non-streaming usage
:class:`SuggestionsRefiner` needs. Any OpenAI-compatible endpoint
works: Ollama's ``/v1``, LM Studio's server, ``llama.cpp --server``,
or a remote provider.

This is intentionally a near-verbatim copy of Inscription's
``inscription.llm.client`` — the protocol is identical, the suite is
expected to point both apps at the same Ollama instance, and keeping
the implementations parallel avoids cross-package coupling between
two PyInstaller bundles. If divergence ever pays off (different auth
shapes, streaming tokens) we'll factor into a shared package then.
"""

from __future__ import annotations

import json
import logging
import socket
import urllib.error
import urllib.request
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)

DEFAULT_TEMPERATURE = 0.2


@runtime_checkable
class ChatClient(Protocol):
    """Structural type for anything that can chat.

    :class:`LLMClient` is the concrete implementation; tests supply fakes.
    Only the kwargs we actually use are required — callers may accept and
    ignore additional ones.
    """

    def chat(self, *, system: str, user: str) -> str:  # pragma: no cover - protocol
        ...


class LLMError(Exception):
    """Base class for LLM-related failures."""


class LLMConfigError(LLMError):
    """The client is misconfigured (empty base URL, bad timeout, etc.)."""


class LLMRequestError(LLMError):
    """The HTTP request itself failed (connection, timeout, HTTP 5xx)."""


class LLMResponseError(LLMError):
    """The endpoint responded but the body wasn't a usable chat completion."""


class LLMClient:
    """Minimal OpenAI-compatible chat-completions client."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_s: float,
        api_key: str | None = None,
    ) -> None:
        if not base_url:
            msg = "LLM base_url is empty"
            raise LLMConfigError(msg)
        if not model:
            msg = "LLM model is empty"
            raise LLMConfigError(msg)
        if timeout_s <= 0:
            msg = f"LLM timeout_s must be > 0 (got {timeout_s})"
            raise LLMConfigError(msg)
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_s = timeout_s
        self._api_key = api_key

    def chat(
        self,
        *,
        system: str,
        user: str,
        json_mode: bool = True,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> str:
        """Send one chat completion. Returns the assistant's message content.

        ``json_mode`` sets ``response_format={"type": "json_object"}`` which
        Ollama, LM Studio, and OpenAI respect — the model is biased toward
        emitting strict JSON. The caller is still responsible for parsing
        and validating.
        """
        body: dict[str, object] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "stream": False,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        url = f"{self._base_url}/chat/completions"
        req = urllib.request.Request(  # noqa: S310 - http(s) only via the base_url config
            url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:  # noqa: S310
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            detail = _safe_body(exc.read() if exc.fp else b"")
            msg = f"LLM HTTP {exc.code} from {url}: {detail}"
            raise LLMRequestError(msg) from exc
        except urllib.error.URLError as exc:
            msg = f"LLM request to {url} failed: {exc.reason}"
            raise LLMRequestError(msg) from exc
        except TimeoutError as exc:
            msg = f"LLM request to {url} timed out after {self._timeout_s}s"
            raise LLMRequestError(msg) from exc
        except OSError as exc:
            if isinstance(exc, socket.timeout):
                msg = f"LLM request to {url} timed out after {self._timeout_s}s"
                raise LLMRequestError(msg) from exc
            msg = f"LLM request to {url} failed: {exc}"
            raise LLMRequestError(msg) from exc

        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            msg = f"LLM returned non-JSON from {url}: {_safe_body(raw)}"
            raise LLMResponseError(msg) from exc

        try:
            content = parsed["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            msg = f"LLM response missing choices[0].message.content: {parsed!r}"
            raise LLMResponseError(msg) from exc

        if not isinstance(content, str) or not content.strip():
            msg = f"LLM response content empty or non-string: {content!r}"
            raise LLMResponseError(msg)
        return content


def _safe_body(raw: bytes, *, limit: int = 500) -> str:
    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001 - guarded best-effort decode for log/UI text
        return "<unreadable>"
    if len(text) > limit:
        return text[:limit] + "…"
    return text
