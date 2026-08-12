# Skill Store Web

Skill Store 的 Astro 静态站点前端。

## 本地开发

```bash
# 1. 从 registry 导出数据
cd ..
uv run python scripts/export_web_data.py

# 2. 安装依赖并启动
cd web
npm install
npm run dev
```

访问 http://localhost:4321

## 构建

```bash
npm run build
npm run preview
```

## 部署到 Cloudflare Pages

| 配置项 | 值 |
|--------|-----|
| Root directory | `web` |
| Build command | `npm run build` |
| Build output | `dist` |
| NODE_VERSION | 22 |

可选环境变量：`SITE_URL=https://skill-store.pages.dev`

## 数据流

```
skill-store sync → registry/skills.json
                → scripts/export_web_data.py
                → web/data/skills.yml
                → Astro build
```

建议在 CI sync 后自动运行 `export_web_data.py` 并提交 `web/data/skills.yml`。

## Skill 详情页

每个 skill 有独立静态页：`/skills/{id}`（id 含 `/` 时自动分段，如 `/skills/anthropics/skills/docx`）。

## GitHub Actions 部署

`.github/workflows/deploy-web.yml` 在 `main` 分支 `web/` 或 registry 变更时构建并部署到 Cloudflare Pages。

需在仓库 Secrets 配置：

| Secret | 说明 |
|--------|------|
| `CLOUDFLARE_API_TOKEN` | Cloudflare API Token（Pages Edit 权限） |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare Account ID |

可选 Variables：`SITE_URL`（canonical URL，默认 `https://skill-store.pages.dev`）。
