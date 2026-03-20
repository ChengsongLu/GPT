# Git Progress Tracker 执行计划

## 1. 目标

基于 [project.md](/Users/lcs/Projects/GPT/docs/project.md) 的需求与架构，按多个 stage 分步实现项目，确保每一步都可以独立验证，逐步跑通完整闭环。

执行原则：

- 先跑通，再补细节
- 每个 stage 都必须可验证
- 所有后端接口、数据库访问、外部 HTTP 调用都使用异步实现
- 优先保证主链路稳定：配置 -> 同步 commit -> 查看 commit -> 生成日报 -> 发送飞书
- 优先使用本地 mock 场景做分步验证，再接入真实外部系统

## 1.1 Mock 验证基线

为了降低联调成本，项目内维护一套正式的 Mock GitLab 和 Mock Feishu 能力，作为后续 stage 的默认验证基础设施。

当前约定：

- 使用根目录入口 `run_mock_gitlab.py`
- 使用根目录入口 `run_mock_feishu.py`
- Mock 数据放在 `mock/fixtures/`
- 支持的基础场景：
  - `basic`
  - `no_commits`
  - `many_commits`
  - `feishu_basic`
- 支持通过启动参数注入慢响应和接口错误，验证容错逻辑
- `basic` 和 `many_commits` 场景都应包含多天 commits，便于验证“历史展示”和“昨日日报统计范围”

建议使用方式：

1. 先启动 `run_mock_gitlab.py` / `run_mock_feishu.py`
2. 再启动主应用
3. 将 GitLab / Feishu Base URL 指向本地 mock 服务
4. 使用固定场景重复验证同步、筛选、分页、成员同步、日报等能力

## 2. 总体阶段划分

```mermaid
flowchart LR
    S0[Stage 0 项目骨架] 
    S0 --> S1[Stage 1 配置与数据库]
    S1 --> S2[Stage 2 GitLab 分支与 Commit 同步]
    S2 --> S3[Stage 3 提交历史页面]
    S3 --> S4[Stage 4 飞书成员同步]
    S4 --> S5[Stage 5 日报生成]
    S5 --> S6[Stage 6 飞书发送]
    S6 --> S7[Stage 7 定时任务闭环]
    S7 --> S8[Stage 8 联调验收与收尾]
```

## 3. Stage 详细拆分

## 3.1 Stage 0：项目骨架

目标：

- 初始化 FastAPI 项目结构
- 建立前后端最小可运行骨架
- 确保项目可以本地启动

实现内容：

- 建立目录结构：
  - `app/`
  - `app/api/`
  - `app/core/`
  - `app/db/`
  - `app/models/`
  - `app/services/`
  - `app/schemas/`
  - `app/templates/`
  - `app/static/`
  - `data/`
- 创建 FastAPI 应用入口
- 配置静态文件和基础 HTML 页面
- 接入基础日志
- 增加依赖清单和启动说明

完成标志：

- 本地启动服务成功
- 浏览器能打开首页
- 存在健康检查接口

验证方式：

- 启动服务后访问首页成功
- `GET /health` 返回成功状态

## 3.2 Stage 1：配置与数据库

目标：

- 建立异步 SQLite 数据层
- 跑通 GitLab 和飞书配置保存与读取

实现内容：

- 配置 SQLAlchemy Async + `sqlite+aiosqlite`
- 初始化数据库连接和异步 Session
- 创建数据表：
  - `app_settings`
  - `branches`
  - `commits`
  - `contributors`
  - `daily_reports`
- 实现配置相关接口：
  - `GET /api/settings`
  - `POST /api/settings/gitlab`
  - `POST /api/settings/feishu`
- 实现配置页面表单提交

完成标志：

- 配置可写入 SQLite 文件
- 页面刷新后仍能读回配置

验证方式：

- 提交 GitLab 配置后数据库中有记录
- 提交飞书配置后接口可读取正确内容
- 项目目录下生成数据库文件

## 3.3 Stage 2：GitLab 分支与 Commit 同步

目标：

- 跑通从 GitLab 拉取所有分支及其 commit 并落库

实现内容：

- 实现异步 GitLab Client
- 实现 GitLab 连接测试接口
- 拉取仓库所有分支
- 按分支拉取 commit
- commit 去重入库
- 保存分支基础信息
- 增加可复用的 Mock GitLab 验证能力
- 实现手动同步接口：
  - `POST /api/sync/branches`
  - `POST /api/sync/commits`

完成标志：

- 能针对已配置仓库同步所有分支
- 每个分支的 commit 能写入数据库
- 重复同步不会生成重复数据

验证方式：

- 使用 `basic` mock 场景验证主链路
- 手动触发同步后 `branches` 和 `commits` 表有数据
- 同步两次后 commit 数量不异常增长
- 提交历史接口能返回按时间倒序数据

## 3.4 Stage 3：提交历史页面

目标：

- 跑通“按分支查看 commit 历史”的页面

实现内容：

- 实现接口：
  - `GET /api/branches`
  - `GET /api/commits`
- 支持查询参数：
  - `branch`
  - `author`
  - `date_from`
  - `date_to`
  - `page`
  - `page_size`
- 页面按分支渲染 Tab
- 支持按开发者、时间筛选
- 支持分页加载

完成标志：

- 可以从页面切换不同分支查看 commit
- 可以筛选开发者和时间范围
- 默认按最新时间排在最上面

验证方式：

- 使用 `many_commits` mock 场景验证分页和筛选
- 切换分支时数据正确变化
- 输入筛选条件后结果正确缩小
- 翻页后仍保持筛选条件

## 3.5 Stage 4：飞书成员同步

目标：

- 跑通从飞书多维表格同步成员映射

实现内容：

- 实现飞书鉴权
- 实现飞书连接测试接口
- 拉取多维表格记录
- 按固定字段映射为 `contributors`
- 增加可复用的 Mock Feishu 验证能力
- 实现同步接口：
  - `POST /api/sync/feishu-contributors`
- 飞书页面支持保存配置、测试连接、同步成员

完成标志：

- 可以从指定多维表格读取成员信息
- 成员映射可落库并更新

验证方式：

- 使用 Mock Feishu 场景验证成员同步链路
- `contributors` 表出现同步后的成员数据
- 能正确读取“开发者姓名 / GitLab 用户名 / 负责组件”
- 重复同步不会无限新增脏数据

## 3.6 Stage 5：日报生成

目标：

- 跑通基于昨天 commit 的日报生成

实现内容：

- 计算昨天时间范围，固定 `Asia/Shanghai`
- 查询昨天全部 commit
- 关联 `contributors`
- 将结构化事实交给 LLM 生成日报文案
- 生成两层日报：
  - 项目整体日报
  - 分支日报
- 保存到 `daily_reports`
- 实现接口：
  - `GET /api/reports`
  - `GET /api/reports/project-daily`
  - `POST /api/reports/generate-daily`

完成标志：

- 手动触发后可以生成昨天的项目整体日报
- 同时生成对应的分支日报
- 日报能保存到数据库
- 日报内容由 LLM 生成，且不脱离给定 commit 事实

验证方式：

- `daily_reports` 中同时存在 `project` 和 `branch` 类型记录
- 整体日报能体现项目整体进展
- 分支日报能体现各自分支的提交摘要

## 3.7 Stage 6：飞书发送

目标：

- 跑通日报发送到指定飞书群

实现内容：

- 实现飞书群消息发送服务
- 按选定日期发送项目整体日报
- 按选定日期连续发送各分支日报
- 实现接口：
-  - `POST /api/reports/send`
-  - `POST /api/settings/test-feishu`
- 更新发送状态和发送时间
- Mock Feishu 支持消息发送验证

消息建议结构：

1. 日期
2. 项目整体进度总结
3. 活跃开发者汇总
4. 组件进展汇总
5. 各分支摘要

完成标志：

- 可以手动发送指定日期的日报到飞书群
- 项目整体日报和分支日报都能成功发送
- 发送状态和发送时间可追踪

验证方式：

- 飞书群实际收到消息
- 对应日报状态更新为 `sent`
- `sent_at` 被写入数据库
- Mock Feishu 的 `/mock/sent-messages` 能看到发送记录

## 3.8 Stage 7：定时任务闭环

目标：

- 跑通无人值守的自动同步与自动发送

实现内容：

- 接入 `AsyncIOScheduler`
- 配置定时任务：
  - commit 同步：按配置中的同步间隔分钟数执行
  - 飞书成员同步：每天 23:50
  - 日报生成并发送：每天 00:00:00
- 增加启动时注册任务逻辑
- 保存配置后自动重载任务
- 增加任务日志

完成标志：

- 应用启动后自动注册任务
- 修改同步间隔或时区后任务能自动重载
- 到点会自动执行同步和日报发送

验证方式：

- 本地完成调度器启动 / 重载 / 停止检查
- 日志中能看到任务注册记录
- 手动调用任务实现时数据库和飞书结果正确

## 3.9 Stage 8：联调验收与收尾

目标：

- 补齐主链路稳定性，形成可演示版本

实现内容：

- 检查页面文案和基本交互
- 补充错误提示和空状态
- 统一接口返回结构
- 补充最小测试：
  - 配置读写
  - commit 同步去重
  - 日报生成
- 补充 README 启动文档

完成标志：

- 从零配置到飞书收到日报可以完整跑通
- 关键路径具备基础错误处理

验证方式：

- 按完整演示流程执行一次
- 新环境下按 README 能启动
- 关键接口最小测试通过

## 4. 推荐实现顺序

建议严格按下面顺序推进：

1. Stage 0
2. Stage 1
3. Stage 2
4. Stage 3
5. Stage 4
6. Stage 5
7. Stage 6
8. Stage 7
9. Stage 8

原因：

- 先把“数据能采进来”跑通，再做页面和日报
- 先把“日报能生成”跑通，再做自动发送
- 先把“手动闭环”跑通，再做定时自动化

## 5. 每阶段验收策略

每个 stage 完成后都做三类检查：

### 5.1 功能检查

- 对应页面或接口是否可用
- 主流程是否真实跑通
- 优先确认 mock 场景下的结果稳定复现

### 5.2 数据检查

- 数据是否正确写入 SQLite
- 是否有重复数据、脏数据、空字段

### 5.3 回归检查

- 新功能是否影响前一阶段能力
- 页面和接口是否仍然可访问

## 6. 里程碑定义

### Milestone A

完成 Stage 0 到 Stage 2。

结果：

- 项目可启动
- 配置可保存
- GitLab 所有分支 commit 可同步入库
- Mock GitLab 验证链路可复用

### Milestone B

完成 Stage 3 到 Stage 5。

结果：

- 页面可查看 commit
- 飞书成员可同步
- 项目整体日报和分支日报可生成

### Milestone C

完成 Stage 6 到 Stage 8。

结果：

- 日报可发送到飞书群
- 定时任务可自动执行
- 形成完整 MVP 闭环

## 7. 当前建议

实现时优先保证以下三点：

- 不要一开始追求复杂 UI，先保证页面可用
- 日报先做结构化事实聚合，再交给 LLM 生成文案
- 所有外部集成都先提供“测试连接”接口，避免联调时排查困难
- 对每个 stage 保留至少一个稳定可复现的 mock 验证场景
