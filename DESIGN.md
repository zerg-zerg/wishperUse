# Voice Note — Design System

A single-screen voice recorder for a phone, saving transcriptions to Joplin. This file is the
contract for the UI in `app.py`; every color, size, spacing value and component in the template
must trace back to a token defined here.

---

## 1. Atmosphere & Identity

A quiet audio instrument in a dark room. The screen is nearly empty — one glowing control, one
number, one line of live signal — because the only thing a person holding a phone wants is to speak
and be done. The signature is **the lit pad**: a warm red-orange recording key sitting in a pool of
its own glow on an off-black surface, with the microphone's live energy drawn as a waveform beneath
it. Depth comes from tonal shifts and light, never from boxes and shadows stacked on boxes. When
recording, the room warms up: a soft ring breathes around the pad and the glow behind it intensifies.

## 2. Color

Single dark theme (`color-scheme: dark`). Dark is the design, not a mode — the device is used in
dim rooms and in bed.

### Palette

| Role | Token | Value | Usage |
|------|-------|-------|-------|
| Surface/base | `--surface-base` | `#0b0b0f` | Page background |
| Surface/raised | `--surface-raised` | `#14141a` | Recorder card, status banner |
| Surface/overlay | `--surface-overlay` | `#1c1c24` | Install button, secondary controls |
| Text/primary | `--text-primary` | `#f4f4f6` | Title, live timer, button icons |
| Text/secondary | `--text-secondary` | `#a3a3b0` | Status text, body copy |
| Text/tertiary | `--text-tertiary` | `#74748a` | Idle timer, overline labels |
| Border/subtle | `--border-subtle` | `#23232c` | Card outline, banner outline |
| Border/strong | `--border-strong` | `#34343f` | Install button outline |
| Accent/record | `--accent` | `#ff5a4d` | Record key, live waveform, recording ring |
| Accent/high | `--accent-hi` | `#ff8577` | Key gradient highlight, focus ring |
| Accent/deep | `--accent-deep` | `#d8412f` | Key gradient shadow stop |
| Accent/wash | `--accent-wash` | `rgba(255,90,77,.12)` | Recording card tint |
| Accent/glow | `--accent-glow` | `rgba(255,90,77,.38)` | Key drop shadow, glow halo |
| Status/success | `--success` | `#4ade80` | Success dot |
| Status/success text | `--success-text` | `#c9f7d9` | Success message |
| Status/error | `--error` | `#ff6b6b` | Error dot |
| Status/error text | `--error-text` | `#ffd4d4` | Error message |

### Rules
- Exactly one accent hue (warm red-orange). It marks the live/recordable thing only — never decoration.
- Surfaces step by tone (`base → raised → overlay`); no surface is separated by a drop shadow.
- No blue/purple gradients anywhere. Background warmth stays within the accent's hue family.
- Never introduce a color outside this table; extend the table first.

## 3. Typography

### Font stack
- Primary: `system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif` — no
  webfont: the app must cold-start offline from the service-worker cache, so no network font fetch.
- Numeric: `ui-monospace, "SF Mono", "Cascadia Mono", "Roboto Mono", Menlo, monospace` with
  `font-variant-numeric: tabular-nums` so the timer does not jitter.

### Scale

| Level | Size | Weight | Line height | Tracking | Usage |
|-------|------|--------|-------------|----------|-------|
| Title | 24px / 1.5rem | 650 | 1.2 | -0.02em | `h1` «Голосовая заметка» |
| Timer | 34px / 2.125rem | 500 | 1 | 0.04em | `MM:SS` mono readout |
| Body | 15px / 0.9375rem | 400 | 1.45 | 0 | Status message |
| Body/sm | 14px / 0.875rem | 400 | 1.4 | 0 | Hint under the pad |
| Overline | 12px / 0.75rem | 600 | 1.3 | 0.14em | «Whisper · Joplin» label, uppercase |

### Rules
- Nothing below 12px. Body copy never below 14px.
- Timer and only the timer uses the mono face.
- No emoji in UI text or icons; state is carried by the accent, the dot, and the message.

## 4. Spacing & Layout

Base unit **4px**. Tokens: `--space-1…--space-6` (4/8/12/16/20/24) and `--space-8` (32),
`--space-10` (40).

### Shell
- App column: `max-width: 480px`, centered, `min-height: 100dvh` (never `100vh`).
- Safe areas respected on all four edges: `padding: max(token, env(safe-area-inset-*))`.
- Vertical rhythm: header → recorder (flex-grow, vertically centered) → status → install button.
- Single column at every width; the phone layout is the only layout. Desktop shows the same column.
- No horizontal scrolling at 375px; long messages wrap, they never widen the page.
- Tap targets ≥ 48px; the record key is ≥ 96px.

### Radii
`--radius-sm 10` · `--radius-md 16` · `--radius-lg 22` · `--radius-xl 28` · `--radius-pill 999`.
Card uses `xl`, banner/install use `md`, key uses `pill`.

## 5. Components

### App shell
- **Structure**: `main.app` column → `header` (overline + title), `section.recorder`, `div.status`,
  `button.install`.
- **Spacing**: `--space-6` gaps, `--space-5` side padding.
- **States**: static.
- **Accessibility**: `main` landmark, single `h1`, `section` labelled by an off-screen `h2`.
- **Layout**: vertical stack, recorder is the flexible middle region.

### Record key (`#record`)
- **Structure**: `button.pad__btn` inside `div.pad` with `span.pad__halo` behind it; contains mic SVG,
  stop SVG and a spinner, exactly one of which is visible per state.
- **Variants**: mic glyph (idle/success/error), stop square (recording), spinner (processing).
- **States**:
  - default — 96–104px circle, accent radial gradient, inner top highlight, accent-tinted drop glow.
  - hover — none beyond pointer feedback (touch-first).
  - active — `scale(.96)`.
  - focus-visible — 2px `--accent-hi` outline, 4px offset.
  - recording — `.is-recording`: stop glyph, halo ring breathing behind the key, card gains
    `--accent-wash` tint.
  - processing / disabled — spinner, `filter: saturate(.5) brightness(.8)`, `cursor: progress`, button
    not clickable.
- **Accessibility**: `aria-pressed` reflects recording, `aria-label` switches
  «Начать запись» / «Остановить запись», `aria-describedby="hint"`.
- **Motion**: press 140ms; halo pulsing 2.4s (transform + opacity only).
- **Layout**: centered in the card's flexible area.

### Live waveform (`#wave`)
- **Structure**: `canvas` fed by `AnalyserNode.getByteFrequencyData`, 44 rounded bars, mirrored
  around the vertical center.
- **States**:
  - idle — even, faint 3px bars (`--text-secondary` at 28% alpha), no motion.
  - live — bars scale with voice energy, accent fill, opacity 1.
- **Accessibility**: `aria-hidden="true"` — it is an ornament of state already announced by the
  status region.
- **Motion**: drawn per animation frame while recording; redraws once on idle; honors reduced motion
  by simply not animating when idle.

### Timer (`#timer`)
- **Structure**: `div.timer` text `MM:SS`, mono + tabular figures.
- **States**: idle (`--text-tertiary`) / live (`.is-live`, `--text-primary`).
- **Accessibility**: `aria-hidden="true"`; the status region announces recording state instead of a
  number that changes every second.

### Status banner (`#status`)
- **Structure**: `div[role=status][aria-live=polite]` with a dot and a text span.
- **Variants**: neutral, busy, success, error via `data-tone`.
- **States**: neutral (`--text-secondary`), busy (accent dot, gentle opacity pulse), success
  (success border/dot/text), error (error border/dot/text).
- **Accessibility**: polite live region; messages are sentence-case Russian, no exclamation marks.

### Install button (`#install`)
- **Structure**: full-width `button.install`, hidden until `beforeinstallprompt` fires.
- **States**: default overlay surface + strong border; active `scale(.98)`; focus-visible accent
  outline; hidden in standalone display mode and after install.
- **Accessibility**: plain button label «Установить приложение».

## 6. Motion & Interaction

| Type | Duration | Easing | Usage |
|------|----------|--------|-------|
| Micro | 140ms | `cubic-bezier(.2,.8,.2,1)` | Key press, install press |
| Standard | 240ms | `cubic-bezier(.2,.8,.2,1)` | Color/tone changes, card tint, halo appear |
| Emphasis | 420ms | `cubic-bezier(.16,1,.3,1)` | Reserved for future screen transitions |
| Ambient | 2400ms loop | `cubic-bezier(.2,.8,.2,1)` | Recording halo pulse |

### Rules
- Animate only `transform` and `opacity`; color/filter transitions are allowed on state changes.
- Every state change the user can trigger (press, recording, processing, success, error) is visible
  without reading the text: key glyph + halo + card tint + dot color.
- `prefers-reduced-motion: reduce` disables the halo pulse and all transitions; no information is
  lost.
- The timer's seconds tick is content, not animation — it never animates.

## 7. Depth & Surface

**Strategy: tonal-shift + rim light.** No decorative drop shadows on containers.

- Surface ramp: `#0b0b0f → #14141a → #1c1c24`; the card sits one step above the page.
- Rim: `inset 0 1px 0 rgba(255,255,255,.04)` on the card and key, suggesting one light source above.
- Glow: only the record key carries a shadow — `0 16px 40px -18px var(--accent-glow)` — and it is
  light, not structure.
- Atmosphere: two warm radial washes on the body (top and bottom) plus a 3.5% grain overlay.
- One light direction only: highlights on top edges, glow below the key.

## 8. Accessibility Constraints & Accepted Debt

### Constraints
- WCAG 2.2 AA: body text ≥ 4.5:1 against its surface, large text ≥ 3:1.
- Every interactive element has a visible `focus-visible` ring.
- Record key and install button are ≥ 48px tall; key ≥ 96px.
- Status is a polite live region; no `window.alert`.
- `prefers-reduced-motion` respected (Section 6).
- Canvas and timer are `aria-hidden`; state is always available as text.
- Works offline from the service-worker shell cache; uploading requires network and fails with a
  visible error, never a false success.

### Accepted Debt

| Item | Location | Why accepted | Owner / Exit |
|------|----------|--------------|--------------|
| No light theme | `app.py` | Single-purpose bedtime/voice utility; dark is the intended identity, not a preference | Revisit only if requested |
| No iOS install prompt UI | `app.py` | iOS has no `beforeinstallprompt`; install is via Share → «На экран Домой» | Add an iOS-only hint if iOS use begins |
| Waveform is decorative, not a level meter | `app.py` | Users need confidence that audio is captured, not dB accuracy | Revisit if recording quality complaints appear |
