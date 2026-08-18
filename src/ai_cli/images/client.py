"""OpenAI 兼容图片接口的调用。

用 openai 客户端拿到 base_url / api_key / 超时 / 重试这些既有能力，
但请求体按 docs/生成图片.md、docs/编辑图片.md 原样构造并发出，
返回值统一为 dict，不引入 SDK 的模型类型到上层。
"""

from __future__ import annotations

import os
from typing import Any, Mapping

from openai import APIStatusError, OpenAI, OpenAIError

from ..core.imageparams import ImageRequest
from ..errors import AppError, ExitCode, input_error

BASE_URL_ENV = "HUB_BASE_URL"
API_KEY_ENV = "HUB_API_KEY"


def make_client(*, timeout: float, max_retries: int) -> OpenAI:
    base_url = os.environ.get(BASE_URL_ENV)
    api_key = os.environ.get(API_KEY_ENV)
    missing = [name for name, value in ((BASE_URL_ENV, base_url), (API_KEY_ENV, api_key)) if not value]
    if missing:
        raise input_error("missing_credentials", f"缺少环境变量：{', '.join(missing)}")
    return OpenAI(base_url=base_url, api_key=api_key, timeout=timeout, max_retries=max_retries)


def generate(client: OpenAI, request: ImageRequest) -> dict[str, Any]:
    return _post(client, "/images/generations", request.body)


def edit(client: OpenAI, request: ImageRequest) -> dict[str, Any]:
    return _post(client, "/images/edits", request.body)


def _post(client: OpenAI, path: str, body: Mapping[str, Any]) -> dict[str, Any]:
    try:
        response = client.post(path, body=dict(body), cast_to=object)
    except APIStatusError as exc:
        raise AppError(
            f"http_{exc.status_code}",
            f"图片接口返回 {exc.status_code}：{_message_of(exc)}",
            ExitCode.API,
            {"endpoint": path, "response": _body_of(exc)},
        ) from None
    except OpenAIError as exc:
        raise AppError("request_failed", f"调用图片接口失败：{exc}", ExitCode.API, {"endpoint": path}) from None
    if not isinstance(response, dict):
        raise AppError(
            "unexpected_response",
            f"{path} 期望 JSON 对象，实际得到 {type(response).__name__}",
            ExitCode.API,
        )
    return response


def _body_of(exc: APIStatusError) -> Any:
    try:
        return exc.response.json()
    except ValueError:
        return exc.response.text[:2000]


def _message_of(exc: APIStatusError) -> str:
    body = _body_of(exc)
    if isinstance(body, Mapping):
        error = body.get("error")
        if isinstance(error, Mapping):
            return str(error.get("message") or error)
        if error:
            return str(error)
    return str(body)[:500]
