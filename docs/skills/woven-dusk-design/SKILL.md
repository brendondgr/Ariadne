---
name: woven-dusk-design
description: Woven Dusk design system for the Ariadne webfront. Use when designing or implementing UI colors, typography, components, layout, depth, responsive behavior, or visual polish. All-in-one reference — Geist typography, shadow-as-border depth, dark Woven Dusk palette.
---

# Woven Dusk Design System

> Category: Developer Tools / Agent Infrastructure
> Structural inspiration: Vercel/Geist precision. Palette: Woven Dusk dark theme.

A blend of warmth and technical precision — feels premium without feeling cold. The green-undertoned dark background is unusual without being jarring; oxidized teal connects directly to the Ariadne thread motif; antique amber gives warmth that prevents the site from reading as generic dark tech.

## 1. Visual Theme & Atmosphere

Woven Dusk treats the interface like a compiler treats code — every unnecessary token is stripped away until only structure remains. The page sits on charcoal with green undertone (`#1B2122`) with warm off-white text (`#EBE6DC`), creating a gallery-like depth where every element earns its pixel. This is minimalism as engineering principle, not decoration.

The Geist font family is the crown jewel. Geist Sans uses aggressive negative letter-spacing (-2.4px to -2.88px at display sizes), creating headlines that feel compressed, urgent, and engineered — like code minified for production. At body sizes, tracking relaxes but geometric precision persists. Geist Mono completes the system for code, terminal output, and technical labels. Both fonts enable OpenType `"liga"` globally.

What distinguishes this system is its shadow-as-border philosophy. On dark surfaces, traditional CSS borders are replaced with `box-shadow: rgba(235, 230, 220, 0.08) 0px 0px 0px 1px` — a zero-offset, zero-blur, 1px-spread shadow that creates a border-like line without box-model implications. Depth is built on layered multi-value shadow stacks: one layer for the border, one for soft elevation, one for ambient depth.

**Key Characteristics:**

- Geist Sans with extreme negative letter-spacing (-2.4px to -2.88px at display)
- Geist Mono for code and technical labels with OpenType `"liga"` globally
- Shadow-as-border replaces traditional CSS borders throughout
- Multi-layer shadow stacks for nuanced depth (border + elevation + ambient)
- Woven Dusk dark canvas — charcoal background, warm off-white text, moss surfaces
- Oxidized teal (`#4E9E96`) for primary interactive accents; antique amber (`#C9924A`) for warm secondary accents
- Focus ring: `#4E9E96` (oxidized teal) for accessibility
- Pill badges (9999px radius) with tinted teal or amber backgrounds

## 2. Color Palette & Roles

### Woven Dusk Core

> **Base neutralized (2026-07):** per analyst direction the base canvas was
> de-greened to neutral black/dark-gray. Teal (`#4E9E96`) and amber (`#C9924A`)
> remain the *only* accents — green now appears as a highlight, never as the base.

| Role | Hex | CSS Variable | Usage |
|------|-----|--------------|-------|
| Background | `#0E0F11` | `--color-bg` | Page canvas — near-black neutral |
| Surface | `#17181A` | `--color-surface` | Cards, panels — dark gray |
| Primary accent | `#4E9E96` | `--color-primary` | CTAs, links, focus — oxidized teal |
| Secondary accent | `#C9924A` | `--color-secondary` | Warm highlights — antique amber |
| Text primary | `#ECEBE8` | `--color-text` | Headings, body — near-neutral off-white |
| Text secondary | `#9A9A97` | `--color-text-muted` | Captions, metadata — neutral gray |
| Border / divider | `#2A2B2E` | `--color-border` | Dividers, input borders — neutral gray |

### Workflow Accent Colors

Use only in workflow or pipeline context — never decoratively:

| Step | Color | Hex | Role |
|------|-------|-----|------|
| Explore | Sage | `#8A9E98` | Discovery / planning stage |
| Build | Teal | `#4E9E96` | Active development stage |
| Ship | Amber | `#C9924A` | Completion / deployment stage |

### Console / Code Colors

Syntax highlighting on dark surfaces:

- **Console Teal** (`#4E9E96`): strings, primary syntax
- **Console Amber** (`#C9924A`): constants, numbers
- **Console Sage** (`#8A9E98`): comments, muted tokens
- **Console Text** (`#EBE6DC`): default code foreground

### Interactive

- **Link Teal** (`#4E9E96`): Primary link color with underline decoration
- **Focus Teal** (`#4E9E96`): `--color-focus`, focus ring on interactive elements
- **Ring Teal** (`rgba(78, 158, 150, 0.5)`): Tailwind ring utility on dark surfaces

### Neutral Scale (Dark)

| Token | Hex | Usage |
|-------|-----|-------|
| Text primary | `#EBE6DC` | Headings, nav text, primary body |
| Text secondary | `#8A9E98` | Description copy, captions |
| Text tertiary | `#6B7F79` | Muted links, placeholder-adjacent |
| Text disabled | `#4A5A55` | Disabled states |
| Border | `#2D3D3A` | Dividers, structural borders |
| Surface elevated | `#2A3532` | Modals, dropdowns, floating panels |

### Surface & Overlay

- **Overlay Backdrop** (`rgba(27, 33, 34, 0.85)`): modal/dialog backdrop
- **Selection** (`rgba(78, 158, 150, 0.25)`): text selection highlight
- **Badge Teal Bg** (`rgba(78, 158, 150, 0.15)`): pill badge background
- **Badge Teal Text** (`#4E9E96`): pill badge text
- **Badge Amber Bg** (`rgba(201, 146, 74, 0.15)`): secondary badge background
- **Badge Amber Text** (`#C9924A`): secondary badge text

### Shadows & Depth

- **Border Shadow** (`rgba(235, 230, 220, 0.08) 0px 0px 0px 1px`): signature — replaces traditional borders
- **Subtle Elevation** (`rgba(0, 0, 0, 0.2) 0px 2px 4px`): minimal lift for cards
- **Card Stack** (`rgba(235, 230, 220, 0.08) 0px 0px 0px 1px, rgba(0, 0, 0, 0.2) 0px 2px 4px, rgba(0, 0, 0, 0.15) 0px 8px 16px -8px, rgba(235, 230, 220, 0.04) 0px 0px 0px 1px`): full multi-layer card shadow with inner warm highlight
- **Ring Border** (`rgba(235, 230, 220, 0.12) 0px 0px 0px 1px`): lighter ring for tabs and images

### CSS Variables (Implementation)

```css
:root {
  --color-bg: #0E0F11;
  --color-surface: #17181A;
  --color-primary: #4E9E96;
  --color-secondary: #C9924A;
  --color-text: #ECEBE8;
  --color-text-muted: #9A9A97;
  --color-border: #2A2B2E;
  --color-focus: #4E9E96;
  --shadow-border: rgba(235, 230, 220, 0.08) 0px 0px 0px 1px;
  --shadow-elevation: rgba(0, 0, 0, 0.2) 0px 2px 4px;
}
```

## 3. Typography Rules

### Font Family

- **Primary**: `Geist Variable`, fallbacks: `Arial, Apple Color Emoji, Segoe UI Emoji, Segoe UI Symbol`
- **Monospace**: `Geist Mono Variable`, fallbacks: `ui-monospace, SFMono-Regular, Roboto Mono, Menlo, Monaco, Liberation Mono, DejaVu Sans Mono, Courier New`
- **OpenType Features**: `"liga"` enabled globally; `"tnum"` for tabular numbers on captions

Install via `@fontsource-variable/geist` and `@fontsource-variable/geist-mono`.

### Hierarchy

| Role | Font | Size | Weight | Line Height | Letter Spacing | Notes |
|------|------|------|--------|-------------|----------------|-------|
| Display Hero | Geist | 48px (3.00rem) | 600 | 1.00–1.17 | -2.4px to -2.88px | Maximum compression |
| Section Heading | Geist | 40px (2.50rem) | 600 | 1.20 | -2.4px | Feature section titles |
| Sub-heading Large | Geist | 32px (2.00rem) | 600 | 1.25 | -1.28px | Card headings |
| Sub-heading | Geist | 32px (2.00rem) | 400 | 1.50 | -1.28px | Lighter sub-headings |
| Card Title | Geist | 24px (1.50rem) | 600 | 1.33 | -0.96px | Feature cards |
| Card Title Light | Geist | 24px (1.50rem) | 500 | 1.33 | -0.96px | Secondary card headings |
| Body Large | Geist | 20px (1.25rem) | 400 | 1.80 | normal | Introductions |
| Body | Geist | 18px (1.13rem) | 400 | 1.56 | normal | Standard reading |
| Body Small | Geist | 16px (1.00rem) | 400 | 1.50 | normal | Standard UI text |
| Body Medium | Geist | 16px (1.00rem) | 500 | 1.50 | normal | Navigation, emphasis |
| Body Semibold | Geist | 16px (1.00rem) | 600 | 1.50 | -0.32px | Strong labels, active states |
| Button / Link | Geist | 14px (0.88rem) | 500 | 1.43 | normal | Buttons, links |
| Button Small | Geist | 14px (0.88rem) | 400 | 1.00 | normal | Compact buttons |
| Caption | Geist | 12px (0.75rem) | 400–500 | 1.33 | normal | Metadata, tags |
| Mono Body | Geist Mono | 16px (1.00rem) | 400 | 1.50 | normal | Code blocks |
| Mono Caption | Geist Mono | 13px (0.81rem) | 500 | 1.54 | normal | Code labels |
| Mono Small | Geist Mono | 12px (0.75rem) | 500 | 1.00 | normal | Uppercase technical labels |
| Micro Badge | Geist | 7px (0.44rem) | 700 | 1.00 | normal | Uppercase tiny badges |

### Principles

- **Compression as identity**: Display sizes use -2.4px to -2.88px letter-spacing. Tracking relaxes progressively: -1.28px at 32px, -0.96px at 24px, -0.32px at 16px, normal at 14px.
- **Ligatures everywhere**: Every Geist element enables `"liga"`. Ligatures are structural, not decorative.
- **Three weights, strict roles**: 400 (body), 500 (UI), 600 (headings). No bold (700) except micro-badges.
- **Mono for identity**: Geist Mono uppercase serves as the developer-console voice.

## 4. Component Stylings

### Buttons

**Primary Teal (Primary CTA)**

- Background: `#4E9E96`
- Text: `#1B2122`
- Padding: 8px 16px
- Radius: 6px
- Hover: opacity 0.9
- Focus: `2px solid #4E9E96` outline
- Use: Primary CTA ("Get Started", "Start Building")

**Ghost (Shadow-bordered)**

- Background: transparent
- Text: `#EBE6DC`
- Padding: 8px 16px
- Radius: 6px
- Shadow: `rgba(235, 230, 220, 0.08) 0px 0px 0px 1px`
- Hover: background `#222C2A`
- Focus: `2px solid #4E9E96` outline
- Use: Secondary actions

**Pill Badge**

- Background: `rgba(78, 158, 150, 0.15)` (teal tint) or `rgba(201, 146, 74, 0.15)` (amber tint)
- Text: `#4E9E96` or `#C9924A`
- Padding: 0px 10px
- Radius: 9999px
- Font: 12px weight 500
- Use: Status badges, tags, feature labels

**Large Pill (Navigation)**

- Background: transparent or `#222C2A`
- Radius: 64px–100px
- Use: Tab navigation, section selectors

### Cards & Containers

- Background: `#222C2A`
- Border: via shadow — `rgba(235, 230, 220, 0.08) 0px 0px 0px 1px`
- Radius: 8px (standard), 12px (featured/image cards)
- Shadow stack: border + elevation + ambient + inner warm highlight (see Card Stack above)
- Image cards: shadow-border with 12px top radius
- Hover: subtle shadow intensification

### Inputs & Forms

- Background: `#222C2A`
- Text: `#EBE6DC`
- Placeholder: `#8A9E98`
- Focus outline: `2px solid #4E9E96`
- Border: via shadow technique, not traditional border
- Error state: amber accent + text label (never color alone)

### Navigation

- Sticky header on `#1B2122` with bottom shadow-border
- Logo/wordmark left-aligned
- Links: Geist 14px weight 500, `#EBE6DC` text, `#8A9E98` on hover
- Active: weight 600 or underline in teal
- CTA: primary teal button right-aligned
- Mobile: hamburger menu collapse

### Image Treatment

- Screenshots with shadow-border treatment
- Top-rounded images: `12px 12px 0px 0px` radius
- Subtle atmospheric gradient behind hero (teal/amber at very low opacity — not neon)

### Distinctive Components

**Workflow Pipeline**

- Three-step horizontal pipeline: Explore → Build → Ship
- Accent colors: Sage → Teal → Amber
- Connected with lines/arrows
- Each step: 14px Geist Mono uppercase label + 24px Geist weight 600 title + 16px description in `#8A9E98`

**Trust Bar / Logo Grid**

- Logos in desaturated/muted treatment on dark background
- Horizontal scroll or grid layout
- Subtle `#2D3D3A` border separation

**Metric Cards**

- Large number: Geist 48px weight 600, `#EBE6DC`
- Description: `#8A9E98` body text
- Shadow-bordered card on `#222C2A`

## 5. Layout Principles

### Spacing System

- Base unit: 8px
- Scale: 1px, 2px, 3px, 4px, 5px, 6px, 8px, 10px, 12px, 14px, 16px, 32px, 36px, 40px
- Notable gap: jumps from 16px to 32px — no 20px or 24px in primary scale

### Grid & Container

- Max content width: approximately 1200px
- Hero: centered single-column with generous top padding
- Feature sections: 2–3 column grids for cards
- Full-width dividers using shadow-border or `#2D3D3A`
- Code/dashboard screenshots as full-width or contained with shadow-border

### Whitespace Philosophy

- **Gallery depth**: Massive vertical padding between sections (80px–120px+). Space communicates intentionality.
- **Compressed text, expanded space**: Aggressive negative letter-spacing on headlines counterbalanced by generous surrounding whitespace.
- **Section rhythm**: Separation comes from shadow-borders and spacing — not color banding.

### Border Radius Scale

| Size | Value | Use |
|------|-------|-----|
| Micro | 2px | Inline code snippets |
| Subtle | 4px | Small containers |
| Standard | 6px | Buttons, functional elements |
| Comfortable | 8px | Cards, list items |
| Image | 12px | Featured cards, image containers |
| Large | 64px | Tab navigation pills |
| XL | 100px | Large navigation links |
| Full Pill | 9999px | Badges, status pills |
| Circle | 50% | Menu toggle, avatars |

## 6. Depth & Elevation

| Level | Treatment | Use |
|-------|-----------|-----|
| Flat (Level 0) | No shadow | Page background `#1B2122`, text blocks |
| Ring (Level 1) | `rgba(235,230,220,0.08) 0px 0px 0px 1px` | Shadow-as-border for most elements |
| Light Ring (Level 1b) | `rgba(235,230,220,0.12) 0px 0px 0px 1px` | Lighter ring for tabs, images |
| Subtle Card (Level 2) | Ring + `rgba(0,0,0,0.2) 0px 2px 4px` | Standard cards |
| Full Card (Level 3) | Ring + Subtle + ambient + inner warm highlight | Featured cards, highlighted panels |
| Focus | `2px solid #4E9E96` outline | Keyboard focus on all interactive elements |

**Shadow Philosophy**: Multi-value shadow stacks where each layer has a distinct purpose — border (1px spread), ambient softness (2–4px blur), depth at distance (8px blur with negative spread), and an inner warm ring (`rgba(235, 230, 220, 0.04)`) that makes cards feel built, not floating.

### Decorative Depth

- Hero gradient: barely visible teal/amber atmospheric wash — not neon or pastel
- Section borders: shadow-border or `#2D3D3A` between major sections
- Depth comes from shadow layering and text contrast — not background color banding

## 7. Do's and Don'ts

### Do

- Use Geist Sans with aggressive negative letter-spacing at display sizes (-2.4px to -2.88px at 48px)
- Use shadow-as-border (`rgba(235, 230, 220, 0.08) 0px 0px 0px 1px`) instead of traditional CSS borders
- Enable `"liga"` on all Geist text
- Use the three-weight system: 400 (body), 500 (UI), 600 (headings)
- Apply teal for primary actions, amber for warm secondary accents
- Use multi-layer shadow stacks for cards (border + elevation + ambient + inner highlight)
- Keep the palette achromatic-warm — Woven Dusk tokens are the system
- Follow anti-generic rules in `docs/skills/ui-frontend/ui/design-quality.md`
- Pair status colors with icons or text labels (WCAG 2.2 AA)

### Don't

- Don't use positive letter-spacing on Geist Sans at display sizes
- Don't use weight 700 on body text — 600 is the maximum (except micro-badges)
- Don't use traditional CSS `border` on cards — use shadow-border
- Don't introduce neon colors, generic gradient heroes, or off-palette accents
- Don't apply workflow accent colors (sage/teal/amber) decoratively outside pipeline context
- Don't use heavy shadows (>0.2 opacity)
- Don't use pill radius (9999px) on primary action buttons — pills are for badges/tags only
- Don't skip the inner warm highlight ring in card shadows
- Don't rely on color alone to convey meaning

## 8. Responsive Behavior

### Breakpoints

| Name | Width | Key Changes |
|------|-------|-------------|
| Mobile Small | <400px | Tight single column, minimal padding |
| Mobile | 400–600px | Standard mobile, stacked layout |
| Tablet Small | 600–768px | 2-column grids begin |
| Tablet | 768–1024px | Full card grids, expanded padding |
| Desktop Small | 1024–1200px | Standard desktop layout |
| Desktop | 1200–1400px | Full layout, maximum content width |
| Large Desktop | >1400px | Centered, generous margins |

### Touch Targets

- Buttons: 8px–16px vertical padding minimum
- Navigation links: 14px with adequate spacing
- Pill badges: 10px horizontal padding for tap targets
- Mobile menu toggle: 50% radius circular button

### Collapsing Strategy

- Hero: 48px display → scales down, maintains negative tracking proportionally
- Navigation: horizontal links + CTAs → hamburger menu
- Feature cards: 3-column → 2-column → single column stacked
- Section spacing: 80px+ → 48px on mobile

## 9. Agent Prompt Guide

### Quick Color Reference

- Primary CTA: Oxidized Teal (`#4E9E96`) with text `#1B2122`
- Background: Charcoal (`#1B2122`)
- Surface: Dark Moss (`#222C2A`)
- Heading text: Warm Off-White (`#EBE6DC`)
- Body text: Greyed Sage (`#8A9E98`)
- Border (shadow): `rgba(235, 230, 220, 0.08) 0px 0px 0px 1px`
- Link: Teal (`#4E9E96`)
- Focus ring: Teal (`#4E9E96`)
- Secondary accent: Amber (`#C9924A`)

### Example Component Prompts

- "Create a hero section on `#1B2122` background. Headline at 48px Geist weight 600, line-height 1.00, letter-spacing -2.4px, color `#EBE6DC`. Subtitle at 20px Geist weight 400, line-height 1.80, color `#8A9E98`. Teal CTA button (`#4E9E96` bg, `#1B2122` text, 6px radius, 8px 16px padding) and ghost button (transparent, shadow-border, 6px radius)."
- "Design a card: `#222C2A` background, no CSS border. Use shadow stack with inner warm highlight. Radius 8px. Title at 24px Geist weight 600, letter-spacing -0.96px, color `#EBE6DC`. Body at 16px weight 400, `#8A9E98`."
- "Build a pill badge: `rgba(78,158,150,0.15)` background, `#4E9E96` text, 9999px radius, 0px 10px padding, 12px Geist weight 500."
- "Create navigation: sticky header on `#1B2122`. Geist 14px weight 500 for links, `#EBE6DC` text. Teal CTA right-aligned. Shadow-border on bottom."
- "Design a workflow section: Explore (sage `#8A9E98`), Build (teal `#4E9E96`), Ship (amber `#C9924A`). Each step: 14px Geist Mono uppercase label + 24px Geist weight 600 title + 16px description in `#8A9E98`."

### Iteration Guide

1. Always use shadow-as-border instead of CSS border on dark surfaces
2. Letter-spacing scales with font size: -2.4px at 48px, -1.28px at 32px, -0.96px at 24px, normal at 14px
3. Three weights only: 400 (read), 500 (interact), 600 (announce)
4. Color is functional — teal for primary, amber for warm secondary, sage for muted
5. The inner warm highlight ring in card shadows creates subtle depth on dark surfaces
6. Geist Mono uppercase for technical labels, Geist Sans for everything else
7. After webfront changes, run `npm run build` to verify compilation

## Implementation Reference

| Resource | Path |
|----------|------|
| CSS tokens | `web/src/styles/tokens.css` |
| Tailwind theme | `web/src/index.css` |
| Color details | `docs/skills/ui-frontend/ui/colors.md` |
| Typography details | `docs/skills/ui-frontend/ui/typography.md` |
| Anti-generic quality | `docs/skills/ui-frontend/ui/design-quality.md` |
