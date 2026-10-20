# Briefs

A brief is everything the shoggoth knows about a task: it hasn't seen this
conversation. The script adds the contract
([../assets/contract.md](../assets/contract.md)) and the report format, so the
brief holds only the task.

## Template

```markdown
# <n>. <what changes>

Goal: <the outcome in 1–2 sentences; the why, if it changes the how>

Read first:
- `path:line-line`: <why it matters>

Decisions made (don't reopen):
- <choice>: <reason>

Scope: may change `<glob>`; must not change `<glob>`. <No new dependencies. / No public API change.>

Done when:
- <observable result>

Verify:
- `<exact command>` → <what passing looks like>

Stop and ask if: <situations specific to this task>
```

Rules:

- **Size**: one brief is one unit you can check on its own. Split a brief
  that leaves the shoggoth more than one decision; do a rename yourself.
- **Read first** holds paths, not contents.
- **Decisions made** carries your judgment. Whatever you leave open, the
  shoggoth settles.
- **Scope** globs are the ones you pass to `--scope`.
- **Verify** commands must be exact and fast, covering a package or a test
  file rather than the whole suite.
- **Language**: English, or the language of the repo's code.

## Style

- `detailed` for small or fast models (Flash, build-fast, Haiku, mini or
  lite): add `Steps:`, a numbered list where each step names its files and its
  change, so it doesn't have to work out where they are.
- `lean` otherwise: the template as is. The shoggoth finds call sites itself.
- A `style` key in the config overrides both.

## Feedback brief

Same session (`--session ID`):

```markdown
# <n>b. Fix: <problem>

- `path:line`: <wrong> → <expected>

Answers: <one per question in the last report>
Keep: <what was right>
Done when / Verify: <unchanged, or updated>
```

## Scout brief

Read-only (`--scout`). Findings come back in `notes`. Use one only for a
list you can check: re-run the search in Done when for gaps, and spot-check a
few entries.

```markdown
# <n>. Map <thing>

Find: <question, e.g. every caller of `formatPrice` and the currency it passes>
Report each finding as `path:line`: <one line>.
Done when: every match of <a search the elder can repeat> is accounted for.
```

## Example (lean)

```markdown
# 1. Export the filtered order list as CSV

Goal: `GET /api/orders/export` returns the orders matching the list's filters
as CSV for Excel. Endpoint only; the button is brief 2.

Read first:
- `src/api/orders/list.ts:18-64`: filter parsing to reuse; same query params.
- `src/api/orders/list.test.ts`: test style and fixtures.

Decisions made (don't reopen):
- Columns: id, created_at (ISO 8601, UTC), customer_name, total (2 decimals), status.
- The file starts with a UTF-8 byte-order mark (bytes EF BB BF): Excel needs it for non-ASCII names.
- Over 50,000 rows → 413 `{"error":"too_many_rows"}`; no pagination in v1.

Scope: may change `src/api/orders/**`; must not change `list.ts` behaviour. No new dependencies.

Done when:
- `text/csv; charset=utf-8` with `Content-Disposition: attachment; filename="orders-YYYYMMDD.csv"`
- fields with a comma, a quote, or a newline are quoted per RFC 4180
- the 50,000-row cap holds

Verify:
- `pnpm vitest run src/api/orders` → all pass, with new cases for quoting and the cap
- `pnpm tsc --noEmit` → no errors

Stop and ask if: the filter parsing can't be reused without changing `list.ts`.
```
