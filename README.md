# ai-cli

给 AI agent 用的图像生成 CLI：包装本地 ComfyUI 的 HTTP 接口，以及 OpenAI 兼容的图片生成/编辑接口。

设计取向：**stdout 只放结果，stderr 放进度，退出码有契约，失败一定带上游报文。**

```powershell
uv sync
uv run ai-cli --help
```

## 全局

| 选项 | 说明 |
| --- | --- |
| `--format text\|json` | 默认 `text`。可写在任意一层（root / comfyui / 叶子命令），就近者优先 |

`--format json` 时 stdout 恰好是一个 JSON 对象：成功 `{"ok": true, ...}`，失败 `{"ok": false, "error": {code, message, details}}`。
进度、上传日志、执行错误详情一律走 stderr，不污染解析。

### 退出码

| 码 | 含义 |
| --- | --- |
| 0 | 成功 |
| 2 | 命令行用法错误（Typer） |
| 3 | 本地输入有问题（文件不存在、路径写错、workflow 格式不对） |
| 4 | 上游接口返回错误 |
| 5 | 等待超时（任务仍在服务端执行，没有被取消） |
| 6 | 任务执行失败 |
| 7 | 任务被取消 |
| 8 | 部分成功（例如 4 张图只落盘 3 张） |
| 130 | 用户 Ctrl+C 中断。已提交的任务不会被取消，仍在服务端继续执行 |

## ai-cli comfyui

服务器地址优先级：`--server` > `COMFYUI_SERVER` 环境变量 > `http://127.0.0.1:8188`。

### job submit

```powershell
# 阻塞直到出图，返回图片路径列表
ai-cli comfyui job submit --workflow wf.json `
  --values "75:74.inputs.text=一只柯基穿着西装" `
  --values "7.inputs.seed=42" `
  --values "7.inputs.steps=30" `
  --output-path out --timeout 300

# 本地资源用 @upload{...} 包围：提交前自动上传，再把服务端文件名填回该位置
ai-cli comfyui job submit --workflow wf.json `
  --values "10.inputs.image=@upload{./cat.png}" `
  --values "12.inputs.video=@upload{./clip.mp4}"

# 只看打好补丁的 workflow，不上传不提交
ai-cli comfyui job submit --workflow wf.json --values "7.inputs.seed=42" --dry-run
```

`--values` 的约定：

- `path=value`，**只按第一个 `=` 切分**（提示词里可以有 `=`）。
- path 用 `.` 分段，节点 id 里的 `:` 不是分隔符；数组用 `a[0]`。
- **路径必须已存在**，打错字直接报错并列出同层可用键（打错字静默生成一张“没改过”的图更糟）。
- value 先按 JSON 字面量解析（`42`→数字、`true`→布尔、`[..]`→数组），解析不了才当字符串。
  ComfyUI 的 `seed`/`steps` 需要真数字，字符串会被节点拒绝。
- 需要上传的本地文件写成 `@upload{./cat.png}`。图片、视频、音频、文本走同一个上传入口
  （`POST /api/upload/image` 对字节内容不做类型限制），服务端按“文件名 + 内容哈希”自动去重。
  标记可以出现在 JSON 数组里：`--values '10.inputs.images=["@upload{a.png}","@upload{b.png}"]'`。

并发上传/下载由 `--concurrency` 控制（默认 4）。

### 长任务与并发

`--mode sync`（默认）= submit + wait 的糖。**超时不等于失败，也不会取消任务**：

```powershell
ai-cli comfyui job submit --workflow wf.json --timeout 90
# 超时 → 退出码 5，stdout 给出 timeout.unfinished 与继续等待的命令
```

`--on-timeout cancel` 才会顺手取消。想要并发就 async 提交、批量收网，**不需要写 bash 并发**：

```powershell
$a = ai-cli comfyui job submit --workflow wf.json --values "7.inputs.seed=1" --mode async
$b = ai-cli comfyui job submit --workflow wf.json --values "7.inputs.seed=2" --mode async
ai-cli comfyui job wait $a $b --output-path out --timeout 600
```

`job wait` 一次等待多个 id，并发下载全部产物，输出一个完整 JSON，不会出现输出交错。

### 其余子命令

```powershell
ai-cli comfyui job status <job_id> [<job_id> ...]   # 只查状态，不下载
ai-cli comfyui job cancel <job_id> [<job_id> ...]   # 幂等
ai-cli comfyui job list --status pending,in_progress --limit 20   # 丢了 job id 时找回来
ai-cli comfyui workflow inspect wf.json [--filter text]          # 列出可赋值的输入槽与当前值
```

`workflow inspect` 是给 agent 省上下文的：不必把整个 workflow.json 读进对话就知道该改哪个路径。

任务执行失败时，服务端的 `execution_error`（节点 id、异常信息）会完整出现在结果的 `jobs[].error`
里并同时打到 stderr —— 那是修 workflow 的唯一线索，不做截断。

## ai-cli openai-image

地址与密钥取自环境变量 `HUB_BASE_URL` / `HUB_API_KEY`。

```powershell
ai-cli openai-image generate --prompt "生成个城市夜景" --number 2 --output-path out
ai-cli openai-image edit --prompt "把图一的帽子戴在图二的人物上，用图三的画风" `
  --input-image a.png --input-image b.png --input-image c.png --output-path out
```

- `--model`（默认 `gpt-image-2`）、`--size` / `--quality` / `--background` / `--number` 全部按字符串透传，
  取值合法性由上游判定。唯一的例外：`gpt-image-2` 只支持 `background=auto`，会被强制改写，
  并在 stderr 与 sidecar 的 `overrides` 里如实记录。
- 输入图片读成 base64 data URL 后走 `images[].image_url` 传入。
- 落盘命名：`提示词前20字符-序号-uuid.png`，例如 `生成个城市夜景-01-1b7a6a49.png`；
  同批共享一份参数记录 `生成个城市夜景-1b7a6a49.json`（含请求参数、覆盖项、usage、输出文件名，**不含 api key**）。

## 结构

```
src/ai_cli/
  errors.py     失败的唯一表示 + 退出码契约
  render.py     输出的唯一出口（Output / emit_error / note）
  core/         纯函数：--values 解析与打补丁、workflow 自省、文件命名、请求体装配
  comfy/        ComfyUI：client(单次调用) / service(上传+补丁+入队) / waiting(轮询) / outputs(产物落盘)
  images/       OpenAI 兼容图片接口：client(调用) / save(落盘与 sidecar)
  cli/          Typer 命令：解析参数 → 调下层 → run() 收尾
```

`cli/context.py` 的 `run()` 是唯一的错误出口，所以不存在“某个子命令忘了处理 --format 或退出码”。

## 测试

```powershell
uv run pytest -q
```

`tests/fake_servers/` 下有两个 stdlib 假服务端，可用来跑端到端验证：

```powershell
python tests\fake_servers\fake_comfy.py   # 127.0.0.1:8199
python tests\fake_servers\fake_hub.py     # 127.0.0.1:8200
```
