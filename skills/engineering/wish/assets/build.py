#!/usr/bin/env python3
"""Check a plan JSON and embed it in template.html.

    python3 build.py docs/plan.json                 # writes docs/plan.html next to it
    python3 build.py docs/plan.json -o out.html
    python3 build.py docs/plan.json --check         # validate only

No dependencies. The JSON is checked against doc.schema.json first (types,
required fields, lengths), then against what a schema can't express (terms,
option groups, table cells). Exit code 1 when anything is wrong; nothing is
written in that case.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA = json.loads((HERE / "doc.schema.json").read_text(encoding="utf-8"))
MARKER = '<script type="application/json" id="doc-data">null</script>'
# Inline marks, matched the way the page matches them: `code`, **bold**, [[term]] / [[shown text|term]].
MARK = re.compile(r"`([^`]+)`|\*\*(.+?)\*\*|\[\[([^\]|]+?)(?:\|([^\]]+?))?\]\]")
# In "a | b" strings, a | inside `code` or [[shown text|term]] belongs to the mark and \| is a literal pipe.
PIPE = re.compile(r"`[^`]+`|\[\[[^\]|]+?(?:\|[^\]]+?)?\]\]|\\\||\|")
HAN = re.compile(r"[㐀-鿿]")
WORD = re.compile(r"[A-Za-z0-9]+")
MAX_MINUTES = 8

# Block fields that take [[marks]], in the order the page shows them.
MARKED = {
    "p": ("text",),
    "list": ("items",),
    "table": ("rows", "caption"),
    "option": ("how", "reason"),
    "row": ("text",),
    "step": ("what", "done"),
    "flow": ("note",),
    "check": ("question", "answer", "detail"),
    "callout": ("text",),
}

TYPE_NAMES = {"object": "an object", "array": "a list", "string": "a string", "boolean": "true or false", "integer": "a whole number"}
ANNOTATIONS = {"$schema", "$defs", "title", "description", "default"}


def cells(row):
    """Split "a | b | c" into stripped cells."""
    out, start = [], 0
    for m in PIPE.finditer(row):
        if m.group() == "|":
            out.append(row[start:m.start()])
            start = m.end()
    out.append(row[start:])
    return [c.replace("\\|", "|").strip() for c in out]


def spans(text, offset=0):
    """(start, end, term) for each mark the page renders; term is None for `code`, whose content stays literal."""
    for m in MARK.finditer(text):
        if m.group(1) is not None:
            yield offset + m.start(), offset + m.end(), None
        elif m.group(2) is not None:
            yield from spans(m.group(2), offset + m.start(2))
        else:
            yield offset + m.start(), offset + m.end(), (m.group(4) or m.group(3)).strip()


def at(where, msg):
    return f"{where or 'top level'}: {msg}"


def item(where, i, value):
    """Label for element i of the list at `where`."""
    if where == "blocks":
        kind = value.get("type") if isinstance(value, dict) else None
        return f"block {i + 1}" + (f" ({kind})" if isinstance(kind, str) else "")
    if where == "decisions":
        return f"decision {i + 1}"
    return f"{where}[{i + 1}]"


def is_a(value, t):
    if isinstance(value, bool):
        return t == "boolean"
    if t == "integer":
        return isinstance(value, int) or isinstance(value, float) and value.is_integer()
    return isinstance(value, {"object": dict, "array": list, "string": str, "boolean": bool}[t])


def deref(schema):
    return SCHEMA["$defs"][schema["$ref"].rsplit("/", 1)[1]] if "$ref" in schema else schema


def schema_errors(value, schema=SCHEMA, where=""):
    """What doc.schema.json rejects. Covers exactly the keywords that file uses; a new one stops the build."""
    if "type" in schema and not is_a(value, schema["type"]):
        return [at(where, f"must be {TYPE_NAMES[schema['type']]}")]
    errs = []
    for key, rule in schema.items():
        if key in ANNOTATIONS or key == "type":
            continue
        if key == "$ref":
            errs += schema_errors(value, deref(schema), where)
        elif key == "enum":
            if value not in rule:
                errs.append(at(where, f"must be one of {', '.join(map(str, rule))}"))
        elif key == "const":
            if value != rule:
                errs.append(at(where, f"must be {rule!r}"))
        elif key == "not":
            if not schema_errors(value, rule, where):
                errs.append(at(where, schema.get("description") or f"must not match {json.dumps(rule)}"))
        elif key == "pattern":
            if isinstance(value, str) and not re.search(rule, value):
                errs.append(at(where, f"{value!r} does not match {rule}"))
        elif key == "minLength":
            if isinstance(value, str) and len(value) < rule:
                errs.append(at(where, "must not be empty" if rule == 1 else f"needs at least {rule} characters"))
        elif key == "maxLength":
            if isinstance(value, str) and len(value) > rule:
                errs.append(at(where, f"{len(value)} characters; at most {rule}"))
        elif key == "minimum":
            if is_a(value, "integer") and value < rule:
                errs.append(at(where, f"must be at least {rule}"))
        elif key == "minItems":
            if isinstance(value, list) and len(value) < rule:
                errs.append(at(where, f"has {len(value)}; needs at least {rule}"))
        elif key == "maxItems":
            if isinstance(value, list) and len(value) > rule:
                errs.append(at(where, f"has {len(value)}; at most {rule}"))
        elif key == "items":
            if isinstance(value, list):
                for i, v in enumerate(value):
                    errs += schema_errors(v, rule, item(where, i, v))
        elif key == "maxProperties":
            if isinstance(value, dict) and len(value) > rule:
                errs.append(at(where, f"has {len(value)}; at most {rule}"))
        elif key == "required":
            missing = [k for k in rule if isinstance(value, dict) and k not in value]
            if missing:
                errs.append(at(where, f"missing {', '.join(missing)}"))
        elif key == "properties":
            for k, sub in rule.items():
                if isinstance(value, dict) and k in value:
                    errs += schema_errors(value[k], sub, f"{where} → {k}" if where else k)
        elif key == "additionalProperties":
            extra = [k for k in value if k not in schema.get("properties", {})] if isinstance(value, dict) else []
            if rule is False and extra:
                errs.append(at(where, f"unknown fields {', '.join(extra)}"))
            elif isinstance(rule, dict):
                for k in extra:
                    errs += schema_errors(value[k], rule, f"{where} → {k}")
        elif key == "propertyNames":
            for k in value if isinstance(value, dict) else ():
                errs += schema_errors(k, rule, f"{where} → {k!r}")
        elif key == "oneOf":
            results = [schema_errors(value, sub, where) for sub in rule]
            if sum(not r for r in results) != 1:
                # Report against the alternative whose "type" constant this value names.
                kinds = [deref(sub).get("properties", {}).get("type", {}).get("const") for sub in rule]
                kind = value.get("type") if isinstance(value, dict) else None
                if kind in kinds:
                    errs += results[kinds.index(kind)]
                elif isinstance(value, dict):
                    errs.append(at(where, f"type must be one of {', '.join(map(str, kinds))}"))
                else:
                    errs.append(at(where, "must be an object"))
        else:
            sys.exit(f"✗ doc.schema.json uses {key!r}, which build.py does not check yet")
    return errs


def texts_in_order(doc):
    """(where, text) for every text that takes marks, in reading order."""
    out = [("summary", doc["summary"])]
    for i, d in enumerate(doc.get("decisions", []), 1):
        texts = [d["question"], *(cells(o)[0] for o in d["options"]), d.get("why", "")]
        out += [(f"decision {i}", t) for t in texts]
    for n, b in enumerate(doc["blocks"], 1):
        for key in MARKED.get(b["type"], ()):
            values = b.get(key, [])
            for v in values if isinstance(values, list) else [values]:
                out += [(f"block {n} ({b['type']})", c) for c in (cells(v) if key == "rows" else [v])]
    return out


def check(doc):
    """Return a list of problems: the schema first, then the rules it can't express, which assume valid types."""
    errs = schema_errors(doc)
    if errs:
        return errs
    terms = doc.get("terms", {})

    for i, d in enumerate(doc.get("decisions", []), 1):
        for j, option in enumerate(d["options"], 1):
            parts, where = cells(option), f"decision {i} → options[{j}]"
            if len(parts) > 2:
                errs.append(f'{where}: more than one |; write "option | cost", and a literal pipe as \\|')
            elif not parts[0]:
                errs.append(f"{where}: no option text before the |")
            elif len(parts) == 2 and "[[" in parts[1]:
                errs.append(f"{where}: the cost after | is plain text, [[marks]] are not allowed")

    ids, checks, run = {"decide"}, 0, []

    def close_option_run():
        if run and sum(b["chosen"] for _, b in run) != 1:
            errs.append(f"blocks {run[0][0]}–{run[-1][0]}: an option group needs exactly one chosen: true")
        run.clear()

    for n, b in enumerate(doc["blocks"], 1):
        t, where = b["type"], f"block {n} ({b['type']})"
        if t == "option":
            run.append((n, b))
        else:
            close_option_run()
        if t == "h2" and "id" in b:
            if b["id"] in ids:
                errs.append(f"{where}: id {b['id']!r} is duplicated or reserved")
            ids.add(b["id"])
        checks += t == "check"
        if t == "table":
            for r, row in enumerate(b["rows"], 1):
                if len(cells(row)) != len(b["columns"]):
                    errs.append(f"{where}: row {r} has {len(cells(row))} cells; header has {len(b['columns'])}")
    close_option_run()
    if checks > 4:
        errs.append(f"{checks} self-checks; at most 4")

    # Marks: every [[x]] has a term, every term is marked, and the first use in reading order is the marked one.
    seq = texts_in_order(doc)
    used = set()
    for where, text in seq:
        for _, _, name in spans(text):
            if name in terms:
                used.add(name)
            elif name is not None:
                errs.append(f"{where}: [[{name}]] has no entry in terms")
    for name, text in terms.items():
        for s, e, ref in spans(text):
            if ref is not None and ref not in terms:
                errs.append(f"term {name!r}: {text[s:e]} has no entry in terms")
        if name not in used:
            errs.append(f"term {name!r} is never marked as [[{name}]]")
            continue
        for where, text in seq:
            found = list(spans(text))
            marked = min((s for s, _, ref in found if ref == name), default=None)
            plain = next((m.start() for m in re.finditer(re.escape(name), text)
                          if not any(s <= m.start() < e for s, e, _ in found)), None)
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
    if errs:
        print(f"✗ {args.json}: {len(errs)} problem(s)", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    mins = minutes(doc)
    long_note = f"\n  note: ~{mins} min read; aim for ≤ {MAX_MINUTES} — move detail out or split the task" if mins > MAX_MINUTES else ""
    if args.check:
        print(f"✓ {args.json} is valid · ~{mins} min read{long_note}")
        return

    template = args.template.read_text(encoding="utf-8")
    if template.count(MARKER) != 1:
        sys.exit(f"✗ {args.template}: data marker not found exactly once")
    # Inside <script>, only "</" can end the block early; \u003c parses back to the same JSON.
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
        f"{sum(b.get('type') == 'check' for b in blocks)} checks · {len(doc.get('terms') or {})} terms{long_note}"
    )


if __name__ == "__main__":
    main()
