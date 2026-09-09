# PricePilot UI — design system & conventions (Phase 6)

This document defines the frontend design system and the conventions every
page follows. It exists so the premium Phase 6 UI stays consistent, honest,
and maintainable.

## Stack

- **Framework:** Next.js 16 App Router, React 19, TypeScript.
- **Styling:** Tailwind CSS v3 with CSS variables (<code>:root</code> / `.dark`)
  in `src/app/globals.css`.
- **Primitives:** hand-written shadcn-style components in `src/components/ui/`
  (Badge, Button, Card, Input, Label, Textarea, Select, Tabs, Dialog,
  DropdownMenu, Tooltip, Switch, Skeleton, Alert, Separator, Spinner).
  Several are thin wrappers over Radix primitives for accessible behavior.
- **Icons:** `lucide-react`.
- **Utilities:** `cn` (clsx + tailwind-merge), `formatPrice` (Intl).

## Layout & spacing

- Every routed page uses `PageContainer` from `@/components/container` (max-w-6xl,
  `px-4 sm:px-6`, `py-8 sm:py-10`).
- Vertical rhythm: sections are separated by `space-y-*`, grids by `gap-3/4`.
- Headers use `PageHeader` (title + description). The `phase` prop is
  discouraged — pages should describe real capability, not a roadmap phase.

## Typography

- Page titles: `text-2xl font-bold tracking-tight`.
- Section headings: `text-lg font-semibold`.
- Body: `text-sm`; secondary text uses `text-muted-foreground`.
- Numeric/price values: `font-medium`/`font-semibold` via `formatPrice` (never a
  hardcoded symbol).

## Cards & surfaces

- `Card` is the base surface (`rounded-lg border bg-card shadow-sm`).
- Product/tracking/alerts cards share a layout: header row, key values row,
  evidence/meta rows, action row. Actions live at the card bottom
  (`mt-auto flex items-center gap-2`).

## Buttons

- One `Button` primitive with `default | destructive | outline | secondary |
  ghost | link` variants and `default | sm | lg | icon` sizes.
- Primary action in a card is the first button; destructive secondary actions
  use `variant="destructive"`.
- Icon buttons use `size="icon"` with an accessible `aria-label`.

## Badges

- `Badge` variants: `default`, `secondary`, `outline`, `destructive`,
  `success`, `warning`, `info`.
- Semantic usage:
  - price down / healthy → `success`
  - price up / risk → `destructive`
  - paused / monitoring disabled → `warning`
  - informational (new low, target reached) → `info`
  - neutral / unavailable → `secondary`

## Forms

- Use `Label` + `Input`/`Textarea`/`Select`/`Switch` with `htmlFor`/`id`.
- Inline validation is client-side before sending; server errors render as
  `ErrorState`.
- Numeric inputs use `inputMode="decimal"` where appropriate.

## Honest-data UI rules (REQUIRED)

These rules are non-negotiable — no fake data may ever be rendered:

1. **Never fabricate** prices, offers, reviews, sellers, history, alerts, or
   statistics. Render only what the API returned.
2. **Missing price** → `formatPrice` returns `—`; never show `$0`.
3. **Provider unavailable** → `ProviderUnavailable` state; say the external
   provider could not be reached.
4. **Insufficient history** (<2 observations) → `InsufficientData`; never draw a
   chart line from one point.
5. **Empty states** → `EmptyState` with a next-step action.
6. **Errors** → `ErrorState` (human-readable) + retry affordance.
7. **Verified vs insufficient** — in the shopping assistant, every evidence row
   is labeled `verified` or `insufficient/unavailable`.
8. **Demo/fixture data** must be labeled with a `demo data` badge whenever
   rendered (never in a way that looks live).

Shared state components live in `@/components/states.tsx`:
`EmptyState`, `ErrorState`, `WarnState`, `InfoState`, `ProviderUnavailable`,
`InsufficientData`, `LoadingBlock`, `InlineSpinner`.

## Responsive conventions

- Desktop nav hides below `md`; a fixed bottom tab bar appears on small screens
  (`MobileNav` in `src/components/site-nav.tsx`).
- Grids: `grid gap-3 sm:grid-cols-2 lg:grid-cols-3` (or similar) — never a
  single rigid column on mobile.
- Allow horizontal scroll only inside contained tables/charts, never the page.
- Touch targets ≥ 36px on mobile.

## Accessibility conventions

- Semantic HTML (`main`, `nav`, `header`, `footer`, `dl`, `table`, etc.).
- Keyboard: focus-visible rings on all interactive primitives; Radix handles
  dialog/tabs/select/dropdown key nav.
- `aria-current="page"` on the active nav link.
- `aria-live`/`role="status"` for transient loading/saved states.
- `prefers-reduced-motion`: all animations are disabled via the media query in
  `globals.css`; the chart and dialogs do not force motion.

## Motion

- Subtle only: fade/slide for dialogs and dropdowns, skeleton pulse for
  loading. No ambient/looping animation.
- All animation CSS is defined in `globals.css` (no external plugin) and gated
  behind `prefers-reduced-motion`.

## Testing

- Vitest (node env). Tests exercise **pure logic** and **real-data states**
  (null price, provider unavailable, insufficient history, empty/loading/error),
  never fake product corpora.
- Component logic is extracted into pure functions where practical
  (e.g. `classifyPriceChange`, `alertKindLabel`, `trackingStateLabel`) so it is
  unit-testable without a DOM.