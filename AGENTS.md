# AGENTS.md

Guidance for AI agents working in this repository.

## Layout

- Each top-level folder containing a `SKILL.md` is one skill.
- `catalog.yml` holds the README categories and per-skill bilingual summaries.
- `scripts/sync_readme.py` generates the skills catalog inside `README.md` and `README.zh-CN.md`.

## Rules

- Never hand-edit content between `<!-- BEGIN:xxx -->` and `<!-- END:xxx -->` in the READMEs. Change `catalog.yml` or `SKILL.md`, then run `uv run scripts/sync_readme.py`.
- Text outside those markers is hand-written; keep both language versions in sync when changing it.

## Registering new skills in catalog.yml

1. Run `uv run scripts/sync_readme.py`; it prints a stub for every skill not fully registered.
2. Read each listed skill's `SKILL.md`, then add an entry under `skills:` keyed by the folder name:
   - `category`: pick an existing category id. Only add a new category when at least two skills share a theme that no existing category covers.
   - `summary.zh` / `summary.en`: one sentence each, ≤ 60 characters (zh) / ≤ 100 characters (en), stating what the skill produces — not when it triggers.
   - `api_key: true` only if the skill needs a key and has no `.env.example`.
3. Run the script again and confirm it reports no pending skills.
