#!/usr/bin/env python3
"""shoggoth: run a worker agent CLI (the shoggoth) headless on a brief, then report what it did.

The elder, the agent the user talks to, writes a brief. This script prepends the contract and
runs the shoggoth's CLI with nobody at its keyboard. In the default "ask" mode, a gate stands in
front of every tool call: reads and edits inside the repo, read-only commands, and commands the
user already approved go through; anything else waits until the elder has asked the user. When
the run ends, the script prints a summary built from ground truth, the git diff and the
shoggoth's own tool log, checked against the report the shoggoth wrote.

  shoggoth.py doctor
  shoggoth.py models CLI                         what a CLI offers, and the recommended pick
  shoggoth.py config show|set|unset [--elder NAME --cli CLI --model M --effort E]
  shoggoth.py run    --brief FILE|- [--elder NAME] [--shoggoth CLI[:MODEL]] [--session ID]
                     [--allow CMD]... [--scope GLOB]... [--scout] [--permissions ask|full]
                     [--timeout 30m] [--cwd DIR]  starts the run, then waits like `wait`
  shoggoth.py start  ...same options...           starts the run and returns
  shoggoth.py wait   RUN [--max 9m]               waits for the summary or a request
  shoggoth.py answer RUN ID allow|deny [--always] [--note TEXT]
  shoggoth.py show   RUN                          prints a finished run's summary
  shoggoth.py stop   RUN                          stops a running shoggoth
  shoggoth.py undo   RUN [--force]                reverts a writing run's changes

Exit codes of run and wait: 0 the summary is printed; 4 a request waits for the user;
3 still running after --max; 1 error. RUN is a run directory, its number ("3"), or its name.
Every subcommand accepts --elder; `config set` merges into the elder's entry (--cli only to change it).
Zero dependencies, Python 3.9+, macOS, Linux, and Windows (Windows untested so far).
Config: ~/.config/shoggoth/config.json (SHOGGOTH_CONFIG overrides). Runs: <tmp>/shoggoth/<repo>/
(SHOGGOTH_HOME overrides).
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fnmatch
import hashlib
import json
import ntpath
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import unquote, urlparse

WIN = os.name == "nt"
if WIN:
    import msvcrt
else:
    import fcntl

SKILL = Path(__file__).resolve().parent.parent
CONTRACT = SKILL / "assets" / "contract.md"
SCHEMA = SKILL / "assets" / "report.schema.json"
CONFIG = Path(os.environ.get("SHOGGOTH_CONFIG") or Path.home() / ".config" / "shoggoth" / "config.json")
HOME = Path(os.environ.get("SHOGGOTH_HOME") or Path(tempfile.gettempdir()) / "shoggoth")
GRACE = 30  # seconds the worker waits past the timeout before it kills the shoggoth
GATE_WAIT = int(os.environ.get("SHOGGOTH_GATE_WAIT") or 3300)  # how long a request waits for the user
HOOK_TIMEOUT = GATE_WAIT + 120  # the CLI's own limit on the hook, which must outlast the wait

SCOUT_RULE = ("This brief is read-only: do not create, modify, or delete any file. "
              "Put what you find in `notes`, each with a `path:line`.")
NEXT_ROUND = ("Next brief from the elder. The contract above still applies; a read-only rule applies only to "
              "the brief that carried it.")
REPORT_NATIVE = "Finish with your report as your final message; this run enforces its JSON schema."
REPORT_TEXT = ("Finish with your report: the last thing in your final message is one ```json "
               "block with exactly these keys.\n```json\n%s\n```")
REPORT_EXAMPLE = {
    "status": "done | partial | blocked",
    "summary": "what you did, at most 5 lines",
    "files_changed": ["repo-relative/path"],
    "checks": [{"command": "a Verify command, as written", "result": "pass | fail | not_run",
                "evidence": "the last lines of its real output"}],
    "notes": ["a fact the elder should know, with path:line"],
    "deviations": [],
    "concerns": [],
    "questions": [],
}
REPORT_LISTS = ("files_changed", "checks", "notes", "deviations", "concerns", "questions")
RISKY = re.compile(
    r"\bgit\s+(push|commit|merge|rebase|tag|reset\s+--hard|clean\s+-\w*f|checkout\s+--\s|restore)\b"
    r"|\bgit\s+branch\b[^;&|\n]*\s(-[a-zA-Z]*[dDf]|--delete|--force)\b"
    r"|(?<![\w.-])rm\s+([^;&|\n]*\s)?(-[a-zA-Z]*[rRf]|--recursive|--force)"
    r"|(?<![\w.-])(chmod|chown)\b|(?<![\w.-])dd\s+[^;&|\n]*\b(if|of)="
    r"|\bsudo\b|\b(npm|pnpm|yarn|cargo|twine|gem)\s+publish\b"
    r"|\b(pip3?|pipx)\s+install\b|\b(npm|pnpm|yarn)\s+(add|install|i)\b|\baws\s+[^;&|\n]*\brm\b"
    r"|\bcurl\b[^|;]*\|\s*(ba|z)?sh\b|\bterraform\s+apply\b|\bkubectl\s+(apply|delete)\b|\bdeploy\b"
    # Windows: cmd and PowerShell spellings of the same.
    r"|(?i:\b(rd|rmdir)\s+([^;&|\n]*\s)?/s\b|\bdel\s+([^;&|\n]*\s)?/[sfq]\b|\bremove-item\b[^;&|\n]*-(recurse|force)"
    r"|\b(icacls|takeown|format)\b|\breg\s+(add|delete|import)\b|\bset-executionpolicy\b"
    r"|\b(iwr|irm|invoke-webrequest|invoke-restmethod)\b[^;\n]*\|\s*iex\b)")
# The exit header a tool puts above a command's output ("Command exited with code 0." in agy,
# "Exit code 1" in Claude Code); only the first lines count, so the command's own output can't fake it.
EXIT_RE = re.compile(r"(?i)^\s*(?:command\s+)?(?:exited\s+with\s+code|exit\s+code|exit\s+status)\s*[:=]?\s*(-?\d+)\b")
EXIT_LINES = 3
SHELL_WRAPPERS = {"bash", "sh", "zsh", "powershell", "pwsh", "cmd"}
WRAPPER_FLAGS = {"-c", "-lc", "-cl", "-command", "/c"}


def die(msg: str) -> None:
    print("shoggoth: " + msg, file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------- gate policy
# The gate decides every tool call the shoggoth makes in "ask" mode. Calls that stay inside
# the repo and can't change anything outside it go through on their own; the rest wait for
# the user. Each CLI speaks its own hook dialect: _normalize_* turns its payload into a Call,
# _emit turns a decision back into what that CLI expects.

SAFE_PROGRAMS = {"ls", "pwd", "cat", "head", "tail", "wc", "stat", "which", "echo", "tree",
                 "rg", "grep", "du", "date", "true"}
# Not `grep` (-O runs a pager command) or `branch` (-D deletes).
SAFE_GIT = {"status", "diff", "log", "show", "rev-parse", "ls-files", "blame", "describe", "shortlog"}
UNSAFE_GIT_FLAGS = ("-O", "--open-files-in-pager", "--output", "--ext-diff", "--textconv")
UNSAFE_FLAGS = {"find": {"-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint", "-fprint0", "-fprintf",
                         "-fls"},
                "rg": {"--pre", "--pre-glob"}, "tree": {"-o"}}
SHELL_SYNTAX = set(";&|<>`$(){}\\\n")
# On Windows a backslash is a path separator, but cmd expands %VAR% and !VAR! and escapes with ^, and
# PowerShell turns `a,b` into two arguments.
SHELL_SYNTAX_WIN = set(";&|<>`$(){}\n\r%^!,")
PROTECTED = (".git/", ".agents/hooks.json", ".cursor/hooks.json")
PATHEXT = (".exe", ".com", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".wsf")

# agy's tool names differ between models (one calls `view_file`, another `read_file`), so beyond
# these lists it is classified by name, and anything unrecognized goes to the user.
AGY_COMMANDS = {"run_command", "shell_exec", "execute_notebook", "notebook_execution", "send_command_input",
                "run_extension_code", "restart_dev_server", "compile", "compile_applet", "blaze_build_targets",
                "blaze_test_targets", "build_cleaner", "lint_applet", "install_applet_dependencies",
                "install_applet_package"}
AGY_INTERNAL = {"finish", "wait", "wait_5_seconds", "command_status", "read_terminal", "ask_question",
                "ask_permission", "ask_custom_permission", "list_permissions", "manage_task", "task_boundary",
                "notify_user", "checkpoint", "tool_search", "retrieve_memory", "suggested_responses",
                "planner_response", "ephemeral_message", "system_message", "code_acknowledgement", "findings",
                "critique"}
AGY_REFUSED = {"invoke_subagent", "define_subagent", "manage_subagents", "browser_subagent", "schedule",
               "send_message", "manage_inbox", "delete_knowledge", "run_workflow", "brain_update", "ki_insertion",
               "knowledge_generation", "knowledge_artifacts", "memory", "deploy_firebase", "set_up_firebase",
               "set_up_cloud_sql", "cloud_sql_execute_sql", "cloud_sql_update_schema", "post_pr_review",
               "start_code_review", "propose_ai_comments", "git_commit", "search_marketplace",
               "list_plugin_accounts", "generate_image"}
AGY_MCP = {"call_mcp_tool", "mcp_tool", "read_resource", "list_resources", "agency_tool_call"}
AGY_NETWORK = {"read_url_content", "search_web", "open_browser_url", "read_browser_page", "execute_browser_javascript",
               "click_browser_pixel", "list_browser_pages", "internal_search", "retrieve_content"}
WRITE_WORDS = ("edit", "write", "replace", "create", "delete", "move", "rename", "patch", "sed", "insert",
               "append", "file_change")
READ_PREFIXES = ("view_", "read_", "list_", "find", "grep", "code_search", "search_")
CLAUDE_READS = {"Read", "Glob", "Grep", "LS", "NotebookRead"}
# Readers that search the working directory when given no path; any other read without a path asks.
CWD_READERS = {"grep_search", "find_by_name", "list_dir", "list_directory", "code_search", "codesearch",
               "find_all_references", "Glob", "Grep", "LS"}
CLAUDE_WRITES = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
CLAUDE_INTERNAL = {"TodoWrite", "Task", "Agent", "ExitPlanMode", "BashOutput", "KillShell", "KillBash",
                   "TaskOutput", "TaskStop", "Skill"}


def _call(tool, kind, text="", paths=(), target=None):
    """target: the URL of a network call, or "server/tool" of an MCP call, for the elder's rules."""
    return {"tool": tool, "kind": kind, "text": text, "paths": list(paths), "target": target}


def _url_in(args):
    for v in (args or {}).values():
        m = re.search(r"https?://[^\s\"'<>]+", v) if isinstance(v, str) else None
        if m:
            return m.group(0)
    return None


def _mcp_name(server, tool):
    return "%s/%s" % (server, tool) if server and tool else server or None


def _mcp_from_args(args):
    """agy's call_mcp_tool names the server and the tool in its arguments."""
    args = args or {}
    server = next((v for k, v in args.items() if "server" in k.lower() and isinstance(v, str)), None)
    tool = next((v for k, v in args.items() if "tool" in k.lower() and "server" not in k.lower()
                 and isinstance(v, str)), None)
    return _mcp_name(server, tool)


def _mcp_from_name(name):
    """Claude Code and Codex call MCP tools mcp__server__tool."""
    parts = (name or "").split("__")
    return _mcp_name(parts[1], "__".join(parts[2:])) if len(parts) > 1 and parts[0] == "mcp" else None


def _paths_in(args):
    """Values of the arguments whose names say they hold a path (edited text is never a path)."""
    out = []
    for key, value in (args or {}).items():
        if not any(w in key.lower() for w in ("path", "file", "dir", "folder", "uri")):
            continue
        for v in value if isinstance(value, list) else [value]:
            if isinstance(v, str) and v:
                out.append(v)
    return out


def _normalize_agy(payload):
    call = payload.get("toolCall") or {}
    name, args = call.get("name") or "?", call.get("args") or {}
    summary = json.dumps(args, ensure_ascii=False)[:300]
    if name in AGY_REFUSED:
        return _call(name, "refused")
    if name in AGY_INTERNAL:
        return _call(name, "internal")
    if name in AGY_COMMANDS:
        if name == "send_command_input":
            return _call(name, "command", "send input to a running command: %s" % summary)
        cwd = args.get("Cwd")  # a relative path in the command resolves against it
        return _call(name, "command", args.get("CommandLine") or summary, [cwd] if isinstance(cwd, str) and cwd else ())
    if name in AGY_MCP:
        return _call(name, "mcp", summary, target=_mcp_from_args(args))
    if name in AGY_NETWORK or "browser" in name:
        return _call(name, "network", summary, target=_url_in(args))
    if any(w in name for w in WRITE_WORDS):
        return _call(name, "write", summary, _paths_in(args))
    if name in CWD_READERS or name.startswith(READ_PREFIXES):
        return _call(name, "read", summary, _paths_in(args))
    return _call(name, "other", summary)


def _normalize_claude(payload):
    name, inp = payload.get("tool_name") or "?", payload.get("tool_input") or {}
    if name == "Bash":
        return _call(name, "command", inp.get("command") or "")
    if name in CLAUDE_READS:
        return _call(name, "read", paths=_paths_in(inp))
    if name in CLAUDE_WRITES:
        return _call(name, "write", paths=_paths_in(inp))
    if name in CLAUDE_INTERNAL:
        return _call(name, "internal")  # hooks also gate what a Task subagent runs
    if name in ("WebFetch", "WebSearch"):
        return _call(name, "network", json.dumps(inp)[:300], target=_url_in(inp))
    if name.startswith("mcp__"):
        return _call(name, "mcp", json.dumps(inp)[:300], target=_mcp_from_name(name))
    return _call(name, "other", json.dumps(inp)[:300])


def _normalize_codex(payload):
    # PermissionRequest only fires when a call wants out of Codex's sandbox.
    name, inp = payload.get("tool_name") or "?", payload.get("tool_input") or {}
    reason = inp.get("description") if isinstance(inp, dict) else None
    if name == "Bash":
        c = _call(name, "command", (inp or {}).get("command") or "")
    elif name in ("apply_patch", "Edit", "Write"):
        c = _call(name, "write", "patch outside the sandbox: %s" % str((inp or {}).get("command") or "")[:300])
    elif name.startswith("mcp__"):
        c = _call(name, "mcp", json.dumps(inp)[:300], target=_mcp_from_name(name))
    else:
        c = _call(name, "other", json.dumps(inp)[:300])
    c["why"] = reason
    return c


def _normalize_cursor(payload):
    event = payload.get("hook_event_name") or ""
    if event == "beforeMCPExecution" or "mcp_server_name" in payload:
        # Its `command` field is the MCP server's launch string, not a shell command.
        return _call(payload.get("tool_name") or "mcp", "mcp", json.dumps(payload.get("tool_input"))[:300],
                     target=_mcp_name(payload.get("mcp_server_name"), payload.get("tool_name")))
    if event == "preToolUse" or (not event and "tool_input" in payload):
        # Installed for Write|Edit|Delete only: Cursor has no other hook that sees edits.
        name, inp = payload.get("tool_name") or "?", payload.get("tool_input")
        inp = _json_or(inp, {}) if isinstance(inp, str) else inp if isinstance(inp, dict) else {}
        if any(w in name.lower() for w in WRITE_WORDS):
            return _call(name, "write", json.dumps(inp, ensure_ascii=False)[:300], _paths_in(inp))
        if name == "Read":
            return _call(name, "read", paths=_paths_in(inp))
        return _call(name, "other", json.dumps(inp, ensure_ascii=False)[:300])
    if event == "beforeReadFile" or ("file_path" in payload and "command" not in payload):
        return _call("read", "read", paths=[p for p in [payload.get("file_path")] if isinstance(p, str) and p])
    if event == "beforeShellExecution" or "command" in payload:
        return _call("shell", "command", payload.get("command") or "")
    return _call(event or "?", "other", json.dumps(payload)[:300])


def _emit(cli, decision, reason):
    allow = decision == "allow"
    if cli == "agy":
        return {"decision": "allow"} if allow else {"decision": decision, "reason": reason}
    if cli == "claude":
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": decision,
                                       "permissionDecisionReason": reason}}
    if cli == "codex":
        d = {"behavior": "allow"} if allow else {"behavior": "deny", "message": reason}
        return {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": d}}
    if cli == "cursor":
        out = {"permission": decision}
        if not allow:
            out.update(user_message=reason, agent_message=reason)
        return out
    return {"decision": decision, "reason": reason}


NORMALIZERS = {"agy": _normalize_agy, "claude": _normalize_claude, "codex": _normalize_codex,
               "cursor": _normalize_cursor}


def _split(cmd, win=WIN):
    """shlex.split, except that on Windows a backslash is a path separator, not an escape."""
    words = shlex.split(cmd, posix=not win)
    if win:  # non-POSIX shlex reads backslashes literally but keeps a quoted word's quotes
        words = [w[1:-1] if len(w) > 1 and w[0] == w[-1] and w[0] in "\"'" else w for w in words]
    return words


def _tokens(cmd, win=WIN):
    """Words of a plain command line, or None when it uses shell syntax shoggoth doesn't read."""
    if not cmd or any(ch in (SHELL_SYNTAX_WIN if win else SHELL_SYNTAX) for ch in cmd):
        return None
    try:
        return _split(cmd, win)
    except ValueError:
        return None


def _win_clean(p):
    """Windows drops a trailing dot or space from a name and reads `name:stream` as the file `name`,
    so `.git.` and `.git::$INDEX_ALLOCATION` both mean `.git`."""
    drive, rest = ntpath.splitdrive(p)
    parts = [x if x in (".", "..") else x.split(":", 1)[0].rstrip(" .") for x in re.split(r"[\\/]", rest)]
    return drive + "\\".join(parts)


def _win_stream(path):
    """A Windows alternate data stream (`a.txt:hidden`): stored beside the file, where git never looks."""
    p = str(path)
    if p.lower().startswith("file://"):
        p = unquote(p[7:].partition("/")[2])
    return ":" in ntpath.splitdrive(p)[1]


def _resolve(path, repo):
    """The real absolute path a tool argument names: file:// stripped, ~ expanded, relative to the repo."""
    p = str(path)
    if p.lower().startswith("file://"):
        host, _, rest = p[7:].partition("/")
        # file:///x and file://localhost/x name a local path; any other host is never inside the repo.
        if host.lower() in ("", "localhost"):
            p = unquote(rest) if WIN and re.match(r"[A-Za-z]:", unquote(rest)) else unquote("/" + rest)
        else:
            p = "//%s/%s" % (host, rest)
    p = os.path.expanduser(p)
    if WIN:
        p = _win_clean(p)
    if not os.path.isabs(p):
        p = os.path.join(str(repo), p)  # the hook's own working directory isn't the repo
    return os.path.realpath(p)


def inside(path, repo):
    # normcase: Windows paths compare without case (it changes nothing elsewhere).
    p, root = os.path.normcase(_resolve(path, repo)), os.path.normcase(os.path.realpath(str(repo)))
    return p == root or p.startswith(root + os.sep)


def _protected(path, repo):
    # Compared without case: on a case-insensitive disk `.GIT/config` is `.git/config`.
    try:
        rel = os.path.relpath(_resolve(path, repo), os.path.realpath(str(repo)))
    except ValueError:  # on another Windows drive, so not in the repo at all
        return False
    rel = (rel.replace("\\", "/") if WIN else rel).lower()
    return any(rel == x.rstrip("/") or rel.startswith(x) for x in PROTECTED)


def read_only(cmd, repo, cwds=(), win=WIN):
    words = _tokens(cmd, win)
    if not words:
        return False
    # A program given by path may be a script the shoggoth just wrote (`./ls`): only bare names count.
    if re.search(r"[\\/]" if win else "/", words[0]):
        return False
    prog, args = words[0], words[1:]
    if win:
        prog = prog.lower()[:-4] if prog.lower().endswith(".exe") else prog.lower()
        # cmd.exe runs a program in the current directory before PATH: `git` could be the repo's git.bat.
        for d in [repo] + list(cwds):
            base = _resolve(d, repo)
            if any(os.path.isfile(os.path.join(base, words[0] + ext)) for ext in ("",) + PATHEXT):
                return False
    if prog == "git":
        if not args or args[0] not in SAFE_GIT or any(a.startswith(UNSAFE_GIT_FLAGS) for a in args):
            return False
    elif prog not in SAFE_PROGRAMS and prog != "find":
        return False
    if any(a.split("=", 1)[0] in UNSAFE_FLAGS.get(prog, ()) for a in args):
        return False
    for a in args:
        value = a.split("=", 1)[1] if a.startswith("-") and "=" in a else a
        if win:
            # `env:TOKEN` and `HKLM:\...` are PowerShell drives, `a.txt:s` a stream: only C:\ paths pass.
            if ":" in value and not re.match(r"[A-Za-z]:[\\/]", value):
                return False
            # Read both ways: literally (cmd, PowerShell) and with backslash escapes (Git Bash).
            if any(v and not inside(v, repo) for v in {value, re.sub(r"\\(.)", r"\1", value)}):
                return False
        elif value.startswith(("/", "~")) or ".." in value.split("/"):
            if not inside(value, repo):
                return False
    return True


def approved(cmd, approvals):
    """Exactly an approved command line (spacing aside): `rm -rf build` doesn't approve `rm -rf build /`."""
    line = " ".join(str(cmd or "").split())
    return bool(line) and any(line == " ".join(str(a or "").split()) for a in approvals)


def decide(call, repo, approvals, policy=None):
    """(decision, rule): decision is allow, deny, or ask. The floor comes first (.git/ and hook-file writes,
    tools a shoggoth never gets); then the elder's own permission rules and mode, so the shoggoth has the
    elder's permissions; then shoggoth's built-in rules for what those don't decide."""
    kind = call["kind"]
    if kind == "internal":
        return "allow", "internal"
    if kind == "refused":
        return "deny", "not available to a shoggoth"
    if kind == "write" and any(_protected(p, repo) for p in call["paths"]):
        return "deny", "protected path"
    if not policy:
        return _builtin(call, repo, approvals)
    host = policy.get("host")
    rule = _policy_hit(policy, "deny", call, repo)
    if rule:
        return "deny", "%s deny rule %s" % (host, _one(rule["text"], 100))
    if not (kind == "command" and approved(call["text"], approvals)):
        rule = _policy_hit(policy, "ask", call, repo)
        # Grok's always-approve still asks for shell `ask` rules, not for other tools' (its docs).
        if rule and not (policy.get("open") and host == "grok" and kind != "command"):
            return "ask", "%s ask rule %s" % (host, _one(rule["text"], 100))
    rule = _policy_hit(policy, "allow", call, repo)
    if rule:
        return "allow", "%s allow rule %s" % (host, _one(rule["text"], 100))
    if policy.get("open"):
        return "allow", "%s runs without asking (%s)" % (host, policy.get("mode"))
    decision, why = _builtin(call, repo, approvals)
    if decision == "ask" and policy.get("closed"):
        return "deny", "%s never asks (%s): %s" % (host, policy.get("mode"), why)
    return decision, why


def _builtin(call, repo, approvals):
    kind = call["kind"]
    if kind in ("read", "write"):
        if kind == "write" and WIN and any(_win_stream(p) for p in call["paths"]):
            return "ask", "a Windows stream, which git doesn't see"
        if not call["paths"]:
            if kind == "read" and call["tool"] in CWD_READERS:
                return "allow", "inside the repo"  # searches the working directory, which is the repo
            return "ask", "a %s shoggoth can't place" % kind
        if all(inside(p, repo) for p in call["paths"]):
            return "allow", "inside the repo"
        return "ask", "outside the repo"
    if kind == "command":
        outside = [p for p in call["paths"] if not inside(p, repo)]
        if outside:
            return "ask", "runs outside the repo, in %s" % outside[0]
        if approved(call["text"], approvals):
            return "allow", "approved"
        if read_only(call["text"], repo, call["paths"]):
            return "allow", "read-only"
        return "ask", "command"
    return "ask", kind


# ---------------------------------------------------------------- the elder's permission rules
# The shoggoth gets the elder's permissions. Each host's settings (global and project) become one
# policy: deny, ask, and allow rules in a shared shape, and the host's mode: "open" when it runs without
# asking, "closed" when it never asks and refuses instead. Rule matching follows Grok's documented
# reference, which Claude Code shares: commands split at ; & | and newlines, deny and ask rules hit on
# any segment, allow rules must cover every segment, and leading VAR=x and wrappers are peeled first.

PEELED = {"timeout", "nice", "ionice", "chrt", "stdbuf", "env"}
ENV_ASSIGN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
SCRIPT_SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
SAFE_SINKS = {"/dev/null", "/dev/stdout", "/dev/stderr", "nul"}


def _segments(cmd):
    """(segments, opaque): the command line split at ; & | && || and newlines outside quotes. Opaque when it
    substitutes a command ($(...), backticks, <(...)), which no rule can vet."""
    segs, cur, quote, opaque, i = [], "", None, False, 0
    while i < len(cmd):
        c = cmd[i]
        if quote == "'":
            cur += c
            quote = None if c == "'" else quote
        elif c == "\\" and i + 1 < len(cmd):
            cur += cmd[i:i + 2]
            i += 2
            continue
        else:
            if c == "`" or cmd.startswith("$(", i) or (not quote and cmd.startswith(("<(", ">("), i)):
                opaque = True
            if quote == '"':
                cur += c
                quote = None if c == '"' else quote
            elif c in "'\"":
                quote = c
                cur += c
            elif c in ";|\n\r" or (c == "&" and not cur.endswith((">", "<")) and not cmd.startswith("&>", i)):
                if cur.strip():
                    segs.append(cur.strip())
                cur = ""
            else:
                cur += c
        i += 1
    if cur.strip():
        segs.append(cur.strip())
    return segs, opaque


def _peel(words):
    """Drop leading VAR=x assignments and wrappers such as `timeout 30` or `nice -n 5`."""
    i = 0
    while i < len(words):
        if ENV_ASSIGN.match(words[i]):
            i += 1
            continue
        if os.path.basename(words[i]) not in PEELED:
            break
        i += 1
        while i < len(words) and (words[i].startswith("-") or ENV_ASSIGN.match(words[i])
                                  or re.fullmatch(r"-?[\d.]+[smhd]?", words[i])):
            i += 1
    return words[i:]


def _script_of(words):
    """The script inside `bash -c '...'`, `powershell -Command ...`, or `cmd /c ...`, else None."""
    prog = re.split(r"[\\/]", words[0])[-1].lower() if words else ""
    prog = prog[:-4] if prog.endswith(".exe") else prog
    if len(words) < 3 or prog not in SCRIPT_SHELLS | {"powershell", "pwsh", "cmd"}:
        return None
    for i, w in enumerate(words[1:], 1):
        if w.lower() in WRAPPER_FLAGS:
            return words[i + 1] if prog != "cmd" else " ".join(words[i + 1:])
        if not w.startswith(("-", "/")):
            return None
    return None


def _commands(cmd, depth=0):
    """(commands, opaque): each simple command as (words, raw text), wrappers peeled, `bash -c` scripts opened."""
    segs, opaque = _segments(cmd)
    out = []
    for seg in segs:
        try:
            words = _peel(_split(seg))
        except ValueError:
            opaque = True
            continue
        if not words:
            continue
        script = _script_of(words)
        if script is not None and depth < 3:
            inner, more = _commands(script, depth + 1)
            out += inner
            opaque = opaque or more
            continue
        out.append((words, seg))
    return out, opaque


def _glob_re(pattern):
    """A path glob as a regex: * and ? stay within a folder, ** crosses folders."""
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif pattern[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return out


def _abs_glob(pattern, repo, flavor, base=None):
    """A host's path pattern as an absolute glob. Claude Code: //abs, ~/home, /relative-to-the-settings-file,
    a bare name at any depth (gitignore). Grok and Cursor: absolute, or relative to the working directory."""
    p = pattern.strip().replace("\\", "/")
    root = str(repo).replace("\\", "/").rstrip("/")
    if p in ("", "*", "**", "/", "//"):
        return "**"
    if p.startswith("~/"):
        return str(Path.home()).replace("\\", "/") + p[1:]
    if flavor == "claude":
        if p.startswith("//"):
            return p[1:]
        if p.startswith("/"):
            return str(base or repo).replace("\\", "/").rstrip("/") + p
        if "/" not in p.rstrip("/"):
            return root + "/**/" + p
    if p.startswith("/") or re.match(r"[A-Za-z]:/", p) or p.startswith("**"):
        return p
    return root + "/" + (p[2:] if p.startswith("./") else p)


def _rule(text, verdict, kind, **kw):
    return dict(kw, text=text, verdict=verdict, kind=kind)


def _claude_rule(text, verdict, repo, flavor="claude", base=None):
    """A Claude Code / Grok rule string: Bash(...), Read(...), Edit(...), WebFetch(...), mcp__..., MCPTool(...)."""
    m = re.fullmatch(r"\s*([A-Za-z_*][\w-]*)\s*(?:\((.*)\))?\s*", text or "", re.S)
    if not m:
        return None
    tool, arg = m.group(1), m.group(2)
    arg = arg.strip() if arg is not None else None
    if tool == "*":
        return _rule(text, verdict, "any", all=True)
    if tool == "Bash":
        if arg in (None, "", "*", ":*"):
            return _rule(text, verdict, "command", all=True)
        arg = " ".join(arg.split())
        if arg.endswith(":*"):
            return _rule(text, verdict, "command", match="word" if flavor == "claude" else "prefix", value=arg[:-2].strip())
        if any(ch in arg for ch in "*?["):
            return _rule(text, verdict, "command", match="glob", value=arg)
        return _rule(text, verdict, "command", match="exact" if flavor == "claude" else "prefix", value=arg)
    kinds = {"Read": "read", "Grep": "read", "Glob": "read", "LS": "read", "NotebookRead": "read",
             "Edit": "write", "Write": "write", "MultiEdit": "write", "NotebookEdit": "write"}
    if tool in kinds:
        if arg in (None, "", "*", "**"):
            return _rule(text, verdict, kinds[tool], all=True)
        return _rule(text, verdict, kinds[tool], path=_glob_re(_abs_glob(arg, repo, flavor, base)))
    if tool == "WebFetch":
        if not arg:
            return _rule(text, verdict, "network", url=True)
        if arg.startswith("domain:"):
            return _rule(text, verdict, "network", domain=arg[7:].strip().lower())
        return _rule(text, verdict, "network", url_glob=arg)
    if tool == "WebSearch":
        return _rule(text, verdict, "network", search=True)
    if tool == "MCPTool":
        return _rule(text, verdict, "mcp", glob=arg or "*")
    if tool.startswith("mcp__"):
        parts = tool.split("__")[1:]
        glob = "*" if parts in ([], ["*"]) else "%s__%s" % (parts[0], "__".join(parts[1:]) or "*")
        return _rule(text, verdict, "mcp", glob=glob)
    return None


def _agy_rule(text, verdict, repo):
    """agy: command(prefix), command(regex:one pattern per word), read_file(/path), write_file(/path),
    read_url(domain), execute_url(domain), mcp(server/tool)."""
    m = re.fullmatch(r"\s*(command|read_file|write_file|read_url|execute_url|mcp)\((.*)\)\s*", text or "", re.S)
    if not m:
        return None
    kind, arg = m.group(1), m.group(2).strip()
    if kind == "command":
        if arg == "*":
            return _rule(text, verdict, "command", all=True)
        if arg.startswith("regex:"):
            pats = arg[6:].split()
            try:
                [re.compile(p) for p in pats]
            except re.error:
                return None
            return _rule(text, verdict, "command", match="words", value=pats)
        return _rule(text, verdict, "command", match="word", value=" ".join(arg.split()))
    if kind in ("read_file", "write_file"):
        k = "read" if kind == "read_file" else "write"
        if arg in ("*", "/"):
            return _rule(text, verdict, k, all=True)
        under = os.path.expanduser(arg).replace("\\", "/").rstrip("/")
        return _rule(text, verdict, k, path=re.escape(under) + "(?:/.*)?")
    if kind in ("read_url", "execute_url"):
        return _rule(text, verdict, "network", all=True) if arg == "*" else \
            _rule(text, verdict, "network", domain=arg.lower())
    return _rule(text, verdict, "mcp", glob="*" if arg == "*" else arg.replace("/", "__"))


def _cursor_rule(text, verdict, repo):
    """Cursor CLI: Shell(base command), Read(glob), Write(glob), Mcp(server:tool), WebFetch(domain)."""
    m = re.fullmatch(r"\s*(Shell|Read|Write|Mcp|WebFetch)\((.*)\)\s*", text or "", re.S)
    if not m:
        return None
    kind, arg = m.group(1), m.group(2).strip()
    if kind == "Shell":
        return _rule(text, verdict, "command", all=True) if arg in ("*", "") else \
            _rule(text, verdict, "command", match="word", value=" ".join(arg.split()))
    if kind in ("Read", "Write"):
        k = kind.lower() if kind == "Read" else "write"
        return _rule(text, verdict, k, all=True) if arg in ("*", "**") else \
            _rule(text, verdict, k, path=_glob_re(_abs_glob(arg, repo, "cursor")))
    if kind == "Mcp":
        return _rule(text, verdict, "mcp", glob="*" if arg in ("*", "") else arg.replace(":", "__"))
    return _rule(text, verdict, "network", domain=arg.lower())


def _codex_rule(kw, verdict):
    pattern = kw.get("pattern")
    if not isinstance(pattern, list) or not pattern:
        return None
    alts = [[p] if isinstance(p, str) else [x for x in p if isinstance(x, str)] for p in pattern]
    return _rule("prefix_rule(%s)" % json.dumps(pattern), verdict, "command", match="argv", value=alts)


def _command_text_hits(rule, words, raw):
    joined, raw = " ".join(words), " ".join(raw.split())
    match, value = rule.get("match"), rule.get("value")
    for text in (joined, raw):
        if match == "exact" and text == value:
            return True
        if match == "prefix" and text.startswith(value):
            return True
        if match == "word" and (text == value or text.startswith(value + " ")):
            return True
        if match == "glob" and fnmatch.fnmatchcase(text, value):
            return True
    if match == "words":
        return len(words) >= len(value) and all(re.search(p, w) for p, w in zip(value, words))
    if match == "argv":
        return len(words) >= len(value) and all(w in alt for alt, w in zip(value, words))
    return False


def _sinks_ok(raw, repo):
    """Does every output redirection in this command go to /dev/null, a stream, or a file in the repo?"""
    for m in re.finditer(r"(?:\d*|&)>>?\|?\s*(&\d+|\"[^\"]*\"|'[^']*'|[^\s;&|<>]+)", raw):
        target = m.group(1).strip("\"'")
        if not (target.startswith("&") or target.lower() in SAFE_SINKS or inside(target, repo)):
            return False
    return True


def _path_hits(rule, path, repo, whole):
    p = _resolve(path, repo).replace("\\", "/")
    flags = re.I if WIN else 0
    if re.fullmatch(rule["path"], p, flags):
        return True
    # deny and ask cover a folder's contents too
    return not whole and any(re.fullmatch(rule["path"], p[:i], flags) for i in range(1, len(p)) if p[i] == "/")


def _operands(words, repo):
    """The arguments of a command that name files: path-like (a slash, a leading . or ~) or existing.
    Plain words (`add`, `zod`) aren't files, even though they'd resolve inside the repo."""
    out = []
    for w in words[1:]:
        if w.startswith("-"):
            if "=" not in w:
                continue
            w = w.split("=", 1)[1]
        if w and (re.search(r"[\\/]", w) or w.startswith((".", "~")) or os.path.lexists(_resolve(w, repo))):
            out.append(w)
    return out


def _rule_hits(rule, call, repo):
    """Does this rule cover the call? Allow rules must cover all of it; deny and ask rules any part."""
    kind, whole = call["kind"], rule["verdict"] == "allow"
    if rule["kind"] == "any":
        return True
    if kind == "command" and rule["kind"] in ("read", "write") and not whole and not rule.get("all"):
        # A Read or Edit deny also covers files a shell command names (`cat .env`).
        cmds, _ = _commands(call["text"])
        return any(_path_hits(rule, w, repo, False) for words, _ in cmds for w in _operands(words, repo))
    if rule["kind"] != kind:
        return False
    if kind == "command":
        if rule.get("all"):
            return True
        cmds, opaque = _commands(call["text"])
        if whole:
            return bool(cmds) and not opaque and all(
                _command_text_hits(rule, w, raw) and (">" in rule["text"] or _sinks_ok(raw, repo)) for w, raw in cmds)
        if any(_command_text_hits(rule, w, raw) for w, raw in cmds):
            return True
        text = " ".join(call["text"].split())
        if rule.get("match") in ("prefix", "word", "glob") and _command_text_hits(rule, text.split(" "), text):
            return True
        # what a substitution would run: $(rm -rf ~) hides a segment
        hidden = re.sub(r"\$\(|`|<\(|>\(|\)", "\n", call["text"])
        return hidden != call["text"] and any(_command_text_hits(rule, w, raw) for w, raw in _commands(hidden)[0])
    if kind in ("read", "write"):
        if rule.get("all"):
            return True
        hits = [_path_hits(rule, p, repo, whole) for p in call["paths"]]
        return bool(hits) and (all(hits) if whole else any(hits))
    if kind == "network":
        url = call.get("target")
        if rule.get("all"):
            return True
        if rule.get("search"):
            return not url and "search" in call["tool"].lower()
        if not url:
            return False
        if rule.get("url"):
            return True
        if "url_glob" in rule:
            return fnmatch.fnmatchcase(url, rule["url_glob"])
        host = (urlparse(url).hostname or "").lower()
        host = host[4:] if host.startswith("www.") else host
        d = rule["domain"][4:] if rule["domain"].startswith("www.") else rule["domain"]
        return host == d or host.endswith("." + d)
    if kind == "mcp":
        return rule.get("all") or bool(call.get("target")) and fnmatch.fnmatchcase(call["target"], rule["glob"])
    return False


def _policy_hit(policy, verdict, call, repo):
    for rule in policy.get(verdict) or []:
        try:
            if _rule_hits(rule, call, repo):
                return rule
        except (re.error, ValueError, TypeError):
            continue
    return None


def _read_json(path, pol):
    try:
        doc = json.loads(_decode(path.read_bytes()))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        pol["skipped"].append("%s: %s" % (path, type(e).__name__))
        return None
    if isinstance(doc, dict):
        pol["sources"].append(str(path))
        return doc
    return None


def _read_toml(path, pol):
    try:
        text = _decode(path.read_bytes())
    except (FileNotFoundError, NotADirectoryError):
        return None
    except OSError as e:
        pol["skipped"].append("%s: %s" % (path, type(e).__name__))
        return None
    try:
        try:
            import tomllib
            doc = tomllib.loads(text)
        except ImportError:  # Python < 3.11
            doc = _mini_toml(text)
    except Exception as e:  # noqa: BLE001 (a broken file shouldn't stop the run; it's listed instead)
        pol["skipped"].append("%s: %s" % (path, type(e).__name__))
        return None
    pol["sources"].append(str(path))
    return doc


def _add_rules(pol, rules, parse, *args):
    for verdict in ("allow", "ask", "deny"):
        for text in (rules or {}).get(verdict) or []:
            r = parse(text, verdict, *args) if isinstance(text, str) else None
            if r:
                pol[verdict].append(r)
            else:
                pol["skipped"].append("rule %r" % (text,))


def _same_dir(a, b):
    return os.path.normcase(os.path.realpath(str(a))) == os.path.normcase(os.path.realpath(str(b)))


def _policy_agy(pol, repo):
    g = Path.home() / ".gemini"
    cli = _read_json(g / "antigravity-cli" / "settings.json", pol) or {}
    _add_rules(pol, cli.get("permissions"), _agy_rule, repo)
    mode = cli.get("toolPermission")
    shared = _read_json(g / "config" / "config.json", pol) or {}
    _add_rules(pol, (shared.get("userSettings") or {}).get("globalPermissionGrants"), _agy_rule, repo)
    for f in sorted((g / "config" / "projects").glob("*.json")):
        try:
            doc = json.loads(_decode(f.read_bytes()))
        except (OSError, ValueError):
            continue
        folders = [((r or {}).get("gitFolder") or {}).get("folderUri")
                   for r in ((doc.get("projectResources") or {}).get("resources") or [])]
        if any(u and _same_dir(_resolve(u, repo), repo) for u in folders):  # this repo's project wins
            pol["sources"].append(str(f))
            _add_rules(pol, (doc.get("permissionGrants") or {}).get("permissionGrants"), _agy_rule, repo)
            mode = (doc.get("settings") or {}).get("toolPermission") or mode
    pol["mode"] = mode or "request-review"
    pol["open"] = pol["mode"] == "always-proceed"


def _claude_settings(pol, repo, flavor):
    """Claude Code's settings files, lowest precedence first; the mode is the last one set."""
    home = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    managed = [Path("C:/Program Files/ClaudeCode/managed-settings.json"),
               Path("C:/ProgramData/ClaudeCode/managed-settings.json")] if WIN else \
        [Path("/Library/Application Support/ClaudeCode/managed-settings.json"),
         Path("/etc/claude-code/managed-settings.json")]
    files = [(home / "settings.json", Path.home())] if flavor == "claude" else []
    files += [(repo / ".claude" / "settings.json", repo), (repo / ".claude" / "settings.local.json", repo)]
    files += [(m, repo) for m in managed] if flavor == "claude" else []
    mode, locked = None, False
    for f, base in files:
        perms = (_read_json(f, pol) or {}).get("permissions") or {}
        _add_rules(pol, perms, _claude_rule, repo, "claude", base)
        mode = perms.get("defaultMode") or mode
        locked = locked or perms.get("disableBypassPermissionsMode") == "disable"
    return mode, locked


def _policy_claude(pol, repo):
    mode, locked = _claude_settings(pol, repo, "claude")
    pol["mode"] = mode or "default"
    pol["open"] = pol["mode"] == "bypassPermissions" and not locked
    pol["closed"] = pol["mode"] == "dontAsk"


def _grok_rule(text, verdict, repo):
    return _claude_rule(text, verdict, repo, "grok")


def _policy_grok(pol, repo):
    g = Path(os.environ.get("GROK_HOME") or Path.home() / ".grok")
    files = [Path("/etc/grok/managed_config.toml"), g / "managed_config.toml", g / "config.toml"]
    if os.environ.get("GROK_CONFIG_PATH"):
        files.append(Path(os.environ["GROK_CONFIG_PATH"]))
    files += [repo / ".grok" / "config.toml", g / "requirements.toml", Path("/etc/grok/requirements.toml")]
    mode, yolo, locked = None, False, False
    for f in files:
        doc = _read_toml(f, pol) or {}
        perm = doc.get("permission") or {}
        _add_rules(pol, perm, _grok_rule, repo)
        tools = {"bash": "Bash", "read": "Read", "edit": "Edit", "grep": "Grep", "mcp": "MCPTool",
                 "webfetch": "WebFetch", "websearch": "WebSearch"}
        for r in perm.get("rules") or []:  # { action = "deny", tool = "bash", pattern = "rm -rf *" }
            if isinstance(r, dict) and r.get("action") in ("allow", "ask", "deny") and str(r.get("tool")).lower() in tools:
                text = tools[str(r["tool"]).lower()] + ("(%s)" % r["pattern"] if r.get("pattern") else "")
                rule = _grok_rule(text, r["action"], repo)
                if rule:
                    pol[r["action"]].append(rule)
        ui = doc.get("ui") or {}
        if f.name == "requirements.toml":
            locked = locked or ui.get("disable_bypass_permissions_mode") is True or ui.get("yolo") is False
        elif f.parent != repo / ".grok":  # a project file contributes rules only
            mode = ui.get("permission_mode") or doc.get("permission_mode") or mode
            yolo = ui.get("yolo") is True or yolo
    claude_mode, claude_locked = _claude_settings(pol, repo, "grok")  # Grok reads .claude/settings*.json too
    pol["mode"] = mode or claude_mode or "default"
    pol["open"] = (pol["mode"] in ("always-approve", "bypassPermissions") or yolo) and not (locked or claude_locked)
    pol["closed"] = pol["mode"] == "dontAsk"


def _codex_rules_in(text):
    """The prefix_rule(...) calls in a Codex .rules file (Starlark, whose literals are Python's)."""
    import ast
    out = []
    for m in re.finditer(r"\bprefix_rule\s*\(", text):
        i = j = m.end()
        depth, quote = 1, None
        while j < len(text) and depth:
            c = text[j]
            if quote:
                if c == "\\":
                    j += 1
                elif c == quote:
                    quote = None
            elif c in "\"'":
                quote = c
            elif c in "([{":
                depth += 1
            elif c in ")]}":
                depth -= 1
            j += 1
        try:
            call = ast.parse("f(%s)" % text[i:j - 1], mode="eval").body
            out.append({k.arg: ast.literal_eval(k.value) for k in call.keywords if k.arg})
        except (SyntaxError, ValueError):
            continue
    return out


def _policy_codex(pol, repo):
    c = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    cfg = _read_toml(c / "config.toml", pol) or {}
    prof = (cfg.get("profiles") or {}).get(cfg.get("profile")) or {}
    proj = _read_toml(repo / ".codex" / "config.toml", pol) or {}
    approval = proj.get("approval_policy") or prof.get("approval_policy") or cfg.get("approval_policy")
    sandbox = proj.get("sandbox_mode") or prof.get("sandbox_mode") or cfg.get("sandbox_mode")
    approval = approval if isinstance(approval, str) else "on-request"
    sandbox = sandbox if isinstance(sandbox, str) else "workspace-write"
    for d in (c / "rules", repo / ".codex" / "rules"):
        for f in sorted(d.glob("*.rules")) if d.is_dir() else []:
            try:
                rules = _codex_rules_in(_decode(f.read_bytes()))
            except OSError:
                continue
            pol["sources"].append(str(f))
            verdicts = {"allow": "allow", "prompt": "ask", "forbidden": "deny"}
            for kw in rules:
                verdict = verdicts.get(kw.get("decision", "allow"))
                rule = _codex_rule(kw, verdict) if verdict else None
                if rule:
                    pol[verdict].append(rule)
    pol["mode"] = "approval %s, sandbox %s" % (approval, sandbox)
    pol["open"] = approval == "never" and sandbox == "danger-full-access"
    pol["closed"] = approval == "never" and not pol["open"]


def _policy_cursor(pol, repo):
    mode = None
    for f in (Path.home() / ".cursor" / "cli-config.json", repo / ".cursor" / "cli.json"):
        doc = _read_json(f, pol) or {}
        _add_rules(pol, doc.get("permissions"), _cursor_rule, repo)
        mode = doc.get("approvalMode") or mode
    pol["mode"] = mode or "allowlist"
    pol["open"] = pol["mode"] in ("unrestricted", "yolo")


POLICY_LOADERS = {"agy": _policy_agy, "claude": _policy_claude, "codex": _policy_codex, "cursor": _policy_cursor,
                  "grok": _policy_grok}


def elder_policy(elder, repo):
    """The elder host's permission settings as one policy, or None for a host shoggoth can't read."""
    if elder not in POLICY_LOADERS:
        return None
    pol = {"host": elder, "sources": [], "mode": None, "open": False, "closed": False,
           "allow": [], "ask": [], "deny": [], "skipped": []}
    POLICY_LOADERS[elder](pol, Path(repo))
    return pol


def policy_line(pol):
    if not pol:
        return "shoggoth's own rules (this elder's settings aren't readable yet)"
    return "%s's settings · mode %s%s · %d allow, %d ask, %d deny rules%s" % (
        pol["host"], pol["mode"], " (the shoggoth won't ask either)" if pol["open"] else
        " (what would ask is refused)" if pol.get("closed") else "",
        len(pol["allow"]), len(pol["ask"]), len(pol["deny"]),
        " · %d skipped" % len(pol["skipped"]) if pol["skipped"] else "")


# ---------------------------------------------------------------- minimal TOML (Python < 3.11 has no tomllib)


def _toml_strip(line):
    out, quote = "", None
    for i, c in enumerate(line):
        if quote:
            if c == quote and not (quote == '"' and line[i - 1] == "\\"):
                quote = None
        elif c in "\"'":
            quote = c
        elif c == "#":
            break
        out += c
    return out


def _toml_open(text):
    depth, quote, i = 0, None, 0
    while i < len(text):
        c = text[i]
        if quote:
            if c == quote and not (quote == '"' and text[i - 1] == "\\"):
                quote = None
        elif text.startswith('"""', i) or text.startswith("'''", i):
            end = text.find(text[i:i + 3], i + 3)
            if end < 0:
                return 1
            i = end + 3
            continue
        elif c in "\"'":
            quote = c
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
        i += 1
    return depth


def _toml_keys(text):
    keys, cur, quote = [], "", None
    for c in text.strip():
        if quote:
            if c == quote:
                quote = None
            else:
                cur += c
        elif c in "\"'":
            quote = c
        elif c == ".":
            keys.append(cur.strip())
            cur = ""
        else:
            cur += c
    keys.append(cur.strip())
    return keys


def _toml_value(s, i=0):
    """(value, next index) for the TOML value starting at s[i]."""
    while i < len(s) and s[i] in " \t\r\n,":
        i += 1
    if s.startswith('"""', i) or s.startswith("'''", i):
        end = s.index(s[i:i + 3], i + 3)
        body = s[i + 3:end].lstrip("\n")
        return (json.loads('"%s"' % body.replace("\n", "\\n")) if s[i] == '"' else body), end + 3
    if s[i] == '"':
        j = i + 1
        while s[j] != '"':
            j += 2 if s[j] == "\\" else 1
        return json.loads(s[i:j + 1]), j + 1
    if s[i] == "'":
        j = s.index("'", i + 1)
        return s[i + 1:j], j + 1
    if s[i] in "[{":
        close, out, i = ("]", [], i + 1) if s[i] == "[" else ("}", {}, i + 1)
        while True:
            while i < len(s) and s[i] in " \t\r\n,":
                i += 1
            if s[i] == close:
                return out, i + 1
            if close == "]":
                v, i = _toml_value(s, i)
                out.append(v)
            else:
                eq = s.index("=", i)
                keys = _toml_keys(s[i:eq])
                v, i = _toml_value(s, eq + 1)
                t = out
                for k in keys[:-1]:
                    t = t.setdefault(k, {})
                t[keys[-1]] = v
    m = re.match(r"[^,\]}\s]+", s[i:])
    word = m.group(0)
    v = {"true": True, "false": False}.get(word, word)
    if isinstance(v, str) and re.fullmatch(r"[+-]?\d+", word.replace("_", "")):
        v = int(word.replace("_", ""))
    return v, i + len(word)


def _mini_toml(text):
    root, buf = {}, ""
    cur = root
    for line in text.splitlines():
        piece = _toml_strip(line)
        buf = buf + "\n" + piece if buf else piece
        if not buf.strip():
            buf = ""
            continue
        if _toml_open(buf) > 0:  # an array or inline table that goes on to the next line
            continue
        s, buf = buf.strip(), ""
        if s.startswith("[["):
            keys = _toml_keys(s[2:-2])
            t = root
            for k in keys[:-1]:
                t = t.setdefault(k, {})
            cur = {}
            t.setdefault(keys[-1], []).append(cur)
        elif s.startswith("["):
            cur = root
            for k in _toml_keys(s[1:-1]):
                cur = cur.setdefault(k, {})
        elif "=" in s:
            eq = s.index("=")
            keys = _toml_keys(s[:eq])
            t = cur
            for k in keys[:-1]:
                t = t.setdefault(k, {})
            t[keys[-1]] = _toml_value(s, eq + 1)[0]
    return root


@contextlib.contextmanager
def _locked(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+b") as fh:
        if not WIN:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)
            return
        fh.seek(0)  # msvcrt locks bytes from the current position: always the first one
        while True:
            try:
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                time.sleep(0.05)
        try:
            yield
        finally:
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)


def _approvals(run):
    return _json_or((run / "gate" / "approved.json").read_text(encoding="utf-8"), [])  \
        if (run / "gate" / "approved.json").exists() else []


def _add_approval(run, cmd):
    with _locked(run / "gate" / ".lock"):
        items = _approvals(run)
        if cmd not in items:
            items.append(cmd)
        _save(run / "gate", "approved.json", items)


def _gate_log(run, entry):
    with _locked(run / "gate" / ".lock"):
        with open(run / "gate" / "log.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def cmd_gate(a):
    """Hook entry point: the shoggoth's CLI runs this before a tool call and obeys its answer."""
    cli = a.cli
    try:
        payload = json.loads(_decode(sys.stdin.buffer.read()) or "{}")
    except ValueError:
        payload = {}
    run_env = os.environ.get("SHOGGOTH_RUN")
    if not run_env or not (Path(run_env) / "meta.json").exists():
        # Not one of this script's runs, e.g. the user's own agy session while the hook file is in place.
        print(json.dumps(_emit(cli, "ask", "shoggoth gate: not a shoggoth run")))
        return
    run = Path(run_env)
    try:
        meta = _load(run, "meta.json")
        call = NORMALIZERS[cli](payload)
        policy = _load(run / "gate", "policy.json") if (run / "gate" / "policy.json").exists() else None
        decision, rule = decide(call, meta["repo"], _approvals(run), policy)
        entry = {"time": time.time(), "tool": call["tool"], "kind": call["kind"], "text": call["text"],
                 "paths": call["paths"], "decision": decision, "by": "shoggoth", "rule": rule}
        reason = "gate: %s" % rule
        if decision == "ask":
            decision, reason, entry = _ask_user(run, call, rule, entry)
        if decision == "deny" and entry["by"] == "shoggoth":
            reason = "The gate refused this call (%s)." % rule
        _gate_log(run, entry)
        print(json.dumps(_emit(cli, decision, reason)))
    except Exception as e:  # fail closed: a broken gate never lets a call through
        print(json.dumps(_emit(cli, "deny", "Gate error, so the call is refused: %r" % e)))


def _ask_user(run, call, rule, entry):
    rid = uuid.uuid4().hex[:6]
    request = {"id": rid, "time": time.time(), "tool": call["tool"], "kind": call["kind"], "rule": rule,
               "text": call["text"], "paths": call["paths"], "why": call.get("why")}
    _save(run / "gate", "req-%s.json" % rid, request)
    answer_file = run / "gate" / ("ans-%s.json" % rid)
    deadline = time.time() + GATE_WAIT
    while time.time() < deadline and not answer_file.exists() and not (run / "stopped").exists():
        time.sleep(0.5)
    answer = _json_or(answer_file.read_text(encoding="utf-8"), {}) if answer_file.exists() else {}
    entry.update(request=rid, answered=answer.get("time"))
    if answer.get("decision") == "allow":
        if answer.get("always") and call["kind"] == "command":
            _add_approval(run, call["text"])
        entry.update(decision="allow", by="user", note=answer.get("note"))
        return "allow", "approved by the user", entry
    if answer.get("decision") == "deny":
        note = answer.get("note") or ""
        entry.update(decision="deny", by="user", note=note)
        reason = "The user denied this in the elder's session. Don't retry it unchanged." + (" " + note if note else "")
        return "deny", reason, entry
    entry.update(decision="deny", by="timeout")
    if not answer_file.exists():
        _save(run / "gate", "ans-%s.json" % rid, {"decision": "deny", "time": time.time(), "note": "expired"})
    return "deny", "No answer from the user in time; carry on without it, or ask in `questions`.", entry


def pending(run):
    gate = run / "gate"
    if not gate.exists():
        return []
    out = []
    for req in sorted(gate.glob("req-*.json"), key=lambda p: p.stat().st_mtime):
        if not (gate / req.name.replace("req-", "ans-")).exists():
            out.append(_json_or(req.read_text(encoding="utf-8"), {}))
    return [r for r in out if r]


def waited(run):
    """Seconds the shoggoth spent waiting on the user, so the run timeout doesn't count them."""
    total = 0.0
    for req in (run / "gate").glob("req-*.json") if (run / "gate").exists() else []:
        r = _json_or(req.read_text(encoding="utf-8"), {})
        ans = req.with_name(req.name.replace("req-", "ans-"))
        end = _json_or(ans.read_text(encoding="utf-8"), {}).get("time") if ans.exists() else time.time()
        total += max(0.0, (end or time.time()) - r.get("time", time.time()))
    return total


# ---------------------------------------------------------------- hook files
# agy and Cursor read hooks from a file in the repo. shoggoth installs it after the baseline
# snapshot, shares it between concurrent runs, and the last run out restores what was there.

HOOK_FILES = {"agy": ".agents/hooks.json", "cursor": ".cursor/hooks.json"}


def _gate_command(cli):
    me = str(Path(__file__).resolve())
    if WIN:
        return "%s %s _gate %s" % (_win_word(sys.executable), _win_word(me), cli)
    return "%s %s _gate %s" % (shlex.quote(sys.executable), shlex.quote(me), cli)


def _short_path(path):
    """The 8.3 form of a Windows path (C:\\Users\\JOHNSM~1\\...), or the path itself when it has none."""
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(32768)
        n = ctypes.windll.kernel32.GetShortPathNameW(str(path), buf, len(buf))
        return buf.value if 0 < n < len(buf) else str(path)
    except (AttributeError, OSError):
        return str(path)


def _win_word(path, short=_short_path):
    """A path that cmd, PowerShell, and Git Bash all run as one word: forward slashes, no spaces
    (the 8.3 form), and quotes only when it still needs them."""
    p = short(path).replace("\\", "/")
    return '"%s"' % p if re.search(r"[\s&()\[\]{}^=;!'+,`$%@]", p) else p


def _read_exact(path):
    """A file's text with its bytes kept: CRLF, a BOM, even invalid UTF-8 come back unchanged."""
    return path.read_bytes().decode("utf-8", "surrogateescape")


def _write_exact(path, text):
    path.write_bytes(text.encode("utf-8", "surrogateescape"))


def _hook_entry(cli):
    cmd = _gate_command(cli)
    if cli == "agy":
        return {"shoggoth-gate": {"PreToolUse": [{"matcher": "*", "hooks": [
            {"type": "command", "command": cmd, "timeout": HOOK_TIMEOUT}]}]}}
    hook = {"command": cmd, "timeout": HOOK_TIMEOUT, "failClosed": True}
    return {"version": 1, "hooks": {"beforeShellExecution": [dict(hook)], "beforeMCPExecution": [dict(hook)],
                                    "beforeReadFile": [dict(hook)],
                                    "preToolUse": [dict(hook, matcher="Write|Edit|Delete")]}}


def _is_gate_hook(cli, item):
    return isinstance(item, dict) and ("_gate %s" % cli) in str(item.get("command") or "")


def _has_gate(cli, doc):
    if cli == "agy":
        return "shoggoth-gate" in doc
    return any(_is_gate_hook(cli, h) for items in (doc.get("hooks") or {}).values()
               if isinstance(items, list) for h in items)


def _strip_gate(cli, doc):
    """The hook file's content without shoggoth's entries, for when a lost run left its gate behind."""
    doc = dict(doc)
    if cli == "agy":
        doc.pop("shoggoth-gate", None)
        return doc
    hooks = {}
    for event, items in (doc.get("hooks") or {}).items():
        kept = [h for h in items if not _is_gate_hook(cli, h)] if isinstance(items, list) else items
        if kept or not items:
            hooks[event] = kept
    doc["hooks"] = hooks
    return doc


def _before_gate(cli, path):
    """(text, created_dir): the hook file as it was before shoggoth, i.e. what's on disk minus any gate in it."""
    text = _read_exact(path) if path.exists() else None
    doc = _json_or(text.lstrip("﻿"), None) if text else None
    if text and not isinstance(doc, dict):
        raise RuntimeError("%s isn't a JSON object, so shoggoth won't add its gate to it" % path)
    if not doc or not _has_gate(cli, doc):
        return text, not path.parent.exists()
    rest = _strip_gate(cli, doc)
    if not (rest if cli == "agy" else rest.get("hooks") or set(rest) - {"version", "hooks"}):
        # Nothing but the gate: the file wasn't there before, and nor was the folder if it holds only this.
        return None, not any(p != path for p in path.parent.iterdir())
    return json.dumps(rest, indent=2) + "\n", False


def _merged(cli, original, entry):
    if cli == "agy":
        doc = dict(original or {})
        doc.update(entry)
        return doc
    doc = dict(original or {})
    hooks = dict(doc.get("hooks") or {})
    for event, items in entry["hooks"].items():
        hooks[event] = list(hooks.get(event) or []) + items
    doc.update(version=doc.get("version", 1), hooks=hooks)
    return doc


def _run_active(run_dir):
    r = Path(run_dir)
    if not (r / "meta.json").exists() or (r / "summary.json").exists():
        return False
    return _alive(_load(r, "meta.json").get("worker_pid"))


def _live_runs(base, cli, state, own):
    """Other runs still using this CLI's hook file. The state lists them; if it was lost, the run folders do."""
    if state.get("path"):
        runs = [r for r in state.get("runs", []) if r != own]
    else:
        runs = []
        for d in sorted(base.iterdir()) if base.exists() else []:
            m = _json_or((d / "meta.json").read_text(encoding="utf-8"), {}) if (d / "meta.json").exists() else {}
            if str(d) != own and m.get("gated") and (m.get("shoggoth") or {}).get("cli") == cli:
                runs.append(str(d))
    return [r for r in runs if _run_active(r)]


def install_gate(meta):
    cli, repo = meta["shoggoth"]["cli"], Path(meta["repo"])
    if cli not in HOOK_FILES:
        return
    base = Path(meta["run"]).parent
    state_file, path = base / ("gate-%s.json" % cli), repo / HOOK_FILES[cli]
    with _locked(base / ".hooks.lock"):
        state = _json_or(state_file.read_text(encoding="utf-8"), {}) if state_file.exists() else {}
        live = _live_runs(base, cli, state, meta["run"])
        if not live:
            _restore_gate(state)
            state = {}
        if not state.get("path"):
            backup, created = _before_gate(cli, path)
            state = {"path": str(path), "backup": backup, "created_dir": created}
        state["runs"] = live + [meta["run"]]
        # The state goes first: if it were lost while the gated file stays, the original would be lost with it.
        state_file.write_text(json.dumps(state), encoding="utf-8")
        if not live:
            original = _json_or(state["backup"].lstrip("﻿"), None) if state["backup"] else None
            path.parent.mkdir(parents=True, exist_ok=True)
            _write_exact(path, json.dumps(_merged(cli, original, _hook_entry(cli)), indent=2) + "\n")


def remove_gate(meta):
    cli, repo = meta["shoggoth"]["cli"], Path(meta["repo"])
    if cli not in HOOK_FILES:
        return
    base = Path(meta["run"]).parent
    state_file, path = base / ("gate-%s.json" % cli), repo / HOOK_FILES[cli]
    with _locked(base / ".hooks.lock"):
        state = _json_or(state_file.read_text(encoding="utf-8"), {}) if state_file.exists() else {}
        rest = _live_runs(base, cli, state, meta["run"])
        if not state.get("path"):  # the state was lost: what's on disk, minus the gate, is the original
            try:
                backup, created = _before_gate(cli, path)
            except RuntimeError:
                return  # not JSON any more, so not the file shoggoth wrote: leave it
            state = {"path": str(path), "backup": backup, "created_dir": created}
        if rest:
            state["runs"] = rest
            state_file.write_text(json.dumps(state), encoding="utf-8")
            return
        _restore_gate(state)
        if state_file.exists():
            state_file.unlink()


def _restore_gate(state):
    if not state.get("path"):
        return
    path = Path(state["path"])
    if state.get("backup") is not None:
        _write_exact(path, state["backup"])
    elif path.exists():
        path.unlink()
        if state.get("created_dir"):
            with contextlib.suppress(OSError):
                path.parent.rmdir()


# ---------------------------------------------------------------- adapters
# Each adapter turns one round into an argv (and extra environment), and its CLI's log into
# the same shape: session, ok, error, final text, report, usage, commands, refusals, writes.
# `commands` is None when shoggoth can't see the CLI's shell calls in its log.


TIER_SUFFIXES = ("-low", "-medium", "-high", "-xhigh", "-max")


def _agy(c):
    a = [c.bin, "-p", c.prompt, "--output-format", "stream-json", "--json-schema", str(SCHEMA),
         "--print-timeout", "0", "--mode", "accept-edits"]
    model = c.model
    if model and c.effort:
        # agy rejects a tiered id plus a different --effort ("gemini-4-argon-high" + "low"),
        # so the chosen effort wins and the id goes back to its base name.
        model = next((model[:-len(t)] for t in TIER_SUFFIXES if model.endswith(t)), model)
    if model:
        a += ["--model", model]
    if c.effort:
        a += ["--effort", c.effort]
    if c.session:
        a += ["--conversation", c.session]
    # In "ask" mode agy's own checks are switched off and the PreToolUse gate decides every
    # call: headless agy can't hand a permission prompt to anyone, but its hooks can deny.
    return a + ["--dangerously-skip-permissions"] + c.args


def _codex(c):
    a = [c.bin, "exec", "--json", "--skip-git-repo-check", "-C", c.repo,
         "--output-schema", str(SCHEMA), "-o", str(c.run / "last-message.txt")]
    if c.model:
        a += ["-m", c.model]
    if c.effort:
        a += ["-c", "model_reasoning_effort=%s" % c.effort]
    if c.full:
        a += ["--dangerously-bypass-approvals-and-sandbox"]
    else:
        # Commands run in Codex's sandbox (repo-only writes, no network); anything that wants
        # out of it raises a PermissionRequest, which the gate answers.
        hook = "[{hooks=[{type=\"command\", command=%s, timeout=%d}]}]" % (json.dumps(_gate_command("codex")),
                                                                          HOOK_TIMEOUT)
        a += ["--sandbox", "workspace-write", "-c", "approval_policy=\"on-request\"",
              "-c", "hooks.PermissionRequest=" + hook, "--dangerously-bypass-hook-trust"]
    a += c.args
    if c.session:
        a += ["resume", c.session]
    return a + [c.prompt]


def _cursor(c):
    a = [c.bin, "-p", "--output-format", "stream-json", "--workspace", c.repo, "--trust", "--force"]
    if c.model:
        a += ["--model", c.model]
    if c.session:
        a += ["--resume", c.session]
    return a + c.args + [c.prompt]


def _claude(c):
    a = [c.bin, "-p", c.prompt, "--output-format", "stream-json", "--verbose", "--json-schema", _schema_text()]
    if c.model:
        a += ["--model", c.model]
    if c.effort:
        a += ["--effort", c.effort]
    a += ["--resume", c.session] if c.session else ["--session-id", c.new_session]
    if c.full:
        a += ["--dangerously-skip-permissions"]
    else:
        hooks = {"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [
            {"type": "command", "command": _gate_command("claude"), "timeout": HOOK_TIMEOUT}]}]}}
        a += ["--permission-mode", "acceptEdits", "--settings", json.dumps(hooks)]
    return a + c.args


def _grok(c):
    a = [c.bin, "--prompt-file", str(c.prompt_file), "--json-schema", _schema_text(), "--cwd", c.repo]
    if c.model:
        a += ["-m", c.model]
    if c.effort:
        a += ["--reasoning-effort", c.effort]
    a += ["-r", c.session] if c.session else ["-s", c.new_session]
    return a + ["--always-approve"] + c.args


def _parsed():
    return {"session": None, "ok": None, "error": None, "text": "", "report": None, "usage": None,
            "commands": [], "refused": [], "gated": [], "touched": [], "tools": {}}


def _events(text):
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                yield json.loads(line)
            except ValueError:
                continue


def _count(p, name):
    p["tools"][name] = p["tools"].get(name, 0) + 1


def _cmd(cmd, code, error, output, ident=None):
    return {"cmd": cmd or "", "exit": code, "error": error or None, "tail": _tail(output), "id": ident}


def _exit_from(text):
    for line in [r for r in (text or "").splitlines() if r.strip()][:EXIT_LINES]:
        m = EXIT_RE.match(line)
        if m:
            return int(m.group(1))
    return None


def _usage(u, inp, out, cached):
    if not isinstance(u, dict):
        return None
    return {"input": u.get(inp), "output": u.get(out), "cached": u.get(cached)}


GATE_REASONS = ("denied by pre-tool hook", "blocked by hook", "the gate refused", "the user denied this",
                "gate error", "no answer from the user")


def _hook_denial(msg):
    m = (msg or "").lower()
    return any(s in m for s in GATE_REASONS)


def _refusal(msg):
    m = (msg or "").lower()
    return "permission" in m and any(w in m for w in ("denied", "check failed", "not granted", "rejected"))


def _parse_agy(out, run):
    p = _parsed()
    for e in _events(out):
        kind = e.get("event")
        if kind == "init":
            p["session"] = e.get("conversation_id") or p["session"]
        elif kind == "step_update":
            s = e.get("step_update") or {}
            p["session"] = p["session"] or s.get("conversation_id")
            if s.get("step_type") != "tool" or s.get("state") not in ("DONE", "ERROR"):
                continue
            info = s.get("tool_info") or {}
            name = s.get("tool_name") or info.get("name") or "?"
            params = info.get("parameters") or {}
            err = (info.get("error") or {}).get("message") or ""
            output = info.get("output") or ""
            label = params.get("CommandLine") or "%s %s" % (name, _first_value(params))
            _count(p, name)
            if _hook_denial(err):
                p["gated"].append(label)
            elif _refusal(err):
                p["refused"].append(label)
            elif name == "run_command":
                code = _exit_from(output)
                p["commands"].append(_cmd(params.get("CommandLine"), _exit_from(err) if code is None else code, err,
                                          output or err))
            elif name == "command_status":
                # A long command finishes asynchronously; its exit shows up here.
                code = _exit_from(output)
                waiting = [c for c in p["commands"] if c["exit"] is None and not c["error"]]
                if waiting and code is not None:
                    waiting[-1].update(exit=code, tail=_tail(output))
            elif any(w in name for w in WRITE_WORDS):
                p["touched"] += _paths_in(params)
        elif kind == "result":
            r = e.get("result") or {}
            p["session"] = r.get("conversation_id") or p["session"]
            p["ok"] = r.get("status") == "SUCCESS"
            p["error"] = r.get("error") or (None if p["ok"] else r.get("status"))
            p["text"] = r.get("response") or ""
            p["report"] = r.get("structured_output")
            p["usage"] = _usage(r.get("usage"), "input_tokens", "output_tokens", "cache_read_tokens")
            if not p["refused"]:
                p["refused"] = ["%s (no detail in the log)" % d.get("action", "?")
                                for d in r.get("denied_actions") or []]
    return p


def _parse_codex(out, run):
    p = _parsed()
    for e in _events(out):
        t = e.get("type")
        if t == "thread.started":
            p["session"] = e.get("thread_id") or p["session"]
        elif t == "item.completed":
            it = e.get("item") or {}
            k = it.get("type") or "?"
            _count(p, k)
            if k == "command_execution":
                status = it.get("status")
                p["commands"].append(_cmd(it.get("command"), it.get("exit_code"),
                                          None if status in (None, "completed") else status,
                                          it.get("aggregated_output") or it.get("output") or ""))
            elif k == "file_change":
                p["touched"] += [ch.get("path") for ch in it.get("changes") or [] if ch.get("path")]
            elif k == "agent_message":
                p["text"] = it.get("text") or p["text"]
            elif k == "error":
                p["error"] = it.get("message") or p["error"]
        elif t == "turn.completed":
            p["ok"] = True
            p["usage"] = _usage(e.get("usage"), "input_tokens", "output_tokens", "cached_input_tokens")
        elif t == "turn.failed":
            p["ok"] = False
            p["error"] = (e.get("error") or {}).get("message") or "turn failed"
        elif t == "error":
            p["error"] = e.get("message") or p["error"]
    last = run / "last-message.txt"
    if last.exists():
        p["text"] = last.read_text(encoding="utf-8", errors="replace") or p["text"]
    return p


def _parse_cursor(out, run):
    p = _parsed()
    for e in _events(out):
        t = e.get("type")
        p["session"] = e.get("session_id") or p["session"]
        if t == "assistant":
            parts = [b.get("text", "") for b in (e.get("message") or {}).get("content") or []
                     if isinstance(b, dict) and b.get("type") == "text"]
            if parts:
                p["text"] = "".join(parts)
        elif t == "tool_call" and e.get("subtype") == "completed":
            for kind, body in (e.get("tool_call") or {}).items():
                if not isinstance(body, dict):
                    continue
                args = body.get("args") or {}
                if kind == "function":
                    args = _json_or(body.get("arguments"), {})
                _count(p, body.get("name") if kind == "function" else kind)
                res = body.get("result") if isinstance(body.get("result"), dict) else {}
                good = res.get("success")
                bad = res.get("failure") or res.get("error") or res.get("rejected") or res.get("permissionDenied")
                cmd = args.get("command") or args.get("cmd")
                if cmd:
                    if res.get("rejected") or res.get("permissionDenied"):
                        p["gated"].append(cmd)
                        continue
                    data = good if isinstance(good, dict) else bad if isinstance(bad, dict) else {}
                    code = data.get("exitCode", data.get("exit_code"))
                    text = "\n".join(str(data.get(k) or "") for k in ("stdout", "stderr", "output", "message"))
                    p["commands"].append(_cmd(cmd, code, None if good is not None else (bad and str(bad)), text))
                path = args.get("path") or args.get("file_path") or args.get("filePath")
                if path and "read" not in kind.lower():
                    p["touched"].append(path)
        elif t == "result":
            p["ok"] = e.get("subtype") == "success" and not e.get("is_error")
            if not p["ok"]:
                p["error"] = e.get("result") or e.get("subtype") or "error"
            p["text"] = p["text"] or e.get("result") or ""
    return p


def _parse_claude(out, run):
    p = _parsed()
    pending_calls = {}
    for e in _events(out):
        t = e.get("type")
        p["session"] = e.get("session_id") or p["session"]
        if e.get("parent_tool_use_id"):
            continue  # a subagent's turn; its parent call is already counted
        if t == "assistant":
            for b in (e.get("message") or {}).get("content") or []:
                if b.get("type") == "tool_use":
                    name, inp = b.get("name") or "?", b.get("input") or {}
                    pending_calls[b.get("id")] = (name, inp)
                    _count(p, name)
                    if name in CLAUDE_WRITES and inp.get("file_path"):
                        p["touched"].append(inp["file_path"])
                elif b.get("type") == "text":
                    p["text"] = b.get("text") or p["text"]
        elif t == "user":
            content = (e.get("message") or {}).get("content")
            for b in content if isinstance(content, list) else []:
                if not isinstance(b, dict) or b.get("type") != "tool_result":
                    continue
                name, inp = pending_calls.pop(b.get("tool_use_id"), (None, {}))
                if name != "Bash":
                    continue
                body = b.get("content")
                text = body if isinstance(body, str) else "\n".join(
                    x.get("text", "") for x in body or [] if isinstance(x, dict))
                if b.get("is_error") and _hook_denial(text):
                    p["gated"].append(inp.get("command") or "")
                    continue
                failed = bool(b.get("is_error"))
                code = _exit_from(text) if failed else 0
                p["commands"].append(_cmd(inp.get("command"), code, text if failed and code is None else None,
                                          text, b.get("tool_use_id")))
        elif t == "result":
            p["ok"] = e.get("subtype") == "success" and not e.get("is_error")
            if not p["ok"]:
                p["error"] = e.get("result") or e.get("subtype") or "error"
            p["text"] = e.get("result") or p["text"]
            p["report"] = e.get("structured_output")
            p["usage"] = _usage(e.get("usage"), "input_tokens", "output_tokens", "cache_read_input_tokens")
            refused = {d.get("tool_use_id") for d in e.get("permission_denials") or []}
            for d in e.get("permission_denials") or []:
                p["refused"].append((d.get("tool_input") or {}).get("command") or d.get("tool_name") or "?")
            p["commands"] = [c for c in p["commands"] if c["id"] not in refused]
    return p


def _parse_grok(out, run):
    p = _parsed()
    p["commands"] = None  # grok's log isn't mapped yet, so its shell calls can't be checked
    try:
        doc = json.loads(out)
    except ValueError:
        docs = list(_events(out))
        doc = docs[-1] if docs else None
    if isinstance(doc, dict):
        p["session"] = doc.get("session_id") or doc.get("sessionId")
        p["report"] = doc.get("structured_output") or doc.get("structuredOutput") or (
            doc if "status" in doc and "checks" in doc else None)
        for key in ("result", "response", "text", "content", "message"):
            if isinstance(doc.get(key), str):
                p["text"] = doc[key]
                break
        p["ok"] = not doc.get("is_error") and not doc.get("error")
        p["error"] = doc.get("error") if isinstance(doc.get("error"), str) else None
    else:
        p["text"] = out
    return p


ADAPTERS = {
    "agy": {"bins": ["agy"], "argv": _agy, "parse": _parse_agy, "native": True, "preset_session": False,
            "gate": "hook file", "checked": "run against agy 1.4.3 on 2026-10-20, gate included"},
    "codex": {"bins": ["codex"], "argv": _codex, "parse": _parse_codex, "native": True, "preset_session": False,
              "gate": "sandbox + PermissionRequest hook",
              "checked": "built from the codex exec and hooks docs (2026-10); not run here"},
    # Newer Cursor installs call the binary `agent`, a name other CLIs use too (Grok Build ships
    # one), so shoggoth only looks for `cursor-agent`; a config entry can set "bin" to Cursor's `agent`.
    "cursor": {"bins": ["cursor-agent"], "argv": _cursor, "parse": _parse_cursor, "native": False,
               "preset_session": False, "gate": "hook file",
               "checked": "built from the Cursor CLI and hooks docs (2026-10); not run here"},
    "claude": {"bins": ["claude"], "argv": _claude, "parse": _parse_claude, "native": True, "preset_session": True,
               "gate": "PreToolUse hook via --settings",
               "checked": "built from the Claude Code CLI and hooks docs (2026-10); not run here"},
    "grok": {"bins": ["grok"], "argv": _grok, "parse": _parse_grok, "native": True, "preset_session": True,
             "gate": None, "checked": "flags from grok 1.0.62 --help; not run here; no gate yet"},
}


# ---------------------------------------------------------------- helpers


def _first_value(d):
    for v in (d or {}).values():
        if isinstance(v, str):
            return v
    return ""


def _json_or(text, default):
    try:
        v = json.loads(text) if isinstance(text, str) else text
    except ValueError:
        return default
    return v if isinstance(v, (dict, list)) else default


def _tail(text, lines=3, width=160):
    rows = [r.rstrip() for r in (text or "").replace("\r", "").splitlines() if r.strip()]
    return " | ".join(r[:width] for r in rows[-lines:])


def _one(text, width=200):
    flat = " ".join(str(text or "").split())
    return flat if len(flat) <= width else flat[:width - 1] + "…"


def _dur(secs):
    secs = int(secs or 0)
    return "%dm%02ds" % (secs // 60, secs % 60) if secs >= 60 else "%ds" % secs


def _schema_text():
    return json.dumps(json.loads(SCHEMA.read_text(encoding="utf-8")), separators=(",", ":"))


def _seconds(text):
    m = re.fullmatch(r"\s*(\d+)\s*([smh]?)\s*", text or "")
    if not m:
        raise argparse.ArgumentTypeError("use a duration like 900s, 45m, or 2h")
    return int(m.group(1)) * {"": 1, "s": 1, "m": 60, "h": 3600}[m.group(2)]


def _decode(raw):
    """Text from bytes another program wrote: UTF-8 (BOM or not), UTF-16 with a BOM (PowerShell's
    Out-File), else the system's code page."""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        import locale
        return raw.decode(locale.getpreferredencoding(False) or "utf-8", "replace")


def _replace(tmp, target):
    """os.replace, which on Windows fails while another process has the target open: retry briefly."""
    for attempt in range(50):
        try:
            tmp.replace(target)
            return
        except PermissionError:
            if not WIN or attempt == 49:
                raise
            time.sleep(0.05)


def _save(directory, name, data):
    directory.mkdir(parents=True, exist_ok=True)
    tmp = directory / (name + ".%s.tmp" % uuid.uuid4().hex[:6])
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    _replace(tmp, directory / name)


def _load(run, name):
    return json.loads((run / name).read_text(encoding="utf-8"))


def _alive(pid):
    if not pid:
        return False
    if WIN:  # os.kill(pid, 0) would send Ctrl-C there: ask the kernel instead
        import ctypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() == 5  # access denied: it exists, it just isn't ours
        try:
            code = ctypes.c_ulong()
            return not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259  # STILL_ACTIVE
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _report_from_text(text):
    text = (text or "")[-60000:]
    for block in reversed(re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)):
        doc = _json_or(block, None)
        if isinstance(doc, dict) and "status" in doc:
            return doc
    dec = json.JSONDecoder()
    for m in reversed(list(re.finditer(r"\{", text))):
        try:
            doc, _ = dec.raw_decode(text[m.start():])
        except ValueError:
            continue
        if isinstance(doc, dict) and "status" in doc:
            return doc
    return None


def _normal_report(r):
    if not isinstance(r, dict):
        return None
    out = dict(r)
    out["status"] = str(out.get("status") or "?")
    out["summary"] = str(out.get("summary") or "")
    for key in REPORT_LISTS:
        v = out.get(key)
        out[key] = v if isinstance(v, list) else ([] if v in (None, "") else [v])
    out["checks"] = [c for c in out["checks"] if isinstance(c, dict)]
    return out


# ---------------------------------------------------------------- git truth


def _git(repo, *args, env=None):
    r = subprocess.run(["git", *args], cwd=str(repo), env=env, capture_output=True, encoding="utf-8",
                       errors="replace")
    if r.returncode:
        raise RuntimeError((r.stderr or "").strip() or "git %s failed" % args[0])
    return r.stdout


def repo_root(cwd):
    try:
        return Path(_git(cwd, "rev-parse", "--show-toplevel").strip())
    except (RuntimeError, OSError):
        return None


def snapshot(repo):
    """Tree id of the whole working tree, untracked files included. Leaves the real index alone."""
    index = Path(_git(repo, "rev-parse", "--git-path", "index").strip())
    if not index.is_absolute():
        index = repo / index
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / "index"
        if index.exists():
            shutil.copy2(index, tmp)  # keeps git's stat cache, so only changed files get hashed
        env = dict(os.environ, GIT_INDEX_FILE=str(tmp))
        _git(repo, "add", "-A", "--", ".", env=env)
        return _git(repo, "write-tree", env=env).strip()


def tree_diff(repo, a, b):
    parts = _git(repo, "diff", "--name-status", "--no-renames", "-z", a, b).split("\0")
    items = [(parts[i][:1], parts[i + 1]) for i in range(0, len(parts) - 1, 2) if parts[i]]
    return items, _git(repo, "diff", "--shortstat", a, b).strip()


def in_scope(path, globs):
    for g in globs:
        g = g.strip().replace("\\", "/") if WIN else g.strip()  # git paths use forward slashes
        while g.startswith("./"):
            g = g[2:]
        if not g:
            continue
        if g.endswith("/"):
            g += "**"
        if fnmatch.fnmatchcase(path, g):
            return True
        if not any(ch in g for ch in "*?[") and path.startswith(g.rstrip("/") + "/"):
            return True
    return False


# ---------------------------------------------------------------- config


def load_config():
    if not CONFIG.exists():
        return {}
    try:
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    except ValueError as e:
        die("%s is not valid JSON: %s" % (CONFIG, e))
    if not isinstance(cfg, dict):
        die("%s must hold a JSON object" % CONFIG)
    return cfg


def _spec(value, name):
    if isinstance(value, str):
        cli, _, model = value.partition(":")
        sk = {"cli": cli.strip(), "model": model.strip() or None}
    elif isinstance(value, dict):
        sk = dict(value)
    else:
        die("%r: a shoggoth is \"cli:model\" or an object with \"cli\"" % name)
    if sk.get("cli") not in ADAPTERS:
        die("%r: the shoggoth CLI must be one of %s" % (name, ", ".join(ADAPTERS)))
    sk["name"] = name
    sk.setdefault("permissions", "ask")
    if sk["permissions"] not in ("ask", "full"):
        die("%r: permissions must be \"ask\" or \"full\"" % name)
    sk.setdefault("style", "lean")
    return sk


def resolve(spec, elder):
    if spec:
        return _spec(spec, spec)
    cfg = load_config()
    for key in ([elder] if elder else []) + ["default"]:
        if cfg.get(key):
            return _spec(cfg[key], key)
    found = [cli for cli in ADAPTERS if find_bin({"cli": cli})]
    die("no shoggoth set for elder %r yet. Ask the user which one to use (this skill's references/setup.md), "
        "save it with `shoggoth.py config set --elder %s --cli CLI --model MODEL --effort EFFORT`, then run again. "
        "Shoggoth CLIs on this machine: %s" % (elder or "?", elder or "ELDER", ", ".join(found) or "none"))


# ---------------------------------------------------------------- setup: models and config
# Suggested shoggoth settings (as of 2026-10) and how to ask each CLI what it offers right now.
# The elder builds its setup questions from `shoggoth.py models CLI`; the user can always type their own.

CATALOG = {
    "agy": {"list": ["models"], "model": "gemini-4-argon", "effort": "medium", "efforts": ["low", "medium", "high"],
            "why": "a strong coder; medium effort keeps a busy shoggoth affordable"},
    "codex": {"list": None, "models": ["gpt-6.1-sol"], "model": "gpt-6.1-sol", "effort": "medium",
              "efforts": ["low", "medium", "high", "xhigh"], "why": "the model the Codex docs feature"},
    "claude": {"list": None, "models": ["sonnet", "opus", "haiku", "fable"], "model": "sonnet", "effort": "medium",
               "efforts": ["low", "medium", "high", "xhigh", "max"], "why": "Sonnet 5.5 codes well for less than Opus"},
    "cursor": {"list": ["--list-models"], "models": [], "model": None, "effort": None, "efforts": [],
               "why": "Cursor sets reasoning through the model id, so pick one from its list"},
    "grok": {"list": ["models"], "models": [], "model": "grok-4.7", "effort": "medium",
             "efforts": ["low", "medium", "high"], "why": "Grok Build's default model"},
}


MODELS_TTL = 900  # seconds a model list stays fresh for `config set`


def _live_models(cli, binary, cached=False):
    """[(model, [efforts])] from the CLI itself, or None when it can't list them. `cached` reuses a list
    fetched in the last MODELS_TTL seconds: asking agy takes seconds, and setup asks right before saving."""
    spec = CATALOG[cli]
    if not spec["list"] or not binary:
        return None
    cache = HOME / ("models-%s.json" % cli)
    if cached and cache.exists():
        c = _json_or(cache.read_text(encoding="utf-8"), {})
        if c.get("bin") == binary and time.time() - c.get("time", 0) < MODELS_TTL and c.get("models"):
            return [(m, list(e)) for m, e in c["models"]]
    try:
        r = subprocess.run([binary] + spec["list"], capture_output=True, encoding="utf-8", errors="replace",
                           timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    found = _models_from(cli, r.stdout + "\n" + r.stderr)
    if found:
        with contextlib.suppress(OSError):
            _save(HOME, cache.name, {"bin": binary, "time": time.time(), "models": found})
    return found


def _models_from(cli, text):
    spec = CATALOG[cli]
    models = {}
    if cli == "agy":
        for line in text.splitlines():
            ident = line.split("\t")[0].strip()
            if not re.fullmatch(r"[a-z0-9][a-z0-9._-]+", ident):
                continue
            base = next((ident[:-len(t)] for t in TIER_SUFFIXES if ident.endswith(t)), ident)
            tier = ident[len(base) + 1:] if base != ident else None
            models.setdefault(base, [])
            if tier:
                models[base].append(tier)
    elif cli == "grok":
        for m in re.finditer(r"^\s*[*-]\s+([A-Za-z0-9._-]+)", text, re.M):
            models.setdefault(m.group(1), list(spec["efforts"]))
    else:
        for line in text.splitlines():
            m = re.match(r"^\s*[*-]?\s*([A-Za-z0-9][A-Za-z0-9._/-]+)\b", line)
            if m and not line.strip().endswith(":"):
                models.setdefault(m.group(1), [])
    order = ["low", "medium", "high", "xhigh", "max"]
    return [(k, sorted(set(v), key=lambda e: order.index(e) if e in order else 9)) for k, v in models.items()] or None


def cmd_models(a):
    cli = a.cli
    spec, binary = CATALOG[cli], find_bin({"cli": cli})
    built_in = spec.get("models", [])
    rec = "%s%s" % (spec["model"] or "(pick from the list)", " · effort %s" % spec["effort"] if spec["effort"] else "")
    print("%s · %s · recommended: %s (%s)" % (cli, binary or "NOT INSTALLED", rec, spec["why"]))
    live = _live_models(cli, binary)
    if live:
        print("models (from `%s %s`):" % (cli, " ".join(spec["list"])))
        for model, efforts in live[:30]:
            print("  %-28s %s" % (model, "efforts: " + ", ".join(efforts) if efforts else ""))
    elif built_in:
        print("models (the built-in list; the CLI may offer more): " + ", ".join(built_in))
    else:
        print("models: this CLI didn't list any; type the id")
    if spec["efforts"]:
        print("efforts: " + ", ".join(spec["efforts"]))
    else:
        print("efforts: none (the model id sets it)")
    gate = ADAPTERS[cli]["gate"]
    print("approvals: %s" % ("come back to the elder (%s)" % gate if gate else
                             "no gate yet: this CLI runs with full permissions, so confirm that with the user first"))


def _write_config(cfg):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG.with_name(CONFIG.name + ".tmp")
    tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _replace(tmp, CONFIG)


def cmd_config(a):
    cfg = load_config()
    if a.action == "show":
        print("config: %s%s" % (CONFIG, "" if CONFIG.exists() else " (not created yet)"))
        for key, value in cfg.items():
            if key.startswith("_"):
                continue
            sk = _spec(value, key)
            print("  %-8s -> %s %s%s · permissions %s · style %s%s%s" % (
                key, sk["cli"], sk.get("model") or "(CLI default model)",
                " · effort %s" % sk["effort"] if sk.get("effort") else "", sk["permissions"], sk["style"],
                " · bin %s" % sk["bin"] if sk.get("bin") else "",
                " · args %s" % " ".join(shlex.quote(str(x)) for x in sk["args"]) if sk.get("args") else ""))
        return
    if not a.elder:
        die("config %s needs --elder (the agent shoggoth runs in: claude, codex, cursor, agy, grok)" % a.action)
    if a.action == "unset":
        if cfg.pop(a.elder, None) is None:
            die("no entry for elder %r" % a.elder)
        _write_config(cfg)
        print("shoggoth: removed the shoggoth for elder %s" % a.elder)
        return
    # set merges into the elder's entry: only the flags given change. A new --cli starts a fresh entry.
    old = cfg.get(a.elder)
    if isinstance(old, str):
        cli, _, model = old.partition(":")
        old = {"cli": cli.strip(), "model": model.strip() or None}
    old = {k: v for k, v in old.items() if v is not None} if isinstance(old, dict) else {}
    cli = a.cli or old.get("cli")
    if not cli or cli not in ADAPTERS:
        die("config set needs --cli, one of %s" % ", ".join(ADAPTERS))
    entry = old if old.get("cli") == cli else {"cli": cli}
    for key in ("model", "effort", "bin"):
        value = getattr(a, key)
        if value is not None:  # an empty value clears the key, e.g. --model "" for the CLI's default
            if value.strip():
                entry[key] = value.strip()
            else:
                entry.pop(key, None)
    model, effort = entry.get("model"), entry.get("effort")
    if cli == "agy" and model and effort:
        entry["model"] = model = next((model[:-len(t)] for t in TIER_SUFFIXES if model.endswith(t)), model)
    if cli == "cursor" and effort:
        print("shoggoth: Cursor has no effort flag, so the effort is dropped; pick a model id that carries it")
        entry.pop("effort")
    if model and a.model:
        live = _live_models(cli, find_bin({"cli": cli}), cached=True)
        if live and model not in {m for m, _ in live}:
            print("shoggoth: note: %s isn't in `%s %s`; saved anyway" % (model, cli, " ".join(CATALOG[cli]["list"])))
    if a.permissions:
        entry["permissions"] = a.permissions
    if entry.get("permissions", "ask") == "ask":
        entry.pop("permissions", None)
        if not ADAPTERS[cli]["gate"]:
            die("%s has no approval gate yet. Ask the user whether it may run with full permissions; "
                "if yes, run this again with --permissions full" % cli)
    if a.style:
        entry["style"] = a.style
    if entry.get("style") == "lean":
        entry.pop("style")
    cfg[a.elder] = entry
    _write_config(cfg)
    sk = _spec(entry, a.elder)
    print("shoggoth: elder %s -> shoggoth %s %s%s · permissions %s (saved to %s)" % (
        a.elder, sk["cli"], sk.get("model") or "(CLI default model)",
        " · effort %s" % sk["effort"] if sk.get("effort") else "", sk["permissions"], CONFIG))


def find_bin(sk):
    tried = [sk["bin"]] if sk.get("bin") else ADAPTERS[sk["cli"]]["bins"]
    for b in tried:
        path = shutil.which(os.path.expanduser(b))
        if path:
            return path
    return None


# ---------------------------------------------------------------- runs


def runs_base(work_dir):
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", work_dir.name) or "repo"
    # normcase: on Windows C:\Repo and c:\repo are one checkout (and one writer lock).
    return HOME / ("%s-%s" % (slug, hashlib.sha1(os.path.normcase(str(work_dir)).encode()).hexdigest()[:6]))


def new_run(base):
    base.mkdir(parents=True, exist_ok=True)
    numbers = [int(m.group(1)) for d in base.iterdir() for m in [re.match(r"(\d+)-", d.name)] if m]
    run = base / ("%02d-%s" % (max(numbers or [0]) + 1, dt.datetime.now().strftime("%y%m%d-%H%M%S")))
    run.mkdir()
    return run


def find_run(arg):
    p = Path(arg).expanduser()
    if p.is_dir() and (p / "meta.json").exists():
        return p.resolve()
    if re.fullmatch(r"\d+(-[\w.-]+)?", arg):  # a run number ("3") or a run name ("03-261020-101010")
        cwd = Path.cwd()
        base = runs_base(repo_root(cwd) or cwd)
        if "-" in arg:
            hits = [base / arg] if (base / arg / "meta.json").exists() else []
        else:
            hits = sorted(base.glob("%02d-*" % int(arg))) if base.exists() else []
        if hits:
            return hits[-1]
    die("no run %r (pass a run directory, or a run number or name from this checkout)" % arg)


def check_writer(base):
    lock = base / "writer.json"
    if not lock.exists():
        return
    held = _json_or(lock.read_text(encoding="utf-8"), {})
    other = Path(held.get("run") or "/nonexistent")
    if _run_active(other):
        die("a writing shoggoth is already running in this checkout (%s). Wait for it, "
            "stop it with `shoggoth.py stop %s`, or make this one a --scout." % (other.name, other))


def prepare(a):
    cwd = Path(a.cwd).expanduser().resolve()
    repo = repo_root(cwd)
    work_dir = repo or cwd
    if (a.scope or a.scout) and not repo:
        die("--scope and --scout need a git repository")
    sk = resolve(a.shoggoth, a.elder)
    if a.permissions:
        sk["permissions"] = a.permissions
    ad = ADAPTERS[sk["cli"]]
    if sk["permissions"] == "ask" and not ad["gate"]:
        die("%s has no approval gate in shoggoth yet, so it can't run in \"ask\" mode. Use a shoggoth that has "
            "one, or run this one with \"permissions\": \"full\" if the user agrees." % sk["cli"])
    binary = find_bin(sk)
    if not binary:
        die("%s isn't on PATH (tried %s)" % (sk["cli"], ", ".join([sk["bin"]] if sk.get("bin") else ad["bins"])))
    try:
        brief = _decode(sys.stdin.buffer.read() if a.brief == "-" else Path(a.brief).expanduser().read_bytes())
    except OSError as e:
        die("can't read the brief: %s" % e)
    if not brief.strip():
        die("the brief is empty")
    base = runs_base(work_dir)
    if not a.scout:
        check_writer(base)
    run = new_run(base)
    parts = [CONTRACT.read_text(encoding="utf-8").replace("{repo}", str(work_dir)).strip()
             if not a.session else NEXT_ROUND]
    if a.scout:
        parts.append(SCOUT_RULE)
    parts.append("BRIEF\n\n" + brief.strip())
    parts.append(REPORT_NATIVE if ad["native"] else REPORT_TEXT % json.dumps(REPORT_EXAMPLE, indent=1))
    prompt = "\n\n".join(parts) + "\n"
    (run / "brief.md").write_text(brief, encoding="utf-8")
    (run / "prompt.md").write_text(prompt, encoding="utf-8")
    new_session = str(uuid.uuid4()) if ad["preset_session"] and not a.session else None
    ctx = SimpleNamespace(bin=binary, prompt=prompt, prompt_file=run / "prompt.md", model=sk.get("model"),
                          effort=sk.get("effort"), session=a.session, new_session=new_session,
                          full=sk["permissions"] == "full", timeout=a.timeout, repo=str(work_dir), run=run,
                          args=[str(x) for x in sk.get("args") or []])
    try:
        baseline = snapshot(repo) if repo else None
    except RuntimeError as e:
        shutil.rmtree(run, ignore_errors=True)
        die("can't snapshot the working tree: %s" % e)
    approvals = list(a.allow or [])
    if a.session and (base / "approvals" / ("%s.json" % a.session)).exists():
        approvals += [x for x in _json_or((base / "approvals" / ("%s.json" % a.session)).read_text(
            encoding="utf-8"), []) if x not in approvals]
    if sk["permissions"] == "ask":
        _save(run / "gate", "approved.json", approvals)
        # The elder's own permission settings, read once per run: the gate applies them to every call.
        policy = elder_policy(a.elder, work_dir)
        if policy:
            _save(run / "gate", "policy.json", policy)
    meta = {"run": str(run), "repo": str(work_dir), "git": bool(repo), "shoggoth": sk, "bin": binary,
            "argv": ad["argv"](ctx), "session_in": a.session, "new_session": new_session, "elder": a.elder,
            "scope": a.scope or [], "scout": bool(a.scout), "timeout": a.timeout, "started": time.time(),
            "baseline": baseline, "gated": sk["permissions"] == "ask"}
    _save(run, "meta.json", meta)
    if not a.scout:
        (base / "writer.json").write_text(json.dumps({"run": str(run)}), encoding="utf-8")
    return run


def _kill_group(pid, hard=False):
    """Stop a process and everything it started."""
    if WIN:  # no process groups or SIGKILL: taskkill takes the tree, and console programs need /F
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        return
    try:
        os.killpg(pid, signal.SIGKILL if hard else signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass


# Windows process flags: its own process group (no stray Ctrl-C), no console window, and out of
# the caller's job, so the worker outlives the elder's command the way a new session does on POSIX.
CREATE_NEW_PROCESS_GROUP, CREATE_NO_WINDOW, CREATE_BREAKAWAY_FROM_JOB = 0x200, 0x08000000, 0x01000000


def _popen(argv, worker=False, **kw):
    if not WIN:
        return subprocess.Popen(argv, start_new_session=True, **kw)
    flags = CREATE_NEW_PROCESS_GROUP | (CREATE_NO_WINDOW if worker else 0)
    if worker:
        try:
            return subprocess.Popen(argv, creationflags=flags | CREATE_BREAKAWAY_FROM_JOB, **kw)
        except OSError:  # the job doesn't allow breakaway: start inside it
            pass
    return subprocess.Popen(argv, creationflags=flags, **kw)


def _win_argv(argv, win=WIN):
    """npm installs a CLI on Windows as a .cmd shim, and cmd.exe cuts an argument at its first newline,
    which would cut the brief. Run the shim's node script directly instead."""
    exe = argv[0]
    if not win or not exe.lower().endswith((".cmd", ".bat")):
        return argv
    try:
        text = Path(exe).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    # npm writes "%dp0%\node_modules\pkg\bin\cli.js", pnpm "%~dp0\..\pkg\bin\cli.js".
    m = re.search(r'"%(?:~dp0|dp0%)\\?([^"%]+\.[cm]?js)"', text)
    here = Path(exe).parent
    script = here / m.group(1).replace("\\", "/") if m else None
    if script and script.exists():
        node = here / "node.exe"
        node = str(node) if node.exists() else shutil.which("node")
        if node:
            return [node, str(script)] + list(argv[1:])
    raise RuntimeError("%s is a batch file, which can't pass a multi-line brief; set the CLI's .exe with "
                       "`shog config set --elder ELDER --bin PATH`" % exe)


def _tool_finished(cli, events_path):
    """Has the shoggoth's log recorded a finished tool call yet? (Used to prove the gate is live.)"""
    try:
        text = events_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    for e in _events(text):
        if cli == "agy" and e.get("event") == "step_update":
            s = e.get("step_update") or {}
            if s.get("step_type") == "tool" and s.get("state") in ("DONE", "ERROR"):
                return True
        elif cli == "cursor" and e.get("type") == "tool_call" and e.get("subtype") == "completed":
            return True
        elif cli == "claude" and e.get("type") == "user":
            content = (e.get("message") or {}).get("content")
            if isinstance(content, list) and any(isinstance(b, dict) and b.get("type") == "tool_result"
                                                 for b in content):
                return True
    return False


def work(run):
    meta = _load(run, "meta.json")
    meta["worker_pid"] = os.getpid()
    _save(run, "meta.json", meta)
    code, why, gate_installed = None, None, False
    env = dict(os.environ, SHOGGOTH_RUN=str(run))
    try:
        if (run / "stopped").exists():
            raise InterruptedError  # stopped before the shoggoth started
        if meta.get("gated"):
            install_gate(meta)
            gate_installed = True
        with open(run / "events.ndjson", "wb") as out, open(run / "stderr.txt", "wb") as err:
            proc = _popen(_win_argv(meta["argv"]), cwd=meta["repo"], stdin=subprocess.DEVNULL, stdout=out,
                          stderr=err, env=env)
            meta["child_pid"] = proc.pid
            _save(run, "meta.json", meta)
            # Every tool call passes the gate first, so a finished call with no gate record means
            # the CLI never loaded the gate. Stop the run before it acts unchecked.
            canary = meta.get("gated") and meta["shoggoth"]["cli"] in ("agy", "cursor", "claude")
            while code is None and not why:
                try:
                    code = proc.wait(timeout=0.25 if canary else 1)
                except subprocess.TimeoutExpired:
                    if canary and _tool_finished(meta["shoggoth"]["cli"], run / "events.ndjson"):
                        if _gate_entries(run):
                            canary = False
                        else:
                            why = "the gate never saw a tool call, so the CLI didn't load it; stopped the run"
                    busy = time.time() - meta["started"] - waited(run)  # time spent waiting on the user is free
                    if busy > meta["timeout"] + GRACE:
                        why = "timed out after %s of work" % _dur(meta["timeout"])
                except KeyboardInterrupt:
                    why = "interrupted"
            if why:
                _kill_group(proc.pid)
                try:
                    code = proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    _kill_group(proc.pid, hard=True)
                    code = proc.wait()
    except InterruptedError:
        pass
    except (OSError, RuntimeError) as e:
        why = "could not start %s: %s" % (meta["bin"], e)
    finally:
        if gate_installed:
            remove_gate(meta)
    if (run / "stopped").exists():
        why = "stopped by the elder"
    for req in pending(run):  # nobody will answer these now
        _save(run / "gate", "ans-%s.json" % req["id"], {"decision": "deny", "time": time.time(), "note": "run ended"})
    summary = summarize(run, meta, code, why)
    _save(run, "summary.json", summary)
    (run / "summary.txt").write_text(render(summary), encoding="utf-8")
    base = Path(meta["run"]).parent
    session = summary.get("session")
    if meta.get("gated") and session:
        _save(base / "approvals", "%s.json" % session, _approvals(run))
    lock = base / "writer.json"
    if lock.exists() and _json_or(lock.read_text(encoding="utf-8"), {}).get("run") == meta["run"]:
        lock.unlink()
    return summary


# ---------------------------------------------------------------- summary


def _norm_cmd(cmd):
    return " ".join(str(cmd or "").replace('"', " ").replace("'", " ").split())


def _unwrap(cmd, win=WIN):
    """The command inside a shell wrapper, which Codex logs around each one: `bash -lc '...'`, `sh -c`,
    `zsh -lc`, and on Windows `powershell -NoProfile -Command "..."` or `cmd /c ...`."""
    cmd = str(cmd or "")
    try:
        words = _split(cmd, win)
    except ValueError:
        return cmd
    prog = re.split(r"[\\/]", words[0])[-1].lower() if words else ""
    prog = prog[:-4] if prog.endswith(".exe") else prog
    if len(words) < 3 or prog not in SHELL_WRAPPERS:
        return cmd
    for i, w in enumerate(words[1:], 1):
        if w.lower() in WRAPPER_FLAGS:
            if i == len(words) - 2:
                return words[-1]
            return " ".join(words[i + 1:]) if prog == "cmd" else cmd
        if not w.startswith(("-", "/")):
            break
    return cmd


def _match(claimed, logged):
    """"exact" when the claimed command is the logged one (wrapper, quotes, and spacing aside), "close"
    when one only contains the other, else None. Only an exact match confirms a claim."""
    a, b = _norm_cmd(claimed), _norm_cmd(_unwrap(logged))
    if not a or not b:
        return None
    if a == b:
        return "exact"
    short, long_ = sorted((a, b), key=len)
    return "close" if len(short) >= 6 and short in long_ else None


def check_claims(report, commands):
    rows, used = [], set()
    for ch in (report or {}).get("checks") or []:
        claim, cmd = str(ch.get("result") or "?"), str(ch.get("command") or "")
        row = {"claim": claim, "command": cmd, "log": "", "flag": None}
        if commands is None:
            row["log"] = "not visible"
        else:
            hits = [i for i, c in enumerate(commands) if _match(cmd, c["cmd"]) == "exact"]
            close = [i for i, c in enumerate(commands) if not hits and _match(cmd, c["cmd"]) == "close"]
            used.update(hits)
            if close:
                # Left in "also ran", so the elder can compare: `pytest tests/unit_broken` isn't `pytest tests/unit`.
                row["log"] = "close match"
                if claim in ("pass", "fail"):
                    row["flag"] = "UNCONFIRMED"
            elif not hits:
                row["log"] = "not in log"
                if claim in ("pass", "fail"):
                    row["flag"] = "NOT_IN_LOG"
            else:
                last = commands[hits[-1]]
                if last["exit"] == 0:
                    row["log"] = "exit 0"
                elif last["exit"] is not None:
                    row["log"] = "exit %s" % last["exit"]
                elif last["error"]:
                    row["log"] = "error: " + _one(last["error"], 60)
                else:
                    row["log"] = "ran, exit unknown"
                if claim == "pass" and (last["exit"] not in (0, None) or (last["exit"] is None and last["error"])):
                    row["flag"] = "CONTRADICTED"
                elif claim == "pass" and last["exit"] is None:
                    row["flag"] = "UNCONFIRMED"
        rows.append(row)
    return rows, used


def _rel(path, repo, win=WIN):
    p = str(path or "")
    if p.startswith("file://"):
        p = p[7:]
    if win:  # the report may say C:\Repo\src\a.ts or /C:/repo/src/a.ts; git says src/a.ts
        p = p.replace("\\", "/")
        p = p[1:] if re.match(r"/[A-Za-z]:/", p) else p
        for root in (str(repo), os.path.realpath(str(repo))):
            root = root.replace("\\", "/").rstrip("/") + "/"
            if p.lower().startswith(root.lower()):
                return p[len(root):]
        return p[2:] if p.startswith("./") else p
    root = str(repo).rstrip("/") + "/"
    for prefix in (root, os.path.realpath(root.rstrip("/")) + "/"):
        if p.startswith(prefix):
            return p[len(prefix):]
    return p[2:] if p.startswith("./") else p


def _gate_entries(run):
    log = run / "gate" / "log.jsonl"
    if not log.exists():
        return []
    return [e for e in (_json_or(line, None) for line in log.read_text(encoding="utf-8").splitlines()) if e]


def _writer_during(meta):
    """Did a writing run share the working tree with this scout at any point? Then the diff isn't the scout's."""
    base, start, end = Path(meta["run"]).parent, meta["started"], time.time()
    for d in base.iterdir() if base.exists() else []:
        if str(d) == meta["run"] or not (d / "meta.json").exists():
            continue
        m = _json_or((d / "meta.json").read_text(encoding="utf-8"), {})
        if m.get("scout") or not isinstance(m.get("started"), (int, float)):
            continue
        try:
            if (d / "summary.json").exists():
                finished = (d / "summary.json").stat().st_mtime
            elif _alive(m.get("worker_pid")):
                finished = end
            else:  # it died without a summary: its last write is as late as it could have run
                finished = max(f.stat().st_mtime for f in d.iterdir())
        except OSError:
            finished = end  # can't tell, so assume it overlapped
        if m["started"] < end and finished > start:
            return True
    return False


def summarize(run, meta, code, why):
    events = run / "events.ndjson"
    out = events.read_text(encoding="utf-8", errors="replace") if events.exists() else ""
    err = (run / "stderr.txt").read_text(encoding="utf-8", errors="replace") if (run / "stderr.txt").exists() else ""
    sk = meta["shoggoth"]
    try:
        p = ADAPTERS[sk["cli"]]["parse"](out, run)
    except Exception as e:  # a CLI changed its log format; the git truth below still holds
        p = _parsed()
        p["commands"] = None
        p["error"] = "shoggoth could not read this log: %r" % e
    report = _normal_report(p["report"]) or _normal_report(_report_from_text(p["text"]))
    repo = Path(meta["repo"])

    changes, stat, after, git_note = [], "", None, None
    if meta.get("git") and meta.get("baseline"):
        try:
            after = snapshot(repo)
            changes, stat = tree_diff(repo, meta["baseline"], after)
        except RuntimeError as e:
            git_note = "git diff failed: %s" % e
    else:
        git_note = "not a git repository: check the changes by hand"
    hook_file = HOOK_FILES.get(sk["cli"]) if meta.get("gated") else None
    changes = [(s, path) for s, path in changes if path != hook_file]  # the gate's own hook file
    scope = meta.get("scope") or []
    scout = bool(meta.get("scout"))
    writer_during = scout and bool(changes) and _writer_during(meta)
    rows = [{"status": s, "path": path,
             "out_of_scope": bool((scout and not writer_during) or (scope and not in_scope(path, scope)))}
            for s, path in changes]

    checks, used = check_claims(report, p["commands"])
    commands = p["commands"] or []
    others = []
    for i, c in enumerate(commands):
        if i not in used and c["cmd"] and c["cmd"] not in others:
            others.append(c["cmd"])
    risky = sorted({c["cmd"] for c in commands if RISKY.search(c["cmd"] or "")})

    gate = _gate_entries(run)
    asked = [e for e in gate if e.get("request")]
    passed = {_norm_cmd(e.get("text")) for e in gate if e.get("kind") == "command" and e.get("decision") == "allow"}
    ungated = []
    if meta.get("gated") and sk["cli"] in HOOK_FILES.keys() | {"claude"} and p["commands"] is not None:
        ungated = [c["cmd"] for c in commands if _norm_cmd(c["cmd"]) not in passed]

    failed = bool(why) or (code not in (0, None)) or p["ok"] is False
    flags = []
    if failed:
        flags.append("FAILED")
    if ungated:
        flags.append("GATE_BYPASSED")
    if not report:
        flags.append("NO_REPORT")
    if p["refused"]:
        flags.append("REFUSED")
    if any(r["out_of_scope"] for r in rows):
        flags.append("SCOUT_EDITED" if meta.get("scout") else "OUT_OF_SCOPE")
    for name in ("CONTRADICTED", "NOT_IN_LOG", "UNCONFIRMED"):
        if any(c["flag"] == name for c in checks):
            flags.append(name)
    if risky:
        flags.append("RISKY_COMMAND")
    if report and meta.get("git") and not git_note:
        claimed = {_rel(f, repo) for f in report["files_changed"] if isinstance(f, str)}
        actual = {r["path"] for r in rows}
        if claimed - actual:
            flags.append("CLAIMED_NOT_CHANGED")
        if actual - claimed and not writer_during:
            flags.append("UNREPORTED_CHANGES")
    if report and report["status"] == "blocked":
        flags.append("BLOCKED")
    if report and report["questions"]:
        flags.append("QUESTIONS")

    baseline = meta.get("baseline")
    diff = undo = None
    if baseline and after and rows:
        diff = "git diff %s %s -- <path>" % (baseline[:12], after[:12])
    if baseline and after and rows and not scout:  # a scout's diff may hold a writer's edits: never undo it
        # A subcommand, not shell lines: `rm` and `&&` don't work in every shell an elder runs (PowerShell).
        restore = sum(1 for r in rows if r["status"] in "MDT")
        undo = "shog undo %s  (restores %d file%s, deletes %d)" % (
            meta["run"], restore, "" if restore == 1 else "s", len(rows) - restore)

    session = p["session"] or meta.get("session_in") or meta.get("new_session")
    gate_note = None
    if sk["cli"] == "codex" and meta.get("gated"):
        gate_note = "commands ran inside Codex's sandbox; the gate saw only escalations"
    policy_file = run / "gate" / "policy.json"
    permissions = None
    if meta.get("gated"):
        permissions = policy_line(_load(run / "gate", "policy.json") if policy_file.exists() else None)
    return {
        "run": Path(meta["run"]).name, "dir": meta["run"], "repo": meta["repo"], "shoggoth": sk,
        "scout": meta.get("scout"), "writer_during": writer_during, "gate_note": gate_note, "permissions": permissions,
        "scope": scope, "elapsed": time.time() - meta["started"],
        "waited": waited(run), "exit": code, "why": why, "ok": not failed, "error": p["error"],
        "session": session, "usage": p["usage"], "tools": p["tools"], "flags": flags, "report": report,
        "changes": rows, "stat": stat, "git_note": git_note, "checks": checks,
        "commands_visible": p["commands"] is not None, "other_commands": others[:12], "risky": risky,
        "refused": p["refused"], "ungated": ungated,
        "asked": [{"text": e.get("text") or ", ".join(e.get("paths") or []) or e.get("tool"),
                   "decision": e.get("decision"), "by": e.get("by"), "note": e.get("note")} for e in asked],
        "auto": sum(1 for e in gate if not e.get("request") and e.get("kind") != "internal"),
        "baseline": baseline, "after": after, "diff": diff, "undo": undo,
        "log": str(events), "stderr_tail": _tail(err, lines=5, width=240) if failed else "",
    }


def render(s):
    sk, r = s["shoggoth"], s["report"]
    lines = ["shoggoth run %s · %s = %s%s · permissions %s · style %s%s" % (
        s["run"], sk["name"], sk["cli"], " " + sk["model"] if sk.get("model") else "", sk["permissions"],
        sk.get("style", "lean"), " · scout" if s["scout"] else "")]
    state = "finished" if s["ok"] else "FAILED (%s)" % (s["why"] or _one(s["error"], 160) or "exit %s" % s["exit"])
    waited_note = " (+%s waiting on the user)" % _dur(s["waited"]) if s.get("waited", 0) >= 1 else ""
    lines.append("result: %s after %s%s · exit %s · session %s" % (
        state, _dur(s["elapsed"] - s.get("waited", 0)), waited_note, s["exit"], s["session"] or "unknown"))
    if s["usage"]:
        lines.append("tokens: " + " · ".join("%s %s" % (k, format(v, ",")) for k, v in s["usage"].items()
                                              if isinstance(v, int)))
    lines.append("flags: " + (", ".join(s["flags"]) or "none"))
    lines.append("")
    if r:
        lines.append("report (the shoggoth's claims): %s · %s" % (r["status"], _one(r["summary"], 300)))
    else:
        lines.append("report: none found in the shoggoth's final message")
    if s["git_note"]:
        lines.append("changes: " + s["git_note"])
    else:
        lines.append("%s: %s" % ("tree changes during the scout (a writer was running)" if s.get("writer_during")
                                 else "changes (git, ground truth)", s["stat"] or "none"))
        for c in s["changes"][:40]:
            lines.append("  %s %s%s" % (c["status"], c["path"], "  <- out of scope" if c["out_of_scope"] else ""))
        if len(s["changes"]) > 40:
            lines.append("  ... %d more" % (len(s["changes"]) - 40))
    if s["checks"]:
        lines.append("checks (claim -> log):")
        for c in s["checks"]:
            lines.append("  %-7s -> %-18s %s%s" % (c["claim"], c["log"], c["command"],
                                                   "  <- " + c["flag"] if c["flag"] else ""))
    if not s["commands_visible"]:
        lines.append("commands: not visible in this CLI's log; re-run the checks yourself")
    elif s["other_commands"]:
        lines.append("also ran: " + "; ".join(_one(c, 80) for c in s["other_commands"]))
    if s.get("permissions"):
        lines.append("permissions: " + s["permissions"])
    if s.get("gate_note"):
        lines.append("gate: " + s["gate_note"])
    if s["asked"] or s["auto"]:
        lines.append("approvals: %d asked, %d let through by the gate's rules" % (len(s["asked"]), s["auto"]))
        for x in s["asked"]:
            lines.append("  %-5s by %-7s %s%s" % (x["decision"], x["by"], _one(x["text"], 100),
                                                 "  (%s)" % _one(x["note"], 80) if x.get("note") else ""))
    for key, label in (("ungated", "ran without the gate"), ("risky", "risky"), ("refused", "refused by the CLI")):
        if s[key]:
            lines.append("%s: %s" % (label, "; ".join(_one(c, 120) for c in s[key])))
    if r:
        for key in ("notes", "deviations", "concerns", "questions"):
            if r[key]:
                lines.append(key + ":")
                lines += ["  - " + _one(x, 300) for x in r[key]]
    lines.append("")
    if s["diff"]:
        lines.append("diff: " + s["diff"])
    if s["undo"]:
        lines.append("undo: " + s["undo"])
    lines.append("log: " + s["log"])
    if s["stderr_tail"]:
        lines.append("stderr: " + s["stderr_tail"])
    return "\n".join(lines) + "\n"


def render_requests(run, reqs):
    lines = ["shoggoth run %s · %d request%s waiting for the user · RUN=%s"
             % (run.name, len(reqs), "" if len(reqs) == 1 else "s", run)]
    for q in reqs:
        what = q.get("text") or ", ".join(q.get("paths") or []) or q.get("tool")
        rule = "" if q["rule"] == q["kind"] else " · " + q["rule"]
        lines.append("  [%s] %s%s · %s: %s" % (q["id"], q["kind"], rule, q["tool"], _one(what, 300)))
        if q.get("why"):
            lines.append("      why: %s" % _one(q["why"], 200))
    lines.append("next: shog answer RUN <id> allow|deny [--always] [--note TEXT], then shog wait RUN")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- commands


def _version(path):
    if not path:
        return ""
    try:
        r = subprocess.run([path, "--version"], capture_output=True, encoding="utf-8", errors="replace", timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    text = (r.stdout or r.stderr).strip()
    return _one(text.splitlines()[0] if text else "", 60)


def cmd_doctor(a):
    from concurrent.futures import ThreadPoolExecutor
    cfg = load_config()
    print("config: %s%s" % (CONFIG, "" if CONFIG.exists() else "  (not set up yet: /elder config asks and saves it)"))
    for key, value in cfg.items():
        if not key.startswith("_"):
            sk = _spec(value, key)
            print("  %-8s -> %s %s · permissions %s · %s" % (
                key, sk["cli"], sk.get("model") or "(CLI default model)", sk["permissions"],
                "ready" if find_bin(sk) else "CLI not found"))
    if a.elder:
        cwd = Path.cwd()
        pol = elder_policy(a.elder, repo_root(cwd) or cwd)
        print("permissions for elder %s: %s" % (a.elder, policy_line(pol)))
        for src in (pol or {}).get("sources") or []:
            print("  from %s" % src)
        for item in (pol or {}).get("skipped") or []:
            print("  skipped %s" % _one(item, 160))
    print("shoggoth CLIs:")
    paths = {cli: find_bin({"cli": cli}) for cli in ADAPTERS}
    with ThreadPoolExecutor(max_workers=len(paths)) as pool:  # some CLIs take seconds to print a version
        versions = dict(zip(paths, pool.map(_version, paths.values())))
    for cli, ad in ADAPTERS.items():
        path = paths[cli]
        print("  %-7s %s%s" % (cli, path or "not found", "  (%s)" % versions[cli] if path else ""))
        print("          gate: %s · adapter %s" % (ad["gate"] or "none (\"full\" only)", ad["checked"]))
    print("runs: %s" % HOME)


def _spawn(run):
    with open(run / "worker.log", "wb") as log:
        return _popen([sys.executable, str(Path(__file__).resolve()), "_work", str(run)], worker=True,
                      stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)


def cmd_start(a):
    run = prepare(a)
    proc = _spawn(run)
    print("shoggoth: started run %s (%s, worker pid %d). Next: shog wait RUN · RUN=%s"
          % (run.name, _load(run, "meta.json")["shoggoth"]["name"], proc.pid, run))


def cmd_run(a):
    run = prepare(a)
    _spawn(run)
    _wait(run, a.max)


def _wait(run, limit):
    deadline = time.time() + limit
    while True:
        if (run / "summary.txt").exists():
            print((run / "summary.txt").read_text(encoding="utf-8"), end="")
            sys.exit(0)
        meta = _load(run, "meta.json")
        reqs = [] if (run / "stopped").exists() or not _alive(meta.get("worker_pid")) else pending(run)
        if reqs:
            print(render_requests(run, reqs), end="")
            sys.exit(4)
        if not _alive(meta.get("worker_pid")) and time.time() - meta["started"] > 10:
            time.sleep(1)
            if not (run / "summary.txt").exists():
                die("run %s ended without a summary; see %s" % (run.name, run / "worker.log"))
        if time.time() >= deadline:
            print("shoggoth: run %s still running after %s; wait again, or `stop` it · RUN=%s"
                  % (run.name, _dur(time.time() - meta["started"]), run))
            sys.exit(3)
        time.sleep(1)


def cmd_wait(a):
    _wait(find_run(a.run), a.max)


def cmd_answer(a):
    run = find_run(a.run)
    req = run / "gate" / ("req-%s.json" % a.id)
    if not req.exists():
        die("run %s has no request %r" % (run.name, a.id))
    if (run / "gate" / ("ans-%s.json" % a.id)).exists():
        die("request %s was already answered" % a.id)
    _save(run / "gate", "ans-%s.json" % a.id,
          {"decision": a.decision, "always": bool(a.always), "note": a.note, "time": time.time()})
    q = _json_or(req.read_text(encoding="utf-8"), {})
    print("shoggoth: %s%s: %s" % (a.decision, " (for the rest of this task)" if a.always else "",
                              _one(q.get("text") or ", ".join(q.get("paths") or []) or q.get("tool"), 200)))


def cmd_show(a):
    run = find_run(a.run)
    if not (run / "summary.txt").exists():
        die("run %s has no summary yet; use `wait`" % run.name)
    print((run / "summary.txt").read_text(encoding="utf-8"), end="")


def cmd_stop(a):
    run = find_run(a.run)
    meta = _load(run, "meta.json")
    if (run / "summary.txt").exists():
        print("shoggoth: run %s already finished" % run.name)
        return
    (run / "stopped").touch()
    pid = meta.get("child_pid")
    if pid:
        _kill_group(pid)
        for _ in range(20):
            if not _alive(pid):
                break
            time.sleep(0.5)
        else:
            _kill_group(pid, hard=True)
    for _ in range(40):  # let the worker put the repo's hook file back and write the summary
        if (run / "summary.txt").exists():
            print("shoggoth: stopped run %s; `show %s` prints its summary" % (run.name, run))
            return
        time.sleep(0.5)
    print("shoggoth: stopping run %s; `wait %s` prints its summary" % (run.name, run))


def cmd_undo(a):
    """Put back what a writing run changed: modified and deleted files from the baseline, added files removed.
    Refuses when one of those files changed again after the run, unless --force."""
    run = find_run(a.run)
    if not (run / "summary.json").exists():
        die("run %s has no summary yet; `wait` for it or `stop` it first" % run.name)
    s = _load(run, "summary.json")
    if s.get("scout"):
        die("run %s was a scout; its changes may be a writer's, so it has nothing to undo" % run.name)
    if not (s.get("baseline") and s.get("after") and s.get("changes")):
        die("run %s left no git changes to undo" % run.name)
    repo = Path(s["repo"])
    paths = [c["path"] for c in s["changes"]]
    try:
        later = {p for _, p in tree_diff(repo, s["after"], snapshot(repo))[0]} & set(paths)
    except RuntimeError as e:
        die("can't compare with the working tree: %s" % e)
    if later and not a.force:
        die("changed again after run %s, so undo would lose that work: %s. Pass --force to undo anyway."
            % (run.name, ", ".join(sorted(later))))
    restore = [c["path"] for c in s["changes"] if c["status"] in "MDT"]
    added = [c["path"] for c in s["changes"] if c["status"] == "A"]
    if restore:
        try:
            _git(repo, "restore", "--source=%s" % s["baseline"], "--worktree", "--", *restore)
        except RuntimeError as e:
            die("git restore failed: %s" % e)
    for p in added:
        with contextlib.suppress(FileNotFoundError):
            (repo / p).unlink()
    print("shoggoth: undid run %s: restored %d file%s, deleted %d" % (
        run.name, len(restore), "" if len(restore) == 1 else "s", len(added)))


def main(argv=None):
    if WIN:  # the elder reads our output as UTF-8; the console code page can't print · or →
        for stream in (sys.stdout, sys.stderr):
            with contextlib.suppress(AttributeError, ValueError):
                stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(prog="shoggoth.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True,
                            metavar="{doctor,models,config,run,start,wait,answer,show,stop,undo}")
    # Every subcommand takes --elder, so the elder can pass it on every call; only config, run, and start use it.
    elder = argparse.ArgumentParser(add_help=False)
    elder.add_argument("--elder", help="the agent running shoggoth (claude, codex, cursor, agy, grok, or its own "
                                       "lowercase name): picks its shoggoth")
    sub.add_parser("doctor", parents=[elder], help="list shoggoth CLIs, the config, and each CLI's gate"
                   ).set_defaults(fn=cmd_doctor)
    p = sub.add_parser("models", parents=[elder], help="what a shoggoth CLI offers: models, efforts, the recommended pick")
    p.add_argument("cli", choices=list(ADAPTERS))
    p.set_defaults(fn=cmd_models)
    p = sub.add_parser("config", parents=[elder], help="show, set, or unset the shoggoth for an elder")
    p.add_argument("action", choices=("show", "set", "unset"))
    p.add_argument("--cli", help="the shoggoth CLI; set without it keeps the current one")
    p.add_argument("--model", help="the shoggoth's model id; omit for the CLI's default")
    p.add_argument("--effort", help="the shoggoth's reasoning effort")
    p.add_argument("--permissions", choices=("ask", "full"), help="default ask; full only with the user's word")
    p.add_argument("--style", choices=("lean", "detailed"), help="how much the elder spells out in briefs")
    p.add_argument("--bin", help="the binary, when it isn't the usual name on PATH")
    p.set_defaults(fn=cmd_config)
    for name, fn, text in (("run", cmd_run, "start a run, then wait for its summary or a request"),
                           ("start", cmd_start, "start a run and return")):
        p = sub.add_parser(name, parents=[elder], help=text)
        p.add_argument("--brief", required=True, help="brief file, or - for stdin")
        p.add_argument("--shoggoth", help="CLI[:MODEL], such as agy:gemini-4-argon-high (overrides the config)")
        p.add_argument("--session", help="continue this shoggoth session (from an earlier summary)")
        p.add_argument("--allow", action="append", default=[], help="a command the user approved up front; repeatable")
        p.add_argument("--scope", action="append", default=[], help="path glob the brief allows; repeatable")
        p.add_argument("--scout", action="store_true", help="read-only brief: any change is flagged")
        p.add_argument("--permissions", choices=("ask", "full"), help="override the config for this run")
        p.add_argument("--timeout", type=_seconds, default=1800, help="working time, e.g. 45m (default 30m)")
        p.add_argument("--cwd", default=".", help="repository to work in (default: here)")
        if name == "run":
            p.add_argument("--max", type=_seconds, default=540, help="return after this long (default 9m); exit 3")
        p.set_defaults(fn=fn)
    p = sub.add_parser("wait", parents=[elder], help="wait for the summary or the next request")
    p.add_argument("run")
    p.add_argument("--max", type=_seconds, default=540, help="return after this long (default 9m); exit 3")
    p.set_defaults(fn=cmd_wait)
    p = sub.add_parser("answer", parents=[elder], help="pass the user's decision on a request to the shoggoth")
    p.add_argument("run")
    p.add_argument("id")
    p.add_argument("decision", choices=("allow", "deny"))
    p.add_argument("--always", action="store_true", help="allow exactly this command line for the rest of the task")
    p.add_argument("--note", help="a word for the shoggoth, e.g. why it was denied")
    p.set_defaults(fn=cmd_answer)
    for name, fn, text in (("show", cmd_show, "print a finished run's summary"),
                           ("stop", cmd_stop, "stop a running shoggoth")):
        p = sub.add_parser(name, parents=[elder], help=text)
        p.add_argument("run")
        p.set_defaults(fn=fn)
    p = sub.add_parser("undo", parents=[elder], help="revert a writing run's changes")
    p.add_argument("run")
    p.add_argument("--force", action="store_true", help="undo even files that changed again after the run")
    p.set_defaults(fn=cmd_undo)
    w = sub.add_parser("_work")  # the detached half of start and run
    w.add_argument("run")
    w.set_defaults(fn=lambda a: work(Path(a.run)))
    g = sub.add_parser("_gate")  # the hook the shoggoth's CLI calls before a tool call
    g.add_argument("cli", choices=sorted(NORMALIZERS))
    g.set_defaults(fn=cmd_gate)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
