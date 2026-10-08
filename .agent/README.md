# .agent/ — AI agent workspace

Shared instructions and memory for any AI IDE or CLI used on this project. Start with [`../AGENTS.md`](../AGENTS.md).

| Folder | Contents | When to read |
|---|---|---|
| `rules/` | Coding and project rules. Each file has YAML frontmatter (`trigger`, `description`, `globs`) so Google Antigravity loads them automatically; other tools read them via AGENTS.md links. | Before editing code in the matching area |
| `workflows/` | Step-by-step playbooks for recurring tasks (start/finish a subphase, add a model, add an endpoint, run a Kaggle job…). Antigravity exposes them as `/workflow-name`. | When doing that task |
| `context/` | Project knowledge: brief, architecture, data contracts, API contract, domain glossary, India grid rules, decision log | When you need background |
| `memory/` | Living state: `handoff.md` (where we are, what's next), `known-issues.md` | **Start and end of every session** |
| `prompts/` | Reusable prompts (code review, test writing, results explanation) | On demand |
| `templates/` | ADR, model card, PR description, subphase notes | When creating those documents |

## Tool compatibility

| Tool | What it reads |
|---|---|
| Codex, Cursor, Antigravity, Copilot coding agent, many others | `AGENTS.md` (root) |
| Claude Code | `CLAUDE.md` → imports `AGENTS.md` |
| Gemini CLI | `GEMINI.md` → points to `AGENTS.md` |
| GitHub Copilot (IDE chat) | `.github/copilot-instructions.md` → points to `AGENTS.md` |
| Google Antigravity | `AGENTS.md` + `.agent/rules/*.md` (legacy path, still supported; newer path is `.agents/rules/`) and workflows |

If a tool supports only one instruction file, point it at `AGENTS.md`; it links here.

## Maintenance rules

- Keep each rule file under ~24 KB (Antigravity truncates larger files) and focused on one area.
- Only files directly inside `rules/` are scanned by Antigravity — no subfolders there.
- Update `memory/handoff.md` at the end of every session (see `workflows/session-handoff.md`).
- Record any change of plan in `context/decisions.md` (ADR style) and the ROADMAP changelog.
