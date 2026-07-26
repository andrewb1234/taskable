# Mouvadah UI Design System

Status: foundation for the Unified Landing & Product UI v1 program
Source: Mouvadah knowledge node #32 and implementation ticket #95

## Design thesis

Mouvadah is a control and memory plane for human-agent software delivery. Its
visual system should make operational state, provenance, and review legible
without looking like a generic issue tracker.

The public experience may be editorial and expressive. The authenticated
application stays calm, dense, and predictable. Both surfaces use the same
mark, type roles, warm-paper/ink/brass palette, semantic states, focus
treatment, and motion rules.

Three principles govern new work:

1. **State before decoration.** Status, ownership, provenance, and risk must be
   readable without depending on color or animation.
2. **Technical, not cryptic.** Monospace is reserved for identifiers, labels,
   commands, paths, and structured evidence. Reading content stays sans-serif.
3. **Motion explains change.** Animate a reveal, transition, or system trace
   only when it clarifies sequence. A static reduced-motion state must carry
   the same meaning.
4. **Decision value sets hierarchy.** Current work, risk, ownership, evidence,
   and the next action lead. Product explanation, full briefs, history, and
   empty secondary states use progressive disclosure.

## Semantic tokens

Tokens are defined in `web/src/index.css` and exposed through
`web/tailwind.config.js`. Components should use semantic classes instead of raw
palette utilities.

### Application surfaces

| Purpose | Tailwind class |
| --- | --- |
| Page background | `bg-background text-foreground` |
| Standard panel | `bg-surface text-surface-foreground` |
| Raised panel or popover | `bg-surface-elevated` |
| Quiet grouping surface | `bg-surface-subtle` |
| Structural border | `border-border` |
| Form border | `border-input` |
| Keyboard focus | `ring-ring` or `focus-ring` |

The light application palette is warm rather than pure white. `.dark` provides
the same semantic contracts for dark application surfaces.

### Brand palette

| Purpose | Tailwind class |
| --- | --- |
| Marketing ink | `bg-brand-ink` / `text-brand-ink` |
| Marketing paper | `bg-brand-paper` / `text-brand-paper` |
| Supporting sandstone | `bg-brand-sandstone` |
| Restrained action accent | `bg-brand-brass` / `text-brand-brass` |

Use brass for a small number of decisive actions, active traces, or focus
details. It is not a general-purpose warning color.

Add `data-surface="marketing"` to a marketing page boundary to remap shared
background, foreground, surface, border, and control tokens without forcing the
authenticated application into the marketing theme.

```tsx
<main data-surface="marketing" className="min-h-screen bg-background text-foreground">
  ...
</main>
```

### Ticket states

Each ticket state has background, foreground, and border tokens:

- `status-todo`
- `status-progress`
- `status-blocked`
- `status-review`
- `status-done`

Use `TicketStatusIndicator` from
`web/src/components/ui/state-indicator.tsx`. It adds a distinct icon and visible
label so state never depends on color alone. Do not substitute
`bg-blue-500`, `text-red-300`, or similar raw colors in product components.

### Actor states

Human, agent, and unassigned use the separate `actor-human`, `actor-agent`, and
`actor-unassigned` token families. Use `AssigneeIndicator`; it pairs the color
with an actor-specific icon and label.

Success, warning, and destructive semantics are separate from ticket and actor
identity. Do not use a ticket-state color to confirm a destructive action.
On a solid destructive background, use `text-destructive-foreground`. On a
transparent, neutral, or lightly tinted surface, use `text-destructive`;
`destructive-foreground` is not a general-purpose red text token.

## Typography

- `font-sans`: product copy, navigation, forms, headings, and long-form
  reading.
- `font-mono`: ticket/node IDs, technical labels, source paths, command
  snippets, worker IDs, and timestamps where fixed-width scanning helps.
- `TechnicalLabel`: reusable uppercase metadata eyebrow. Keep labels short.
- `MouvadahWordmark`: the only approved wordmark treatment. The lowercase form
  is the product default; the uppercase mono treatment is reserved for compact
  editorial contexts.

The system uses local platform fonts only. Do not add remote font requests or
make interface availability depend on font loading.

Technical labels are optional metadata, not decoration. Remove one when the
following heading already communicates the same thing. Never render a category
label such as “Control plane” as a status pill: pills are reserved for state,
identity, or compact actionable metadata.

## Brand mark

`MouvadahMark` and `MouvadahLockup` live in
`web/src/components/brand/mouvadah-brand.tsx`.

The mark is a deterministic `currentColor` SVG. Its central disc and symmetric
strokes reference Assyrian winged-disc geometry while the right-facing center
signals action. It must remain one color, retain its aspect ratio, and remain
recognizable at the `sm` 20px size.

- Use `MouvadahLockup` when the product name should be announced.
- Use `MouvadahMark` alone only when adjacent text already names Mouvadah or
  when a concise accessible `label` is supplied.
- Do not redraw, stretch, gradient-fill, shadow, rotate, or place the mark over
  a low-contrast texture.

## Surfaces and controls

`Surface` provides four panel tones: `default`, `elevated`, `subtle`, and
`marketing`. It also standardizes radius and padding without prescribing
layout.

Shared controls use the `focus-ring` utility. Buttons, inputs, textareas, and
select triggers provide:

- a two-pixel visible focus ring;
- two-pixel focus offset from the component;
- a background-colored gap so the ring survives dense layouts;
- consistent disabled opacity and cursor behavior;
- color transitions using `--motion-duration-fast`.

Icon-only controls still require an `aria-label`. Focus styling does not replace
an accessible name.

## Radius, spacing, and elevation

- Base radius: `0.625rem`; use `rounded-sm`, `rounded-md`, and `rounded-lg`
  through the configured radius tokens.
- Dense metadata: four-pixel increments (`gap-1`, `gap-2`).
- Standard controls and cards: eight to sixteen-pixel increments.
- Page sections: twenty-four to forty-eight-pixel increments according to
  viewport.
- Use borders to define operational regions. Reserve shadows for elevated
  popovers, dialogs, and the occasional raised panel.

Avoid a grid of unrelated floating cards. Group information by workflow and
shared state.

### Progressive disclosure

Keep visible anything required to decide or act:

- blocked or review work;
- work in flight and ownership;
- the next safe action;
- stale or proposed knowledge when it requires review; and
- a recorded handoff that can actually be resumed.

Collapse or omit explanatory lifecycle tours, full briefs, aggregate ownership,
archived counts, extended notes, and empty recovery panels. A collapsed summary
must say what is inside; a secondary section with no action and no state should
usually not render.

Marketing examples follow the same rule. Show the resulting project state
(outcome, owner, dependencies, evidence, blocker, and next action) before the
process that produced it. Put process history behind a disclosure on narrow
screens.

## Accessibility and responsive floor

- One visible `h1` per page or route state.
- Skip links target a focusable main region on landing and application shells.
- Native nested lists are preferred over ARIA tree roles unless the complete
  tree keyboard interaction and roving focus model are implemented.
- Mobile controls and touch targets are at least 44 by 44 CSS pixels. Dense
  desktop variants may return to their documented component height at `sm` or
  above.
- Status labels may not overlap or leak from their container at 320–360 pixels
  or 200% text size. When a pill no longer fits a metric card, remove the pill
  treatment and use a plain label/count pair.
- Authentication copy names enabled methods (“Google sign-in,” “API-key
  sign-in”) rather than inferring hosted or local deployment from provider
  flags.
- Text below 12 CSS pixels is limited to nonessential identifiers or compact
  metadata. User decisions, errors, controls, and state labels use 12 pixels or
  larger.

## Motion

Durations and easing are CSS variables:

- `--motion-duration-fast`: control feedback;
- `--motion-duration-standard`: ordinary state transitions;
- `--motion-duration-slow`: one-time content entry;
- `--motion-duration-trace`: an explanatory SVG trace;
- `--motion-ease-standard`: the shared deceleration curve.

Reusable utilities:

- `motion-enter`: one-time opacity/vertical reveal. An optional
  `--motion-delay` custom property may stagger a small sequence.
- `motion-trace`: draws an SVG path. The path must declare `pathLength="1"`.
- `motion-continuous`: opt-in marker for any continuous decorative animation.

Under `prefers-reduced-motion: reduce`, these utilities remove animation and
render the complete static state. Never use motion as the only sign that work
changed, failed, completed, or needs review.

Reduced motion targets the application’s animation and transition utilities;
do not use a global `*` rule that rewrites every duration. Browser-native
focus, disclosure, and scrolling behavior must remain predictable.

## Extension checklist

Before merging a new UI surface:

1. Use existing surface, text, border, ticket, actor, and feedback tokens.
2. Use `MouvadahLockup`, `TechnicalLabel`, `Surface`, and state indicators
   where their contracts apply.
3. Provide visible labels/icons in addition to semantic color.
4. Verify keyboard focus, disabled state, loading, empty, error, and narrow
   layout behavior.
5. Verify the complete static experience with reduced motion.
6. Add a new token only when the meaning recurs across surfaces. Add it to
   light, dark, and marketing scopes when applicable and document its purpose.
7. Reject page-local hex/HSL values, raw Tailwind palette colors for domain
   state, copied brand SVGs, and one-off focus styles.
8. Lead with live state; move explanation and empty secondary panels behind
   progressive disclosure or remove them.
9. At 320–360 pixels, check the bounding box of badges, tab labels, dialog
   chrome, and action rows inside their immediate containers. A document-width
   assertion alone does not detect clipped descendants.

## Verification

Foundation and downstream UI changes run from `web/`:

```bash
npm run lint
npm run build
npm run test:e2e -- --project=chromium
```

Interaction-changing PRs add focused Playwright assertions against user-visible
behavior and stable semantic/test contracts rather than CSS class strings.
