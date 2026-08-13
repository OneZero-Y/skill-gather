# Skill Store

**AI Agent Skill 发现引擎 · 兼容性注册表**

Skill 散落在 GitHub 各处、skillhub、mcpmarket 等平台，Skill Store 把它们统一索引。内容留在原地，这里只存元数据——告诉你哪里有、是什么、支持哪个平台、质量怎样。

[![Auto Sync](https://img.shields.io/badge/auto--sync-daily-brightgreen)](/.github/workflows/sync.yml)
[![Python](https://img.shields.io/badge/python-3.12+-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

---

## 和同类项目的区别

| | 同类（镜像型） | Skill Store |
|---|---|---|
| 定位 | 搬运 skill 内容到本地 | 只存索引，指向原始来源 |
| 数据 | 整份 skill 文件 | 元数据 + 信号 + 兼容性标注 |
| 扩展 | 加新源要改爬虫代码 | 加新源只需在 `config.yml` 追加一行 |
| 规范 | 自定义格式 | 遵循 [agentskills.io](https://agentskills.io/specification) 官方规范 |
| 输出 | 静态页面 | 可查询 Registry JSON + CLI |

---

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/OneZero-Y/skill-gather.git
cd skill-gather

# 2. 安装依赖（使用 uv）
uv sync

# 3. 配置 GitHub Token（可选，推荐）
#    不配置时 GitHub API 限速 60 次/小时，配置后 5000 次/小时
cp .env.example .env
# 编辑 .env，填入 GITHUB_TOKEN=ghp_xxxxxxxxxxxx

# 4. 首次同步
uv run skill-gather sync

# 5. 查看结果
uv run skill-gather stats
```

---

## CLI 命令

### `sync` — 采集并更新注册表

```bash
# 同步所有启用的数据源
skill-gather sync

# 只同步指定数据源（会合并进现有 registry，不覆盖其他源）
skill-gather sync --source anthropics-skills
skill-gather sync --source anthropics-skills --source voltagent-awesome

# 试运行（不写文件，只看日志）
skill-gather sync --dry-run

# 详细日志
skill-gather -v sync
```

### `stats` — 查看注册表统计

```bash
skill-gather stats
```

输出示例：

```
╭──────────────────────────────────────╮
│  Skill Store Registry                │
│  286 skills across 4 sources         │
│  Last synced: 2026-08-12T10:00:00Z   │
╰──────────────────────────────────────╯

By Category
  development   87  ████████████████████████
  creative      42  ████████████
  document      31  █████████
  devops        28  ████████
  ...

By Source
  voltagent-awesome    162
  anthropics-skills     17
  community-repos       11
  openai-skills          2
```

### `list` — 浏览技能列表

```bash
# 列出所有（默认最多 50 条）
skill-gather list

# 筛选
skill-gather list --category development
skill-gather list --platform kiro
skill-gather list --source anthropics-skills
skill-gather list --min-score 60
skill-gather list --limit 100
```

### `search` — 关键词搜索

```bash
skill-gather search "mcp server"
skill-gather search react --category development --min-score 50
skill-gather search terraform --platform claude_code
```

### `show` — 查看 skill 详情

```bash
# 按 skill_id 或名称（支持部分匹配）
skill-gather show anthropics/skills/mcp-builder
skill-gather show mcp-builder

# 输出 JSON
skill-gather show mcp-builder --json
```

### `install` — 安装 skill 到本地

需要本机已安装 `git`。默认安装到 `~/.cursor/skills/`。

```bash
# 安装到 Cursor 全局目录（默认）
skill-gather install mcp-builder

# 安装到 Claude Code 全局目录
skill-gather install mcp-builder --preset claude

# Kiro / OpenClaw / Hermes
skill-gather install mcp-builder --preset kiro
skill-gather install mcp-builder --preset openclaw
skill-gather install mcp-builder --preset hermes

# 安装到当前项目的 .cursor/skills/
skill-gather install mcp-builder --preset project-cursor

# 自定义目录 / 覆盖已有安装
skill-gather install mcp-builder --target ~/my-skills
skill-gather install mcp-builder --force
```

### `export` — 导出数据

```bash
# 导出为 CSV（默认）
skill-gather export skills.csv

# 导出为 JSON
skill-gather export skills.json --format json

# 导出为 YAML（供 Astro 前端消费）
skill-gather export data/skills.yml --format yaml

# 带筛选
skill-gather export dev-skills.csv --category development --min-score 50
```

### `daemon` — 定时自动同步

```bash
# 每 24 小时同步一次（默认）
skill-gather daemon

# 自定义间隔（小时）
skill-gather daemon --interval 12

# 只同步特定数据源
skill-gather daemon --interval 6 --source anthropics-skills
```

---

## 数据源

| ID | 类型 | 来源 | 说明 |
|----|------|------|------|
| `anthropics-skills` | GitHub Repo | [anthropics/skills](https://github.com/anthropics/skills) | Anthropic 官方，Apache-2.0 |
| `openai-skills` | GitHub Repo | [openai/skills](https://github.com/openai/skills) | OpenAI 官方 |
| `vercel-agent-skills` | GitHub Repo | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills) | Vercel 官方，支持 76+ agent |
| `langchain-skills` | GitHub Repo | [langchain-ai/langchain-skills](https://github.com/langchain-ai/langchain-skills) | LangChain 官方，21 个 skill |
| `voltagent-awesome` | Awesome List | [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) | 社区最大聚合列表，~160 条 |
| `community-repos` | GitHub Repo List | 精选社区仓库 | 已实现；与 awesome-list 重叠时会去重 |
| `skills-sh-signals` | Web 解析（信号层） | [skills.sh](https://skills.sh) | 已实现；只丰富安装量信号，不新增条目 |
| `skillhub-cn` | Web API | [skillhub.cn](https://skillhub.cn) | 已实现；分页采集 Top 500（按 score 排序） |
| `mcpmarket-cn` | Web API | [mcpmarket.cn/skills](https://mcpmarket.cn/skills) | 已实现；分页采集前 500 条（与 GitHub 源去重） |

新增数据源只需在 [`skill_gather/adapters/config.yml`](skill_gather/adapters/config.yml) 追加一个条目，无需修改代码。

---

## 项目结构

```
skill-gather/
├── skill_gather/
│   ├── adapters/
│   │   ├── base.py           # 采集器基类 + 注册表机制
│   │   ├── github_repo.py    # GitHub 仓库采集器
│   │   ├── awesome_list.py   # Awesome-list 解析器
│   │   ├── skills_sh.py      # skills.sh 安装量信号采集器
│   │   └── config.yml        # 数据源声明（改这里加新源）
│   ├── pipeline/
│   │   ├── normalize.py      # 数据规范化 + 分类推断
│   │   ├── deduplicate.py    # 跨源去重
│   │   ├── score.py          # 质量评分（0-100）
│   │   └── run.py            # 管道编排
│   ├── models.py             # Pydantic v2 数据模型
│   ├── registry_writer.py    # 输出 registry/ + 变更检测
│   └── main.py               # CLI 入口
├── registry/
│   ├── skills.json           # 完整索引（自动生成）
│   ├── meta.json             # 统计 + 变更日志（自动生成）
│   └── by-category/          # 按分类拆分的 JSON（自动生成）
├── scripts/
│   ├── update_readme.py      # 同步后自动刷新 README 统计区块
│   └── export_web_data.py    # registry → web/data/skills.yml
├── web/                      # Astro 前端
│   ├── data/skills.yml       # 前端数据（自动生成）
│   └── src/components/react/ # SkillCard / SearchCommand / SkillApp
├── docs/
│   └── DESIGN.md             # 架构设计文档
├── .github/workflows/
│   └── sync.yml              # GitHub Actions 定时同步
├── .env.example
└── pyproject.toml
```

---

## 数据模型

每条注册表记录遵循 [agentskills.io 规范](https://agentskills.io/specification)，并扩展了发现层和信号层：

```json
{
  "skill_id": "anthropics/skills/mcp-builder",
  "spec": {
    "name": "mcp-builder",
    "description": "Build MCP servers with best practices",
    "license": "Apache-2.0",
    "compatibility": "Claude Code, Claude.ai"
  },
  "discovery": {
    "source_id": "anthropics-skills",
    "source_type": "github_repo",
    "source_url": "https://github.com/anthropics/skills",
    "install_url": "https://github.com/anthropics/skills/tree/main/skills/mcp-builder",
    "last_synced": "2026-08-12T10:00:00Z"
  },
  "signals": {
    "repo_stars": 1200,
    "last_commit_date": "2026-08-10",
    "has_scripts": true,
    "has_references": true,
    "file_count": 5
  },
  "platform": {
    "claude_code": true,
    "claude_ai": true,
    "kiro": false,
    "codex": false,
    "universal": false
  },
  "category": "development",
  "tags": ["mcp", "builder", "server"],
  "score": 84
}
```

### 质量评分（0-100）

| 维度 | 权重 |
|------|------|
| 有描述 | 20 |
| 有许可证 | 10 |
| 有可执行脚本（scripts/） | 15 |
| 有参考文档（reference/） | 10 |
| GitHub Stars（对数归一化） | 20 |
| 更新时效（近期提交加分） | 15 |
| 字段完整度 | 10 |

---

## 自动同步（GitHub Actions）

推送到 GitHub 后，[`.github/workflows/sync.yml`](.github/workflows/sync.yml) 会：

- 每天 UTC 04:00 自动运行采集管道
- 将更新的 `registry/` 文件提交回仓库
- 支持手动触发（`workflow_dispatch`），可指定单个数据源

**需要在仓库 Settings → Secrets 添加：**

```
SKILL_STORE_GITHUB_TOKEN = ghp_xxxxxxxxxxxx
```

使用独立的 PAT 而非默认 `GITHUB_TOKEN`，以避免 Actions 触发 API 限速。

---

## 添加新数据源

**方式一：添加单个 GitHub 仓库**（该仓库根目录有 `SKILL.md`）

在 `config.yml` 的 `community-repos` 下追加一行：

```yaml
- id: community-repos
  adapter: github_repo_list
  repos:
    - antonbabenko/terraform-skill
    - your-new/skill-repo        # ← 追加这里
```

**方式二：添加多 skill 结构的仓库**（如 `anthropics/skills`）

```yaml
- id: my-org-skills
  adapter: github_repo
  repo: my-org/skills
  branch: main
  skill_root: skills
  skill_marker: SKILL.md
```

**方式三：解析 awesome-list**

```yaml
- id: my-awesome-list
  adapter: awesome_list
  repo: my-org/awesome-agent-skills
  branch: main
  readme_path: README.md
```

---

## 贡献

欢迎通过以下方式参与：

- **提交新数据源**：在 `skill_gather/adapters/config.yml` 中追加配置，提 PR
- **改进分类规则**：编辑 `pipeline/normalize.py` 中的 `_CATEGORY_KEYWORDS`
- **优化评分算法**：编辑 `pipeline/score.py` 中的权重配置
- **接入新平台**：参照 `adapters/base.py` 的 `BaseAdapter` 接口实现新 adapter

---

## License

MIT

<!-- REGISTRY-STATS-START -->
<!-- Auto-generated by scripts/update_readme.py — do not edit manually -->

## Registry Stats

| | |
|---|---|
| **Total Skills** | 3954 |
| **Data Sources** | 15 |
| **Last Synced** | 2026-08-13 10:41 UTC |

**By Category** (top 5): development `1458` · devops `481` · creative `440` · other `425` · document `404`

**Platform Compatibility**: Claude Code `3910` · Kiro `3893` · Codex `3195` · Claude.ai `18` · Universal `3931`

**Active Sources**:
  - `anthropics-skills`
  - `aws-agent-toolkit`
  - `bytedance-deerflow`
  - `community-repos`
  - `github-awesome-copilot`
  - `heilcheng-awesome`
  - `langchain-skills`
  - `mcpmarket-cn`
  - `microsoft-vscode-skills`
  - `openai-skills`
  - `scientific-agent-skills`
  - `skillhub-cn`
  - `supabase-skills`
  - `vercel-agent-skills`
  - `voltagent-awesome`

> Last sync changes: +613 added / -1 removed / ~18 modified

<!-- REGISTRY-STATS-END -->
