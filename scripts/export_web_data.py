#!/usr/bin/env python3
"""Export registry/skills.json → web/data/skills.yml for Astro frontend."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

# PyYAML will write strings like '096' without quotes, which js-yaml then
# parses back as the integer 96.  Register a representer that forces quoting
# whenever yaml.safe_load would not give back the same string.
class _SafeDumperWithQuotedStrings(yaml.SafeDumper):
    pass

def _str_representer(dumper: yaml.Dumper, data: str) -> yaml.ScalarNode:
    # If round-tripping through YAML would lose the string, force single-quote style.
    try:
        reloaded = yaml.safe_load(data)
    except Exception:
        reloaded = None
    if not isinstance(reloaded, str) or reloaded != data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="'")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)

_SafeDumperWithQuotedStrings.add_representer(str, _str_representer)


ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = ROOT / "registry" / "sources"
META = ROOT / "registry" / "meta.json"
OUTPUT = ROOT / "web" / "data" / "skills.yml"

CATEGORY_LABELS = {
    "development": "开发",
    "creative": "创意",
    "document": "文档",
    "devops": "DevOps",
    "security": "安全",
    "data": "数据",
    "content": "内容",
    "ecommerce": "电商",
    "education": "教育",
    "productivity": "效率",
    "other": "其他",
}

# ---------------------------------------------------------------------------
# 中文关键词映射表
# 格式：英文 token（小写）→ 中文同义词列表
# 搜索中文时会命中含这些 token 的 skill
# ---------------------------------------------------------------------------
_ZH_KEYWORD_MAP: dict[str, list[str]] = {
    # 开发基础
    "git":              ["版本控制", "git", "代码管理"],
    "github":           ["github", "代码托管"],
    "code":             ["代码", "编程", "开发"],
    "coding":           ["编程", "代码"],
    "debug":            ["调试", "排错", "debug"],
    "refactor":         ["重构", "代码优化", "refactor"],
    "review":           ["审查", "代码审查", "review"],
    "test":             ["测试", "单元测试", "test"],
    "testing":          ["测试", "自动化测试"],
    "lint":             ["代码检查", "lint", "格式化"],
    "format":           ["格式化", "代码格式"],
    "build":            ["构建", "编译", "build"],
    "compile":          ["编译", "构建"],
    "deploy":           ["部署", "发布", "deploy"],
    "release":          ["发布", "release", "上线"],
    "ci":               ["持续集成", "CI", "自动化"],
    "cd":               ["持续部署", "CD"],
    "pipeline":         ["流水线", "pipeline", "CI/CD"],
    "commit":           ["提交", "commit", "git提交"],
    "pull":             ["拉取", "pull request", "PR"],
    "merge":            ["合并", "merge", "代码合并"],
    "branch":           ["分支", "branch", "git分支"],
    "diff":             ["差异", "diff", "变更"],
    "changelog":        ["变更日志", "更新日志", "changelog"],

    # 语言 & 框架
    "python":           ["Python", "python", "蟒蛇"],
    "javascript":       ["JavaScript", "JS", "前端"],
    "typescript":       ["TypeScript", "TS", "类型"],
    "react":            ["React", "前端框架", "组件"],
    "vue":              ["Vue", "前端框架", "组件"],
    "angular":          ["Angular", "前端框架"],
    "node":             ["Node.js", "后端", "服务端"],
    "java":             ["Java", "后端", "企业级"],
    "kotlin":           ["Kotlin", "Android", "安卓"],
    "swift":            ["Swift", "iOS", "苹果"],
    "go":               ["Go", "Golang", "后端"],
    "rust":             ["Rust", "系统编程", "性能"],
    "php":              ["PHP", "后端", "web"],
    "ruby":             ["Ruby", "Rails", "后端"],
    "csharp":           ["C#", "dotnet", ".NET"],
    "dotnet":           ["dotnet", ".NET", "C#"],
    "cpp":              ["C++", "系统编程"],
    "sql":              ["SQL", "数据库", "查询"],
    "html":             ["HTML", "前端", "网页"],
    "css":              ["CSS", "样式", "前端"],
    "shell":            ["脚本", "Shell", "命令行"],
    "bash":             ["Bash", "脚本", "命令行"],
    "powershell":       ["PowerShell", "脚本", "Windows"],

    # 数据库
    "database":         ["数据库", "DB", "存储"],
    "mysql":            ["MySQL", "数据库", "关系型"],
    "postgres":         ["PostgreSQL", "数据库", "关系型"],
    "mongodb":          ["MongoDB", "NoSQL", "文档数据库"],
    "redis":            ["Redis", "缓存", "键值存储"],
    "sqlite":           ["SQLite", "轻量数据库", "本地数据库"],
    "elasticsearch":    ["Elasticsearch", "搜索引擎", "全文搜索"],
    "supabase":         ["Supabase", "数据库", "后端"],
    "prisma":           ["Prisma", "ORM", "数据库"],

    # 云 & DevOps
    "docker":           ["Docker", "容器", "虚拟化"],
    "kubernetes":       ["Kubernetes", "k8s", "容器编排"],
    "k8s":              ["k8s", "Kubernetes", "容器编排"],
    "terraform":        ["Terraform", "基础设施", "IaC"],
    "aws":              ["AWS", "亚马逊云", "云服务"],
    "azure":            ["Azure", "微软云", "云服务"],
    "gcp":              ["GCP", "谷歌云", "云服务"],
    "cloudflare":       ["Cloudflare", "CDN", "边缘计算"],
    "vercel":           ["Vercel", "部署", "前端托管"],
    "nginx":            ["Nginx", "反向代理", "web服务器"],
    "monitoring":       ["监控", "监测", "告警"],
    "logging":          ["日志", "logging", "日志收集"],

    # AI & 机器学习
    "ai":               ["人工智能", "AI", "机器学习"],
    "ml":               ["机器学习", "ML", "模型"],
    "llm":              ["大模型", "LLM", "语言模型"],
    "gpt":              ["GPT", "大模型", "生成式AI"],
    "claude":           ["Claude", "AI助手", "Anthropic"],
    "prompt":           ["提示词", "prompt", "提示工程"],
    "rag":              ["RAG", "检索增强", "知识库"],
    "vector":           ["向量", "向量数据库", "embedding"],
    "embedding":        ["向量", "embedding", "语义搜索"],
    "agent":            ["智能体", "Agent", "AI代理"],
    "workflow":         ["工作流", "流程", "自动化"],
    "automation":       ["自动化", "自动", "workflow"],
    "langchain":        ["LangChain", "AI框架", "链式调用"],
    "openai":           ["OpenAI", "GPT", "AI"],

    # 文档 & 内容
    "document":         ["文档", "doc", "文件"],
    "docs":             ["文档", "文档生成"],
    "readme":           ["README", "说明文档"],
    "markdown":         ["Markdown", "文档格式", "md"],
    "pdf":              ["PDF", "文档", "文件处理"],
    "word":             ["Word", "文档", "docx"],
    "excel":            ["Excel", "表格", "xlsx"],
    "spreadsheet":      ["表格", "电子表格", "Excel"],
    "writing":          ["写作", "文案", "内容创作"],
    "translation":      ["翻译", "多语言", "国际化"],
    "summarize":        ["摘要", "总结", "概括"],
    "summary":          ["摘要", "总结"],

    # 安全
    "security":         ["安全", "网络安全", "信息安全"],
    "auth":             ["认证", "鉴权", "登录"],
    "authentication":   ["认证", "身份验证", "登录"],
    "authorization":    ["授权", "权限", "鉴权"],
    "encryption":       ["加密", "密码学", "安全"],
    "vulnerability":    ["漏洞", "安全漏洞", "CVE"],
    "pentest":          ["渗透测试", "安全测试"],
    "firewall":         ["防火墙", "安全"],

    # 效率 & 协作
    "productivity":     ["效率", "生产力", "工作效率"],
    "task":             ["任务", "待办", "任务管理"],
    "todo":             ["待办", "TODO", "任务清单"],
    "calendar":         ["日历", "日程", "时间管理"],
    "email":            ["邮件", "email", "邮箱"],
    "slack":            ["Slack", "即时通讯", "协作"],
    "notion":           ["Notion", "笔记", "知识管理"],
    "jira":             ["Jira", "项目管理", "敏捷"],
    "project":          ["项目", "项目管理"],
    "meeting":          ["会议", "会议记录"],
    "resume":           ["简历", "resume", "求职"],

    # 前端 & 设计
    "ui":               ["UI", "界面", "用户界面"],
    "ux":               ["UX", "用户体验", "交互设计"],
    "design":           ["设计", "UI设计", "视觉"],
    "figma":            ["Figma", "设计工具", "UI设计"],
    "animation":        ["动画", "动效"],
    "component":        ["组件", "UI组件"],
    "responsive":       ["响应式", "移动端适配"],
    "accessibility":    ["无障碍", "可访问性", "a11y"],

    # 数据 & 分析
    "data":             ["数据", "数据分析", "数据处理"],
    "analytics":        ["分析", "数据分析", "统计"],
    "visualization":    ["可视化", "数据可视化", "图表"],
    "chart":            ["图表", "可视化", "chart"],
    "csv":              ["CSV", "数据文件", "表格"],
    "json":             ["JSON", "数据格式"],
    "api":              ["API", "接口", "REST"],
    "rest":             ["REST", "API", "接口"],
    "graphql":          ["GraphQL", "API", "查询语言"],
    "scraping":         ["爬虫", "抓取", "数据采集"],
    "crawler":          ["爬虫", "数据采集"],

    # 移动端
    "android":          ["Android", "安卓", "移动端"],
    "ios":              ["iOS", "苹果", "移动端"],
    "mobile":           ["移动端", "手机", "App"],
    "app":              ["应用", "App", "应用程序"],

    # 电商 & 业务
    "ecommerce":        ["电商", "电子商务", "购物"],
    "payment":          ["支付", "付款", "结算"],
    "invoice":          ["发票", "账单", "billing"],
    "order":            ["订单", "order"],
    "product":          ["产品", "商品"],
    "marketing":        ["营销", "市场", "推广"],
    "seo":              ["SEO", "搜索优化", "排名"],
    "social":           ["社交", "社媒", "社交媒体"],

    # 教育 & 学习
    "education":        ["教育", "学习", "教学"],
    "learn":            ["学习", "教程"],
    "tutorial":         ["教程", "入门", "学习"],
    "course":           ["课程", "培训"],

    # 通用高频词
    "search":           ["搜索", "查找", "检索"],
    "generate":         ["生成", "创建", "AI生成"],
    "analyze":          ["分析", "解析"],
    "optimize":         ["优化", "性能优化"],
    "migrate":          ["迁移", "migration"],
    "integration":      ["集成", "整合"],
    "plugin":           ["插件", "扩展"],
    "extension":        ["扩展", "插件"],
    "template":         ["模板", "template"],
    "scaffold":         ["脚手架", "初始化", "scaffold"],
    "boilerplate":      ["模板", "脚手架", "样板"],
    "image":            ["图片", "图像", "Image"],
    "video":            ["视频", "Video"],
    "audio":            ["音频", "语音", "Audio"],
    "file":             ["文件", "文件管理"],
    "upload":           ["上传", "文件上传"],
    "download":         ["下载", "文件下载"],
    "notification":     ["通知", "消息提醒"],
    "report":           ["报告", "报表"],
    "dashboard":        ["仪表盘", "看板", "dashboard"],
    "admin":            ["后台", "管理", "运维"],
    "config":           ["配置", "设置"],
    "setting":          ["设置", "配置"],
    "permission":       ["权限", "访问控制"],
    "role":             ["角色", "权限角色"],
    "user":             ["用户", "用户管理"],
    "profile":          ["个人资料", "用户信息"],
    "feedback":         ["反馈", "用户反馈"],
    "error":            ["错误", "异常", "报错"],
    "performance":      ["性能", "性能优化", "速度"],
    "cache":            ["缓存", "cache"],
    "queue":            ["队列", "消息队列"],
    "webhook":          ["webhook", "回调", "事件通知"],
    "websocket":        ["WebSocket", "实时通信", "ws"],
    "oauth":            ["OAuth", "第三方登录", "授权"],
    "jwt":              ["JWT", "令牌", "token认证"],
    "microservice":     ["微服务", "服务拆分"],
    "serverless":       ["Serverless", "无服务器", "函数计算"],
    "game":             ["游戏", "游戏开发"],
    "unity":            ["Unity", "游戏引擎"],
    "science":          ["科学", "科研", "学术"],
    "research":         ["研究", "科研"],
    "medical":          ["医疗", "医学", "健康"],
    "finance":          ["金融", "财务", "理财"],
    "legal":            ["法律", "合规", "法务"],
    "hr":               ["HR", "人力资源", "招聘"],
    "chinese":          ["中文", "中国", "汉语"],
    "english":          ["英文", "英语", "翻译"],
}


def _zh_keywords(skill: dict) -> str:
    """根据 skill 的 name / tags / category 生成中文搜索关键词字符串。

    逻辑：把 name、tags、category 拆成 token，查映射表，收集对应中文词，
    去重后以空格拼接，供前端直接做字符串 includes 搜索。
    """
    # 提取所有英文 token
    spec = skill.get("spec", {})
    name: str = spec.get("name") or skill.get("skill_id", "")
    tags: list = skill.get("tags", [])
    category: str = skill.get("category", "")
    platforms: dict = skill.get("platform", {})

    # 把连字符/下划线/斜杠拆成单词
    import re
    raw_tokens = re.split(r"[-_/\s.]+", name.lower()) + \
                 [re.split(r"[-_/\s.]+", str(t).lower())[0] for t in tags] + \
                 re.split(r"[-_/\s.]+", category.lower())

    zh_words: list[str] = []
    seen: set[str] = set()

    for token in raw_tokens:
        token = token.strip()
        if not token:
            continue
        mappings = _ZH_KEYWORD_MAP.get(token, [])
        for word in mappings:
            if word not in seen:
                seen.add(word)
                zh_words.append(word)

    # 加上 category 对应中文标签（如 "开发" "安全" 等）
    cat_zh = CATEGORY_LABELS.get(category, "")
    if cat_zh and cat_zh not in seen:
        zh_words.append(cat_zh)

    # 加上平台中文名
    platform_zh = {
        "claude_code": "Claude Code",
        "claude_ai": "Claude",
        "kiro": "Kiro",
        "codex": "Codex",
        "universal": "通用",
    }
    for k, v in platforms.items():
        if v and k in platform_zh and platform_zh[k] not in seen:
            zh_words.append(platform_zh[k])

    return " ".join(zh_words)


def _row(skill: dict) -> dict:
    spec = skill.get("spec", {})
    discovery = skill.get("discovery", {})
    signals = skill.get("signals", {})
    platform = skill.get("platform", {})
    desc = str((spec.get("description") or ""))
    return {
        "id": str(skill.get("skill_id", "")),
        "name": str(spec.get("name", "")),
        # 列表视图 line-clamp-2 ~80字符，detail 页面由 SSG 各自内联完整数据
        # 160 字符足够列表展示，可节省 ~20% skills.yml 体积
        "description": desc[:160],
        "description_full": desc[:1024],  # detail 页面用
        "category": str(skill.get("category", "other")),
        "score": int(skill.get("score", 0)),
        "tags": [str(t) for t in skill.get("tags", [])][:8],
        "source": str(discovery.get("source_id", "")),
        "install_url": str(discovery.get("install_url", "")),
        "stars": int(signals.get("repo_stars", 0)),
        "installs": int(signals.get("install_count", 0)),
        "platforms": [str(k) for k, v in platform.items() if v],
        "license": str(spec.get("license") or ""),
        "zh_keywords": _zh_keywords(skill),  # 中文搜索关键词
    }


def _pick_featured(rows: list[dict], n: int = 12) -> list[dict]:
    """Pick featured skills with source diversity (not just top-N by score)."""
    seen_sources: set[str] = set()
    featured: list[dict] = []
    # First pass: one skill per source (highest score)
    for row in rows:
        src = row["source"]
        if src not in seen_sources:
            seen_sources.add(src)
            featured.append(row)
        if len(featured) >= n:
            break
    # Second pass: fill remaining slots from top-scored regardless of source
    if len(featured) < n:
        existing_ids = {r["id"] for r in featured}
        for row in rows:
            if row["id"] not in existing_ids:
                featured.append(row)
                if len(featured) >= n:
                    break
    return featured


def main() -> None:
    if not SOURCES_DIR.exists() or not any(SOURCES_DIR.glob("*.json")):
        raise SystemExit(
            f"Sources directory not found or empty: {SOURCES_DIR}\n"
            "Run skill-gather sync first."
        )

    # Merge all per-source shard files
    skills_raw: list[dict] = []
    for shard_path in sorted(SOURCES_DIR.glob("*.json")):
        try:
            with open(shard_path, encoding="utf-8") as f:
                data = json.load(f)
            skills_raw.extend(data.get("skills", []))
        except Exception as e:
            print(f"Warning: could not read {shard_path.name}: {e}", flush=True)

    meta: dict = {}
    if META.exists():
        with open(META, encoding="utf-8") as f:
            meta = json.load(f)

    rows = [_row(s) for s in skills_raw]
    rows.sort(key=lambda r: r["score"], reverse=True)

    categories = meta.get("categories", {})
    category_list = [
        {
            "id": cat_id,
            "name": CATEGORY_LABELS.get(cat_id, cat_id),
            "count": count,
        }
        for cat_id, count in sorted(categories.items(), key=lambda x: -x[1])
    ]

    source_counts = meta.get("source_counts", {})
    source_list = [
        {"id": src_id, "count": count}
        for src_id, count in sorted(source_counts.items(), key=lambda x: -x[1])
    ]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(rows),
        "site": {
            "title": "Skill Gather",
            "description": "AI Agent Skill 发现引擎 · 兼容性注册表",
        },
        "meta": {
            "last_synced": meta.get("last_synced"),
            "sources_count": meta.get("sources_count", 0),
            "changelog": meta.get("changelog"),
        },
        "categories": category_list,
        "sources": source_list,
        "featured": _pick_featured(rows, n=12),
        "skills": rows,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        yaml.dump(payload, f, Dumper=_SafeDumperWithQuotedStrings, allow_unicode=True, sort_keys=False)

    print(f"✓ Exported {len(rows)} skills → {OUTPUT}")


if __name__ == "__main__":
    main()
