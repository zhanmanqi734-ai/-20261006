# 真探 TruthSeeker

涉华国际新闻观察与事实核查编辑工作台。公开 RSS / X 官方 API → LangGraph → 去重与主题分组 → AI 辅助主张提取 → 相似报道线索 → 编辑优先榜 → 人工核查 → 历史报告。

## 当前能力与边界

- 响应式中文看板、搜索、情感筛选、优先级排序、详情抽屉、Markdown 日报导出。
- 五节点真实 LangGraph 流水线，手动 POST + SSE 进度；Vercel Cron 每天北京时间 08:00。
- 8 个 RSS 接口配置，源失败记录到报告。近 48 小时；未提供时间的条目保留并标记。标题和 RSS 摘要筛选 China / Chinese。
- 标题/链接去重、去跟踪参数且保留文章标识查询参数；关键词主题分组与标题词项 Jaccard 相似度事件聚类。当前非向量语义聚类。
- AI 可配置兼容 Chat Completions 的接口；最多每轮分析 30 条、5 并发。失败保留原文且情感待研判，不伪造中文摘要。
- 优先分 = 35 + 同事件其他来源数×6（最多30）+ 可核查主张15 + 争议信号10，上限95。它不是虚假概率，也未引入未采集的传播量。
- 相似报道只作为核查线索；自动程序不认定事实真假。编辑可以附证据、关系、说明及结论，系统保留报告内的修订历史。
- 选题持久化为“待调查”，复核后为“已复核”。当前没有多人角色系统、发布审批和完整媒体生产 CMS。
- 本机 SQLite；Vercel 正式运行必须 PostgreSQL。报告、选题、任务互斥租约存储在数据库中。
- 无凭据即可公开浏览；任务执行、选题、编辑复核必须管理员令牌。共享令牌模式适合首版，机构多人使用前应替换为身份认证和权限管理。
- 无真实报告时显示明确标记的演示数据，不把示例当成真实报道。

尚未完成线上验证：当前云网络代理拒绝新闻 RSS 请求；未提供模型、X、数据库和 Vercel 凭据。Reuters/AP/AFP/The Times 暂未接入，不虚构公开 RSS 或绕过授权。BBC/CNN 等接口配置也必须在允许联网后逐源验证；RSS 可用性、更新频率和版权条款会变化。

## 本地运行

```bash
cd /workspace/-20261006
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# 按 .env.example 配置环境变量；uvicorn 不会自动读取 .env。
export ADMIN_TOKEN='自行生成的强随机令牌'
export CRON_SECRET='另一个强随机令牌'
.venv/bin/uvicorn api.index:app --host 0.0.0.0 --port 8000
```

网页“运行设置”填写与服务端一致的 ADMIN_TOKEN 后可手动监测。浏览器仅在内存保留令牌。服务端默认 SQLite 路径 `/tmp/truthseeker.db`；如需本机长期存储，设置 SQLITE_PATH 到持久目录。POST `/api/run` 为流式响应；GET `/api/cron` 必须 `Authorization: Bearer <CRON_SECRET>`。

## Vercel 部署

1. 将 GitHub 仓库导入 Vercel。Python 函数为 `api/index.py`，根目录 `vercel.json` 定义路由、300 秒最大执行时长和 Cron。部署计划必须支持设置的时长；实际 Cron 时间受平台调度影响。
2. 创建 PostgreSQL（例如 Neon / Supabase），为生产和需要的预览环境配置 `DATABASE_URL`，建议使用服务商提供的 SSL 连接字符串。Python 使用 psycopg。首次请求创建表，数据库用户需要 CREATE/SELECT/INSERT/UPDATE/DELETE 权限。
3. 安全配置 `ADMIN_TOKEN`、`CRON_SECRET`。Vercel 会把 CRON_SECRET 作为 Cron 的 Bearer 认证。不要将密钥放在浏览器构建变量或提交到仓库。
4. 配置 `LLM_API_KEY`、可选 `LLM_BASE_URL` 和 `LLM_MODEL`。自托管或国内兼容服务也可使用；需支持 JSON response_format。真实模型调用尚需用自己的凭据验证。X 需要具有 recent search 权限的 `X_BEARER_TOKEN`，API 可能收费。
5. 部署后检查首页及 `/api/status`，执行一轮手动任务，检查 SSE 五步、真实条目、失败源清单、报告历史、选题和人工核查。确认数据库跨部署保存数据。不要用演示页面通过验收。
6. 在 Vercel 项目 Domains 中添加已购买域名，再到阿里云 DNS 按 Vercel 实际显示的记录添加 CNAME / A，等域名验证和 HTTPS 签发。不能预先虚构 DNS 地址；域名尚未提供。

Vercel 不是持续运行的后台机器。超过平台时长的监测规模应迁移到独立队列工作进程；本版上限为每源60条、模型30条并发5。数据库任务租约10分钟可阻止不同函数实例重叠采集；进程异常退出后租约自动到期。

## 云环境网络

公开 RSS 需要：`feeds.bbci.co.uk`, `rss.cnn.com`, `rss.nytimes.com`, `feeds.washingtonpost.com`, `www.theguardian.com`, `www.aljazeera.com`, `www.scmp.com`, `feeds.bloomberg.com`。X：`api.x.com`。默认模型：`api.openai.com`；其他模型需放行自己的服务域名。重定向目的域名需根据实际错误单独补充。网络草稿保存不代表当前运行时已放行。

## 验证

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/pip check
```

测试使用固定采集 fixture，验证过滤、去重、五步 LangGraph、SSE、SQLite 历史、选题、带证据的复核、Cron 认证、失败不伪造成功和演示隔离；不是对外 RSS、模型或生产 PostgreSQL 的通过证明。浏览器测试已检查桌面与390px移动布局、筛选、详情、历史、数据源，无 JS 异常。另一轮端到端测试使用明确的本地 fixture，验证浏览器管理员认证 → SSE → LangGraph → SQLite → 报告历史 → 选题 → 证据复核 → 结论修订；不代表真实新闻、模型或生产服务已验证。

## 下一阶段

增加独立证据检索（官方原始文件、公开数据库、事实核查机构与多方独立来源）、语义主张聚类、原图反搜与视频溯源、热度时序、多人复核及双语/短视频产品输出。核查时应同时保留支持和反对证据，区分可核实事实、观点、预测与未确定信息。
