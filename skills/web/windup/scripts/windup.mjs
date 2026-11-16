#!/usr/bin/env node
// windup.mjs: art.svg + score.json -> one animated SVG. No dependencies. Node >= 18.
//   lint | rig | compile | strip | presets      (run with no arguments for usage)
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
class Fail extends Error {}
const fail = (m) => { throw new Fail(m); };
const r2 = (n) => Math.round(n * 100) / 100;
const r3 = (n) => Math.round(n * 1000) / 1000;
const clamp01 = (n) => Math.max(0, Math.min(1, n));

// ───────────────────────────── xml ─────────────────────────────

const RAW_TEXT = new Set(['style', 'script']);
const NAME_Y = /<([^\s/>]+)/y;
const ATTR_Y = /([^\s=/>]+)\s*=\s*(?:"([^"]*)"|'([^']*)')/y;

function parseXML(src) {
  const doc = { type: 'doc', children: [], parent: null };
  const stack = [doc];
  const lineOf = (pos) => src.slice(0, pos).split('\n').length;
  const bad = (msg, pos) => fail(`XML not well-formed: ${msg} (line ${lineOf(pos)})`);
  const add = (node) => { const top = stack[stack.length - 1]; node.parent = top; top.children.push(node); return node; };
  const n = src.length;
  let i = 0;
  while (i < n) {
    const lt = src.indexOf('<', i);
    if (lt < 0) { add({ type: 'text', value: src.slice(i) }); break; }
    if (lt > i) add({ type: 'text', value: src.slice(i, lt) });
    if (src.startsWith('<!--', lt)) {
      const e = src.indexOf('-->', lt + 4); if (e < 0) bad('unclosed comment', lt);
      add({ type: 'comment', value: src.slice(lt + 4, e) }); i = e + 3; continue;
    }
    if (src.startsWith('<![CDATA[', lt)) {
      const e = src.indexOf(']]>', lt); if (e < 0) bad('unclosed CDATA', lt);
      add({ type: 'cdata', value: src.slice(lt + 9, e) }); i = e + 3; continue;
    }
    if (src.startsWith('<?', lt)) {
      const e = src.indexOf('?>', lt); if (e < 0) bad('unclosed <?', lt);
      add({ type: 'raw', value: src.slice(lt, e + 2) }); i = e + 2; continue;
    }
    if (src.startsWith('<!', lt)) {
      const e = src.indexOf('>', lt); if (e < 0) bad('unclosed <!', lt);
      add({ type: 'raw', value: src.slice(lt, e + 1) }); i = e + 1; continue;
    }
    if (src[lt + 1] === '/') {
      const e = src.indexOf('>', lt); if (e < 0) bad('unclosed tag', lt);
      const name = src.slice(lt + 2, e).trim();
      const open = stack.pop();
      if (!open || open.type !== 'el' || open.name !== name) bad(`</${name}> closes <${open?.name ?? '?'}>`, lt);
      i = e + 1; continue;
    }
    NAME_Y.lastIndex = lt;
    const m = NAME_Y.exec(src);
    if (!m) bad('stray "<"', lt);
    const el = { type: 'el', name: m[1], attrs: {}, children: [], parent: null };
    let j = NAME_Y.lastIndex;
    let selfClose = false;
    for (;;) {
      while (j < n && /\s/.test(src[j])) j++;
      if (j >= n) bad(`unclosed <${el.name}>`, lt);
      if (src[j] === '>') { j++; break; }
      if (src[j] === '/' && src[j + 1] === '>') { selfClose = true; j += 2; break; }
      ATTR_Y.lastIndex = j;
      const am = ATTR_Y.exec(src);
      if (!am) bad(`bad attribute in <${el.name}>`, j);
      el.attrs[am[1]] = am[2] ?? am[3];
      j = ATTR_Y.lastIndex;
    }
    add(el);
    if (!selfClose) {
      if (RAW_TEXT.has(el.name)) {
        const close = src.indexOf(`</${el.name}`, j);
        if (close < 0) bad(`<${el.name}> never closed`, lt);
        if (close > j) { el.children.push({ type: 'text', value: src.slice(j, close), parent: el }); }
        j = close;
      }
      stack.push(el);
    }
    i = j;
  }
  if (stack.length > 1) fail(`XML not well-formed: <${stack[stack.length - 1].name}> never closed`);
  return doc;
}

const escAttr = (s) => String(s).replace(/&(?!#?\w+;)/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
function serialize(node) {
  switch (node.type) {
    case 'doc': return node.children.map(serialize).join('');
    case 'text': return node.value;
    case 'comment': return `<!--${node.value}-->`;
    case 'cdata': return `<![CDATA[${node.value}]]>`;
    case 'raw': return node.value;
    default: {
      const a = Object.entries(node.attrs).map(([k, v]) => ` ${k}="${escAttr(v)}"`).join('');
      if (!node.children.length) return `<${node.name}${a}/>`;
      return `<${node.name}${a}>${node.children.map(serialize).join('')}</${node.name}>`;
    }
  }
}
function clone(node, parent = null) {
  const c = { ...node, parent };
  if (node.attrs) c.attrs = { ...node.attrs };
  if (node.children) c.children = node.children.map((k) => clone(k, c));
  return c;
}
const mk = (name, attrs = {}) => ({ type: 'el', name, attrs, children: [], parent: null });
const txt = (value) => ({ type: 'text', value, parent: null });
const adopt = (parent, child) => { child.parent = parent; parent.children.push(child); return child; };
const swap = (oldNode, newNode) => { const p = oldNode.parent; p.children[p.children.indexOf(oldNode)] = newNode; newNode.parent = p; };
function walk(node, fn) { if (fn(node) === false) return; for (const c of node.children ?? []) walk(c, fn); }
const rootEl = (doc) => doc.children.find((c) => c.type === 'el');
const textOf = (node) => (node.type === 'text' || node.type === 'cdata' ? node.value : (node.children ?? []).map(textOf).join(''));

// ───────────────────────────── css (tiny) ─────────────────────────────

const parseDecl = (s) => Object.fromEntries(String(s ?? '').split(';').map((p) => p.split(':')).filter((p) => p.length >= 2 && p[0].trim()).map(([k, ...v]) => [k.trim(), v.join(':').trim()]));
const declStr = (o) => Object.entries(o).map(([k, v]) => `${k}:${v}`).join(';');
function parseCSS(text) {
  const rules = [];
  const body = String(text).replace(/\/\*[\s\S]*?\*\//g, '');
  for (const m of body.matchAll(/([^{}@;]+)\{([^{}]*)\}/g)) {
    const decl = parseDecl(m[2]);
    for (const sel of m[1].split(',').map((s) => s.trim()).filter(Boolean)) {
      const sm = /^([a-zA-Z][\w-]*)?(?:#([\w-]+))?((?:\.[\w-]+)*)$/.exec(sel);
      if (!sm || !(sm[1] || sm[2] || sm[3])) continue;
      const cls = sm[3] ? sm[3].slice(1).split('.') : [];
      rules.push({ tag: sm[1], id: sm[2], cls, decl, spec: (sm[2] ? 100 : 0) + cls.length * 10 + (sm[1] ? 1 : 0) });
    }
  }
  return rules;
}
const INHERIT = new Set(['fill', 'stroke', 'stroke-width', 'stroke-linecap', 'stroke-dasharray', 'font-size', 'text-anchor', 'visibility']);
const ruleHits = (r, n) => (!r.tag || r.tag === n.name) && (!r.id || r.id === n.attrs.id) && r.cls.every((c) => (n.attrs.class ?? '').split(/\s+/).includes(c));
function styleOf(node, prop, env) {
  for (let n = node; n && n.type === 'el'; n = n.parent) {
    if (n.attrs.style) { const v = parseDecl(n.attrs.style)[prop]; if (v !== undefined) return v; }
    let best, bs = -1;
    for (const r of env.css) if (r.decl[prop] !== undefined && r.spec >= bs && ruleHits(r, n)) { best = r.decl[prop]; bs = r.spec; }
    if (best !== undefined) return best;
    if (n.attrs[prop] !== undefined) return n.attrs[prop];
    if (!INHERIT.has(prop)) return undefined;
  }
  return undefined;
}
function setStyle(el, prop, val) {
  const d = parseDecl(el.attrs.style);
  if (val === null) delete d[prop]; else d[prop] = val;
  if (Object.keys(d).length) el.attrs.style = declStr(d); else delete el.attrs.style;
}
const addClass = (el, c) => { el.attrs.class = el.attrs.class ? `${el.attrs.class} ${c}` : c; };

// ───────────────────────────── geometry ─────────────────────────────

const IDENT = [1, 0, 0, 1, 0, 0];
const mul = (m, k) => [m[0] * k[0] + m[2] * k[1], m[1] * k[0] + m[3] * k[1], m[0] * k[2] + m[2] * k[3], m[1] * k[2] + m[3] * k[3], m[0] * k[4] + m[2] * k[5] + m[4], m[1] * k[4] + m[3] * k[5] + m[5]];
const applyM = (m, [x, y]) => [m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]];
const NUM_G = /[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?/g;
const NUM_Y = /[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?/y;
const nums = (s) => (String(s ?? '').match(NUM_G) ?? []).map(Number);
const pf = (v, d = 0) => { const n = parseFloat(v); return Number.isFinite(n) ? n : d; };

function parseTransform(s) {
  let m = IDENT;
  for (const [, fn, args] of String(s ?? '').matchAll(/(\w+)\s*\(([^)]*)\)/g)) {
    const a = nums(args);
    let k = IDENT;
    if (fn === 'translate') k = [1, 0, 0, 1, a[0] ?? 0, a[1] ?? 0];
    else if (fn === 'scale') k = [a[0] ?? 1, 0, 0, a[1] ?? a[0] ?? 1, 0, 0];
    else if (fn === 'rotate') {
      const t = ((a[0] ?? 0) * Math.PI) / 180, c = Math.cos(t), s2 = Math.sin(t);
      k = [c, s2, -s2, c, 0, 0];
      if (a.length >= 3) k = mul(mul([1, 0, 0, 1, a[1], a[2]], k), [1, 0, 0, 1, -a[1], -a[2]]);
    } else if (fn === 'matrix' && a.length === 6) k = a;
    else if (fn === 'skewX') k = [1, 0, Math.tan(((a[0] ?? 0) * Math.PI) / 180), 1, 0, 0];
    else if (fn === 'skewY') k = [1, Math.tan(((a[0] ?? 0) * Math.PI) / 180), 0, 1, 0, 0];
    m = mul(m, k);
  }
  return m;
}
function ctmOf(node) { // every transform from the root down to and including node
  const chain = [];
  for (let n = node; n && n.type === 'el'; n = n.parent) if (n.attrs.transform) chain.unshift(n.attrs.transform);
  return chain.reduce((m, t) => mul(m, parseTransform(t)), IDENT);
}
const inv2 = (m) => { const d = m[0] * m[3] - m[1] * m[2] || 1; return [m[3] / d, -m[1] / d, -m[2] / d, m[0] / d, 0, 0]; };

const ARITY = { M: 2, L: 2, H: 1, V: 1, C: 6, S: 4, Q: 4, T: 2, A: 7, Z: 0 };
function parsePath(d) {
  const out = [];
  const s = String(d ?? '');
  let i = 0, cmd = null;
  const ws = () => { while (i < s.length && /[\s,]/.test(s[i])) i++; };
  const num = () => { ws(); NUM_Y.lastIndex = i; const m = NUM_Y.exec(s); if (!m) return null; i = NUM_Y.lastIndex; return Number(m[0]); };
  const flag = () => { ws(); const c = s[i]; if (c === '0' || c === '1') { i++; return Number(c); } return null; };
  for (;;) {
    ws();
    if (i >= s.length) break;
    if (/[a-zA-Z]/.test(s[i])) {
      cmd = s[i++];
      if (!(cmd.toUpperCase() in ARITY)) fail(`path: unknown command "${cmd}"`);
      if (cmd.toUpperCase() === 'Z') { out.push({ c: cmd, a: [] }); continue; }
    } else if (!cmd) fail('path: must start with M');
    else if (cmd.toUpperCase() === 'Z') fail(`path: number after Z near "${s.slice(i, i + 12)}"`);
    const U = cmd.toUpperCase();
    const a = [];
    for (let k = 0; k < ARITY[U]; k++) {
      const v = U === 'A' && (k === 3 || k === 4) ? flag() : num();
      if (v === null) fail(`path: bad "${cmd}" arguments near "${s.slice(Math.max(0, i - 10), i + 10)}"`);
      a.push(v);
    }
    out.push({ c: cmd, a });
    if (U === 'M') cmd = cmd === 'M' ? 'L' : 'l';
  }
  if (out.length && out[0].c.toUpperCase() !== 'M') fail('path: must start with M');
  return out;
}
function absPath(cmds) {
  const out = [];
  let x = 0, y = 0, sx = 0, sy = 0;
  for (const { c, a } of cmds) {
    const U = c.toUpperCase(), rel = c !== U;
    const b = a.slice();
    if (rel) {
      if (U === 'H') b[0] += x; else if (U === 'V') b[0] += y;
      else if (U === 'A') { b[5] += x; b[6] += y; }
      else for (let k = 0; k + 1 < b.length; k += 2) { b[k] += x; b[k + 1] += y; }
    }
    if (U === 'M') { x = b[0]; y = b[1]; sx = x; sy = y; }
    else if (U === 'Z') { x = sx; y = sy; }
    else if (U === 'H') x = b[0];
    else if (U === 'V') y = b[0];
    else { x = b[b.length - 2]; y = b[b.length - 1]; }
    out.push({ c: U, a: b });
  }
  return out;
}
const pathStr = (cmds) => cmds.map(({ c, a }) => c + a.map(r2).join(' ')).join(' ');
const pathSig = (cmds) => cmds.map((k) => k.c.toUpperCase()).join('');

function arcPoints(x1, y1, rx, ry, phiDeg, fa, fs2, x2, y2) {
  if (!rx || !ry) return [[x2, y2]];
  rx = Math.abs(rx); ry = Math.abs(ry);
  const phi = (phiDeg * Math.PI) / 180, cp = Math.cos(phi), sp = Math.sin(phi);
  const dx = (x1 - x2) / 2, dy = (y1 - y2) / 2;
  const x1p = cp * dx + sp * dy, y1p = -sp * dx + cp * dy;
  const lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry);
  if (lam > 1) { const s = Math.sqrt(lam); rx *= s; ry *= s; }
  const nu = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p;
  const de = rx * rx * y1p * y1p + ry * ry * x1p * x1p;
  let co = de ? Math.sqrt(Math.max(0, nu / de)) : 0;
  if (fa === fs2) co = -co;
  const cxp = (co * rx * y1p) / ry, cyp = (-co * ry * x1p) / rx;
  const cx = cp * cxp - sp * cyp + (x1 + x2) / 2, cy = sp * cxp + cp * cyp + (y1 + y2) / 2;
  const ang = (ux, uy, vx, vy) => {
    const d = Math.hypot(ux, uy) * Math.hypot(vx, vy) || 1;
    let a = Math.acos(Math.max(-1, Math.min(1, (ux * vx + uy * vy) / d)));
    if (ux * vy - uy * vx < 0) a = -a;
    return a;
  };
  const th1 = ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry);
  let dth = ang((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry);
  if (!fs2 && dth > 0) dth -= 2 * Math.PI; else if (fs2 && dth < 0) dth += 2 * Math.PI;
  const n = Math.max(4, Math.ceil(Math.abs(dth) / (Math.PI / 12)));
  const pts = [];
  for (let k = 1; k <= n; k++) {
    const t = th1 + (dth * k) / n;
    pts.push([cp * rx * Math.cos(t) - sp * ry * Math.sin(t) + cx, sp * rx * Math.cos(t) + cp * ry * Math.sin(t) + cy]);
  }
  pts[pts.length - 1] = [x2, y2];
  return pts;
}
const polyLen = (pts) => { let L = 0; for (let k = 1; k < pts.length; k++) L += Math.hypot(pts[k][0] - pts[k - 1][0], pts[k][1] - pts[k - 1][1]); return L; };
function flatten(cmds) {
  const subs = [];
  let cur = null, x = 0, y = 0, sx = 0, sy = 0, px = 0, py = 0, prev = '';
  const open = () => { if (!cur) { cur = [[x, y]]; subs.push(cur); } };
  for (const { c, a } of cmds) {
    const U = c.toUpperCase(), rel = c !== U, ox = rel ? x : 0, oy = rel ? y : 0;
    if (U === 'M') { x = a[0] + ox; y = a[1] + oy; sx = x; sy = y; cur = [[x, y]]; subs.push(cur); }
    else if (U === 'Z') { open(); cur.push([sx, sy]); x = sx; y = sy; cur = null; }
    else {
      open();
      if (U === 'L') { x = a[0] + ox; y = a[1] + oy; cur.push([x, y]); }
      else if (U === 'H') { x = a[0] + ox; cur.push([x, y]); }
      else if (U === 'V') { y = a[0] + oy; cur.push([x, y]); }
      else if (U === 'C' || U === 'S') {
        let x1, y1, x2, y2, x3, y3;
        if (U === 'C') [x1, y1, x2, y2, x3, y3] = [a[0] + ox, a[1] + oy, a[2] + ox, a[3] + oy, a[4] + ox, a[5] + oy];
        else { [x1, y1] = prev === 'C' || prev === 'S' ? [2 * x - px, 2 * y - py] : [x, y]; [x2, y2, x3, y3] = [a[0] + ox, a[1] + oy, a[2] + ox, a[3] + oy]; }
        for (let k = 1; k <= 16; k++) {
          const t = k / 16, u = 1 - t;
          cur.push([u * u * u * x + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t * t * t * x3, u * u * u * y + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t * t * t * y3]);
        }
        px = x2; py = y2; x = x3; y = y3;
      } else if (U === 'Q' || U === 'T') {
        let x1, y1, x2, y2;
        if (U === 'Q') [x1, y1, x2, y2] = [a[0] + ox, a[1] + oy, a[2] + ox, a[3] + oy];
        else { [x1, y1] = prev === 'Q' || prev === 'T' ? [2 * x - px, 2 * y - py] : [x, y]; [x2, y2] = [a[0] + ox, a[1] + oy]; }
        for (let k = 1; k <= 12; k++) {
          const t = k / 12, u = 1 - t;
          cur.push([u * u * x + 2 * u * t * x1 + t * t * x2, u * u * y + 2 * u * t * y1 + t * t * y2]);
        }
        px = x1; py = y1; x = x2; y = y2;
      } else if (U === 'A') {
        const ex = a[5] + ox, ey = a[6] + oy;
        for (const p of arcPoints(x, y, a[0], a[1], a[2], a[3], a[4], ex, ey)) cur.push(p);
        x = ex; y = ey;
      }
    }
    prev = U;
  }
  const good = subs.filter((s) => s.length > 1);
  return { subs: good, len: good.reduce((L, s) => L + polyLen(s), 0) };
}

const SKIP = new Set(['defs', 'clipPath', 'mask', 'symbol', 'marker', 'pattern', 'linearGradient', 'radialGradient', 'filter', 'style', 'title', 'desc', 'metadata', 'script']);
const LEAF = new Set(['rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'path', 'text', 'image', 'foreignObject']);

function leafGeom(node, env) {
  const a = node.attrs;
  switch (node.name) {
    case 'rect': case 'image': case 'foreignObject': {
      const x = pf(a.x), y = pf(a.y), w = pf(a.width), h = pf(a.height);
      if (!(w > 0 && h > 0)) return null;
      const rx = Math.min(w / 2, pf(a.rx ?? a.ry)), ry = Math.min(h / 2, pf(a.ry ?? a.rx));
      if (node.name !== 'rect' || !(rx > 0 && ry > 0)) return { subs: [[[x, y], [x + w, y], [x + w, y + h], [x, y + h], [x, y]]], len: 2 * (w + h) };
      const pts = [];
      for (const [cx, cy, a0] of [[x + w - rx, y + ry, -90], [x + w - rx, y + h - ry, 0], [x + rx, y + h - ry, 90], [x + rx, y + ry, 180]])
        for (let k = 0; k <= 6; k++) { const t = ((a0 + k * 15) * Math.PI) / 180; pts.push([cx + rx * Math.cos(t), cy + ry * Math.sin(t)]); }
      pts.push(pts[0]);
      return { subs: [pts], len: polyLen(pts) };
    }
    case 'circle': case 'ellipse': {
      const cx = pf(a.cx), cy = pf(a.cy);
      const rx = node.name === 'circle' ? pf(a.r) : pf(a.rx), ry = node.name === 'circle' ? pf(a.r) : pf(a.ry);
      if (!(rx > 0 && ry > 0)) return null;
      const pts = [];
      for (let k = 0; k <= 48; k++) { const t = (k / 48) * 2 * Math.PI; pts.push([cx + rx * Math.cos(t), cy + ry * Math.sin(t)]); }
      return { subs: [pts], len: polyLen(pts) };
    }
    case 'line': return { subs: [[[pf(a.x1), pf(a.y1)], [pf(a.x2), pf(a.y2)]]], len: Math.hypot(pf(a.x2) - pf(a.x1), pf(a.y2) - pf(a.y1)) };
    case 'polyline': case 'polygon': {
      const n = nums(a.points), pts = [];
      for (let k = 0; k + 1 < n.length; k += 2) pts.push([n[k], n[k + 1]]);
      if (pts.length < 2) return null;
      if (node.name === 'polygon') pts.push(pts[0]);
      return { subs: [pts], len: polyLen(pts) };
    }
    case 'path': { if (!a.d) return null; const f = flatten(parsePath(a.d)); return f.subs.length ? f : null; }
    case 'text': {
      const fsz = pf(styleOf(node, 'font-size', env), 16), chars = textOf(node).trim().length;
      if (!chars) return null;
      const w = 0.55 * fsz * chars, anchor = styleOf(node, 'text-anchor', env);
      const x = pf(nums(a.x)[0]), y = pf(nums(a.y)[0]);
      const x0 = anchor === 'middle' ? x - w / 2 : anchor === 'end' ? x - w : x;
      return { subs: [[[x0, y - 0.8 * fsz], [x0 + w, y - 0.8 * fsz], [x0 + w, y + 0.2 * fsz], [x0, y + 0.2 * fsz]]], len: 0, est: true };
    }
    default: return null;
  }
}
const newBox = () => ({ x0: Infinity, y0: Infinity, x1: -Infinity, y1: -Infinity, alpha: 0, n: 0 });
const boxArr = (b) => (b.n ? [b.x0, b.y0, b.x1 - b.x0, b.y1 - b.y0] : null);
const boxTxt = (b) => (b ? b.map((v) => Math.round(v * 10) / 10).join(',') : '-');
function measure(node, M, alpha, env, into, depth = 0, force = false) {
  if (node.type !== 'el' || (!force && SKIP.has(node.name))) return;
  const a = node.attrs;
  if (a.display === 'none' || styleOf(node, 'display', env) === 'none') return;
  if (a.transform) M = mul(M, parseTransform(a.transform));
  const op = pf(a.opacity ?? (a.style ? parseDecl(a.style).opacity : undefined), 1);
  alpha *= op;
  if (node.name === 'use') {
    const ref = env.byId.get(String(a.href ?? a['xlink:href'] ?? '').replace(/^#/, ''));
    if (ref && depth < 8) {
      const M2 = mul(M, [1, 0, 0, 1, pf(a.x), pf(a.y)]);
      if (ref.name === 'symbol') for (const c of ref.children) measure(c, M2, alpha, env, into, depth + 1);
      else measure(ref, M2, alpha, env, into, depth + 1, true);
    }
    return;
  }
  if (LEAF.has(node.name)) {
    if (styleOf(node, 'visibility', env) === 'hidden') return;
    const g = leafGeom(node, env);
    if (!g) return;
    const stroke = styleOf(node, 'stroke', env);
    const sw = stroke && stroke !== 'none' ? pf(styleOf(node, 'stroke-width', env), 1) : 0;
    const k = (Math.sqrt(Math.abs(M[0] * M[3] - M[1] * M[2])) * sw) / 2;
    for (const sub of g.subs) for (const p of sub) {
      const [x, y] = applyM(M, p);
      if (x - k < into.x0) into.x0 = x - k; if (y - k < into.y0) into.y0 = y - k;
      if (x + k > into.x1) into.x1 = x + k; if (y + k > into.y1) into.y1 = y + k;
      if (into.pts) into.pts.push(x, y);
    }
    into.n++;
    if (alpha > into.alpha) into.alpha = alpha;
    return;
  }
  for (const c of node.children) measure(c, M, alpha, env, into, depth);
}

// ───────────────────────────── art ─────────────────────────────

function indexTree(svg) {
  const byId = new Map(), dups = [];
  let cssText = '';
  walk(svg, (n) => {
    if (n.type !== 'el') return;
    if (n.attrs.id !== undefined) { if (byId.has(n.attrs.id)) dups.push(n.attrs.id); else byId.set(n.attrs.id, n); }
    if (n.name === 'style') cssText += textOf(n) + '\n';
  });
  return { byId, dups, css: parseCSS(cssText), cssText };
}
function loadArt(file) {
  if (!file) fail('no art file given');
  if (!fs.existsSync(file)) fail(`no such file: ${file}`);
  const src = fs.readFileSync(file, 'utf8');
  const doc = parseXML(src);
  const svg = rootEl(doc);
  if (!svg || svg.name !== 'svg') fail(`${file}: the root element must be <svg>`);
  const vb = nums(svg.attrs.viewBox);
  const art = { file, src, doc, svg, vb, W: vb[2] ?? pf(svg.attrs.width), H: vb[3] ?? pf(svg.attrs.height), ...indexTree(svg) };
  art.parts = partsOf(art);
  return art;
}
const insideSkip = (n) => { for (let p = n.parent; p && p.type === 'el'; p = p.parent) if (SKIP.has(p.name)) return true; return false; };
const isDrawable = (n) => n.type === 'el' && (n.name === 'g' || n.name === 'use' || LEAF.has(n.name));
function partsOf(art) { // Map id -> { id, el, parent, pivot, box }
  const parts = new Map();
  walk(art.svg, (n) => {
    if (n.type !== 'el' || n === art.svg) return;
    if (SKIP.has(n.name)) return false;
    if (n.attrs.id === undefined || !isDrawable(n) || art.byId.get(n.attrs.id) !== n) return;
    let parent = null;
    for (let p = n.parent; p && p.type === 'el'; p = p.parent) if (p.attrs.id !== undefined && parts.has(p.attrs.id)) { parent = p.attrs.id; break; }
    const b = newBox();
    measure(n, n.parent && n.parent.type === 'el' ? ctmOf(n.parent) : IDENT, 1, art, b);
    parts.set(n.attrs.id, { id: n.attrs.id, el: n, parent, pivot: applyM(ctmOf(n), [0, 0]), box: boxArr(b) });
  });
  return parts;
}

// ───────────────────────────── easing, values ─────────────────────────────

const EASES = { linear: null, in: [0.32, 0, 0.67, 0], out: [0.33, 1, 0.68, 1], inOut: [0.65, 0, 0.35, 1], back: [0.34, 1.56, 0.64, 1] };
const LIN = { kind: 'linear' };
function easeSpec(e) {
  if (e === undefined || e === null) return { kind: 'bezier', b: EASES.inOut };
  if (Array.isArray(e) && e.length === 4 && e.every((v) => typeof v === 'number')) return { kind: 'bezier', b: e };
  if (typeof e === 'string') {
    if (e === 'linear') return LIN;
    if (EASES[e]) return { kind: 'bezier', b: EASES[e] };
    const m = /^steps\((\d+)\)$/.exec(e);
    if (m && Number(m[1]) > 0) return { kind: 'steps', n: Number(m[1]) };
  }
  return null;
}
function easeFn(spec, p) {
  if (spec.kind === 'linear') return p;
  if (spec.kind === 'steps') return Math.min(1, Math.floor(p * spec.n + 1e-9) / spec.n);
  const [x1, y1, x2, y2] = spec.b;
  let lo = 0, hi = 1, u = p;
  for (let k = 0; k < 28; k++) {
    u = (lo + hi) / 2;
    const x = 3 * (1 - u) * (1 - u) * u * x1 + 3 * (1 - u) * u * u * x2 + u * u * u;
    if (x < p) lo = u; else hi = u;
  }
  return 3 * (1 - u) * (1 - u) * u * y1 + 3 * (1 - u) * u * u * y2 + u * u * u;
}
const cssEase = (s) => (s.kind === 'linear' ? 'linear' : s.kind === 'steps' ? `steps(${s.n}, end)` : `cubic-bezier(${s.b.map(r3).join(', ')})`);

const NAMED = { black: [0, 0, 0], white: [255, 255, 255], red: [255, 0, 0], green: [0, 128, 0], blue: [0, 0, 255], yellow: [255, 255, 0], orange: [255, 165, 0], purple: [128, 0, 128], pink: [255, 192, 203], gray: [128, 128, 128], grey: [128, 128, 128], silver: [192, 192, 192], gold: [255, 215, 0], navy: [0, 0, 128], teal: [0, 128, 128] };
function parseColor(s) {
  s = String(s).trim().toLowerCase();
  if (s === 'transparent') return [0, 0, 0, 0];
  if (NAMED[s]) return [...NAMED[s], 1];
  let m = /^#([0-9a-f]{3,8})$/.exec(s);
  if (m) {
    let h = m[1];
    if (h.length === 3 || h.length === 4) h = [...h].map((c) => c + c).join('');
    if (h.length !== 6 && h.length !== 8) return null;
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16), h.length === 8 ? parseInt(h.slice(6, 8), 16) / 255 : 1];
  }
  m = /^rgba?\(([^)]+)\)$/.exec(s);
  if (m) { const a = nums(m[1]); if (a.length >= 3) return [a[0], a[1], a[2], a[3] ?? 1]; }
  return null;
}
function lerpVal(a, b, p, chan) {
  if (typeof a === 'number') return a + (b - a) * p;
  if (chan === 'd') return a.map((k, i) => ({ c: k.c, a: k.a.map((v, j) => (k.c === 'A' && (j === 3 || j === 4) ? (p < 0.5 ? v : b[i].a[j]) : v + (b[i].a[j] - v) * p)) }));
  if (Array.isArray(a)) return a.map((v, i) => v + (b[i] - v) * p);
  const ca = parseColor(a), cb = parseColor(b);
  if (!ca || !cb) return p < 0.5 ? a : b;
  const c = ca.map((v, i) => v + (cb[i] - v) * p);
  return c[3] >= 0.999 ? `rgb(${Math.round(c[0])},${Math.round(c[1])},${Math.round(c[2])})` : `rgba(${Math.round(c[0])},${Math.round(c[1])},${Math.round(c[2])},${r2(c[3])})`;
}
function valueAt(tr, t) {
  const k = tr.keys;
  if (t <= k[0].t) return k[0].v;
  const last = k[k.length - 1];
  if (t >= last.t) return last.v;
  let i = 1;
  while (k[i].t < t) i++;
  const a = k[i - 1], b = k[i], span = b.t - a.t;
  return lerpVal(a.v, b.v, easeFn(b.ease, span > 0 ? (t - a.t) / span : 1), tr.chan);
}
const sameVal = (a, b) => (typeof a === 'number' && typeof b === 'number' ? Math.abs(a - b) < 1e-3 : JSON.stringify(a) === JSON.stringify(b));

// ───────────────────────────── presets ─────────────────────────────

const SIDE = { left: ['x', -1], right: ['x', 1], top: ['y', -1], bottom: ['y', 1] };
const tr = (chan, keys, opt = {}) => ({ chan, keys, ...opt });
const sideOf = (v, c) => SIDE[v] ?? (c.E(`side "${v}" must be left, right, top, or bottom`), SIDE.left);
const sign = (dir) => (dir === 'ccw' ? -1 : 1);

// kind: in (ends at the rest pose) | out (starts at it) | loop (repeats; period) | emph (one shot, rest to rest) | path
const PRESETS = {
  'fade-in': { kind: 'in', dur: 0.4, build: () => [tr('opacity', [[0, 0], [1, 1, 'out']])] },
  pop: { kind: 'in', dur: 0.45, params: { over: 1.12 }, build: ({ p }) => [tr('scale', [[0, 0], [0.6, p.over, 'out'], [1, 1, 'inOut']]), tr('opacity', [[0, 0], [0.3, 1, 'out']])] },
  grow: { kind: 'in', dur: 0.5, params: { axis: 'both' }, build: ({ p }) => [tr(p.axis === 'x' ? 'scaleX' : p.axis === 'y' ? 'scaleY' : 'scale', [[0, 0], [1, 1, 'out']])] },
  'slide-in': { kind: 'in', dur: 0.6, params: { from: 'left', dist: null }, build: (c) => { const d = c.p.dist ?? Math.round(0.15 * c.D), [ch, s] = sideOf(c.p.from, c); return [tr(ch, [[0, s * d], [1, 0, 'out']]), tr('opacity', [[0, 0], [0.6, 1, 'out']])]; } },
  drop: { kind: 'in', dur: 0.7, params: { dist: null }, build: ({ p, D }) => { const d = p.dist ?? Math.round(0.3 * D); return [tr('y', [[0, -d], [0.5, 0, 'in'], [0.72, -0.12 * d, 'out'], [1, 0, 'in']]), tr('opacity', [[0, 0], [0.15, 1, 'out']])]; } },
  draw: { kind: 'in', dur: 0.9, build: () => [tr('draw', [[0, 0], [1, 1, 'inOut']])] },
  wipe: { kind: 'in', dur: 0.6, params: { from: 'left' }, build: (c) => { sideOf(c.p.from, c); return [tr('wipe', [[0, 0], [1, 1, 'inOut']], { from: c.p.from })]; } },

  'fade-out': { kind: 'out', dur: 0.4, build: () => [tr('opacity', [[0, 1], [1, 0, 'in']])] },
  shrink: { kind: 'out', dur: 0.35, build: () => [tr('scale', [[0, 1], [1, 0, 'in']]), tr('opacity', [[0, 1], [0.6, 1, 'linear'], [1, 0, 'in']])] },
  'slide-out': { kind: 'out', dur: 0.5, params: { to: 'right', dist: null }, build: (c) => { const d = c.p.dist ?? Math.round(0.15 * c.D), [ch, s] = sideOf(c.p.to, c); return [tr(ch, [[0, 0], [1, s * d, 'in']]), tr('opacity', [[0, 1], [0.4, 1, 'linear'], [1, 0, 'in']])]; } },
  erase: { kind: 'out', dur: 0.7, build: () => [tr('draw', [[0, 1], [1, 0, 'inOut']])] },

  spin: { kind: 'loop', period: null, params: { turns: 1, dir: 'cw' }, build: ({ p }) => [tr('rotate', [[0, 0], [1, 360 * p.turns * sign(p.dir), 'linear']], { accumulate: true, mod: 360 })] },
  float: { kind: 'loop', period: 3, params: { amp: null }, build: ({ p, D }) => { const a = p.amp ?? r2(0.03 * D); return [tr('y', [[0, 0], [0.5, -a, 'inOut'], [1, 0, 'inOut']])]; } },
  pulse: { kind: 'loop', period: 1.6, params: { amp: 0.08 }, build: ({ p }) => [tr('scale', [[0, 1], [0.5, 1 + p.amp, 'inOut'], [1, 1, 'inOut']])] },
  sway: { kind: 'loop', period: 3, params: { amp: 6 }, build: ({ p }) => [tr('rotate', [[0, 0], [0.25, p.amp, 'out'], [0.5, 0, 'in'], [0.75, -p.amp, 'out'], [1, 0, 'in']])] },
  blink: { kind: 'loop', period: 3, build: () => [tr('scaleY', [[0, 1], [0.9, 1, 'linear'], [0.95, 0.1, 'in'], [1, 1, 'out']])] },
  wiggle: { kind: 'loop', period: 0.6, params: { amp: 4 }, build: ({ p }) => [tr('rotate', [[0, 0], [0.25, p.amp, 'inOut'], [0.75, -p.amp, 'inOut'], [1, 0, 'inOut']])] },
  march: { kind: 'loop', period: 1, params: { step: null, dir: 'cw' }, build: (c) => { const step = c.p.step ?? c.dashStep(); return [tr('dash', [[0, 0], [1, -step * sign(c.p.dir), 'linear']], { accumulate: true, mod: step })]; } },
  orbit: { kind: 'loop', period: null, params: { center: null, dir: 'cw' }, build: ({ p, D }) => {
    const [cx, cy] = p.center ?? [0, r2(0.1 * D)], keys = [];
    for (let k = 0; k <= 24; k++) {
      const t = (k / 24) * 2 * Math.PI * sign(p.dir), co = Math.cos(t), si = Math.sin(t);
      keys.push([k / 24, [r2(cx - (co * cx - si * cy)), r2(cy - (si * cx + co * cy))], 'linear']);
    }
    return [tr('xy', keys)];
  } },

  shake: { kind: 'emph', dur: 0.5, params: { amp: null }, build: ({ p, D }) => { const a = p.amp ?? r2(0.02 * D); return [tr('x', [[0, 0], [0.15, -a], [0.3, a], [0.45, -0.6 * a], [0.6, 0.6 * a], [0.8, -0.3 * a], [1, 0]])]; } },
  bounce: { kind: 'emph', dur: 0.7, params: { amp: null }, build: ({ p, D }) => { const h = p.amp ?? r2(0.08 * D); return [tr('y', [[0, 0], [0.3, -h, 'out'], [0.55, 0, 'in'], [0.75, -0.35 * h, 'out'], [1, 0, 'in']])]; } },
  flash: { kind: 'emph', dur: 0.6, build: () => [tr('opacity', [[0, 1], [0.25, 0.2], [0.5, 1], [0.75, 0.2], [1, 1]])] },
  nod: { kind: 'emph', dur: 0.5, params: { amp: 10 }, build: ({ p }) => [tr('rotate', [[0, 0], [0.4, p.amp, 'out'], [1, 0, 'inOut']])] },

  follow: { kind: 'path', dur: 2, params: { path: undefined, rotate: false, ease: 'inOut' }, build: (c) => c.along(c.p.path, [[0, 0], [1, 1, c.p.ease]], c.p.rotate) },
  morph: { kind: 'path', dur: 0.6, params: { to: undefined }, build: (c) => { const from = c.pathD(), to = c.refD(c.p.to); return from && to ? [tr('d', [[0, from], [1, to, 'inOut']])] : []; } },
};

const DOES = {
  "fade-in": "opacity 0 -> 1",
  "pop": "scale 0 -> over -> 1; opacity 0 -> 1 in the first 30%",
  "grow": "scale 0 -> 1 from the pivot; axis: x, y, or both",
  "slide-in": "x or y starts dist away on side \"from\" and ends at 0; opacity 0 -> 1 in the first 60%. dist: 15% of the short side",
  "drop": "y -dist -> 0 with one small rebound; opacity 0 -> 1 in the first 15%. dist: 30% of the short side",
  "draw": "the stroke draws from its start to its end; hidden before the clip",
  "wipe": "a clip rectangle opens from side \"from\"",
  "fade-out": "opacity 1 -> 0",
  "shrink": "scale 1 -> 0; opacity 1 -> 0 in the last 40%",
  "slide-out": "x or y 0 -> dist toward side \"to\"; opacity 1 -> 0 in the last 60%. dist: 15% of the short side",
  "erase": "the stroke undraws from its end to its start; hidden after the clip",
  "spin": "rotate 0 -> 360 x turns per period, linear. period: the whole clip",
  "float": "y 0 -> -amp -> 0. amp: 3% of the short side",
  "pulse": "scale 1 -> 1 + amp -> 1",
  "sway": "rotate 0 -> amp -> 0 -> -amp -> 0, in degrees",
  "blink": "scaleY 1 -> 0.1 -> 1 in the last 10% of each period",
  "wiggle": "rotate 0 -> amp -> -amp -> 0, in degrees",
  "march": "stroke-dashoffset shifts by one dash pattern (step) per period",
  "orbit": "the pivot circles once per period through its rest position; center: [dx, dy] from the pivot, default [0, 10% of the short side]",
  "shake": "x 0 -> -amp -> amp -> ... -> 0, decaying. amp: 2% of the short side",
  "bounce": "y 0 -> -amp -> 0 -> -0.35 x amp -> 0. amp: 8% of the short side",
  "flash": "opacity 1 -> 0.2 -> 1 -> 0.2 -> 1",
  "nod": "rotate 0 -> amp -> 0, in degrees",
  "follow": "the pivot travels along \"path\" (an id in the art, or a d string), measured from where the part sits; rotate: \"auto\" turns it along the path",
  "morph": "the part's one <path> changes its d to \"to\" (an id in the art, or a d string)"
};

// ───────────────────────────── score -> clips -> tracks ─────────────────────────────

const LAYER = { x: 'T', y: 'T', xy: 'T', rotate: 'R', scale: 'S', scaleX: 'S', scaleY: 'S', opacity: 'O' };
const LEAFCH = new Set(['fill', 'stroke', 'strokeWidth', 'draw', 'dash', 'd', 'wipe']);
const PROPS = ['x', 'y', 'rotate', 'scale', 'scaleX', 'scaleY', 'opacity', 'fill', 'stroke', 'strokeWidth', 'draw', 'd', 'along'];
const COMMON = new Set(['part', 'parts', 'stagger', 'preset', 'prop', 'keys', 'at', 'dur', 'beat', 'times', 'loop', 'period', 'offstage', 'path', 'rotate', 'note']);
const TOP = new Set(['canvas', 'duration', 'loop', 'beats', 'clips', 'checks', 'bg', 'note']);

function lev(a, b) {
  const d = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]);
  for (let j = 1; j <= b.length; j++) d[0][j] = j;
  for (let i = 1; i <= a.length; i++) for (let j = 1; j <= b.length; j++) d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
  return d[a.length][b.length];
}
function hint(name, pool) {
  let best = null, bd = Math.max(2, Math.ceil(String(name).length / 3)) + 1;
  for (const c of pool) { const d = lev(String(name), c); if (d < bd) { bd = d; best = c; } }
  return best ? ` Did you mean "${best}"?` : '';
}
function leafTargets(P, chan, env) {
  const out = [];
  walk(P, (n) => {
    if (n.type !== 'el') return;
    if (SKIP.has(n.name)) return false;
    if (!LEAF.has(n.name)) return;
    if (chan === 'd') { if (n.name === 'path') out.push(n); return; }
    const fill = styleOf(n, 'fill', env), stroke = styleOf(n, 'stroke', env);
    if (chan === 'fill') { if (fill !== 'none') out.push(n); } else if (stroke && stroke !== 'none') out.push(n);
  });
  return out;
}
function pathSampler(sub) { // fraction 0..1 of a polyline -> [x, y, tangentDeg]
  const cum = [0];
  for (let k = 1; k < sub.length; k++) cum.push(cum[k - 1] + Math.hypot(sub[k][0] - sub[k - 1][0], sub[k][1] - sub[k - 1][1]));
  const L = cum[cum.length - 1] || 1;
  return (f) => {
    const s = clamp01(f) * L;
    let k = 1;
    while (k < cum.length - 1 && cum[k] < s) k++;
    const seg = cum[k] - cum[k - 1] || 1, u = (s - cum[k - 1]) / seg, a = sub[k - 1], b = sub[k];
    return [a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, (Math.atan2(b[1] - a[1], b[0] - a[0]) * 180) / Math.PI];
  };
}

function normalize(art, score, issues) {
  const E = (m) => issues.push({ level: 'E', msg: m }), Wn = (m) => issues.push({ level: 'W', msg: m });
  if (!score || typeof score !== 'object' || Array.isArray(score)) { E('score: must be a JSON object'); return null; }
  for (const k of Object.keys(score)) if (!TOP.has(k)) Wn(`score: unknown field "${k}".${hint(k, [...TOP])}`);
  const { W, H } = art, D = Math.min(W, H);
  if (!Array.isArray(score.canvas) || score.canvas[0] !== W || score.canvas[1] !== H) E(`score.canvas ${JSON.stringify(score.canvas)} must equal the art's viewBox size [${W}, ${H}]`);
  const duration = score.duration;
  if (!(typeof duration === 'number' && duration > 0)) { E('score.duration: a number of seconds > 0 is required'); return null; }
  const loop = !!score.loop;
  const beats = {};
  for (const [name, b] of Object.entries(score.beats ?? {})) {
    if (!Array.isArray(b) || !(b[0] >= 0) || !(b[1] > b[0]) || b[1] > duration + 1e-6) E(`beat "${name}": needs [start, end] with 0 <= start < end <= ${duration}`);
    else beats[name] = b;
  }
  if (!Array.isArray(score.clips)) { E('score.clips: an array is required'); return null; }

  const clips = [], addTracks = [], leafSegs = new Map(), usedIds = new Map();
  let prev = { start: 0, end: 0 };
  const resolveAt = (at) => {
    if (typeof at === 'number') return at;
    const s = String(at).trim();
    let m = /^([<>])\s*([+-]?\s*\d*\.?\d+)?$/.exec(s);
    if (m) return (m[1] === '<' ? prev.start : prev.end) + (m[2] ? Number(m[2].replace(/\s/g, '')) : 0);
    m = /^([A-Za-z_][\w-]*)\s*([+-]\s*\d*\.?\d+)?$/.exec(s);
    if (m && beats[m[1]]) return beats[m[1]][0] + (m[2] ? Number(m[2].replace(/\s/g, '')) : 0);
    return /^[+-]?\d*\.?\d+$/.test(s) ? Number(s) : null;
  };

  score.clips.forEach((raw, idx) => {
    const where = `clip ${idx + 1}`;
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return E(`${where}: must be an object`);
    const partList = [].concat(raw.part ?? raw.parts ?? []);
    if (!partList.length) return E(`${where}: needs "part"`);
    let missing = false;
    for (const p of partList) if (!art.parts.has(p)) { E(`${where}: art has no part "${p}".${hint(p, [...art.parts.keys()])}`); missing = true; }
    if (missing) return;
    const what = raw.preset ?? (raw.prop !== undefined ? `${raw.prop} keys` : '?');
    const tag = `${where} (${partList.join(',')} ${what})`;
    const cE = (m) => E(`${tag}: ${m}`), cW = (m) => Wn(`${tag}: ${m}`);

    let P = null, params = {}, keys = null;
    if (raw.preset !== undefined) {
      P = PRESETS[raw.preset];
      if (!P) return E(`${where}: unknown preset "${raw.preset}".${hint(raw.preset, Object.keys(PRESETS))} Run "presets" for the list.`);
      params = { ...(P.params ?? {}) };
      for (const [k, v] of Object.entries(raw)) {
        if (P.params && k in P.params) params[k] = v;
        else if (!COMMON.has(k)) cW(`unknown field "${k}". ${raw.preset} takes: ${Object.keys(P.params ?? {}).join(', ') || 'no parameters'}`);
      }
      for (const [k, v] of Object.entries(params)) if (v === undefined) return cE(`needs "${k}"`);
      if (raw.keys !== undefined) cW('"keys" is ignored on a preset clip');
      if (raw.period !== undefined && P.kind !== 'loop') cW('"period" only applies to loop presets');
      if (raw.times !== undefined && P.kind === 'loop') cW('"times" does not apply to loop presets; set "dur" or "period"');
    } else if (raw.prop !== undefined) {
      if (!PROPS.includes(raw.prop)) return cE(`unknown prop "${raw.prop}".${hint(raw.prop, PROPS)} Props: ${PROPS.join(' ')}`);
      for (const k of Object.keys(raw)) if (!COMMON.has(k)) cW(`unknown field "${k}"`);
      if (!Array.isArray(raw.keys) || raw.keys.length < 2) return cE('"keys" needs at least two [t, value, ease?] entries');
      let last = -1;
      for (const k of raw.keys) {
        if (!Array.isArray(k) || typeof k[0] !== 'number' || k.length < 2) return cE(`bad key ${JSON.stringify(k)}; write [t, value, ease?]`);
        if (k[0] <= last) return cE('key times must increase');
        if (k[2] !== undefined && !easeSpec(k[2])) return cE(`unknown ease ${JSON.stringify(k[2])}. Eases: linear in out inOut back steps(n) [x1,y1,x2,y2]`);
        if (['fill', 'stroke'].includes(raw.prop) ? typeof k[1] !== 'string' : raw.prop === 'd' ? typeof k[1] !== 'string' : typeof k[1] !== 'number') return cE(`key value ${JSON.stringify(k[1])} is the wrong type for ${raw.prop}`);
        last = k[0];
      }
      if (raw.keys[0][0] !== 0) return cE('the first key must be at t = 0 (times are relative to the clip start)');
      keys = raw.keys;
      if (raw.prop === 'along' && raw.path === undefined) return cE('prop "along" needs "path": the id of a <path> in the art, or a d string');
    } else return cE('needs "preset", or "prop" with "keys"');

    const beat = raw.beat !== undefined ? beats[raw.beat] : null;
    if (raw.beat !== undefined && !beat) return cE(`no beat "${raw.beat}".${hint(raw.beat, Object.keys(beats))}`);
    let start = beat ? beat[0] : 0;
    if (raw.at !== undefined) { const s = resolveAt(raw.at); if (s === null) return cE(`cannot read "at": ${JSON.stringify(raw.at)}. Use seconds, "<", ">", "<0.2", ">0.2", or a beat name`); start = s; }
    if (start < 0) return cE(`starts before 0 (${r2(start)}s)`);
    const rangeEnd = beat ? beat[1] : duration;
    const isLoop = P ? P.kind === 'loop' : !!raw.loop;
    const span = keys ? keys[keys.length - 1][0] : null;
    let unit, cycles, total;
    if (isLoop) {
      total = raw.dur ?? rangeEnd - start;
      if (!(total > 0)) return cE(`starts at ${r2(start)}s with nothing left before ${r2(rangeEnd)}s`);
      const fixed = keys ? span : raw.period;
      if (fixed !== undefined && fixed !== null) {
        const c = total / fixed;
        if (!(fixed > 0) || c < 1 - 1e-6 || Math.abs(c - Math.round(c)) > 1e-6) {
          const opts = [...new Set([Math.floor(c), Math.ceil(c), Math.round(c) + 1].filter((n) => n >= 1).map((n) => r3(total / n)))].join('s, ');
          return cE(`a loop needs a whole number of cycles: ${keys ? 'key span' : 'period'} ${fixed}s does not divide ${r3(total)}s. Use ${opts}s`);
        }
        unit = fixed; cycles = Math.round(c);
      } else { cycles = Math.max(1, Math.round(total / (P.period ?? total))); unit = total / cycles; }
    } else {
      unit = keys ? span : raw.dur ?? P.dur;
      if (keys && raw.dur !== undefined) cW('"dur" is ignored on a keys clip; the last key time sets the length');
      cycles = raw.times ?? 1;
      if (!(Number.isInteger(cycles) && cycles >= 1)) return cE('"times" must be a whole number >= 1');
      if (P && beat && raw.dur === undefined && unit * cycles > beat[1] - start) unit = (beat[1] - start) / cycles;
      if (!(unit > 0)) return cE('duration must be > 0');
      total = unit * cycles;
    }
    const stag = raw.stagger ?? 0;
    let groupEnd = start;

    partList.forEach((pid, k) => {
      const s = start + k * stag, e = s + total;
      if (e > duration + 1e-6) cE(`${pid} ends at ${r2(e)}s, past duration ${duration}s`);
      groupEnd = Math.max(groupEnd, e);
      const base = `${pid}-${raw.preset ?? raw.prop}`, nth = (usedIds.get(base) ?? 0) + 1;
      usedIds.set(base, nth);
      const id = nth > 1 ? `${base}-${nth}` : base;
      const part = art.parts.get(pid), Pel = part.el;
      const ctx = {
        p: params, D, W, H, E: cE, W_: cW,
        dashStep: () => { const t = leafTargets(Pel, 'stroke', art)[0]; const sum = t ? nums(styleOf(t, 'stroke-dasharray', art)).reduce((x, y) => x + y, 0) : 0; if (!sum) cE(`${pid} has no stroke-dasharray to march; set one in the art or give "step"`); return sum || 8; },
        pathD: () => { const t = leafTargets(Pel, 'd', art); if (t.length !== 1) { cE(`${pid} must contain exactly one <path> to morph (found ${t.length})`); return null; } return t[0].attrs.d; },
        refD: (ref) => { const n = art.byId.get(String(ref)); if (n) { if (n.name !== 'path') { cE(`"${ref}" is a <${n.name}>, not a <path>`); return null; } return n.attrs.d; } return String(ref); },
        along: (ref, progKeys, autoRotate) => {
          const node = art.byId.get(String(ref));
          let sub, M = IDENT;
          try {
            if (node) { const g = leafGeom(node, art); if (!g) { cE(`path "${ref}" has no geometry`); return []; } sub = g.subs[0]; M = ctmOf(node); }
            else sub = flatten(parsePath(String(ref))).subs[0];
          } catch (err) { cE(`"path": ${err.message}`); return []; }
          if (!sub) { cE(`"path" ${JSON.stringify(ref)} is neither an id in the art nor a d string`); return []; }
          const at = pathSampler(sub.map((q) => applyM(M, q)));
          const inv = inv2(Pel.parent && Pel.parent.type === 'el' ? ctmOf(Pel.parent) : IDENT);
          const prog = { chan: 'n', keys: progKeys.map(([u, v, ez]) => ({ t: u, v, ease: easeSpec(ez) ?? LIN })) };
          const N = Math.max(12, Math.min(60, Math.round(unit * 24)));
          const p0 = at(valueAt(prog, 0)), xy = [], rot = [];
          let lastA = null;
          for (let q = 0; q <= N; q++) {
            const u = q / N, [x, y, ang] = at(valueAt(prog, u));
            const dl = applyM(inv, [x - p0[0], y - p0[1]]);
            xy.push([u, [r2(dl[0]), r2(dl[1])], 'linear']);
            let a = ang;
            if (lastA !== null) while (a - lastA > 180) a -= 360;
            if (lastA !== null) while (a - lastA < -180) a += 360;
            lastA = a;
            rot.push([u, r2(a), 'linear']);
          }
          const d0 = Math.hypot(part.pivot[0] - p0[0], part.pivot[1] - p0[1]);
          if (d0 > Math.max(2, 0.02 * D)) cW(`${pid}'s pivot (${boxTxt(part.pivot)}) is ${r2(d0)} away from the path start (${boxTxt(p0.slice(0, 2))}); it follows the path's shape from where it sits`);
          return autoRotate === 'auto' || autoRotate === true ? [tr('xy', xy), tr('rotate', rot)] : [tr('xy', xy)];
        },
      };
      let built;
      if (P) built = P.build(ctx);
      else if (raw.prop === 'along') built = ctx.along(raw.path, keys.map(([t, v, ez]) => [t / unit, v, ez]), raw.rotate);
      else built = [tr(raw.prop, keys.map(([t, v, ez]) => [t / unit, v, ez]))];

      const kind = P ? P.kind : isLoop ? 'loop' : 'keys';
      const shown = P ? Object.entries(raw).filter(([kk]) => P.params && kk in P.params).map(([kk, v]) => `${kk}=${Array.isArray(v) ? v.join(',') : v}`).join(' ') : '';
      clips.push({ id, part: pid, what, kind, start: s, end: e, unit, cycles, shown, offstage: !!raw.offstage });

      for (const b of built) {
        const out = [];
        let conv = (v) => v;
        if (b.chan === 'd') {
          let sig = null;
          conv = (v) => { const c = absPath(parsePath(v)); const g = pathSig(c); if (sig === null) sig = g; else if (g !== sig) fail(`both sides of a morph need the same commands: ${sig} vs ${g}`); return c; };
        }
        try {
          const first = conv(b.keys[0][1]), lastV = conv(b.keys[b.keys.length - 1][1]);
          for (let c = 0; c < cycles; c++) {
            for (const [u, v0, ez] of b.keys) {
              let v = conv(v0);
              if (b.accumulate && c > 0) v = v + c * (lastV - first);
              let t = s + (c + u) * unit;
              if (c > 0 && u === 0) { if (sameVal(out[out.length - 1].v, v)) continue; t += 0.001; }
              const spec = easeSpec(ez);
              out.push({ t, v, ease: spec ?? LIN });
            }
          }
        } catch (err) { if (err instanceof Fail) { cE(err.message); continue; } throw err; }
        if (b.chan === 'opacity') for (const kk of out) kk.v = clamp01(kk.v);
        if (LAYER[b.chan]) addTracks.push({ id: id.endsWith(`-${b.chan}`) ? id : `${id}-${b.chan === 'xy' ? 'path' : b.chan}`, part: pid, chan: b.chan, keys: out, clip: id, mod: b.mod ?? null });
        else {
          const key = `${pid}|${b.chan}`;
          if (!leafSegs.has(key)) leafSegs.set(key, []);
          leafSegs.get(key).push({ start: s, end: e, keys: out, tag, from: b.from, mod: b.mod ?? null });
        }
      }

      // per-part sanity
      const chans = built.map((b) => b.chan);
      if (chans.some((c) => LAYER[c] === 'R' || LAYER[c] === 'S')) {
        const lb = newBox();
        if (Pel.name === 'g') for (const c of Pel.children) measure(c, IDENT, 1, art, lb); else measure(Pel, inv2(IDENT), 1, art, lb);
        const bb = boxArr(lb);
        const origin = Pel.name === 'g' || Pel.attrs.transform ? null : 'parent';
        if (bb) {
          const o = Pel.name === 'g' ? [0, 0] : applyM(parseTransform(Pel.attrs.transform), [0, 0]);
          const m = 0.5 * Math.max(bb[2], bb[3]) + 1;
          if (o[0] < bb[0] - m || o[0] > bb[0] + bb[2] + m || o[1] < bb[1] - m || o[1] > bb[1] + bb[3] + m)
            cW(`${pid} rotates or scales about its pivot at ${boxTxt(part.pivot)}, which is far outside its box ${boxTxt(part.box)}. ${origin ? `Give it a pivot: wrap it in <g id="${pid}" transform="translate(x y)"> with the geometry around (0,0), or use rig.` : `Draw the geometry around (0,0) of <g id="${pid}">, or re-pivot with rig.`}`);
        }
      }
      for (const c of chans) {
        if (c === 'draw' || c === 'dash' || c === 'stroke' || c === 'strokeWidth') {
          const t = leafTargets(Pel, 'stroke', art);
          if (!t.length) cE(`${pid} has no stroked geometry for "${c}" (needs stroke set and not "none")`);
          else if (c === 'draw' && t.some((n) => styleOf(n, 'fill', art) !== 'none')) cW(`${pid}: draw reveals the stroke only; a shape with a fill shows its fill from the start. Set fill="none"`);
          if (Pel.name === 'use') cE(`${pid} is a <use>; "${c}" needs real geometry`);
        }
        if (c === 'fill' && !leafTargets(Pel, 'fill', art).length) cE(`${pid} has no filled geometry for "fill"`);
      }
    });
    prev = { start, end: groupEnd };
  });

  // merge leaf-channel segments into one track per (part, channel)
  const tracks = [...addTracks];
  for (const [key, segs] of leafSegs) {
    const [pid, chan] = key.split('|');
    segs.sort((a, b) => a.start - b.start);
    const keys = [];
    for (let k = 0; k < segs.length; k++) {
      const sgm = segs[k];
      if (k > 0 && sgm.start < segs[k - 1].end - 1e-6) { E(`${sgm.tag}: overlaps ${segs[k - 1].tag} on ${pid}.${chan} (${r2(sgm.start)}s < ${r2(segs[k - 1].end)}s). One ${chan} clip at a time per part`); continue; }
      if (keys.length && !sameVal(keys[keys.length - 1].v, sgm.keys[0].v)) keys.push({ t: Math.max(keys[keys.length - 1].t, sgm.keys[0].t - 0.001), v: keys[keys.length - 1].v, ease: LIN });
      keys.push(...sgm.keys);
    }
    if (keys.length) tracks.push({ id: `${pid}-${chan}`, part: pid, chan, keys, clip: null, mod: segs[0].mod, from: segs[0].from });
  }
  for (const pid of new Set(tracks.map((t) => t.part))) {
    const ch = new Set(tracks.filter((t) => t.part === pid).map((t) => t.chan));
    if (ch.has('draw') && ch.has('dash')) E(`${pid}: draw and march both drive stroke-dashoffset; use one`);
  }
  if (!clips.length) Wn('score.clips is empty: nothing moves');
  return { W, H, D, duration, loop, beats, clips, tracks, checks: score.checks ?? [], bg: score.bg ?? '#ffffff' };
}
const show = (v) => (typeof v === 'number' ? String(r2(v)) : Array.isArray(v) && typeof v[0] === 'number' ? v.map(r2).join(',') : typeof v === 'string' ? v : '(path)');

// ───────────────────────────── rig tree (shared by compile and snapshot) ─────────────────────────────

function buildRig(art, norm) {
  const doc = clone(art.doc), svg = rootEl(doc), idx = indexTree(svg);
  const env = { byId: idx.byId, css: idx.css };
  const R = { doc, svg, env, wraps: [], leaves: [], wipes: [], top: new Map() };
  for (const pid of art.parts.keys()) R.top.set(pid, idx.byId.get(pid));
  const byPart = new Map();
  for (const t of norm.tracks) { if (!byPart.has(t.part)) byPart.set(t.part, []); byPart.get(t.part).push(t); }
  for (const [pid, tracks] of byPart) {
    const P = idx.byId.get(pid);
    for (const t of tracks) if (LEAFCH.has(t.chan) && t.chan !== 'wipe') {
      const els = leafTargets(P, t.chan === 'fill' || t.chan === 'd' ? t.chan : 'stroke', env);
      R.leaves.push({ els: t.chan === 'd' ? els.slice(0, 1) : els, track: t, lens: els.map((n) => leafGeom(n, env)?.len ?? 0) });
    }
    const inner = ['R', 'S', 'O'].flatMap((L) => tracks.filter((t) => LAYER[t.chan] === L));
    const outer = tracks.filter((t) => LAYER[t.chan] === 'T');
    const wipe = tracks.find((t) => t.chan === 'wipe');
    let top = P;
    if (inner.length || wipe) {
      let host, content;
      if (P.name === 'g') { host = P; content = P.children; P.children = []; }
      else { host = mk('g', P.attrs.transform ? { transform: P.attrs.transform } : {}); swap(P, host); delete P.attrs.transform; content = [P]; top = host; }
      let cur = host;
      for (const t of inner) { cur = adopt(cur, mk('g')); R.wraps.push({ el: cur, track: t }); }
      if (wipe) {
        const b = newBox();
        for (const c of content) measure(c, IDENT, 1, env, b);
        const bb = boxArr(b) ?? [0, 0, 1, 1], pad = 2;
        const cp = adopt(cur, mk('clipPath', { id: `${pid}-wipe` }));
        const rect = adopt(cp, mk('rect'));
        cur = adopt(cur, mk('g', { 'clip-path': `url(#${pid}-wipe)` }));
        R.wipes.push({ rect, track: wipe, box: [bb[0] - pad, bb[1] - pad, bb[2] + 2 * pad, bb[3] + 2 * pad] });
      }
      for (const c of content) adopt(cur, c);
    }
    if (outer.length) {
      const first = mk('g');
      swap(top, first);
      let cur = first;
      R.wraps.push({ el: first, track: outer[0] });
      for (const t of outer.slice(1)) { cur = adopt(cur, mk('g')); R.wraps.push({ el: cur, track: t }); }
      adopt(cur, top);
      top = first;
    }
    R.top.set(pid, top);
  }
  return R;
}
const wipeRect = ([x, y, w, h], from, v) => (from === 'right' ? [x + w * (1 - v), y, w * v, h] : from === 'top' ? [x, y, w, h * v] : from === 'bottom' ? [x, y + h * (1 - v), w, h * v] : [x, y, w * v, h]);

function applyAt(R, t) {
  for (const { el, track } of R.wraps) {
    const v = valueAt(track, t);
    switch (track.chan) {
      case 'x': el.attrs.transform = `translate(${r3(v)} 0)`; break;
      case 'y': el.attrs.transform = `translate(0 ${r3(v)})`; break;
      case 'xy': el.attrs.transform = `translate(${r3(v[0])} ${r3(v[1])})`; break;
      case 'rotate': el.attrs.transform = `rotate(${r3(v)})`; break;
      case 'scale': el.attrs.transform = `scale(${r3(v)})`; break;
      case 'scaleX': el.attrs.transform = `scale(${r3(v)} 1)`; break;
      case 'scaleY': el.attrs.transform = `scale(1 ${r3(v)})`; break;
      case 'opacity': el.attrs.opacity = String(r3(clamp01(v))); break;
    }
  }
  for (const { els, track, lens } of R.leaves) {
    const v = valueAt(track, t);
    els.forEach((el, i) => {
      if (track.chan === 'fill') setStyle(el, 'fill', v);
      else if (track.chan === 'stroke') setStyle(el, 'stroke', v);
      else if (track.chan === 'strokeWidth') setStyle(el, 'stroke-width', String(r3(v)));
      else if (track.chan === 'dash') setStyle(el, 'stroke-dashoffset', String(r3(v)));
      else if (track.chan === 'd') el.attrs.d = pathStr(v);
      else if (track.chan === 'draw') {
        const L = lens[i] || 1;
        setStyle(el, 'visibility', v <= 0.0005 ? 'hidden' : null);
        setStyle(el, 'stroke-dasharray', v >= 0.9995 ? null : `${r3(L)} ${r3(L)}`);
        setStyle(el, 'stroke-dashoffset', v >= 0.9995 ? null : String(r3(L * (1 - v))));
      }
    });
  }
  for (const { rect, track, box } of R.wipes) {
    const [x, y, w, h] = wipeRect(box, track.from, clamp01(valueAt(track, t)));
    Object.assign(rect.attrs, { x: String(r3(x)), y: String(r3(y)), width: String(r3(Math.max(0, w))), height: String(r3(Math.max(0, h))) });
  }
}
function partState(R, pid, withPts = false) {
  const node = R.top.get(pid);
  let alpha = 1;
  for (let n = node.parent; n && n.type === 'el'; n = n.parent) alpha *= pf(n.attrs.opacity, 1);
  const b = newBox();
  if (withPts) b.pts = [];
  measure(node, node.parent && node.parent.type === 'el' ? ctmOf(node.parent) : IDENT, alpha, R.env, b);
  let wiped = false;
  for (const w of R.wipes) if (w.track.part === pid && (pf(w.rect.attrs.width) < 0.01 || pf(w.rect.attrs.height) < 0.01)) wiped = true;
  const box = boxArr(b);
  return { box, alpha: b.alpha, visible: !!box && b.alpha > 0.02 && !wiped, pts: b.pts };
}
function seamIssues(art, norm, issues) { // a loop is judged by what shows, not channel by channel: hidden at both ends is seamless
  if (!norm.loop) return;
  const R = buildRig(art, norm), T = norm.duration;
  const ids = [...new Set(norm.tracks.map((t) => t.part))];
  const grab = (t) => { applyAt(R, t); return new Map(ids.map((id) => [id, partState(R, id, true)])); };
  const a = grab(0), b = grab(T);
  for (const id of ids) {
    const s0 = a.get(id), s1 = b.get(id);
    if (!s0.visible && !s1.visible) continue;
    const E = (m) => issues.push({ level: 'E', msg: `loop seam: ${id} ${m}. A looping score must end as it starts: add an out clip, let the part start visible, or set "loop": false` });
    if (s0.visible !== s1.visible) { E(`is ${s1.visible ? 'visible' : 'hidden'} at ${T}s but ${s0.visible ? 'visible' : 'hidden'} at 0s`); continue; }
    if (Math.abs(s0.alpha - s1.alpha) > 0.02) { E(`has opacity ${r2(s1.alpha)} at ${T}s but ${r2(s0.alpha)} at 0s`); continue; }
    let d = s0.pts.length === s1.pts.length ? 0 : Infinity;
    for (let k = 0; k < s0.pts.length && d < Infinity; k++) d = Math.max(d, Math.abs(s0.pts[k] - s1.pts[k]));
    if (d > 0.3) { E(`sits at box ${boxTxt(s1.box)} at ${T}s but ${boxTxt(s0.box)} at 0s`); continue; }
    for (const t of norm.tracks) {
      if (t.part !== id || !LEAFCH.has(t.chan) || t.chan === 'wipe') continue;
      const v0 = valueAt(t, 0), v1 = valueAt(t, T);
      const m = t.mod && typeof v0 === 'number' ? (((v1 - v0) % t.mod) + t.mod) % t.mod : null;
      if (m !== null ? !(m < 1e-3 || t.mod - m < 1e-3) : !sameVal(v0, v1)) E(`${t.chan} is ${show(v1)} at ${T}s but ${show(v0)} at 0s`);
    }
  }
}

// ───────────────────────────── lint ─────────────────────────────

function lintArt(art, issues) {
  const E = (m) => issues.push({ level: 'E', msg: m }), Wn = (m) => issues.push({ level: 'W', msg: m });
  const { svg, vb } = art;
  if (vb.length !== 4) E('<svg> needs viewBox="0 0 W H"');
  else if (vb[0] !== 0 || vb[1] !== 0) E(`viewBox must start at 0 0 (found "${svg.attrs.viewBox}"). rig rewrites it`);
  if (svg.attrs.width !== undefined || svg.attrs.height !== undefined) Wn('remove width/height from <svg>; the viewBox sizes it');
  for (const id of new Set(art.dups)) E(`duplicate id "${id}"`);
  let decimals = 0, sample = null;
  walk(svg, (n) => {
    if (n.type !== 'el') return;
    if (['animate', 'animateTransform', 'animateMotion', 'set', 'script'].includes(n.name)) E(`art must be static: remove <${n.name}> (motion belongs in the score)`);
    for (const [k, v] of Object.entries(n.attrs)) {
      for (const m of String(v).matchAll(/url\(\s*['"]?#([^)'"\s]+)/g)) if (!art.byId.has(m[1])) E(`<${n.name}${n.attrs.id ? ` id="${n.attrs.id}"` : ''}> ${k} points at missing id "${m[1]}"`);
      if ((k === 'href' || k === 'xlink:href') && String(v).startsWith('#') && !art.byId.has(String(v).slice(1))) E(`<${n.name}> ${k} points at missing id "${String(v).slice(1)}"`);
      if (['d', 'points', 'x', 'y', 'cx', 'cy', 'r', 'rx', 'ry', 'x1', 'y1', 'x2', 'y2', 'width', 'height', 'transform'].includes(k)) {
        const long = String(v).match(/\d\.\d{2,}/g);
        if (long) { decimals += long.length; sample ??= `${n.name}${n.attrs.id ? `#${n.attrs.id}` : ''} ${k}: ${long[0]}…`; }
      }
      if (k === 'style' && /transform-origin/.test(v)) Wn(`<${n.name}> sets transform-origin; the pivot is the part's local (0,0)`);
    }
    if (n.name === 'path' && n.attrs.d && !insideSkip(n)) {
      try { const c = parsePath(n.attrs.d).length; if (c > 12) Wn(`path${n.attrs.id ? ` #${n.attrs.id}` : ''} has ${c} commands (budget 12): split it, or use an asset`); }
      catch (err) { if (err instanceof Fail) E(`path${n.attrs.id ? ` #${n.attrs.id}` : ''}: ${err.message}`); else throw err; }
    }
    if (n.attrs.id !== undefined && /^(path|g|rect|circle|ellipse|group|layer|shape|svg|polygon|line)[-_ ]?\d*$/i.test(n.attrs.id) && !insideSkip(n)) Wn(`id "${n.attrs.id}" says nothing; name the part for what it is`);
  });
  if (/@keyframes|animation\s*:/.test(art.cssText)) E('art must be static: remove @keyframes and animation from <style> (motion belongs in the score)');
  if (/transform-origin/.test(art.cssText)) Wn("<style> sets transform-origin; the pivot is the part's local (0,0)");
  if (decimals) Wn(`${decimals} number${decimals > 1 ? 's' : ''} with 2+ decimals (${sample}); round to at most 1`);
  for (const p of art.parts.values()) {
    const decl = nums(p.el.attrs['data-box']);
    if (p.el.attrs['data-box'] !== undefined) {
      if (decl.length !== 4) Wn(`${p.id}: data-box must be "x y w h"`);
      else if (!p.box) Wn(`${p.id}: declares data-box but draws nothing`);
      else {
        const tol = Math.max(2, 0.06 * Math.max(decl[2], decl[3]));
        const d = [p.box[0] - decl[0], p.box[1] - decl[1], p.box[2] - decl[2], p.box[3] - decl[3]];
        if (d.some((v) => Math.abs(v) > tol)) Wn(`${p.id}: drawn box ${boxTxt(p.box)} differs from data-box ${decl.join(',')} (dx ${r2(d[0])}, dy ${r2(d[1])}, dw ${r2(d[2])}, dh ${r2(d[3])})`);
      }
    }
    if (p.box && vb.length === 4) {
      const over = canvasOver(p.box, art.W, art.H);
      if (over) Wn(`${p.id}: rest box ${boxTxt(p.box)} leaves the canvas (${over})`);
    }
  }
  const hasTitle = svg.children.some((c) => c.type === 'el' && c.name === 'title');
  if (!hasTitle && svg.attrs['aria-hidden'] === undefined && svg.attrs['aria-label'] === undefined) Wn('add <title> as the first child of <svg>, or aria-hidden="true" if it is decorative');
  const kb = Buffer.byteLength(art.src) / 1024, budget = Math.max(art.W, art.H) <= 48 ? 4 : 30;
  if (kb > budget) Wn(`art is ${r2(kb)} KB (budget ${budget} KB for this canvas)`);
}
function canvasOver([x, y, w, h], W, H) {
  const o = [];
  if (x < -0.5) o.push(`left ${r2(-x)}`);
  if (y < -0.5) o.push(`top ${r2(-y)}`);
  if (x + w > W + 0.5) o.push(`right ${r2(x + w - W)}`);
  if (y + h > H + 0.5) o.push(`bottom ${r2(y + h - H)}`);
  return o.join(', ');
}
function readScore(file, issues) {
  if (!fs.existsSync(file)) fail(`no such file: ${file}`);
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); }
  catch (err) { issues.push({ level: 'E', msg: `score: not valid JSON: ${err.message}` }); return null; }
}
function printIssues(issues) {
  for (const i of issues) console.log(`${i.level}  ${i.msg}`);
  const e = issues.filter((i) => i.level === 'E').length, w = issues.length - e;
  console.log(`${e} error${e === 1 ? '' : 's'}, ${w} warning${w === 1 ? '' : 's'}`);
  return e;
}
function partsTable(art) {
  const rows = [...art.parts.values()].map((p) => [p.id, p.el.name, `pivot ${boxTxt(p.pivot)}`, `box ${boxTxt(p.box)}`, p.parent ? `in ${p.parent}` : '']);
  const w = [0, 1, 2, 3].map((c) => Math.max(...rows.map((r) => r[c].length), 0));
  return rows.map((r) => '  ' + r.map((c, i) => (i < 4 ? c.padEnd(w[i] + 2) : c)).join('').trimEnd()).join('\n');
}
function timelineText(norm) {
  const w = Math.max(...norm.clips.map((c) => c.part.length), 4);
  return norm.clips.map((c) => `  ${c.start.toFixed(2)}-${c.end.toFixed(2)}  ${c.part.padEnd(w)}  ${c.what}${c.shown ? ' ' + c.shown : ''}${c.cycles > 1 ? ` x${c.cycles} (${r2(c.unit)}s each)` : ''}`).join('\n');
}

// ───────────────────────────── checks ─────────────────────────────

function makeSampler(art, norm) {
  const R = buildRig(art, norm);
  const ids = [...art.parts.keys()];
  const cache = new Map();
  return {
    R,
    at(t) {
      const key = Math.round(t * 1000);
      if (!cache.has(key)) { applyAt(R, t); cache.set(key, new Map(ids.map((id) => [id, partState(R, id)]))); }
      return cache.get(key);
    },
    set(t) { applyAt(R, t); },
  };
}
function runChecks(art, norm, S) {
  const out = [];
  const T = norm.duration;
  const timeOf = (v) => (v === undefined ? null : v === 'start' ? 0 : v === 'end' ? T : typeof v === 'number' ? v : norm.beats[v] ? norm.beats[v][0] : null);
  const rangeOf = (v) => (v === undefined ? [0, T] : Array.isArray(v) ? v : norm.beats[v] ?? null);
  const samples = ([a, b]) => { const n = Math.max(2, Math.round((b - a) * 30)); return Array.from({ length: n + 1 }, (_, k) => a + ((b - a) * k) / n); };
  const need = (id) => { if (!art.parts.has(id)) throw new Fail(`no part "${id}"`); return id; };
  const center = (b) => [b[0] + b[2] / 2, b[1] + b[3] / 2];
  const enter = (id) => { const cs = norm.clips.filter((c) => c.part === id); const ins = cs.filter((c) => c.kind === 'in'); const pool = ins.length ? ins : cs; return pool.length ? Math.min(...pool.map((c) => c.start)) : 0; };
  for (const [i, c] of norm.checks.entries()) {
    const label = JSON.stringify(c);
    try {
      if (!c || typeof c !== 'object') throw new Fail('must be an object');
      if (c.order) {
        const ts = c.order.map((id) => enter(need(id)));
        const bad = ts.findIndex((t, k) => k > 0 && !(t > ts[k - 1] + 1e-6));
        out.push({ ok: bad < 0, text: `order ${c.order.join(' < ')}`, why: bad < 0 ? ts.map(r2).join(' < ') : `${c.order[bad]} enters at ${r2(ts[bad])}s, not after ${c.order[bad - 1]} at ${r2(ts[bad - 1])}s` });
      } else if (c.moves) {
        const id = need(c.moves), rg = rangeOf(c.in);
        if (!rg) throw new Fail(`no beat "${c.in}"`);
        const text = `moves ${id} ${c.dir} in ${rg.map(r2).join('-')}s`;
        if (c.dir === 'cw' || c.dir === 'ccw') {
          const rot = (t) => norm.tracks.filter((k) => k.part === id && k.chan === 'rotate').reduce((s, k) => s + valueAt(k, t), 0);
          const d = rot(rg[1]) - rot(rg[0]);
          out.push({ ok: c.dir === 'cw' ? d > 0.5 : d < -0.5, text, why: `rotation changes by ${r2(d)} deg` });
        } else {
          const a = S.at(rg[0]).get(id).box, b = S.at(rg[1]).get(id).box;
          if (!a || !b) throw new Fail(`${id} has no geometry`);
          const dx = center(b)[0] - center(a)[0], dy = center(b)[1] - center(a)[1];
          const ok = { up: dy < -0.5, down: dy > 0.5, left: dx < -0.5, right: dx > 0.5 }[c.dir];
          if (ok === undefined) throw new Fail('dir must be up, down, left, right, cw, or ccw');
          out.push({ ok, text, why: `center moves dx ${r2(dx)}, dy ${r2(dy)}` });
        }
      } else if (c.inside) {
        const id = need(c.inside), rg = rangeOf(c.in);
        if (!rg) throw new Fail(`no beat "${c.in}"`);
        const of = c.of ?? 'canvas';
        let fail1 = null;
        for (const t of samples(rg)) {
          const st = S.at(t), me = st.get(id);
          if (!me.visible) continue;
          const reg = of === 'canvas' ? [0, 0, art.W, art.H] : Array.isArray(of) ? of : st.get(need(of)).box;
          if (!reg) continue;
          const [x, y, w, h] = me.box;
          if (x < reg[0] - 0.5 || y < reg[1] - 0.5 || x + w > reg[0] + reg[2] + 0.5 || y + h > reg[1] + reg[3] + 0.5) { fail1 = `at ${r2(t)}s box ${boxTxt(me.box)} is outside ${boxTxt(reg)}`; break; }
        }
        out.push({ ok: !fail1, text: `inside ${id} of ${Array.isArray(of) ? of.join(',') : of}`, why: fail1 ?? 'every sampled frame' });
      } else if (c.apart) {
        const [a, b] = c.apart.map(need), rg = rangeOf(c.in);
        if (!rg) throw new Fail(`no beat "${c.in}"`);
        let fail1 = null;
        for (const t of samples(rg)) {
          const st = S.at(t), A = st.get(a), B = st.get(b);
          if (!A.visible || !B.visible) continue;
          const ox = Math.min(A.box[0] + A.box[2], B.box[0] + B.box[2]) - Math.max(A.box[0], B.box[0]);
          const oy = Math.min(A.box[1] + A.box[3], B.box[1] + B.box[3]) - Math.max(A.box[1], B.box[1]);
          if (ox > 0.5 && oy > 0.5) { fail1 = `boxes overlap at ${r2(t)}s (${boxTxt(A.box)} and ${boxTxt(B.box)})`; break; }
        }
        out.push({ ok: !fail1, text: `apart ${a} / ${b}`, why: fail1 ?? 'boxes never overlap' });
      } else if (c.still) {
        const id = need(c.still), rg = rangeOf(c.in);
        if (!rg) throw new Fail(`no beat "${c.in}"`);
        const b0 = S.at(rg[0]).get(id).box;
        let fail1 = null;
        for (const t of samples(rg)) { const b = S.at(t).get(id).box; if (b0 && b && b.some((v, k) => Math.abs(v - b0[k]) > 0.3)) { fail1 = `box changes at ${r2(t)}s (${boxTxt(b0)} -> ${boxTxt(b)})`; break; } }
        out.push({ ok: !fail1, text: `still ${id} in ${rg.map(r2).join('-')}s`, why: fail1 ?? 'box constant' });
      } else if (c.same) {
        const [t1, t2] = c.same.map(timeOf);
        if (t1 === null || t2 === null) throw new Fail('same needs two times: seconds, "start", "end", or a beat name');
        const diff = norm.tracks.find((k) => !sameVal(valueAt(k, t1), valueAt(k, t2)));
        out.push({ ok: !diff, text: `same ${r2(t1)}s = ${r2(t2)}s`, why: diff ? `${diff.part}.${diff.chan} is ${show(valueAt(diff, t1))} then ${show(valueAt(diff, t2))}` : 'all channels equal' });
      } else if (c.visible || c.hidden) {
        const id = need(c.visible ?? c.hidden), t = timeOf(c.at ?? 'end');
        if (t === null) throw new Fail('"at" must be seconds, "start", "end", or a beat name');
        const st = S.at(t).get(id), want = !!c.visible;
        out.push({ ok: st.visible === want, text: `${want ? 'visible' : 'hidden'} ${id} at ${r2(t)}s`, why: `opacity ${r2(st.alpha)}${st.box ? '' : ', no geometry'}` });
      } else throw new Fail('unknown check. Checks: order, moves, inside, apart, still, same, visible, hidden');
    } catch (err) {
      if (!(err instanceof Fail)) throw err;
      out.push({ ok: false, text: `check ${i + 1} ${label}`, why: err.message });
    }
  }
  return out;
}
function flagsAt(art, norm, S) { // visible animated parts leaving the canvas, at 30 samples per second
  const flags = new Map();
  const animated = new Set(norm.tracks.map((t) => t.part));
  const n = Math.max(2, Math.round(norm.duration * 30));
  for (let k = 0; k <= n; k++) {
    const t = (norm.duration * k) / n, st = S.at(t);
    for (const id of animated) {
      if (flags.has(id)) continue;
      const s = st.get(id);
      if (!s.visible) continue;
      const over = canvasOver(s.box, art.W, art.H);
      if (!over) continue;
      if (norm.clips.some((c) => c.part === id && c.offstage)) continue;
      flags.set(id, `t=${t.toFixed(2)}  ${id}  box ${boxTxt(s.box)}  OUT ${over}`);
    }
  }
  return [...flags.values()];
}

// ───────────────────────────── compile ─────────────────────────────

function prefixIds(root, pre) {
  const ids = new Set();
  walk(root, (n) => { if (n.type === 'el' && n.attrs.id !== undefined) ids.add(n.attrs.id); });
  const fix = (s) => String(s).replace(/url\(\s*(['"]?)#([^)'"\s]+)\1\s*\)/g, (m, q, id) => (ids.has(id) ? `url(#${pre}${id})` : m));
  walk(root, (n) => {
    if (n.type === 'el') {
      for (const [k, v] of Object.entries(n.attrs)) {
        if (k === 'id') n.attrs.id = pre + v;
        else if ((k === 'href' || k === 'xlink:href') && String(v).startsWith('#') && ids.has(String(v).slice(1))) n.attrs[k] = `#${pre}${String(v).slice(1)}`;
        else if (/url\(/.test(v)) n.attrs[k] = fix(v);
      }
      if (n.name === 'style') for (const c of n.children) if (c.type === 'text' || c.type === 'cdata') c.value = fix(c.value).replace(/#([A-Za-z_][\w-]*)(?=[\s,{.:>+~[])/g, (m, id) => (ids.has(id) ? `#${pre}${id}` : m));
    }
  });
}
function keyframes(name, track, dur, decl) {
  let ks = track.keys.slice();
  if (ks[0].t > 1e-6) ks.unshift({ t: 0, v: ks[0].v, ease: LIN });
  if (ks[ks.length - 1].t < dur - 1e-6) ks.push({ t: dur, v: ks[ks.length - 1].v, ease: LIN });
  ks = ks.filter((k, i) => i === 0 || i === ks.length - 1 || !(sameVal(k.v, ks[i - 1].v) && sameVal(k.v, ks[i + 1].v)));
  const lines = [];
  let lastPct = -1;
  ks.forEach((k, i) => {
    let pct = i === ks.length - 1 ? 100 : r3(Math.min(99.999, (k.t / dur) * 100));
    if (pct <= lastPct) pct = r3(lastPct + 0.001);
    lastPct = pct;
    const next = ks[i + 1];
    const tf = next && next.ease.kind !== 'linear' && !sameVal(k.v, next.v) ? ` animation-timing-function: ${cssEase(next.ease)};` : '';
    lines.push(`  ${pct}% { ${decl(k.v)}${tf} }`);
  });
  return `@keyframes ${name} {\n${lines.join('\n')}\n}`;
}
function compile(art, norm, opt = {}) {
  const pre = opt.prefix ?? 'wu';
  const R = buildRig(art, norm);
  const iter = norm.loop ? 'infinite' : '1';
  const css = [], notes = [];
  const anim = (name) => `animation: ${name} ${r3(norm.duration)}s linear ${iter} both;`;
  const px = (n) => (Math.abs(n) < 5e-4 ? '0' : `${r3(n)}px`);
  const tf = {
    x: (v) => `transform: translate(${px(v)}, 0);`, y: (v) => `transform: translate(0, ${px(v)});`, xy: (v) => `transform: translate(${px(v[0])}, ${px(v[1])});`,
    rotate: (v) => `transform: rotate(${r3(v)}deg);`, scale: (v) => `transform: scale(${r3(v)});`, scaleX: (v) => `transform: scale(${r3(v)}, 1);`, scaleY: (v) => `transform: scale(1, ${r3(v)});`,
    opacity: (v) => `opacity: ${r3(clamp01(v))};`, fill: (v) => `fill: ${v};`, stroke: (v) => `stroke: ${v};`, strokeWidth: (v) => `stroke-width: ${r3(v)}px;`,
    dash: (v) => `stroke-dashoffset: ${r3(v)};`, draw: (v) => `stroke-dashoffset: ${r3(1.02 - 1.01 * clamp01(v))}; visibility: ${v <= 0.0005 ? 'hidden' : 'visible'};`,
  };
  for (const { el, track } of R.wraps) {
    const name = `${pre}-${track.id}`;
    addClass(el, `${pre} ${name}`);
    css.push(`.${name} { ${anim(name)} }`, keyframes(name, track, norm.duration, tf[track.chan]));
  }
  for (const { els, track } of R.leaves) {
    const name = `${pre}-${track.id}`;
    if (track.chan === 'd') {
      const ks = track.keys.slice();
      if (ks[0].t > 1e-6) ks.unshift({ t: 0, v: ks[0].v, ease: LIN });
      if (ks[ks.length - 1].t < norm.duration - 1e-6) ks.push({ t: norm.duration, v: ks[ks.length - 1].v, ease: LIN });
      const splines = ks.slice(1).map((k) => (k.ease.kind === 'bezier' ? k.ease.b.map(r3).join(' ') : '0 0 1 1')).join('; ');
      for (const el of els) {
        el.attrs.d = pathStr(ks[0].v);
        adopt(el, mk('animate', { attributeName: 'd', dur: `${r3(norm.duration)}s`, repeatCount: norm.loop ? 'indefinite' : '1', fill: 'freeze', calcMode: 'spline', keyTimes: ks.map((k) => r3(k.t / norm.duration)).join('; '), keySplines: splines, values: ks.map((k) => pathStr(k.v)).join('; ') }));
      }
      notes.push(`${track.part}: the path morph is one SMIL <animate> (Safari has no CSS "d"); prefers-reduced-motion cannot stop it`);
      continue;
    }
    for (const el of els) { addClass(el, `${pre} ${name}`); if (track.chan === 'draw') el.attrs.pathLength = '1'; }
    css.push(`.${name} { ${track.chan === 'draw' ? 'stroke-dasharray: 1.02 1; stroke-dashoffset: 0.01; ' : ''}${anim(name)} }`, keyframes(name, track, norm.duration, tf[track.chan]));
  }
  for (const { rect, track, box } of R.wipes) {
    const name = `${pre}-${track.id}`, [x, y, w, h] = box;
    Object.assign(rect.attrs, { x: String(r3(x)), y: String(r3(y)), width: String(r3(w)), height: String(r3(h)) });
    addClass(rect, `${pre} ${name}`);
    const ax = track.from === 'right' ? x + w : x, ay = track.from === 'bottom' ? y + h : y, horiz = track.from === 'left' || track.from === 'right';
    css.push(`.${name} { ${anim(name)} }`, keyframes(name, track, norm.duration, (v) => `transform: translate(${px(ax)}, ${px(ay)}) scale(${horiz ? r3(clamp01(v)) : 1}, ${horiz ? 1 : r3(clamp01(v))}) translate(${px(-ax)}, ${px(-ay)});`));
  }
  walk(R.svg, (n) => { if (n.type === 'el') delete n.attrs['data-box']; });
  const head = `/* windup: ${r3(norm.duration)}s${norm.loop ? ' loop' : ''}, generated from the score. Edit the score, not this block. */`;
  const base = `.${pre} { transform-box: view-box; transform-origin: 0 0; }`;
  const reduce = `@media (prefers-reduced-motion: reduce) { .${pre} { animation: none !important; } }`;
  const style = mk('style');
  adopt(style, txt(`\n${[head, base, ...css, reduce].join('\n')}\n`));
  adopt(R.svg, style);
  adopt(R.svg, txt('\n'));
  if (opt.idPrefix) prefixIds(R.svg, opt.idPrefix);
  return { svg: serialize(R.doc), notes, tracks: norm.tracks.length };
}

// ───────────────────────────── strip ─────────────────────────────

function pickTimes(norm, max) {
  const T = norm.duration, set = new Set([0, norm.loop ? r2(T - Math.min(0.1, T / 20)) : T]);
  for (const b of Object.values(norm.beats)) { set.add(r2(b[0])); set.add(r2((b[0] + b[1]) / 2)); }
  for (const c of norm.clips) { set.add(r2(c.start)); set.add(r2((c.start + Math.min(c.end, c.start + c.unit)) / 2)); set.add(r2(Math.min(c.end, c.start + c.unit))); }
  let ts = [...set].filter((t) => t >= 0 && t <= T).sort((a, b) => a - b);
  const gap = Math.max(0.04, T / 60), kept = [];
  for (const t of ts) { if (!kept.length || t - kept[kept.length - 1] >= gap) kept.push(t); else if (t === ts[ts.length - 1]) kept[kept.length - 1] = t; }
  ts = kept;
  while (ts.length > max) {
    let k = 1, best = Infinity;
    for (let i = 1; i < ts.length - 1; i++) { const gap = ts[i + 1] - ts[i - 1]; if (gap < best) { best = gap; k = i; } }
    ts.splice(k, 1);
  }
  return ts;
}
function sheetSVG(art, frames, opt) {
  const n = frames.length, cols = n <= 3 ? n : n <= 6 ? 3 : 4, rows = Math.ceil(n / cols);
  const cw = n === 1 ? 800 : 400, ch = Math.round((cw * art.H) / art.W), pad = 12, lab = 22;
  const Wd = cols * (cw + pad) + pad, Hd = rows * (ch + lab + pad) + pad;
  const out = mk('svg', { xmlns: 'http://www.w3.org/2000/svg', 'xmlns:xlink': 'http://www.w3.org/1999/xlink', viewBox: `0 0 ${Wd} ${Hd}`, width: String(Wd), height: String(Hd) });
  adopt(out, mk('rect', { width: String(Wd), height: String(Hd), fill: '#e9e9ee' }));
  frames.forEach((f, i) => {
    const x = pad + (i % cols) * (cw + pad), y = pad + Math.floor(i / cols) * (ch + lab + pad);
    const label = adopt(out, mk('text', { x: String(x), y: String(y + 15), 'font-family': 'Menlo, Consolas, monospace', 'font-size': '13', fill: '#222' }));
    adopt(label, txt(f.label));
    adopt(out, mk('rect', { x: String(x), y: String(y + lab), width: String(cw), height: String(ch), fill: opt.bg }));
    const cell = adopt(out, mk('svg', { x: String(x), y: String(y + lab), width: String(cw), height: String(ch), viewBox: `0 0 ${art.W} ${art.H}` }));
    for (const c of f.nodes) adopt(cell, c);
    const u = art.W / cw;
    for (const o of f.overlay ?? []) {
      if (o.box) adopt(cell, mk('rect', { x: String(r2(o.box[0])), y: String(r2(o.box[1])), width: String(r2(o.box[2])), height: String(r2(o.box[3])), fill: 'none', stroke: '#e0f', 'stroke-width': String(r3(u)), 'stroke-dasharray': `${r3(3 * u)} ${r3(2 * u)}` }));
      if (o.pivot) adopt(cell, mk('path', { d: `M${r2(o.pivot[0] - 4 * u)} ${r2(o.pivot[1])}h${r2(8 * u)}M${r2(o.pivot[0])} ${r2(o.pivot[1] - 4 * u)}v${r2(8 * u)}`, stroke: '#e0f', 'stroke-width': String(r3(1.5 * u)), fill: 'none' }));
      if (o.mark !== undefined) {
        const fsz = 11 * u, tw = String(o.mark).length * 0.62 * fsz + 4 * u;
        adopt(cell, mk('rect', { x: String(r2(o.at[0] - tw / 2)), y: String(r2(o.at[1] - 0.7 * fsz)), width: String(r2(tw)), height: String(r2(1.35 * fsz)), rx: String(r2(2 * u)), fill: '#111', opacity: '0.85' }));
        const tx = adopt(cell, mk('text', { x: String(r2(o.at[0])), y: String(r2(o.at[1] + 0.32 * fsz)), 'text-anchor': 'middle', 'font-family': 'Menlo, Consolas, monospace', 'font-size': String(r2(fsz)), fill: '#fff' }));
        adopt(tx, txt(String(o.mark)));
      }
    }
    adopt(out, mk('rect', { x: String(x), y: String(y + lab), width: String(cw), height: String(ch), fill: 'none', stroke: '#999', 'stroke-width': '1' }));
  });
  return { svg: serialize(out), width: Wd };
}
function frameNodes(svg, k) {
  const c = clone(svg);
  prefixIds(c, `f${k}-`);
  return c.children;
}
function raster(svgFile, pngFile, width) {
  const dir = path.dirname(pngFile);
  const tries = [
    ['rsvg-convert', ['-w', String(width), '-o', pngFile, svgFile]],
    ['resvg', ['-w', String(width), svgFile, pngFile]],
    ['magick', ['-background', 'none', svgFile, '-resize', `${width}x`, pngFile]],
    ['inkscape', [svgFile, '-w', String(width), '-o', pngFile]],
  ];
  for (const [cmd, args] of tries) {
    const r = spawnSync(cmd, args, { stdio: 'ignore' });
    if (!r.error && r.status === 0 && fs.existsSync(pngFile)) return cmd;
  }
  if (process.platform === 'darwin') {
    const r = spawnSync('qlmanage', ['-t', '-s', String(width), '-o', dir, svgFile], { stdio: 'ignore' });
    const made = path.join(dir, `${path.basename(svgFile)}.png`);
    if (!r.error && fs.existsSync(made)) { fs.renameSync(made, pngFile); return 'qlmanage'; }
  }
  return null;
}

// ───────────────────────────── rig (given art) ─────────────────────────────

function rigIndex(art) { // every drawable element, numbered in document order
  const list = [];
  walk(art.svg, (n) => {
    if (n.type !== 'el' || n === art.svg) return;
    if (SKIP.has(n.name)) return false;
    if (!isDrawable(n) || n.attrs['data-windup'] !== undefined) return;
    const b = newBox();
    measure(n, n.parent && n.parent.type === 'el' ? ctmOf(n.parent) : IDENT, 1, art, b);
    let depth = 0;
    for (let p = n.parent; p && p !== art.svg; p = p.parent) if (p.attrs['data-windup'] === undefined) depth++;
    list.push({ n: list.length + 1, el: n, box: boxArr(b), depth });
  });
  return list;
}
function normalizeViewBox(art) {
  const { svg, vb } = art;
  let [x, y, w, h] = vb.length === 4 ? vb : [0, 0, pf(svg.attrs.width), pf(svg.attrs.height)];
  if (!(w > 0 && h > 0)) fail('cannot rig: <svg> has neither a viewBox nor a numeric width and height');
  if (x !== 0 || y !== 0) {
    const g = mk('g', { 'data-windup': 'viewbox', transform: `translate(${r2(-x)} ${r2(-y)})` });
    const keep = [];
    for (const c of svg.children) { if (c.type === 'el' && ['defs', 'style', 'title', 'desc', 'metadata'].includes(c.name)) keep.push(c); else adopt(g, c); }
    svg.children = keep;
    adopt(svg, g);
  }
  svg.attrs.viewBox = `0 0 ${r2(w)} ${r2(h)}`;
  delete svg.attrs.width; delete svg.attrs.height;
}

// ───────────────────────────── cli ─────────────────────────────

function parseArgs(argv) {
  const a = { _: [], group: [] };
  for (let i = 0; i < argv.length; i++) {
    const s = argv[i];
    if (s === '-o') a.o = argv[++i];
    else if (s === '--group') a.group.push(argv[++i]);
    else if (s.startsWith('--')) { const k = s.slice(2); const v = argv[i + 1]; if (v === undefined || v.startsWith('--') || ['marks', 'boxes', 'no-png', 'force'].includes(k)) a[k] = true; else { a[k] = v; i++; } }
    else a._.push(s);
  }
  return a;
}
const USAGE = `windup: art.svg + score.json -> one animated SVG

  node windup.mjs lint    art.svg [score.json]
  node windup.mjs strip   art.svg [score.json] [-o sheet.svg] [--at 0,0.6,1.2] [--frames 12] [--boxes] [--no-png] [--json report.json]
  node windup.mjs compile art.svg score.json -o out.svg [--player out.html] [--prefix wu] [--id-prefix x-]
  node windup.mjs rig     art.svg --marks [-o marks.svg]
  node windup.mjs rig     art.svg --group "name=3,4@center" [--group ...] -o rigged.svg
  node windup.mjs presets

strip without a score renders the rest pose with each part's box and pivot.
Pivots for rig: @center @top @bottom @left @right @top-left @top-right @bottom-left @bottom-right, or @x,y.
Exit code 1 means errors; warnings do not fail.`;

function cmdLint(a) {
  const art = loadArt(a._[0]);
  const issues = [];
  lintArt(art, issues);
  let norm = null;
  if (a._[1]) { const score = readScore(a._[1], issues); if (score) norm = normalize(art, score, issues); }
  if (norm && !issues.some((i) => i.level === 'E')) seamIssues(art, norm, issues);
  console.log(`windup lint  ${path.basename(art.file)}  ${art.W}x${art.H}  ${art.parts.size} parts  ${r2(Buffer.byteLength(art.src) / 1024)} KB`);
  if (art.parts.size) console.log(`parts\n${partsTable(art)}`);
  if (norm && norm.clips.length) console.log(`timeline  ${norm.duration}s${norm.loop ? ' loop' : ''}\n${timelineText(norm)}`);
  return printIssues(issues) ? 1 : 0;
}
function gate(a, needScore) { // lint, then stop on errors
  const art = loadArt(a._[0]);
  const issues = [];
  lintArt(art, issues);
  let norm = null;
  if (a._[1]) { const score = readScore(a._[1], issues); if (score) norm = normalize(art, score, issues); }
  else if (needScore) fail('no score file given');
  if (norm && !issues.some((i) => i.level === 'E')) seamIssues(art, norm, issues);
  const errs = issues.filter((i) => i.level === 'E');
  if (errs.length && !a.force) { printIssues(issues); console.log('stopped: fix the errors first'); return null; }
  return { art, norm, issues };
}
function cmdStrip(a) {
  const g = gate(a, false);
  if (!g) return 1;
  const { art, norm, issues } = g;
  const out = a.o ?? path.join(path.dirname(art.file), norm ? 'sheet.svg' : 'still.svg');
  const lines = [];
  let frames, failed = 0;
  const data = { canvas: [art.W, art.H], frames: [], checks: [], flags: [] };
  if (!norm) {
    const overlay = [...art.parts.values()].map((p) => ({ box: p.box, pivot: p.el.name === 'g' || p.el.attrs.transform ? p.pivot : null }));
    frames = [{ label: 'rest pose: part boxes and pivots', nodes: frameNodes(art.svg, 0), overlay }];
    lines.push(`windup still  ${path.basename(art.file)}  ${art.W}x${art.H}  ${art.parts.size} parts`, `parts\n${partsTable(art)}`);
  } else {
    const S = makeSampler(art, norm);
    const times = a.at ? String(a.at).split(',').map(Number).filter((t) => t >= 0 && t <= norm.duration) : pickTimes(norm, Number(a.frames ?? 12));
    if (!times.length) fail('--at: no time inside the score');
    const animated = [...new Set(norm.tracks.map((t) => t.part))];
    const beatAt = (t) => Object.entries(norm.beats).find(([, b]) => t >= b[0] - 1e-6 && t < b[1] - 1e-6)?.[0] ?? '';
    lines.push(`windup strip  ${path.basename(art.file)}  ${art.W}x${art.H}  ${norm.duration}s${norm.loop ? ' loop' : ''}  ${norm.clips.length} clips  ${times.length} frames`);
    lines.push(`timeline\n${timelineText(norm)}`);
    lines.push('frames  (box = x,y,w,h in canvas units)');
    const w = Math.max(...animated.map((s) => s.length), 4);
    frames = times.map((t, k) => {
      const st = S.at(t);
      S.set(t);
      lines.push(`  t=${t.toFixed(2)}${beatAt(t) ? `  ${beatAt(t)}` : ''}`);
      for (const id of animated) { const s = st.get(id); lines.push(`    ${id.padEnd(w)}  ${s.visible ? `box ${boxTxt(s.box)}${s.alpha < 0.995 ? `  opacity ${r2(s.alpha)}` : ''}` : 'hidden'}`); }
      data.frames.push({ t, parts: Object.fromEntries(animated.map((id) => [id, { box: st.get(id).box?.map(r2) ?? null, opacity: r2(st.get(id).alpha), visible: st.get(id).visible }])) });
      return { label: `t=${t.toFixed(2)}${beatAt(t) ? '  ' + beatAt(t) : ''}`, nodes: frameNodes(S.R.svg, k), overlay: a.boxes ? animated.map((id) => ({ box: st.get(id).visible ? st.get(id).box : null })) : [] };
    });
    const flags = flagsAt(art, norm, S);
    if (flags.length) lines.push(`flags  (first time each part leaves the canvas while visible; "offstage": true on a clip silences it)\n${flags.map((f) => '  ' + f).join('\n')}`);
    const checks = runChecks(art, norm, S);
    failed = checks.filter((c) => !c.ok).length;
    data.checks = checks; data.flags = flags;
    lines.push(`checks  ${checks.length - failed} pass, ${failed} fail${norm.loop ? '  (loop seam: ok)' : ''}`);
    for (const c of checks) lines.push(`  ${c.ok ? 'ok  ' : 'FAIL'}  ${c.text}: ${c.why}`);
    if (!norm.checks.length) lines.push('  (the score has no "checks"; add one for each order, direction, or containment the request states)');
  }
  const sheet = sheetSVG(art, frames, { bg: norm?.bg ?? '#ffffff' });
  fs.mkdirSync(path.dirname(path.resolve(out)), { recursive: true });
  fs.writeFileSync(out, sheet.svg);
  let pngNote = '';
  if (!a['no-png']) {
    const png = out.replace(/\.svg$/i, '') + '.png';
    const via = raster(out, png, Math.min(2000, sheet.width));
    pngNote = via ? `  png: ${png} (${via})` : '  png: no rasterizer found (rsvg-convert, resvg, magick, inkscape); open the svg in a browser to look at it';
  }
  console.log(lines.join('\n'));
  const warns = issues.filter((i) => i.level === 'W');
  if (warns.length) console.log(`lint  ${warns.length} warning${warns.length > 1 ? 's' : ''}\n${warns.map((i) => '  W  ' + i.msg).join('\n')}`);
  if (typeof a.json === 'string') fs.writeFileSync(a.json, JSON.stringify(data, null, 1));
  console.log(`sheet: ${out}${pngNote}`);
  return failed ? 1 : 0;
}
function cmdCompile(a) {
  if (!a.o) fail('compile needs -o out.svg');
  const g = gate(a, true);
  if (!g || !g.norm) return 1;
  const { art, norm, issues } = g;
  const res = compile(art, norm, { prefix: a.prefix, idPrefix: a['id-prefix'] });
  fs.mkdirSync(path.dirname(path.resolve(a.o)), { recursive: true });
  fs.writeFileSync(a.o, res.svg);
  console.log(`windup compile  ${path.basename(a.o)}  ${r2(Buffer.byteLength(res.svg) / 1024)} KB  ${norm.duration}s${norm.loop ? ' loop' : ''}  ${norm.clips.length} clips  ${res.tracks} tracks  driver: CSS${res.notes.length ? ' + SMIL' : ''}`);
  for (const n of res.notes) console.log(`note  ${n}`);
  const warns = issues.filter((i) => i.level === 'W');
  if (warns.length) console.log(warns.map((i) => 'W  ' + i.msg).join('\n'));
  if (a.player) {
    const tpl = fs.readFileSync(path.join(HERE, '..', 'assets', 'player.html'), 'utf8');
    const meta = JSON.stringify({ duration: norm.duration, loop: norm.loop, beats: norm.beats, bg: norm.bg, name: path.basename(a.o) });
    const inline = res.svg.replace(/^\s*<\?xml[^>]*\?>\s*/, '');
    fs.writeFileSync(a.player, tpl.replace('<!--WINDUP_SVG-->', () => inline).replace('/*WINDUP_META*/null', () => meta));
    console.log(`player: ${a.player}`);
  }
  console.log(`out: ${a.o}`);
  return 0;
}
function cmdRig(a) {
  const art = loadArt(a._[0]);
  normalizeViewBox(art);
  Object.assign(art, indexTree(art.svg));
  const vb = nums(art.svg.attrs.viewBox);
  art.vb = vb; art.W = vb[2]; art.H = vb[3];
  const list = rigIndex(art);
  if (a.group.length) {
    if (!a.o) fail('rig --group needs -o rigged.svg');
    for (const spec of a.group) {
      const m = /^([A-Za-z][\w-]*)=([^@]+)(?:@(.+))?$/.exec(String(spec).trim());
      if (!m) fail(`--group "${spec}": write name=3,4@center`);
      const [, name, items, piv = 'center'] = m;
      if (art.byId.has(name)) fail(`--group ${name}: id "${name}" already exists`);
      const els = items.split(',').map((s) => s.trim()).filter(Boolean).map((s) => {
        const hit = /^\d+$/.test(s) ? list.find((e) => e.n === Number(s))?.el : art.byId.get(s);
        if (!hit) fail(`--group ${name}: no element "${s}" (use the numbers from --marks, or an id)`);
        return hit;
      });
      const parent = els[0].parent;
      if (els.some((e) => e.parent !== parent)) fail(`--group ${name}: all items must share one parent; group the inner ones first`);
      const b = newBox();
      for (const e of els) measure(e, IDENT, 1, art, b);
      const bb = boxArr(b);
      if (!bb) fail(`--group ${name}: the items draw nothing`);
      const [x, y, w, h] = bb;
      const named = { center: [x + w / 2, y + h / 2], top: [x + w / 2, y], bottom: [x + w / 2, y + h], left: [x, y + h / 2], right: [x + w, y + h / 2], 'top-left': [x, y], 'top-right': [x + w, y], 'bottom-left': [x, y + h], 'bottom-right': [x + w, y + h] };
      const pv = named[piv] ?? (nums(piv).length === 2 ? nums(piv) : fail(`--group ${name}: pivot "@${piv}" must be a keyword or x,y`));
      const px = r2(pv[0]), py = r2(pv[1]);
      const outer = mk('g', { id: name, transform: `translate(${px} ${py})` }), innerG = mk('g', { transform: `translate(${-px} ${-py})` });
      const at = parent.children.indexOf(els[0]);
      parent.children = parent.children.filter((c) => !els.includes(c));
      parent.children.splice(Math.min(at, parent.children.length), 0, outer);
      outer.parent = parent;
      adopt(outer, innerG);
      for (const e of els) adopt(innerG, e);
      art.byId.set(name, outer);
    }
    fs.writeFileSync(a.o, serialize(art.doc));
    const re = loadArt(a.o);
    console.log(`windup rig  ${path.basename(a.o)}  ${re.W}x${re.H}  ${re.parts.size} parts\nparts\n${partsTable(re)}\nout: ${a.o}`);
    return 0;
  }
  const rows = list.map((e) => {
    const fill = styleOf(e.el, 'fill', art), stroke = styleOf(e.el, 'stroke', art);
    return `${'  '.repeat(e.depth)}#${e.n} ${e.el.name}${e.el.attrs.id ? ` id=${e.el.attrs.id}` : ''}  box ${boxTxt(e.box)}${LEAF.has(e.el.name) ? `${fill && fill !== 'none' ? `  fill ${fill}` : ''}${stroke && stroke !== 'none' ? `  stroke ${stroke}` : ''}` : ''}`;
  });
  console.log(`windup rig  ${path.basename(art.file)}  ${art.W}x${art.H}  ${list.length} elements\n${rows.join('\n')}`);
  if (a.marks) {
    const out = a.o ?? path.join(path.dirname(art.file), 'marks.svg');
    const overlay = list.filter((e) => e.box && e.el.name !== 'g').map((e) => ({ mark: e.n, at: [e.box[0] + e.box[2] / 2, e.box[1] + e.box[3] / 2] }));
    const sheet = sheetSVG(art, [{ label: 'marks: element numbers', nodes: frameNodes(art.svg, 0), overlay }], { bg: '#ffffff' });
    fs.writeFileSync(out, sheet.svg);
    const png = out.replace(/\.svg$/i, '') + '.png';
    const via = a['no-png'] ? null : raster(out, png, sheet.width);
    console.log(`marks: ${out}${via ? `  png: ${png} (${via})` : ''}`);
  }
  console.log('next: rig art.svg --group "name=3,4@center" ... -o rigged.svg   (all groups in one call; numbers change after grouping)');
  return 0;
}
function cmdPresets() {
  const KIND = { in: 'in: ends at the rest pose, holds its start before', out: 'out: starts at the rest pose, holds its end after', loop: 'loop: repeats every period, rest pose to rest pose', emph: 'emphasis: one shot, rest pose to rest pose', path: 'path' };
  const w = Math.max(...Object.keys(PRESETS).map((n) => n.length));
  for (const kind of Object.keys(KIND)) {
    console.log(KIND[kind]);
    for (const [name, p] of Object.entries(PRESETS)) {
      if (p.kind !== kind) continue;
      const time = kind === 'loop' ? `period ${p.period ?? 'clip'}${p.period ? 's' : ''}` : `dur ${p.dur}s`;
      const params = Object.entries(p.params ?? {}).map(([k, v]) => `${k}${v === undefined ? '*' : v === null ? '' : `=${JSON.stringify(v)}`}`).join(' ');
      console.log(`  ${name.padEnd(w)}  ${time.padEnd(12)}  ${DOES[name]}${params ? `  [${params}]` : ''}`);
    }
  }
  console.log(`\n[...] parameters with defaults; * required. Sides: left right top bottom. dir: cw ccw.\nKeys-clip props: ${PROPS.join(' ')}\nEases: linear in out inOut back steps(n) [x1,y1,x2,y2]`);
  return 0;
}

const [cmd, ...rest] = process.argv.slice(2);
try {
  const a = parseArgs(rest);
  const run = { lint: cmdLint, strip: cmdStrip, compile: cmdCompile, rig: cmdRig, presets: cmdPresets }[cmd];
  if (!run || rest.includes('--help') || rest.includes('-h')) { console.log(USAGE); process.exit(run || !cmd || cmd === 'help' || cmd === '--help' ? 0 : 1); }
  process.exit(run(a));
} catch (err) {
  if (err instanceof Fail) { console.log(`E  ${err.message}`); process.exit(1); }
  throw err;
}
