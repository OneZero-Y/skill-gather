# Skill Store — 项目设计文档

## 1. 项目定位

**技能发现引擎 + 兼容性注册表**

不做"技能仓库的搬运工"，做"技能发现引擎"。Skill 内容留在原始来源（GitHub、skillhub 等），本项目做的是：

- 统一检索入口：散落各处的 AI Agent Skills 在这里一站查询
- 质量信号聚合：stars、更新频率、文件完整度等可量化指标
- 兼容性标注：明确标记每个 skill 适用于 Claude Code / Kiro / Codex / 通用
- 安装引导：指向原始安装方式，未来提供一行命令安装

### 与 anbeime/skill 的本质区别

| 维度 | anbeime/skill | 本项目 |
|------|---------------|--------|
| 定位 | 技能仓库镜像 | 技能发现引擎/注册表 |
| 数据 | 存整份 skill 内容 | 只存索引和元数据，指向原始来源 |
| 架构 | 单一爬虫 + JSON 文件 | 插件化采集器 + 结构化 Registry |
| 标准 | 自定义格式 | 遵循 agentskills.io 官方规范 |
| 输出 | 静态网站 | 可查询 Registry + 前端 + CLI |
| 扩展性 | 加新源要改爬虫代码 | 加新源只需写一个 adapter 插件配置 |

---

## 2. 数据来源

| 数据源 | 类型 | 采集方式 | 预估量级 |
|--------|------|----------|----------|
| anthropics/skills | GitHub 仓库（目录结构） | Git Trees API 遍历 SKILL.md | ~18 |
| openai/skills | GitHub 仓库 | Git Trees API | ~10 |
| vercel-labs/agent-skills | GitHub 仓库，支持 76+ agent | Git Trees API | ~12 |
| langchain-ai/langchain-skills | GitHub 仓库，21 个 skill | Git Trees API | ~21 |
| VoltAgent/awesome-agent-skills | GitHub awesome-list | README Markdown 解析 | ~160 |
| 社区独立 skill 仓库 | GitHub 各处 | 配置列表 + Contents API | ~20 |
| skills.sh | 安装量数据平台 | 网页解析（信号层，不新增条目） | 丰富信号 |
| skillhub.tencent.com | Web 平台 | 逆向 API / Playwright | 待探测 |
| mcpmarket.cn/skills | Web 平台 | 逆向 API / Playwright | 待探测 |

---

## 3. 核心架构

```
skill-store/
├── adapters/                  # 采集器插件体系
│   ├── base.py                    # 插件基类接口
│   ├── github_repo.py             # "仓库里多个 skill 目录"模式
│   ├── awesome_list.py            # "awesome-list README 列表"模式
│   ├── web_api.py                 # "平台 API 抓取"模式
│   └── config.yml                 # 所有数据源的声明式配置
├── pipeline/                  # 数据处理管道
│   ├── normalize.py               # 统一数据格式
│   ├── deduplicate.py             # 跨源去重
│   ├── enrich.py                  # 补充元数据（stars、更新时间）
│   └── score.py                   # 质量评分
├── registry/                  # 输出：结构化注册表
│   ├── skills.json                # 完整索引（供前端/CLI 消费）
│   ├── by-source/                 # 按来源拆分
│   ├── by-category/               # 按分类拆分
│   └── meta.json                  # 注册表元数据（总数、更新时间等）
├── web/                       # 前端展示（Phase 2，基于 Astro）
├── cli/                       # CLI 工具（Phase 3）
├── .github/workflows/         # 自动化
│   └── sync.yml                   # 定时采集 + 发布
├── docs/                      # 文档
│   └── DESIGN.md                  # 本文件
└── scripts/                   # 辅助脚本
```

### 3.1 采集器插件体系

核心理念：每个数据源是一个**配置条目**，而非独立的爬虫代码。

```yaml
# adapters/config.yml
sources:
  - id: anthropics-skills
    adapter: github_repo
    repo: anthropics/skills
    branch: main
    skill_root: skills
    skill_marker: SKILL.md
    license_default: Apache-2.0

  - id: voltagent-awesome
    adapter: awesome_list
    repo: VoltAgent/awesome-agent-skills
    branch: main
    readme_path: README.md

  - id: openai-skills
    adapter: github_repo
    repo: openai/skills
    branch: main
    skill_root: skills
    skill_marker: SKILL.md

  - id: community-repos
    adapter: github_repo_list
    repos:
      - antonbabenko/terraform-skill
      - op7418/NanoBanana-PPT-Skills
      - snyk/agent-scan
      # ... 可持续追加

  - id: skillhub-cn
    adapter: web_api
    base_url: https://skillhub.tencent.com
    enabled: false  # 待逆向 API 后启用

  - id: mcpmarket-cn
    adapter: web_api
    base_url: https://mcpmarket.cn
    enabled: false  # 待逆向 API 后启用
```

### 3.2 采集器基类接口

```python
class BaseAdapter:
    """采集器插件接口"""

    def discover(self) -> list[RawSkillEntry]:
        """发现所有 skill，返回原始条目列表"""
        raise NotImplementedError

    def extract_metadata(self, entry: RawSkillEntry) -> SkillIndex:
        """解析单个 skill 的元数据"""
        raise NotImplementedError

    def sync(self) -> list[SkillIndex]:
        """完整同步流程：发现 → 提取 → 返回"""
        entries = self.discover()
        return [self.extract_metadata(e) for e in entries]
```

---

## 4. 数据模型

遵循 [agentskills.io/specification](https://agentskills.io/specification) 官方规范作为基础，扩展发现层和信号层。

```yaml
# 单个 skill 的索引条目
skill_id: "anthropics/mcp-builder"           # 全局唯一 ID

# === 官方规范字段（来自 SKILL.md frontmatter） ===
spec:
  name: "mcp-builder"                        # 必填，1-64 字符
  description: "Build MCP servers..."        # 必填，1-1024 字符
  license: "Apache-2.0"                      # 可选
  compatibility: "Claude Code, Claude.ai"    # 可选
  metadata: {}                               # 可选 k-v

# === 发现层（本项目扩展） ===
discovery:
  source_id: "anthropics-skills"             # 对应 config.yml 中的 source id
  source_type: "github_repo"                 # adapter 类型
  source_url: "https://github.com/anthropics/skills"
  source_path: "skills/mcp-builder"          # 在仓库中的路径
  install_url: "https://github.com/anthropics/skills/tree/main/skills/mcp-builder"
  last_synced: "2026-08-12T10:00:00Z"
  upstream_commit: "abc1234"

# === 质量信号（自动采集） ===
signals:
  repo_stars: 1200
  last_commit_date: "2026-08-10"
  has_scripts: true
  has_references: true
  file_count: 5
  open_issues: 3

# === 兼容性标注（自动推断 + 手动覆盖） ===
platform:
  claude_code: true
  claude_ai: true
  kiro: false
  codex: false
  universal: false

# === 分类与标签 ===
category: "development"
tags: ["mcp", "server", "typescript", "tooling"]

# === 质量评分（算法计算） ===
score: 82
```

### 4.1 质量评分算法（初版）

```
score = (
    has_description * 20 +
    has_license * 10 +
    has_scripts * 15 +
    has_references * 10 +
    repo_stars_normalized * 20 +    # 0-20 按对数归一化
    recency_factor * 15 +           # 最近更新越新分越高
    file_completeness * 10          # SKILL.md 字段完整度
)
```

---

## 5. 同步 anthropics/skills 的具体方案

anthropics/skills 的结构：
```
skills/
├── algorithmic-art/SKILL.md
├── mcp-builder/
│   ├── SKILL.md          ← YAML frontmatter + 指令
│   ├── LICENSE.txt
│   ├── reference/        ← 补充文档
│   └── scripts/          ← 可执行脚本
├── docx/SKILL.md
└── ... (共 17 个 skill)
```

SKILL.md 模板格式：
```markdown
---
name: template-skill
description: Replace with description of the skill and when Claude should use it.
---

# Insert instructions below
```

**采集流程：**

1. 用 GitHub Git Trees API 一次请求拿整个仓库文件树：
   `GET /repos/anthropics/skills/git/trees/main?recursive=1`
2. 过滤出 `skills/*/SKILL.md` 路径
3. 对每个 SKILL.md 用 Contents API 获取文件内容
4. 解析 YAML frontmatter 提取 name、description、license、compatibility
5. 同时检测同级目录是否有 scripts/、reference/、LICENSE.txt 等（用于信号打分）
6. 记录当前 commit SHA 作为版本追踪

**优势：**
- 不需要 clone 仓库
- 认证后 5000 req/h，17 个 skill 只需 ~20 次请求
- 增量同步：比对 commit SHA，未变则跳过

---

## 6. 前端方案（Phase 2）

复用导航站同款技术栈和部署模式：

| 项 | 方案 |
|----|------|
| 框架 | Astro 5 + React 19 |
| 样式 | Tailwind CSS v4（@tailwindcss/vite） |
| 数据校验 | Zod |
| 数据源 | `data/skills.yml`（由采集器自动生成） |
| 构建时读取 | `js-yaml` + Zod parse |
| 部署 | Cloudflare Pages |
| 域名 | skill-store.pages.dev（或自定义） |

### 前端与导航站的对应关系

| 导航站概念 | Skill Store 概念 |
|-----------|-----------------|
| 导航页（daily / ai / explore） | 分类视图（development / creative / document） |
| 分类（效率工具 / 开发工具） | 子分类或来源筛选 |
| 链接卡片（LinkCard） | 技能卡片（SkillCard） |
| 搜索命令面板（SearchCommand） | 技能搜索 + 标签过滤 |
| 站点 favicon | 来源平台图标 + 兼容性标记 |
| 置顶链接 | 精选/高分技能 |
| 侧栏导航 | 分类侧栏 + 来源筛选 |

### 工作流

```
GitHub Actions 定时触发
    → 采集器运行（Python）
    → 生成 registry/skills.json
    → 转换为 data/skills.yml（前端消费格式）
    → git push
    → Cloudflare Pages 自动重建部署
```

---

## 7. 实施路线

### Phase 1：核心引擎

- [x] 项目初始化（Python 环境、目录结构）
- [x] 采集器基类 + github_repo adapter
- [x] 同步 anthropics/skills（作为第一个数据源验证流程）
- [x] awesome_list adapter（同步 VoltAgent）
- [x] 数据规范化 + 去重
- [x] 输出 registry/skills.json
- [x] GitHub Actions 自动化

### Phase 2：前端展示

- [x] Astro 项目初始化（同导航站模式）
- [x] skills.yml 数据加载 + Zod 校验
- [x] SkillCard 组件
- [x] 分类侧栏 + 搜索
- [x] 兼容性/来源标签过滤
- [x] Cloudflare Pages 部署
- [x] Skill 详情页 + 中英文切换

### Phase 3：扩展

- [x] 逆向 skillhub.cn API，接入 web_api adapter
- [x] 逆向 mcpmarket.cn API
- [x] CLI 安装工具（GitHub + SkillHub CLI）
- [x] 质量评分算法优化
- [x] 增量 sync（upstream fingerprint 跳过未变源）
- [ ] 社区贡献流程（提交新 skill 来源）

---

## 8. 技术选型

| 层 | 选型 | 理由 |
|----|------|------|
| 采集器 | Python 3.12+ | 网络请求和数据处理的生态最成熟 |
| 数据校验 | Pydantic v2 | Python 侧的 Zod 对等物 |
| 配置 | YAML | 和前端数据格式统一 |
| CI/CD | GitHub Actions | 零成本，定时触发 |
| 前端 | Astro + React + Tailwind v4 | 和导航站保持一致 |
| 部署 | Cloudflare Pages | 免费、快、你已经熟悉 |
| 版本管理 | Git（数据也入 Git） | 简单，可追溯变更历史 |

---

## 附录：agentskills.io 规范要点

每个 skill 是一个目录，至少包含 `SKILL.md`：

**Frontmatter 字段：**
- `name`（必填）：1-64 字符，小写 + 连字符
- `description`（必填）：1-1024 字符
- `license`（可选）：许可证名称
- `compatibility`（可选）：1-500 字符，环境要求
- `metadata`（可选）：任意 key-value
- `allowed-tools`（可选，实验性）：预授权工具列表

**推荐目录结构：**
- `scripts/` — 可执行脚本
- `references/` — 补充文档
- `assets/` — 静态资源

**渐进式加载：**
- 元数据（~100 tokens）：启动时加载所有 skill 的 name + description
- 指令（<5000 tokens）：skill 激活时加载 SKILL.md body
- 资源（按需）：scripts/references/assets 在需要时加载
