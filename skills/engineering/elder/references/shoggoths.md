# Shoggoth CLIs

This page covers what the script passes to each CLI, how it gates each one, and
what it can check afterwards. Load it to set up a shoggoth, to debug a failed
run, or to add a CLI.

## Config

`~/.config/shoggoth/config.json` (`SHOGGOTH_CONFIG` overrides the path) maps
each elder to its shoggoth. Write it with `shog config set`, through the setup
questions or `/elder config`, rather than by hand.

```json
{ "claude": { "cli": "agy", "model": "gemini-4-argon", "effort": "medium" },
  "codex": { "cli": "codex", "model": "gpt-6.1-sol", "effort": "high" } }
```

| Key | Meaning |
|---|---|
| `cli` | `agy`, `codex`, `cursor`, `claude`, or `grok` (required) |
| `model` | the CLI's model id; if omitted, the CLI's default |
| `effort` | reasoning effort (agy, codex, claude, grok) |
| `permissions` | `ask` (default): the gate decides each call. `full`: no gate |
| `style` | `lean` (default) or `detailed` ([brief.md](brief.md)) |
| `bin` | the binary, if it isn't the usual name on PATH |
| `args` | extra arguments, appended as is |

A value can also be a string: `"cli:model"`, or `"cli"` for the CLI's default
model. A `default` key covers elders that have no entry of their own. The elder
and the shoggoth may be the same CLI on different models.

## The elder's permissions

In `ask` mode the gate reads the elder host's own settings once per run and
applies them before its own rules: the floor first (`.git/` and hook-file
writes, agy's refused tools), then deny, ask, and allow rules, then the mode.

| Elder | Files read | Rules | Runs without asking | Refuses instead of asking |
|---|---|---|---|---|
| `agy` | `~/.gemini/antigravity-cli/settings.json`, `~/.gemini/config/config.json` (`globalPermissionGrants`), the project in `~/.gemini/config/projects/` whose folder is the repo (its mode wins) | `command(prefix)`, `command(regex:…)` with one pattern per word, `read_file(path)`, `write_file(path)`, `read_url(domain)`, `mcp(server/tool)` | `toolPermission: always-proceed` | — |
| `claude` | `~/.claude/settings.json` (or `$CLAUDE_CONFIG_DIR`), `<repo>/.claude/settings.json` and `settings.local.json`, managed settings | `Bash(…)`, `Read(…)`, `Edit(…)`, `WebFetch(domain:…)`, `WebSearch`, `mcp__…` | `defaultMode: bypassPermissions`, unless managed settings disable it | `dontAsk` |
| `codex` | `~/.codex/config.toml` (or `$CODEX_HOME`, active profile), `<repo>/.codex/config.toml`, `rules/*.rules` in both | `prefix_rule(pattern, decision)`: allow, prompt, forbidden | `approval_policy = "never"` with `sandbox_mode = "danger-full-access"` | `never` with a sandbox |
| `cursor` | `~/.cursor/cli-config.json`, `<repo>/.cursor/cli.json` | `Shell(cmd)`, `Read(glob)`, `Write(glob)`, `Mcp(server:tool)`, `WebFetch(domain)` | `approvalMode: unrestricted` | — |
| `grok` | `~/.grok/config.toml` (or `$GROK_HOME`), managed config, `<repo>/.grok/config.toml` (rules only), `<repo>/.claude/settings*.json`, `requirements.toml` | Claude-style strings, and `{ action, tool, pattern }` | `[ui] permission_mode = "always-approve"` or `yolo`, unless `requirements.toml` locks it | `dontAsk` |

Matching follows Grok's documented rules, which Claude Code shares:

- A command is split at `;`, `&`, `|`, and newlines. Leading `VAR=x` and
  `timeout`, `nice`, `ionice`, `chrt`, `stdbuf`, `env` are peeled.
- Deny and ask rules hit any segment, including inside `bash -c '…'` and
  `$(…)`.
- An allow rule must cover every segment, can't vet a command substitution,
  and can't redirect output outside the repo.
- Read and Edit deny rules also cover the file arguments of commands
  (`cat .env`).
- A settings file that doesn't parse, or a rule it can't read, is listed as
  skipped in `shog doctor --elder <host>`. Other elders get the built-in rules
  only.

## Gate per CLI (`ask` mode)

| CLI | How it runs | Where the gate sits | Allowed without asking |
|---|---|---|---|
| `agy` | `--dangerously-skip-permissions` (agy's own checks off) | PreToolUse hook in `<repo>/.agents/hooks.json`, for the run only | repo reads and edits, plain read-only commands, exactly-approved commands |
| `claude` | `--permission-mode acceptEdits` | PreToolUse hook passed in `--settings` | same as agy |
| `codex` | `--sandbox workspace-write` (repo-only writes, no network) | PermissionRequest hook passed in `-c`; it fires only when a call wants out of the sandbox | every command inside the sandbox, which the script can't verify; the summary says the gate saw only escalations |
| `cursor` | `--force` | shell, MCP, and read hooks, plus a `preToolUse` write hook (Write, Edit, Delete), in `<repo>/.cursor/hooks.json`, `failClosed` | same as agy |
| `grok` | no gate: `full` only | — | everything |

Guarantees:

- **A broken gate blocks.** On agy, a gate that crashed, timed out, or printed
  garbage blocked the call. Cursor gets `failClosed`.
- **A finished tool call with no gate record** means the CLI never loaded the
  gate. The script stops the run and flags `GATE_BYPASSED`.
- **Requests wait up to 55 minutes** (`SHOGGOTH_GATE_WAIT`, in seconds), and the
  waiting doesn't count against `--timeout`.
- **An existing `.agents/hooks.json` or `.cursor/hooks.json`** is restored byte
  for byte after the run. Concurrent runs share one copy. A gate a crashed run
  left in the file is stripped before the next backup.

## Flags per CLI

| CLI | Run as | `full` | Resume | Report | Visible in its log |
|---|---|---|---|---|---|
| `agy` | `agy -p … --output-format stream-json --mode accept-edits` | same, without the gate | `--conversation <id>` | `--json-schema` | commands with exit codes, edits, refusals, tokens |
| `codex` | `codex exec --json -C <repo> …` | `--dangerously-bypass-approvals-and-sandbox` | `exec … resume <id>` | `--output-schema`, `-o` | commands with exit codes, file changes, tokens |
| `cursor` | `cursor-agent -p --output-format stream-json --workspace <repo> --trust` | same, without the gate | `--resume <id>` | a ```json block | shell calls (field names guessed), edits |
| `claude` | `claude -p … --output-format stream-json --verbose` | `--dangerously-skip-permissions` | `--resume <id>`; new runs get `--session-id` | `--json-schema` | Bash calls, edits, refusals, tokens |
| `grok` | `grok --prompt-file … --cwd <repo> --always-approve` | the only mode | `-r <id>`; new runs get `-s <uuid>` | `--json-schema` | report only |

## What has been verified (2026-10-20)

- **agy 1.4.3**: run for real, gate included:
  - denied calls stayed blocked, and the shoggoth carried on after them
  - approved calls ran
  - a request waited 45 seconds before it ran
  - a broken gate failed closed
- **claude, codex, cursor**: built from their CLI and hooks docs, but never run.
- **The elder's permissions**: read from this machine's real agy, Claude Code,
  Codex, Cursor, and Grok settings; agy's rules checked end to end with a fake
  shoggoth.
- **grok 1.0.62**: flags read from `--help`; never run as a shoggoth.

Gemini CLI isn't supported: it refuses personal accounts, so use agy.

## Per-CLI notes

- **agy**:
  - Its tool names vary by model (`view_file` vs `read_file`, `edit_file`), so
    the gate classifies calls by name, and unknown names go to the user.
  - A hook can refuse a command but not grant one, which is why agy's own
    checks are off.
  - `~/.gemini/GEMINI.md` and its memories reach the shoggoth too, which may
    change the language it answers in.
- **codex**:
  - The script passes `--skip-git-repo-check`.
  - `--dangerously-bypass-hook-trust` applies to that run only.
  - The final message is saved to `last-message.txt`.
- **cursor**: the script looks only for `cursor-agent`, since `agent` is also
  Grok Build's binary. Set `bin` to Cursor's `agent` if that's what you have.
  `--trust` prevents a headless hang.
- **claude**: `stream-json` needs `--verbose`. `permission_denials` lists
  refusals.
- **grok**: the session id is chosen up front so follow-ups can resume it.

## Windows

Written for Windows but not yet run there.

- **Python**: `py -3` or `python` in place of `python3`.
- **npm-installed CLIs**: a `.cmd` shim can't pass a multi-line brief, so
  the script runs the shim's node script directly. If that fails, set `bin`
  to the CLI's `.exe`.
- **Gate command**: the 8.3 short path with forward slashes, so cmd,
  PowerShell, and Git Bash all run it. A path that keeps a space after
  shortening is quoted, and PowerShell can't run a quoted command.
- **Gate rules**:
  - A trailing dot or space and a `:stream` suffix are stripped before the
    `.git` check.
  - `%`, `^`, `!`, and `,` count as shell syntax.
  - An argument with `:` other than `C:\` waits for the user (PowerShell's
    `env:` and `HKLM:` drives).
  - `git` waits when the repo holds a `git.bat` or `git.exe`: cmd runs those
    before PATH.
- **Undo**: `shog undo RUN`, so no `rm` or `&&` is needed.
- **Brief**: pass a file; a PowerShell pipe can drop non-ASCII text.
- **A CLI that is a `.ps1` script**: not found on PATH. Set `bin`.

## Failures before work starts

The summary's `stderr` line says why:

- **Not signed in**: log in to the CLI once, interactively.
- **Unknown model**: run `shog models <cli>`, then `/elder config`.
- **Unknown flag**: check the CLI's `--help`, then fix its adapter in
  `scripts/shoggoth.py` and the tables above.
- **"the gate never saw a tool call"**: hooks are disabled in the CLI's
  settings. Use another shoggoth, or `full` if the user agrees.

## Adding a CLI

In `scripts/shoggoth.py`:

1. An argv builder covering prompt, model, effort, session, both permission
   modes, and the report schema, if the CLI enforces one.
2. A parser that fills the shared shape: session, ok, error, text, report,
   usage, and commands with exit codes, or `None` when the log doesn't show
   them.
3. A gate dialect: a `_normalize_*` function for the hook payload, an `_emit`
   case for the answer, and the wiring, through `HOOK_FILES` or argv flags.
4. An `ADAPTERS` entry with a `checked` note, and a `CATALOG` entry: how to list
   models, the recommended model and effort, and the effort levels. The setup
   questions are built from it.
5. Rows in the tables above.
