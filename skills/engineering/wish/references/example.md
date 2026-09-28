# Example — Lite plan

Calibrates length, tone, and granularity — not topic or language (headings follow the user's language).
No questions were asked: the repo settled the stack, the code the motive (A-1). A Full plan keeps this
density, splits §5 back into §5–7, and gives §10 a risk table.

---

# Move Modal to native `<dialog>`

| | |
|---|---|
| Date | 26-09-28 |
| Status | Draft |
| Revision | 1 |
| Repo | `shop-admin` @ `main` (`8c1d4e7`) |
| Estimate | ~3 h · 4 files · Lite |
| Related | none |

> **Wish (verbatim):** refactor Modal to use the native dialog

## 1. TL;DR

`Modal` switches internally to `<dialog>` + `showModal()`, dropping the portal, the focus trap, and the Esc listener (~140 lines net) and fixing the nested-modal scroll-lock bug on the way. Props are unchanged; none of the 14 call sites change.

## 2. Background

`src/components/Modal/Modal.tsx` (146 lines) portals into `document.body`, traps focus via `useFocusTrap.ts` (64 lines), and handles Esc with a `keydown` listener; it has 14 call sites (`grep -rn "<Modal" src`). Each instance locks scroll by setting `body.style.overflow`, so closing an inner modal unlocks the page while the outer one is still open (`Modal.tsx:57`).

| Term | Meaning |
|---|---|
| top layer | A layer the browser renders above all content; a `<dialog>` opened with `showModal()` lives there, unaffected by ancestors' `z-index` / `overflow` |
| inert | Not focusable, not clickable; while a modal is open, the rest of the page is inert automatically |

## 3. Goals / Non-goals

- G-1 No call site changes; every existing e2e test passes unmodified.
- G-2 While any modal is open, the page cannot scroll — nested modals included.
- Non-goals: changing props, adding an exit animation, touching other overlays (`Drawer`, `Toast`).

## 4. Users & scenarios

Front-end developers who use `Modal`; keyboard users. On the Orders page, click "Delete order" → the modal opens with focus inside → press Esc → it closes and focus returns to "Delete order".

## 5. Design

Contract that stays fixed: the props `open`, `onClose`, `title`, `children`, and what they do.

| Concern | Now | After |
|---|---|---|
| Open/close sync | Parent passes `open`; a `keydown` listener handles Esc | An effect calls `showModal()` / `close()` from `open`; the `close` event calls `onClose()` only while `open` is still `true` (a native Esc close), so it never fires twice |
| Focus | `useFocusTrap.ts` loops Tab by hand | Native: the rest of the page is inert; on close, focus returns to the element focused before opening |
| Backdrop click | `onClick` on the overlay `div` | A click on `::backdrop` targets the `<dialog>` itself: close when `e.target === e.currentTarget`; the dialog gets `padding: 0` and an inner wrapper, so clicks on inner whitespace don't close it |
| Scroll lock | Each instance sets `body.style.overflow` | `html:has(dialog[open]) { overflow: hidden }` — locked while any modal is open |
| Styles | Rendered under `body` | Rendered in place: inherits the surrounding `font-size` / `line-height` and carries the UA's default `border`, `padding`, `max-width` → set all of them explicitly on `.dialog` |

| ID | Functional requirement | Priority |
|---|---|---|
| FR-1 | All 14 call sites unchanged; title, body, and close button render as they do today | Must |
| FR-2 | Esc, backdrop click, and the close button each call `onClose`; clicks inside the dialog don't | Must |
| FR-3 | While open, Tab never lands on page elements outside the dialog; on close, focus returns to the trigger | Must |
| FR-4 | After an inner modal closes, the page stays unscrollable while the outer one is open | Must |

| Path | Change | Why |
|---|---|---|
| `src/components/Modal/Modal.tsx` | modify | Switch to `<dialog>`; 146 → ~70 lines |
| `src/components/Modal/Modal.module.css` | modify | Overlay → `::backdrop`; scroll lock; style reset |
| `src/components/Modal/useFocusTrap.ts` | delete | Only `Modal.tsx` uses it (`grep -rl useFocusTrap src` lists just these two files) |
| `e2e/modal.spec.ts` | modify | Add cases for AC-1 – AC-3 |

## 6. Implementation steps

| # | Step | Files | Depends on | Done when |
|---|---|---|---|---|
| 1 | Safety net first: write AC-1 – AC-3 as e2e tests and run them against the old implementation | `e2e/modal.spec.ts` | — | Only AC-3 fails (reproduces the scroll-lock bug) |
| 2 | Switch to `<dialog>`, move the overlay to `::backdrop`, add the scroll lock | `Modal.tsx`, `Modal.module.css` | 1 | AC-1 – AC-3 pass |
| 3 | Delete `useFocusTrap.ts`, the portal, and the `keydown` listener | `Modal.tsx`, `useFocusTrap.ts` | 2 | `pnpm tsc --noEmit` and `pnpm lint` pass; AC-4 passes |

## 7. Testing & acceptance

| ID | Given / When / Then | Covers |
|---|---|---|
| AC-1 | Given an open modal, when pressing Esc, clicking the backdrop, or clicking the close button, then it closes and the trigger reopens it; clicking inner whitespace leaves it open | FR-2 |
| AC-2 | Given a modal opened by keyboard, when pressing Tab 20 times, then `document.activeElement` is only ever inside the dialog or `body`; after Esc, focus is on the trigger | FR-3 |
| AC-3 | Given an outer and an inner modal open, when the inner one closes, then wheel-scrolling doesn't move the page; once the outer one closes, the page scrolls | FR-4 |
| AC-4 | Given the finished change, then `git diff --stat` touches only `src/components/Modal/` and `e2e/`, pre-existing tests pass unmodified, and both spot-checked modals match their before-screenshots | FR-1 |

Automated: `pnpm exec playwright test e2e/modal.spec.ts`.
Manual: `pnpm dev`; spot-check "Delete order" on the Orders page and "Change password" on the Settings page.

## 8. Rollout & risks

No migration, no API change; `<dialog>` and `:has()` are supported across the `browserslist` (last two versions of Chrome / Edge / Firefox / Safari); rollback = revert the commit.

## 9. Assumptions & open questions

| ID | Assumption | Why | To reverse |
|---|---|---|---|
| A-1 | Audience is this repo's developers; the motive is deleting home-grown code and fixing the scroll-lock bug | The wish only says "use the native dialog"; `Modal` is used only in this repo, with no publish config; the bug is at `Modal.tsx:57` | If `Modal` is published: the DOM change is a public-API change — replan as Full |
| A-2 | Tab past the dialog's last element goes to the browser UI instead of wrapping to the first | Standard native modal behaviour; doesn't trap keyboard users in the page | Strict wrapping required: keep `useFocusTrap.ts` |

Open questions: none.

## 10. Changelog

- r1 26-09-28 — initial draft
