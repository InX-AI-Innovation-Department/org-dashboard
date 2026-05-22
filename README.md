# Org Dashboard

自动更新的 GitHub Org 开发情况看板，托管于 GitHub Pages。

**展示内容：** Repo 列表 · Open PRs · Open Issues · Top Contributors

## 部署步骤

### 1. 创建 PAT（Personal Access Token）

前往 GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens，创建一个 token：
- **Resource owner**: `InX-AI-Innovation-Department`
- **Repository access**: All repositories
- **Permissions**: `Contents (read)`、`Issues (read)`、`Pull requests (read)`、`Members (read)`

### 2. 把 Token 存到 Repo Secret

进入本 repo → Settings → Secrets and variables → Actions → New repository secret：
- Name: `DASHBOARD_TOKEN`
- Value: 上一步生成的 token

### 3. 开启 GitHub Pages

进入本 repo → Settings → Pages：
- Source: `Deploy from a branch`
- Branch: `gh-pages` / `/ (root)`

### 4. 触发第一次构建

Actions → Build & Deploy Dashboard → Run workflow

构建完成后访问：`https://inx-ai-innovation-department.github.io/org-dashboard/`

## 自动更新

每小时整点自动触发，也可在 Actions 页面手动触发。
