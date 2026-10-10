#!/usr/bin/env python3
"""Check a plan JSON and embed it in template.html.

    python3 build.py docs/plan.json                 # writes docs/plan.html next to it
    python3 build.py docs/plan.json -o out.html
    python3 build.py docs/plan.json --check         # validate only

No dependencies. If the `jsonschema` package is installed, the JSON is also
validated against doc.schema.json. Exit code 1 when anything is wrong; nothing
is written in that case.
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MARKER = '<script type="application/json" id="doc-data">null</script>'
TERM = re.compile(r"\[\[([^\]|]+?)(?:\|([^\]]+?))?\]\]")
CELL_SPLIT = re.compile(r"\s*(?<!\\)\|\s*")
SLUG = re.compile(r"^[a-z][a-z0-9-]*$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HAN = re.compile(r"[㐀-鿿]")
WORD = re.compile(r"[A-Za-z0-9]+")

# type: (required, optional, fields that take [[marks]] — in reading order)
BLOCKS = {
    "h2": ({"text"}, {"id"}, ()),
    "h3": ({"text"}, set(), ()),
    "p": ({"text"}, set(), ("text",)),
    "list": ({"items"}, {"ordered"}, ("items",)),
    "table": ({"columns", "rows"}, {"file", "fileTag", "caption"}, ("rows", "caption")),
    "option": ({"name", "how", "chosen", "reason"}, set(), ("how", "reason")),
    "row": ({"label", "text"}, set(), ("text",)),
    "step": ({"when", "what"}, {"done"}, ("what", "done")),
    "flow": ({"steps"}, {"label", "note"}, ("note",)),
    "check": ({"question", "answer"}, {"detail"}, ("question", "answer", "detail")),
    "callout": ({"text"}, {"tone"}, ("text",)),
    "code": ({"text"}, set(), ()),
}
TOP_REQUIRED = {"title", "status", "date", "reader", "summary", "blocks"}
TOP_OPTIONAL = {"$schema", "lang", "kind", "project", "revision", "decisions", "terms", "changelog"}
MAX_MINUTES = 8


def cells(row):
    return [c.replace("\\|", "|").strip() for c in CELL_SPLIT.split(str(row))]


def strings(value):
    return [v for v in (value if isinstance(value, list) else [value]) if isinstance(v, str)]


def texts_in_order(doc):
    """(where, text) for every field that takes marks, in reading order."""
    out = [("summary", doc.get("summary", ""))]
    for i, d in enumerate(doc.get("decisions") or [], 1):
        if isinstance(d, dict):
            for key in ("question", "options", "why"):
                out += [(f"decision {i}", s) for s in strings(d.get(key))]
    for n, b in enumerate(doc.get("blocks") or [], 1):
        if isinstance(b, dict) and b.get("type") in BLOCKS:
            for key in BLOCKS[b["type"]][2]:
                out += [(f"block {n} ({b['type']})", s) for s in strings(b.get(key))]
    return out


def check(doc):
    """Return a list of problems. Mirrors the checks the page runs itself, plus a few it can't."""
    errs = []
    if not isinstance(doc, dict):
        return ["top level must be an object"]

    missing = TOP_REQUIRED - doc.keys()
    if missing:
        errs.append(f"missing fields: {', '.join(sorted(missing))}")
    unknown = doc.keys() - TOP_REQUIRED - TOP_OPTIONAL
    if unknown:
        errs.append(f"unknown fields: {', '.join(sorted(unknown))}")
    if doc.get("status") not in (None, "draft", "review", "approved"):
        errs.append("status must be draft, review or approved")
    if "date" in doc and not DATE.match(str(doc["date"])):
        errs.append("date must be YYYY-MM-DD")
    if len(str(doc.get("summary", ""))) > 280:
        errs.append("summary is longer than 280 characters")
    for key in ("title", "kind", "project", "reader"):
        if "[[" in str(doc.get(key, "")):
            errs.append(f"{key}: plain field, [[marks]] are not allowed")

    terms = doc.get("terms") or {}
    if not isinstance(terms, dict):
        errs.append("terms must be an object of term → explanation")
        terms = {}

    decisions = doc.get("decisions") or []
    if len(decisions) > 4:
        errs.append(f"{len(decisions)} decisions; at most 4")
    for i, d in enumerate(decisions, 1):
        opts = d.get("options") if isinstance(d, dict) else None
        if not isinstance(opts, list) or not 2 <= len(opts) <= 4:
            errs.append(f"decision {i}: needs 2–4 options (the first is the recommendation)")

    blocks = doc.get("blocks") or []
    ids, checks, prev, run = {"decide"}, 0, None, []

    def close_option_run():
        if run and sum(1 for b in run if b.get("chosen") is True) != 1:
            errs.append(f"blocks {run[0]['_n']}–{run[-1]['_n']}: an option group needs exactly one chosen: true")
        run.clear()

    for n, b in enumerate(blocks, 1):
        where = f"block {n}"
        if not isinstance(b, dict) or b.get("type") not in BLOCKS:
            errs.append(f"{where}: unknown type {b.get('type') if isinstance(b, dict) else b!r}")
            prev = None
            continue
        t = b["type"]
        need, opt, markable = BLOCKS[t]
        where = f"{where} ({t})"
        if need - b.keys():
            errs.append(f"{where}: missing {', '.join(sorted(need - b.keys()))}")
        extra = b.keys() - need - opt - {"type"}
        if extra:
            errs.append(f"{where}: unknown fields {', '.join(sorted(extra))}")
        for key in (need | opt) - set(markable) - {"id", "chosen", "ordered", "tone"}:
            if t != "code" and any("[[" in s for s in strings(b.get(key))):
                errs.append(f"{where}: {key} is plain text, [[marks]] are not allowed there")
        if t != "option" or prev != "option":
            close_option_run()
        if t == "option":
            run.append({**b, "_n": n})
        if t == "h2" and "id" in b:
            if not SLUG.match(str(b["id"])) or b["id"] in ids:
                errs.append(f"{where}: id {b['id']!r} is invalid, duplicated or reserved")
            ids.add(b["id"])
        if t == "check":
            checks += 1
        if t == "flow" and not 2 <= len(b.get("steps") or []) <= 8:
            errs.append(f"{where}: needs 2–8 steps")
        if t == "table":
            cols = b.get("columns") or []
            for r, row in enumerate(b.get("rows") or [], 1):
                if len(cells(row)) != len(cols):
                    errs.append(f"{where}: row {r} has {len(cells(row))} cells; header has {len(cols)}")
        prev = t
    close_option_run()
    if checks > 4:
        errs.append(f"{checks} self-checks; at most 4")

    # Marks: every [[x]] has a term, every term is marked, and the first use in reading order is the marked one.
    seq = texts_in_order(doc)
    used = set()
    for where, text in seq:
        for m in TERM.finditer(text):
            name = (m.group(2) or m.group(1)).strip()
            if name in terms:
                used.add(name)
            else:
                errs.append(f"{where}: [[{name}]] has no entry in terms")
    for name, text in terms.items():
        for m in TERM.finditer(str(text)):
            if (m.group(2) or m.group(1)).strip() not in terms:
                errs.append(f"term {name!r}: {m.group(0)} has no entry in terms")
        if name not in used:
            errs.append(f"term {name!r} is never marked as [[{name}]]")
            continue
        for where, text in seq:
            spans = [(m.start(), m.end(), (m.group(2) or m.group(1)).strip()) for m in TERM.finditer(text)]
            marked = min((s for s, _, ref in spans if ref == name), default=None)
            plain = next((m.start() for m in re.finditer(re.escape(name), text)
                          if not any(s <= m.start() < e for s, e, _ in spans)), None)
            if marked is None and plain is None:
                continue
            if plain is not None and (marked is None or plain < marked):
                errs.append(f"{where}: first use of {name!r} is unmarked; mark it here as [[{name}]] (reading order: summary → decisions → blocks)")
            break
    return errs


def minutes(doc):
    text = " ".join(t for _, t in texts_in_order(doc))
    text += " ".join(str(v) for v in (doc.get("terms") or {}).values())
    han = len(HAN.findall(text))
    words = len(WORD.findall(HAN.sub(" ", text)))
    return max(1, round(words / 230 if doc.get("lang") == "en" else han / 400 + words / 200))


def schema_errors(doc):
    try:
        import jsonschema
    except ImportError:
        return None
    schema = json.loads((HERE / "doc.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    return [f"schema: /{'/'.join(map(str, e.path))}: {e.message}" for e in validator.iter_errors(doc)]


def escape(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("json", type=Path)
    ap.add_argument("-o", "--out", type=Path)
    ap.add_argument("--template", type=Path, default=HERE / "template.html")
    ap.add_argument("--check", action="store_true", help="validate only, write nothing")
    args = ap.parse_args()

    try:
        doc = json.loads(args.json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"✗ {args.json}: invalid JSON at line {e.lineno}, column {e.colno}: {e.msg}")

    errs = check(doc)
    from_schema = schema_errors(doc)
    errs += from_schema or []
    if errs:
        print(f"✗ {args.json}: {len(errs)} problem(s)", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    note = "" if from_schema is not None else "  (jsonschema not installed; built-in checks only)"
    mins = minutes(doc)
    long_note = f"\n  note: ~{mins} min read; aim for ≤ {MAX_MINUTES} — move detail out or split the task" if mins > MAX_MINUTES else ""
    if args.check:
        print(f"✓ {args.json} is valid · ~{mins} min read{note}{long_note}")
        return

    template = args.template.read_text(encoding="utf-8")
    if template.count(MARKER) != 1:
        sys.exit(f"✗ {args.template}: data marker not found exactly once")
    # Inside <script>, only "</" can end the block early; < parses back to the same JSON.
    payload = json.dumps(doc, ensure_ascii=False, indent=2).replace("<", "\\u003c")
    html = template.replace(MARKER, f'<script type="application/json" id="doc-data">\n{payload}\n</script>')
    html = re.sub(r"<title>.*?</title>", lambda _: f"<title>{escape(doc['title'])}</title>", html, count=1)
    html = re.sub(r'<html lang="[^"]*">', f'<html lang="{escape(doc.get("lang", "zh-CN"))}">', html, count=1)

    out = args.out or args.json.with_suffix(".html")
    out.write_text(html, encoding="utf-8")
    blocks = doc["blocks"]
    print(
        f"✓ {out}  {len(html.encode('utf-8')) / 1024:.0f} KB · ~{mins} min read · "
        f"{sum(b.get('type') == 'h2' for b in blocks)} sections · {len(doc.get('decisions') or [])} decisions · "
        f"{sum(b.get('type') == 'check' for b in blocks)} checks · {len(doc.get('terms') or {})} terms{note}{long_note}"
    )


if __name__ == "__main__":
    main()
