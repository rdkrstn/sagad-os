# SagadOS Design System v0.1

**Brand:** SagadOS  
**Category:** Open-source customer operations OS  
**Direction:** Premium Open Ops  
**Status:** Design system foundation only. Logo/icon SVGs are intentionally out of scope for this version.

---

## 1. Brand Intent

SagadOS should signal:

> **Trust. Freedom. Transparency. Modularity. A system that works.**

The brand should feel like open infrastructure, not locked SaaS. It should look credible to business operators and inspectable to technical teams.

### What SagadOS is

- Open-source customer operations infrastructure
- Self-hosted by default
- Modular and extensible
- Transparent and inspectable
- Calm, reliable, and operational

### What SagadOS is not

- A chatbot brand
- A purple AI product
- A glossy SaaS wrapper
- A vendor-lock-in platform
- A playful support widget
- A cyberpunk developer toy

---

## 2. Brand Thesis

```txt
SagadOS is the link between conversations, systems, and outcomes.
```

Design implication:

- Use visible structure.
- Use modular blocks.
- Use connection lines and system states.
- Use restrained color.
- Make the interface feel inspectable.

---

## 3. Design Principles

### 1. Trust through restraint

Do not over-design. Use deep navy, warm off-white, clear hierarchy, and controlled accents.

### 2. Freedom through openness

The product should feel portable, exportable, and self-owned. Avoid visuals that imply a closed black box.

### 3. Transparency through structure

Show routes, states, modules, logs, docs, and configuration. Use cards, borders, code blocks, and status rows.

### 4. Modularity through repetition

Repeat the same visual grammar across the brand:

- modules
- nodes
- connectors
- badges
- workflow cards
- panels
- routes

### 5. Working over magical

SagadOS should not sell AI magic. It should show that the system is running, observable, and useful.

---

## 4. Color System

### Core Palette

| Token | Hex | Role | Signal |
|---|---:|---|---|
| `--sagad-ink` | `#08111F` | Primary text, dark sections, logo base | Trust, infrastructure, seriousness |
| `--sagad-bg` | `#F4F0E8` | Main background | Openness, warmth, transparency |
| `--sagad-surface` | `#FFFFFF` | Cards, docs, product panels | Cleanliness, readability |
| `--sagad-border` | `#D8D3C8` | Borders, dividers, input outlines | Structure without heaviness |
| `--sagad-muted` | `#6F746F` | Secondary text, captions, metadata | Calm support text |
| `--sagad-deep-teal` | `#008F7A` | Main brand accent | Stable connection, ownership |
| `--sagad-electric-teal` | `#00D4AA` | Active nodes, highlights, live states | Working, connected, alive |
| `--sagad-signal-blue` | `#2F80FF` | Links, docs, selected states, info | Software familiarity, navigation |

### Semantic Palette

| Token | Hex | Role |
|---|---:|---|
| `--sagad-success` | `#22C55E` | Success, online, completed, healthy |
| `--sagad-warning` | `#F5B84B` | Warning, pending, requires attention |
| `--sagad-danger` | `#E5484D` | Error, destructive, failed |
| `--sagad-dark` | `#050B12` | Deep dark background |
| `--sagad-dark-surface` | `#0D1724` | Dark panels, terminal blocks |

### Why teal

Teal is the main SagadOS signal because it sits between blue and green.

- **Blue** signals trust and software, but it is generic in B2B SaaS.
- **Green** signals success and health, but it should be reserved for system state.
- **Teal** combines trust, connection, activity, and calm technical confidence.

Main color rule:

```txt
Navy builds trust.
Off-white creates openness.
Teal shows connection.
Blue supports navigation.
Green is only for success.
```

### Color Usage Ratio

Use color with discipline.

| Color Group | Recommended Usage |
|---|---:|
| Off-white / white surfaces | 55–65% |
| Navy / ink | 20–30% |
| Deep teal | 8–12% |
| Electric teal | 3–5% |
| Blue + semantic colors | As needed only |

### CSS Tokens

```css
:root {
  /* Core */
  --sagad-ink: #08111F;
  --sagad-bg: #F4F0E8;
  --sagad-surface: #FFFFFF;
  --sagad-border: #D8D3C8;
  --sagad-muted: #6F746F;

  /* Brand */
  --sagad-deep-teal: #008F7A;
  --sagad-electric-teal: #00D4AA;
  --sagad-signal-blue: #2F80FF;

  /* Semantic */
  --sagad-success: #22C55E;
  --sagad-warning: #F5B84B;
  --sagad-danger: #E5484D;

  /* Dark mode */
  --sagad-dark: #050B12;
  --sagad-dark-surface: #0D1724;
}
```

---

## 5. Typography

### Font Stack

| Role | Font | Use |
|---|---|---|
| Brand / Headings | `Manrope` | Wordmark placeholder, homepage headlines, product headings |
| UI / Body | `Inter` | App UI, documentation, forms, dashboard text |
| Code / Labels | `JetBrains Mono` | CLI, badges, metadata, system logs, API labels |

### CSS Font Tokens

```css
:root {
  --font-brand: "Manrope", ui-sans-serif, system-ui, sans-serif;
  --font-ui: "Inter", ui-sans-serif, system-ui, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, SFMono-Regular, monospace;
}
```

### Type Scale

| Token | Size | Line Height | Weight | Use |
|---|---:|---:|---:|---|
| `display-xl` | `clamp(3rem, 7vw, 5.5rem)` | `0.95` | `800` | Hero headlines |
| `display-lg` | `clamp(2.5rem, 5vw, 4rem)` | `1.0` | `800` | Major section headers |
| `heading-xl` | `40px` | `1.1` | `750` | Page titles |
| `heading-lg` | `32px` | `1.15` | `700` | Section titles |
| `heading-md` | `24px` | `1.2` | `700` | Card titles |
| `body-lg` | `18px` | `1.65` | `400` | Hero/body lead |
| `body-md` | `16px` | `1.6` | `400` | Standard body |
| `body-sm` | `14px` | `1.5` | `400` | Captions, helper text |
| `label` | `12px` | `1.2` | `600` | UI labels |
| `mono-label` | `11px` | `1.2` | `600` | Badges, metadata |

### Typography Rules

- Use `Manrope` for emotional and strategic surfaces.
- Use `Inter` for product clarity.
- Use `JetBrains Mono` only for technical cues.
- Do not make the brand feel like a terminal-only hacker tool.
- Avoid overly round or playful typography.

---

## 6. Layout System

### Container

```css
:root {
  --container-max: 1200px;
  --container-wide: 1440px;
  --container-padding: clamp(20px, 4vw, 48px);
}
```

### Grid

| Breakpoint | Grid |
|---|---|
| Mobile | 4 columns |
| Tablet | 8 columns |
| Desktop | 12 columns |

### Spacing Scale

Use an 8px-based spacing system with a few smaller utility values.

```css
:root {
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-16: 64px;
  --space-20: 80px;
  --space-24: 96px;
  --space-32: 128px;
}
```

### Section Padding

```css
.section {
  padding-block: clamp(72px, 10vw, 128px);
}
```

---

## 7. Shape, Borders, and Surfaces

### Radius Tokens

| Token | Value | Use |
|---|---:|---|
| `--radius-xs` | `6px` | Tiny controls, checkboxes |
| `--radius-sm` | `8px` | Inputs, small cards |
| `--radius-md` | `12px` | Buttons, badges, panels |
| `--radius-lg` | `16px` | Product cards, app panels |
| `--radius-xl` | `24px` | Large hero cards |
| `--radius-pill` | `999px` | Pills and badges |

### Border Tokens

```css
:root {
  --border-subtle: 1px solid #D8D3C8;
  --border-strong: 1px solid rgba(8, 17, 31, 0.18);
  --border-dark: 1px solid rgba(255, 255, 255, 0.10);
}
```

### Shadow Tokens

```css
:root {
  --shadow-sm: 0 4px 12px rgba(8, 17, 31, 0.06);
  --shadow-md: 0 12px 32px rgba(8, 17, 31, 0.08);
  --shadow-lg: 0 24px 64px rgba(8, 17, 31, 0.12);
}
```

### Surface Rules

- Use warm off-white for brand pages.
- Use white for inspectable product panels.
- Use navy for high-trust sections, CLI blocks, and footer areas.
- Use borders to show structure.
- Use shadows subtly, not decoratively.

---

## 8. Component Foundations

### Buttons

#### Primary Button

Use for main actions: deploy, view docs, connect GitHub, start setup.

```css
.btn-primary {
  background: var(--sagad-deep-teal);
  color: #FFFFFF;
  border: 1px solid var(--sagad-deep-teal);
  border-radius: 12px;
  padding: 12px 18px;
  font-family: var(--font-ui);
  font-size: 14px;
  font-weight: 600;
  box-shadow: var(--shadow-sm);
}

.btn-primary:hover {
  background: #007C6B;
}
```

#### Secondary Button

```css
.btn-secondary {
  background: #FFFFFF;
  color: var(--sagad-ink);
  border: 1px solid var(--sagad-border);
  border-radius: 12px;
  padding: 12px 18px;
  font-family: var(--font-ui);
  font-size: 14px;
  font-weight: 600;
}

.btn-secondary:hover {
  border-color: rgba(8, 17, 31, 0.28);
  background: #FAFAF8;
}
```

### Cards

```css
.card {
  background: var(--sagad-surface);
  border: 1px solid var(--sagad-border);
  border-radius: 16px;
  box-shadow: var(--shadow-sm);
  padding: 24px;
}
```

### Module Cards

Use module cards for integrations, workflows, automations, and open-source extensions.

```css
.module-card {
  background: #FFFFFF;
  border: 1px solid var(--sagad-border);
  border-radius: 16px;
  padding: 20px;
  display: grid;
  gap: 12px;
}

.module-card[data-active="true"] {
  border-color: var(--sagad-electric-teal);
  box-shadow: 0 0 0 3px rgba(0, 212, 170, 0.12);
}
```

### Badges

```css
.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--sagad-border);
  background: #FFFFFF;
  color: var(--sagad-ink);
  border-radius: 999px;
  padding: 6px 10px;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
}
```

Recommended badge labels:

```txt
open-source
self-hosted
modular
MIT
API-first
portable
inspectable
```

### Status Pills

```css
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: 999px;
  padding: 6px 10px;
  font-family: var(--font-ui);
  font-size: 13px;
  font-weight: 500;
}

.status-online {
  color: #166534;
  background: rgba(34, 197, 94, 0.12);
}

.status-warning {
  color: #92400E;
  background: rgba(245, 184, 75, 0.18);
}

.status-error {
  color: #991B1B;
  background: rgba(229, 72, 77, 0.12);
}
```

### Code Blocks

```css
.code-block {
  background: var(--sagad-dark);
  color: #E6FFF8;
  border: 1px solid rgba(255,255,255,0.10);
  border-radius: 16px;
  padding: 20px;
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.7;
}

.code-block .success {
  color: var(--sagad-electric-teal);
}
```

### Alerts

```css
.alert-info {
  background: rgba(47, 128, 255, 0.08);
  border: 1px solid rgba(47, 128, 255, 0.24);
  color: #174EA6;
  border-radius: 12px;
  padding: 14px 16px;
}

.alert-success {
  background: rgba(34, 197, 94, 0.10);
  border: 1px solid rgba(34, 197, 94, 0.24);
  color: #166534;
  border-radius: 12px;
  padding: 14px 16px;
}
```

---

## 9. Iconography Direction

Logo iconography is not final. Do not create or lock SVGs yet.

For product and UI icons, use a consistent stroke-based library such as Lucide or Radix Icons.

### Icon Style

- Stroke-based
- Rounded caps
- No filled icons unless used as status dots
- 20px or 24px default size
- `1.75–2px` stroke width
- Navy by default
- Teal only for active/connected states

### Icon Themes

Use icons that signal:

- modules
- workflows
- links
- integrations
- docs
- code
- lock/unlock
- routing
- analytics
- status

### Logo/Icon Exploration Notes for Later

The future SagadOS mark should explore:

```txt
S as chain link
S as modular route
S as connected workflow
S as two linked components
S as open system path
```

Avoid:

```txt
chat bubbles
AI sparkles
purple gradients
mascots
overly glossy app icons
```

---

## 10. Motion System

Motion should make the system feel responsive, not animated for decoration.

### Timing

```css
:root {
  --motion-fast: 120ms;
  --motion-base: 180ms;
  --motion-slow: 280ms;
  --ease-standard: cubic-bezier(0.2, 0.8, 0.2, 1);
}
```

### Usage

Use motion for:

- hover states
- route connection reveals
- module activation
- status updates
- panel transitions

Avoid:

- bouncy easing
- flashy loading animations
- excessive parallax
- AI-glow effects

---

## 11. Voice and Copy

### Voice Attributes

```txt
Clear.
Calm.
Technical.
Transparent.
Operator-focused.
```

### Copy Rules

- Say what the system does.
- Show ownership and portability.
- Avoid hype.
- Avoid vague AI claims.
- Prefer concrete system language.

### Approved Language

```txt
Open customer operations.
Self-host your workflows.
Own your customer data.
Connect conversations, systems, and outcomes.
Transparent by design.
Modular by default.
Built for portability.
No vendor lock-in.
```

### Avoid

```txt
Revolutionary AI
Magical automation
10x support
Skyrocket retention
The future of customer experience
All-in-one growth engine
```

---

## 12. Application Patterns

### Website

- Warm off-white background
- Navy headlines
- Deep teal CTA
- White product cards
- CLI/docs/product previews
- Badges for open-source, self-hosted, modular

### Documentation

- Mostly white surface
- Navy sidebar
- Blue for links
- Teal for active route/state
- Code blocks in dark navy
- Minimal marketing language

### GitHub / README

- Use clean README badges
- Show CLI quickstart
- Show architecture overview
- Show license and self-hosting clearly
- Prioritize credibility over polish

### Product UI

- White panels on off-white page background
- Clear borders
- Visible workflow states
- Modular cards for flows/integrations
- Green reserved for success/healthy states

---

## 13. Starter Homepage Copy

### Hero

```txt
Open customer operations.

SagadOS is the open-source customer operations OS for modern service teams. Self-host your workflows, connect your tools, and keep ownership of your customer data.
```

### CTA Pair

```txt
View GitHub
Read the Docs
```

### Feature Pillars

```txt
Modular by design
Connect only what you need. Extend when the system grows.

Self-hosted by default
Own your workflows, data, and infrastructure.

Transparent operations
Every route, handoff, and automation is inspectable.

Built to work
Clean workflows for conversations, support, and customer outcomes.
```

---

## 14. Implementation Starter CSS

```css
body {
  margin: 0;
  background: var(--sagad-bg);
  color: var(--sagad-ink);
  font-family: var(--font-ui);
  font-size: 16px;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

h1, h2, h3, h4 {
  font-family: var(--font-brand);
  color: var(--sagad-ink);
  letter-spacing: -0.035em;
}

a {
  color: var(--sagad-signal-blue);
  text-decoration-thickness: 1px;
  text-underline-offset: 3px;
}

::selection {
  background: rgba(0, 212, 170, 0.22);
  color: var(--sagad-ink);
}

:focus-visible {
  outline: 3px solid rgba(0, 212, 170, 0.45);
  outline-offset: 2px;
}
```

---

## 15. Brand QA Checklist

Before publishing any SagadOS asset, check:

- Does it feel trustworthy?
- Does it avoid vendor-lock-in signals?
- Does it look transparent and inspectable?
- Does it use teal as a connection/status signal, not decoration?
- Is green reserved for success states?
- Does it avoid generic AI/purple/glow language?
- Does it feel modular?
- Would this look credible in GitHub, docs, and an operator dashboard?
- Can a technical user understand what is happening?
- Can a business user trust that the system works?

---

## 16. Asset Scope for Next Version

Do not create these yet, but plan for them:

```txt
sagados-logo-primary.svg
sagados-logo-compact.svg
sagados-mark.svg
sagados-app-icon-dark.svg
sagados-app-icon-light.svg
sagados-favicon.svg
sagados-og-image.png
sagados-readme-header.png
sagados-docs-header.png
```

The logo should be solved separately after the mark direction is finalized.

---

## Final Direction

SagadOS should look like:

```txt
Premium open-source infrastructure.
Clean enough for operators.
Technical enough for builders.
Transparent enough to trust.
Modular enough to own.
```

Core visual idea:

> **An open operating layer where customer conversations, systems, and outcomes stay connected without lock-in.**
