# GPT - Git Progress Tracker :）

当前仓库已经完成 `Stage 0` 到 `Stage 6` 的基础能力：

- FastAPI 应用入口
- 原生 HTML + JS 工作台页面
- 异步 SQLite 数据库
- GitLab / 飞书配置读写 API
- GitLab 分支与 commit 同步
- 提交历史查询 API
- 飞书连接测试与成员同步
- 基于 LLM 的项目整体日报与分支日报生成
- 手动将指定日期的项目整体日报和分支日报发送到飞书群
- 前端日志页，可查看按天切分的系统日志
- `GET /health` 健康检查

## LLM 配置

日报生成现在默认依赖 LLM。配置方式：

1. 复制项目根目录下的 [.env.example](/Users/lcs/Projects/GPT/.env.example) 为 `.env`
2. 按你使用的 provider 填入配置
3. `.env` 已被 [.gitignore](/Users/lcs/Projects/GPT/.gitignore) 忽略，不会提交到 Git 仓库

支持的 provider：

- `openai`
- `anthropic`

最小示例：

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4.1-mini
```

或者：

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-key
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_MODEL=claude-3-5-sonnet-latest
```

可选公共参数：

- `LLM_TEMPERATURE`
- `LLM_MAX_TOKENS`
- `LLM_TIMEOUT_SECONDS`

## 本地启动

推荐使用 `uv`：

```bash
uv run uvicorn app.main:app --reload
```

也可以直接使用项目根目录的启动入口：

```bash
uv run python run_backend.py
```

如果你想一键启动后端和两个 mock 服务：

```bash
bash run_stack.sh
```

终止这三个服务：

```bash
bash run_stack.sh -e
```

说明：

- 当前项目只有一个 FastAPI 服务
- 这个服务同时托管后端 API 和前端页面
- 启动后直接使用控制台输出的地址访问页面
- `run_stack.sh` 会把 PID 和日志写到 `.runtime/`
- `run_stack.sh` 优先使用 `.venv/bin/python`，也可以通过 `PYTHON_BIN` 覆盖解释器
- `run_stack.sh` 会同时启动：
  - 后端：`http://127.0.0.1:18000`
  - Mock GitLab：`http://127.0.0.1:19001`
  - Mock Feishu：`http://127.0.0.1:19002`

## Mock GitLab

项目内已经正式提供可复用的 Mock GitLab 服务，用于后续各 stage 的本地联调和效果验证。

启动默认场景：

```bash
uv run python run_mock_gitlab.py
```

切换场景：

```bash
uv run python run_mock_gitlab.py --scenario many_commits
```

支持的基础场景：

- `basic`：最小可用同步链路，包含多天 commits
- `no_commits`：验证空数据表现
- `many_commits`：验证分页、筛选、多分支展示和跨天 commits

还支持注入异常和延迟：

```bash
uv run python run_mock_gitlab.py --scenario basic --delay-ms 800
uv run python run_mock_gitlab.py --scenario basic --fail-endpoint commits --fail-status 500
```

联调方式：

1. 启动 `run_mock_gitlab.py`
2. 启动主应用
3. 在 GitLab 配置页中填写：
   - `GitLab Base URL`：`http://127.0.0.1:19001`
   - `Personal Access Token`：填任意非空字符串，例如 `mock-token`
   - `Project ID 或 group/project`：使用对应场景中的 `path_with_namespace`
4. 点击“测试连接”、“同步分支”、“同步 commits”

常用 mock 场景对应值：

- `basic`
  - `GitLab Base URL`：`http://127.0.0.1:19001`
  - `Personal Access Token`：`mock-token`
  - `Project ID 或 group/project`：`group/project`
- `no_commits`
  - `Project ID 或 group/project`：`group/quiet-project`
- `many_commits`
  - `Project ID 或 group/project`：`group/busy-project`

## 真实 GitLab 配置说明

页面里的 GitLab 配置字段含义如下：

- `GitLab Base URL`
  - GitLab 站点根地址
  - 示例：`https://gitlab.example.com`
- `Personal Access Token`
  - 用于访问 GitLab API 的令牌
  - 需要对目标项目至少有读取权限
- `Project ID 或 group/project`
  - 目标项目标识
  - 可以填 GitLab 提供的数字项目 ID，例如 `12345`
  - 也可以填 GitLab 项目的 `path_with_namespace`，例如 `group/project`
  - 这里不是本系统自定义的任意别名，而是 GitLab 项目自身的标识
- `同步间隔（分钟)`
  - 后续定时同步使用
- `时区`
  - 当前默认 `Asia/Shanghai`

当前 fixtures 位于：

- `mock/fixtures/basic/`
- `mock/fixtures/no_commits/`
- `mock/fixtures/many_commits/`

其中 `basic` 和 `many_commits` 现在都包含多天 commits，便于验证：

- 提交历史分页与筛选
- 日报只统计“昨天”的数据
- 历史 commit 仍可在页面中继续查看

## Mock Feishu

项目内也提供了可复用的 Mock Feishu 服务，用于验证飞书多维表格成员同步。

启动：

```bash
uv run python run_mock_feishu.py
```

配置页面中可填写：

- `Feishu Base URL`：`http://127.0.0.1:19002`
- `App ID`：任意非空字符串，例如 `mock-app-id`
- `App Secret`：任意非空字符串，例如 `mock-app-secret`
- `多维表格 App Token`：任意非空字符串，例如 `mock-bitable-app`
- `Table ID`：任意非空字符串，例如 `mock-table`

然后点击：

1. `测试飞书连接`
2. `同步成员映射`

如果要验证“发送日报到飞书群”，先确保已经生成某一天的日报，然后在日报页点击“发送到飞书群”。
Mock Feishu 会返回模拟的消息 ID，并且提供一个查看已发送消息的接口：

```bash
curl http://127.0.0.1:19002/mock/sent-messages
```

当前 mock Feishu fixtures 位于：

- `mock/fixtures/feishu_basic/`

## 真实 Feishu 配置说明

- `App ID`
  - 飞书自建应用的 App ID
- `App Secret`
  - 飞书自建应用的 App Secret
- `Feishu Base URL`
  - 默认使用 `https://open.feishu.cn`
- `多维表格 App Token`
  - 目标多维表格所属应用的 App Token
- `Table ID`
  - 目标数据表的 Table ID
- `群 chat_id`
  - 后续发送日报时使用

当前成员字段约定：

- `开发者姓名`
- `GitLab 用户名`
- `负责组件`

启动后访问：

- 首页：`http://127.0.0.1:18000/`
- 健康检查：`http://127.0.0.1:18000/health`

首次启动会自动创建数据库文件：

- `data/app.db`
