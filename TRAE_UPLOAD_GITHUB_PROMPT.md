# Trae 专属：一键安全脱敏上传项目至 GitHub 提示词

> **使用方法**：直接复制下方全部内容，粘贴发送给 Trae AI 编程助手，Trae 将全自动为您执行检查、初始化 Git、执行脱敏校验并推送到您的 GitHub 仓库。

---

```markdown
你好 Trae，请帮我将当前工程安全脱敏后上传发布到我的个人 GitHub 仓库。请严格按照以下标准化安全流程执行：

### 阶段一：严格隐私与脱敏安全检查 (至关重要)
请首先检查当前工作区，确保以下敏感资产被 `.gitignore` 严格拦截，严禁 staged 或 commit 到版本库：
1. 【登录态与会话隔离】：`boss_browser_data/`、`browser_data/`、`data/accounts/` 绝对不能提交（保护微信与 BOSS Cookie）；
2. 【个人真实简历】：`data/` 目录下的个人真实 PDF/Word/TXT 原件（只保留 `data/sample_resume_template.md` 样例）；
3. 【本地数据库】：`data/*.db`（`rag_knowledge.db`、`rag_store.db` 等含有个人姓名电话教育经历的数据表）；
4. 【真实投递记录】：`history.csv` 及其备份日志（只保留 `history.example.csv`）；
5. 【私有配置与密钥】：`config.json`（已提供脱敏模板 `config.example.json`）。

### 阶段二：Git 仓库初始化与暂存检查
请在终端中按顺序执行以下命令：
```bash
# 1. 检查是否存在 .git，若无则初始化
git init

# 2. 确保默认主分支为 main
git branch -M main

# 3. 暂存非忽略文件
git add .

# 4. 执行状态核对，打印待提交清单
git status
```
在执行完 `git status` 后，请向我汇报是否有任何属于上述黑名单的敏感文件被误加入。如果全部为开源代码、脚本与脱敏文档，请继续。

### 阶段三：执行提交与推送到 GitHub
如果一切正常，请执行：
```bash
# 提交代码
git commit -m "feat: initial release of BossAutoGreet v6.2 (NiceGUI + RAG + Multi-Account + K50U Android Support)"
```
随后请询问我的 GitHub 仓库远程地址（例如 `https://github.com/my-username/BossAutoGreet.git`），并在获得输入后帮我运行：
```bash
git remote add origin <我的GitHub仓库地址>
git push -u origin main
```
请开始帮我执行第一步和第二步吧！
```
