---
name: ai-image
description: 用 ai-cli 生成/编辑图片。包装本地 ComfyUI 工作流（flux2_klein 图片编辑、黑白底图还原透明度）与 OpenAI 兼容的 images 接口。当需要出图、改图、抠图/还原透明通道、批量并发生图时使用。
compatibility: 跨平台（Windows / Linux / macOS），ai-cli 已全局安装
---

# ai-image

统一入口：`ai-cli`（已全局安装，任意目录可用）。约定：**stdout 只有结果，stderr 是进度，退出码有契约**。
给 agent 用时加 `--format json`，stdout 恰好是一个 JSON 对象。

退出码：0 成功 / 2 用法错 / 3 本地输入错 / 4 上游错 / 5 超时（任务仍在跑）/ 6 执行失败 / 7 被取消 / 8 部分成功 / 130 Ctrl+C。

## 工作流清单

| 工作流文件 | 用途 | 参数 |
| --- | --- | --- |
| `D:\TOOLS\workflow\flux2_klein.json` | 用 flux2_klein 编辑图片，单次约 10–20s | `75:74.inputs.text` 提示词<br>`76.inputs.image` 参考图像 |
| `D:\TOOLS\workflow\抠出图片中主体.json` | 将图片中的主体自动抠出来 | `2.inputs.image` 输入图片 |
| `D:\TOOLS\workflow\抠出图片中半透明或是不清晰边缘的主体.json` | 抠出图片中半透明或是不清晰边缘的主体 | `76.inputs.image` 输入图片<br> `168:165.inputs.text` 提示词1，用于将输入图片转成白底图片,例如 保持主体位置和大小不变，保持光照不变，仅将背景变成白色 <br> `75:74.inputs.text` 提示词2，用于将输入图片转成黑底图片,例如 保持主体位置和大小不变，保持光照不变，仅将背景变成黑色|

本地文件必须写成 `@upload{路径}`，提交前自动上传并回填服务端文件名。
POSIX shell（bash/zsh）下 `--values` 一律用**单引号**包起来，防止 `{}` 括号展开与中文/空格被拆；PowerShell 用双引号。

## ComfyUI

`--values` 规则：`path=value` 只按第一个 `=` 切分；`.` 分段，节点 id 里的 `:` 不是分隔符，数组用 `a[0]`；
**路径必须已存在**（打错直接报错并列出同层键）；value 先按 JSON 字面量解析，所以 `seed`/`steps` 会是真数字。

如果要改工作流清单中未标明的参数，要先自省，别把整个 json 读进上下文：

```bash
ai-cli comfyui workflow inspect 'D:/TOOLS/workflow/flux2_klein.json' [--filter text]
ai-cli comfyui job submit --workflow wf.json --values '7.inputs.seed=42' --dry-run   # 只看补丁结果
```

并发：async 提交 + 一次收网，不要自己写并发。

```bash
a=$(ai-cli comfyui job submit --workflow wf.json --values '7.inputs.seed=1' --mode async)
b=$(ai-cli comfyui job submit --workflow wf.json --values '7.inputs.seed=2' --mode async)
ai-cli comfyui job wait "$a" "$b" --output-path out --timeout 600
```

```powershell
$a = ai-cli comfyui job submit --workflow wf.json --values "7.inputs.seed=1" --mode async
$b = ai-cli comfyui job submit --workflow wf.json --values "7.inputs.seed=2" --mode async
ai-cli comfyui job wait $a $b --output-path out --timeout 600
```

其余：`job status|cancel|list`。服务器地址 `--server` > `COMFYUI_SERVER` > `http://127.0.0.1:8188`。

超时（码 5）不等于失败，任务还在服务端跑，stdout 里有继续等待的命令；要取消才加 `--on-timeout cancel`。
执行失败时节点级 `execution_error` 完整出现在 `jobs[].error`，那是修工作流的唯一线索。

## OpenAI 兼容接口

```bash
ai-cli openai-image generate --prompt '城市夜景' --number 2 --output-path out
ai-cli openai-image edit --prompt '把图一的帽子戴到图二的人身上' \
  --input-image a.png --input-image b.png --output-path out
```

默认模型 `gpt-image-2`（只支持 `background=auto`，会被强制改写并记录）。落盘为
`提示词前20字-序号-uuid.png` 加同批一份参数 sidecar json。


## 最佳实践推荐
- 生成图片后不要自动读图复核，除非用户让这样
- 多图合成、自然语言描述改图和生成图片、不想调工作流、效果想要好 使用 openai-image edit，优先auto 或 low, 模型使用gpt-image-2，只有当用户明确指定参数 --quality high的时候才用high
- flux2_klein 是图片编辑模型，速度快，质量一般，简单的图片编辑选这个
- 将素材变成带透明度的，如果素材是简单边缘素材，无半透明用 抠出图片中主体.json，如果边缘复杂带有半透明效果用 抠出图片中半透明或是不清晰边缘的主体.json
- 用户想要图片的某个元素的透明图片的时候，可以openai-image edit取出元素白底图 > 判断元素是简单边缘还是复杂边缘半透明 > 调用将素材变成带透明度的工作流

