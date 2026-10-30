# Agent Rules — SmartKOL

## Mandatory Working Rules (5 rules — apply to every task, no exceptions)
1. **Same failure twice → change method** — never attempt a third try with the same approach hoping for luck. Change the method/plan explicitly.
2. **Every number in a report must come from a real run in that same round** — never quote numbers from memory/assumptions/a previous session. If not actually run: run it now, or clearly label it "not yet verified".
3. **Same tool failing 10 times in one task → stop and report** — what was tried, where it's stuck, what's blocked. Never grind silently.
4. **Stay in scope** — any task outside the IN list of PROJECT.md must be approved by the project owner first. Never guess and act.
5. **Never commit on your own — always ask** — propose (files + commit message) and wait for the owner's "ok commit" (one reply = one commit). Split bigger work into small tasks: do ONE task → report (files changed + real run output) → wait for ok before the next — never deliver one huge unreviewed batch (no black box).

## Git workflow 
- **1 commit = 1 purpose**, explainable in a single sentence — if you need the word "and", it's still too big: split it.
- Before proposing any commit: **run build/tests until they pass** — every commit must be in a working state
- Propose (files + message) → wait for "ok commit" per rule 5 → `git add <named files>` — **never `git add .`** (it mixes several concerns into one blob).
- Message format: `<type>: <what>` + a body explaining why — type is feat/fix/test/docs/refactor/chore. Task IDs (T#) are optional and only used when SSOT.md is committed (see below).
- **Commits carry the owner's name only** — no `Co-Authored-By` or other AI trailers. AI usage is disclosed in the README (or wherever the project requires), not in commit metadata.
- Never: floating "WIP"/"fix"/"update" messages, one commit mixing several concerns, committing a broken build, finishing a task without updating SSOT.md.
- **Secrets (keys, tokens, .env) never enter a commit** — put them in `credential/` and git-ignore it before the first commit; .md files outside credential/ must never contain secret values — reference the path instead.
- **SSOT.md in git — decide once per project (in Project Rules):** tracked (default) or local-only (git-ignored) when the commit log itself is the deliverable and status edits would add noise to every diff.

## Decision policy — when to ask / when to decide
- **Always ask first (batched into one round — never trickling questions):** choosing/changing the tech stack, adding any new library/dependency however small, changing data structures/schema, deploy target, out-of-scope work — present options with a recommendation + reason, then wait. Never start silently.
- **Decide yourself, but report:** micro-details inside an already-chosen frame (colors/chart type, naming, file layout) — test: reversible in minutes **and** adds no new dependency.
- **If Techstack in PROJECT.md still shows `<...>`** = the owner hasn't decided → ask, never guess on their behalf.
- Tasks in the Progress table already carry an AC → don't re-ask about goals; ask only about "how" when it's undecided.
- **Never create new .md files beyond the 4 scaffold files** — if the work genuinely needs another document, propose it first (filename + what it holds) and wait for approval; such documents live in `docs/` only. No floating scratch notes in the root or the working tree.

## Before starting any task
1. Read `SSOT.md` — current status + roadmap (never guess status from memory)
2. Check scope in `PROJECT.md` (enforced by rule 4)

## Finishing a task (final step before reporting done)
- Update `SSOT.md`: new status + roadmap + one history line + date — no update = task not done

## Router — when to read what
- Understanding the system / tech rationale → `PROJECT.md` (Techstack/Architecture section)
- Past context / why things are this way → tail of "History" in SSOT.md / `docs/history.md` (if it exists)
- Install / run → `README.md`

## Project Rules (project-specific — the generic rules above stay unchanged)
- **SSOT.md is local-only (git-ignored)**, as is `spike/` — status edits never go into a commit, so commit messages carry no T# IDs.
- **Commit history is read as a story** — keep commits small and in build order; docs and commit messages read as a normal product, never as an assignment submission.
- **No hardcoded account** — every external service (Apify, LLM provider, OpenRouter) is configured by the user in Settings or `credential/.env`; keys are never logged or returned in full.
- **UI is English, data stays Thai** — never translate creator names, captions or hashtags.
- **Every number shown in the UI or docs is measured or labelled** — LLM guesses (e.g. audience fit) are labelled "estimated"; costs come from a real run or the provider's price list.
- **Privacy** — keep only public, business-relevant fields; mask phone numbers/emails found in creator bios.
- **Tooling** — frontend uses npm (`package-lock.json`); backend uses its own `.venv`. Before proposing a commit run: backend `python -m unittest discover -s tests -t .`, frontend `npx tsc --noEmit` and `npx eslint .`.
