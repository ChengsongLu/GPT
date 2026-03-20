# GPT - Git Progress Tracker :）

当前仓库已经完成 `Stage 0`、`Stage 1` 和 `Stage 2` 的基础能力：

- FastAPI 应用入口
- 原生 HTML + JS 工作台页面
- 异步 SQLite 数据库
- GitLab / 飞书配置读写 API
- GitLab 分支与 commit 同步
- 提交历史查询 API
- `GET /health` 健康检查

## 本地启动

推荐使用 `uv`：

```bash
uv run uvicorn app.main:app --reload
```

也可以直接使用项目根目录的启动入口：

```bash
uv run python run_backend.py
```

说明：

- 当前项目只有一个 FastAPI 服务
- 这个服务同时托管后端 API 和前端页面
- 启动后直接使用控制台输出的地址访问页面

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

- `basic`：最小可用同步链路
- `no_commits`：验证空数据表现
- `many_commits`：验证分页、筛选和多分支展示

还支持注入异常和延迟：

```bash
uv run python run_mock_gitlab.py --scenario basic --delay-ms 800
uv run python run_mock_gitlab.py --scenario basic --fail-endpoint commits --fail-status 500
```

联调方式：

1. 启动 `run_mock_gitlab.py`
2. 启动主应用
3. 在 GitLab 配置页中填写：
   - `GitLab Base URL`：`http://127.0.0.1:9001`
   - `Personal Access Token`：填任意非空字符串，例如 `mock-token`
   - `Project ID 或 group/project`：使用对应场景中的 `path_with_namespace`
4. 点击“测试连接”、“同步分支”、“同步 commits”

常用 mock 场景对应值：

- `basic`
  - `GitLab Base URL`：`http://127.0.0.1:9001`
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
  - 可以填数字 ID，例如 `12345`
  - 也可以填路径，例如 `group/project`
- `同步间隔（分钟)`
  - 后续定时同步使用
- `时区`
  - 当前默认 `Asia/Shanghai`

当前 fixtures 位于：

- `mock/fixtures/basic/`
- `mock/fixtures/no_commits/`
- `mock/fixtures/many_commits/`

启动后访问：

- 首页：`http://127.0.0.1:8000/`
- 健康检查：`http://127.0.0.1:8000/health`

首次启动会自动创建数据库文件：

- `data/app.db`
