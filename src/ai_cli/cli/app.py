"""root Typer app。"""

from __future__ import annotations

import typer

from .comfyui import comfyui_app
from .context import FormatOption, store
from .images import image_app

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="给 AI agent 用的图像生成 CLI：ComfyUI 工作流 + OpenAI 兼容图片接口。",
)
app.add_typer(comfyui_app, name="comfyui")
app.add_typer(image_app, name="openai-image")


@app.callback()
def main(ctx: typer.Context, fmt: FormatOption = None) -> None:
    """--format 也可以写在子命令上，就近者优先。"""
    store(ctx, format=fmt)
