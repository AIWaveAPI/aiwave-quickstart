# AGENTS.md — AIWave Quickstart（云端代理操作手册）

本文件约束所有自动化代理（Codex 云端、CI、脚本）在本仓库的行为。违反任一红线 = 立即停止并报告，不要自行修复。

## 你在操作什么

AIWave（https://aiwave.live/）的官方快速上手仓库：可复制的 curl/SDK 示例、成本估算脚本、模型 ID 查询表。读者是准备掏钱的开发者——**他们复制粘贴这里的命令去调一个付费 API**。

## 权威数据源（唯一事实）

- **实时价格**：`https://aiwave.live/api/pricing`（97 模型，倍率字段：`model_ratio` / `completion_ratio` / `model_price` / `quota_type`）
- **在售判定**：以服务器 abilities 表路由为准；价格端点在场 ≠ 在售（例：`glm-5-turbo` 两端点都在但无路由 = 停售）
- `/api/v1/pricing` 是停在 2026-10-24 的**快照**，禁止用于"现价"表述，只可用于标注日期的历史叙事
- 换算：按量模型输入 USD/1M = `model_ratio` × $2；输出 = `model_ratio` × `completion_ratio` × $2；`model_price` 有值 = 按次计费
- **任何页面/文档/README 里写下的价格数字，必须能逐字回溯到上述端点的具体字段**。回溯不了就不许写数字，改为一行 `Current rates: /pricing` 链接

## 模型 ID 铁律

- 仓库中每个反引号里的模型 ID 必须真实存在于实时端点。CI 的 `verify_model_ids.py` 每日全量校验，编造 ID = CI 红
- 明确的否定句（"There is no `x` ID on our card"）与搜索词列表例外，但须真实可查
- 搜索词 → 精确 ID 的查询表（README 第 0 节）是本仓库最大的自然流量入口，改动需人工复核

## 营销红线（主理人已否决的话术，禁止出现）

- ❌ 未上线功能的预告（如 "free tier included"——免费层未上线）
- ❌ 一键切换话术（"Change one string" / "swap base_url and go" / "Keep your OpenAI SDK"）
- ❌ 无证据竞品断言（"most aggregators don't..."）
- ❌ 未实测声明的性能/延迟/可用性数字

## 写操作规则

- 分支 → commit → PR（草稿）。不直接 push main
- 每个 PR 描述必含：改了什么、为什么、影响面、验证方式
- 不自行 merge 任何 PR（含自己开的）
- 提交前本地跑：`python3 scripts/verify_claims.py --repo-root .` 与 `python3 scripts/verify_model_ids.py --repo-root .`（需要网络拉实时端点）
- 凭据/API key 永不入库；发现疑似凭据立即停止并报告

## 事实冲突裁决

现场锚点（端点实测、页面实际内容）与任何文档/记忆/任务书数字冲突时，**以现场为准**，并双源复核（公网 curl + 服务器侧）后再下结论。单一来源的 grep 0 结果 = 假阴性候选，不许直接当事实。
