"""Keyless Azure OpenAI adapter for the approved GPT-6 Luna deployment."""

import json
import logging
import os
import re
from contextvars import ContextVar
from functools import lru_cache
from typing import Callable

import requests
from azure.core.exceptions import AzureError
from azure.identity import get_bearer_token_provider

from azure_storage import runtime_identity
from inference_budget import InferenceBudget, InferenceBudgetUnavailable

MODEL = "gpt-6-luna"
MODEL_LABEL = "GPT‑6 Luna"
MAX_REQUEST_BYTES = 4000
MAX_OUTPUT_TOKENS = 500
FOUNDRY_TOKEN_SCOPE = "https://ai.azure.com/.default"
logger = logging.getLogger(__name__)
inference_status: ContextVar[str] = ContextVar("gmg_inference_status", default="directory")


class HostedModelUnavailable(RuntimeError):
    """The hosted model cannot return a usable response."""


def redact_contacts(text: str) -> str:
    text = re.sub(r"(?i)\b(?:https?://|www\.)[^\s\"<>\])]+", "[link]", text)
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email]", text)
    return re.sub(r"(?<!\w)\+?\d(?:[ .()\-]*\d){7,}(?!\w)", "[phone]", text)


class HostedInference:
    def __init__(self, endpoint: str, budget: InferenceBudget,
                 bearer_token: Callable[[], str]):
        account = endpoint.rstrip("/")
        if not re.fullmatch(r"https://[a-z0-9][a-z0-9-]*\.services\.ai\.azure\.com", account):
            raise ValueError("Configure a Microsoft Foundry account endpoint.")
        self.url = f"{account}/openai/v1/chat/completions"
        self.budget = budget
        self.bearer_token = bearer_token

    def complete(self, instructions: str, prompt: str, output_tokens: int, timeout: float,
                 schema: dict | None = None) -> str:
        payload = {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": redact_contacts(prompt)},
            ],
            "max_completion_tokens": min(output_tokens, MAX_OUTPUT_TOKENS),
            "reasoning_effort": "none",
            "stream": False,
        }
        if schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "gmg_directory_result", "schema": schema},
            }
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        # Budget the complete wire body and leave room for provider chat framing.
        if len(body) + 128 > MAX_REQUEST_BYTES:
            inference_status.set("request too large")
            raise HostedModelUnavailable("Hosted inference request is too large.")
        step = "allowance storage"
        try:
            self.budget.reserve()
            step = "managed identity"
            token = self.bearer_token()
            step = "Foundry request"
            reply = requests.post(
                self.url, data=body, headers={"Authorization": f"Bearer {token}",
                                             "Content-Type": "application/json"},
                timeout=(3, min(timeout, 45)), allow_redirects=False,
            )
            if reply.status_code != 200:
                inference_status.set(f"Foundry HTTP {reply.status_code}")
                logger.warning("Azure OpenAI returned HTTP %d", reply.status_code)
                raise HostedModelUnavailable("Hosted inference request failed.")
            result = reply.json()
            choice = result["choices"][0]
            content = choice["message"]["content"]
            usage = result.get("usage")
            if isinstance(usage, dict):
                counts = [usage.get(field) for field in ("prompt_tokens", "completion_tokens")]
                if all(type(count) is int and count >= 0 for count in counts):
                    logger.info("Azure OpenAI GPT-6 Luna tokens: input=%d output=%d", *counts)
            if choice.get("finish_reason") != "stop" or not isinstance(content, str) or not content.strip():
                inference_status.set("incomplete answer")
                logger.warning("Azure OpenAI did not return a complete answer")
                raise HostedModelUnavailable("Hosted inference returned an incomplete answer.")
            inference_status.set(MODEL_LABEL)
            return content.strip()
        except InferenceBudgetUnavailable as error:
            status = {
                "Hosted inference allowance reached.": "pilot allowance reached",
                "Hosted inference is paused.": "inference paused",
            }.get(str(error), step)
            inference_status.set(status)
            logger.warning("Hosted inference unavailable: %s", status)
            raise HostedModelUnavailable("Hosted inference is unavailable.") from error
        except (AzureError, requests.RequestException, ValueError, KeyError, IndexError, TypeError, AttributeError) as error:
            inference_status.set(step)
            logger.warning("Hosted inference unavailable: %s", type(error).__name__)
            raise HostedModelUnavailable("Hosted inference is unavailable.") from error


@lru_cache(maxsize=1)
def hosted_inference() -> HostedInference:
    try:
        return HostedInference(
            os.environ["GMG_FOUNDRY_ENDPOINT"],
            InferenceBudget.from_environment(), get_bearer_token_provider(runtime_identity(), FOUNDRY_TOKEN_SCOPE),
        )
    except (KeyError, ValueError) as error:
        inference_status.set("configuration")
        raise HostedModelUnavailable("Hosted inference is not configured.") from error
