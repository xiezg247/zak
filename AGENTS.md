# Agent 协作说明

## Git Commit

- **语言**：commit message 的 subject 与 body 必须使用**简体中文**。
- **格式**：`<type>(<scope>): <简述>`，说明「为什么」而非罗列文件名。
- **示例**：`refactor(ui): 前端目录迁入 ui/workbench 与 ui/admin`

### Cursor ✨ 生成 commit message

Source Control 的 ✨ 按钮**只读**根目录 [`.cursorrules`](.cursorrules)（不读本文件或 `.cursor/rules/`）。改 commit 语言请编辑 `.cursorrules` 中的 `Commit Message Rules`。

Agent 对话提交时见 [.cursor/rules/commit-messages.mdc](.cursor/rules/commit-messages.mdc)。

## Superpowers（spec / plan，本地）

- **可用**：实现前用 Superpowers skills（`brainstorming` → `writing-plans` → 执行）写设计与任务计划。
- **路径**：`docs/superpowers/specs/`、`docs/superpowers/plans/`（见该目录 [README](docs/superpowers/README.md)）。
- **不提交 Git**：已在 [`.gitignore`](.gitignore) 排除；与已提交的 `docs/*.md` 产品文档分工见 superpowers README。
- **已提交文档**：`docs/trading-system.md`、`docs/feature-index.md` 等为产品与能力说明；与代码不一致时以代码为准。
