"""OpenAI 图片接口的请求体构造。纯函数。

不校验取值（model/size/quality/background 由上游负责报错），只做两件事：
1. 把 CLI 的字符串参数装配成请求体；
2. 应用已知的模型约束，并把“我改了你的参数”如实记录下来。
"""

from __future__ import annotations

import base64
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from ..errors import input_error

# gpt-image-2 只接受 background=auto，其余取值上游会直接报错。
FORCED_AUTO_BACKGROUND_MODELS = frozenset({"gpt-image-2"})


@dataclass(frozen=True)
class ImageRequest:
    """一次生成/编辑请求：body 直接发给接口，overrides 用于诚实地告知调用方。"""

    body: Mapping[str, Any]
    overrides: Mapping[str, str] = field(default_factory=dict)


def build_request(
    *,
    prompt: str,
    model: str,
    size: str,
    quality: str,
    background: str,
    number: str,
) -> ImageRequest:
    overrides: dict[str, str] = {}
    if model in FORCED_AUTO_BACKGROUND_MODELS and background != "auto":
        overrides["background"] = f"{background!r} → 'auto'（{model} 只支持 auto）"
        background = "auto"
    body = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "quality": quality,
        "background": background,
        "n": _as_count(number),
    }
    return ImageRequest(body, overrides)


def with_images(request: ImageRequest, paths: tuple[Path, ...]) -> ImageRequest:
    """给编辑请求补上 images：本地文件读成 base64 data URL。"""
    images = [{"image_url": data_url(p)} for p in paths]
    return ImageRequest({**request.body, "images": images}, request.overrides)


def data_url(path: Path) -> str:
    if not path.is_file():
        raise input_error("input_image_missing", f"输入图片不存在：{path}")
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}"


def _as_count(number: str) -> int:
    try:
        return int(number)
    except ValueError:
        raise input_error("invalid_number", f"--number 需要整数，实际得到 {number!r}") from None
