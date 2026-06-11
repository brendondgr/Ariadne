# Colors & Themes — Woven Dusk

The application uses the **Woven Dusk** dark palette. All colors must meet ADA WCAG 2.2 AA contrast requirements.

### Core Accessibility Mandates

- **Text & Core Information**: Must meet a contrast ratio of **4.5:1** against the background.
- **Large Text, Icons & Borders**: Non-text UI components and large text require a contrast ratio of **3:1**.
- **Information Dependency**: Color must **never** be the only way to convey meaning. Pair status colors with icons, text, or patterns.

### Woven Dusk Palette

| Role | Hex | Usage |
|------|-----|-------|
| Background | `#1B2122` | Page canvas — charcoal with green undertone |
| Surface | `#222C2A` | Cards, panels — dark moss |
| Primary accent | `#4E9E96` | CTAs, links, focus — oxidized teal |
| Secondary accent | `#C9924A` | Warm highlights — antique amber |
| Text primary | `#EBE6DC` | Headings, body — warm off-white |
| Text secondary | `#8A9E98` | Captions, metadata — greyed sage |
| Border / divider | `#2D3D3A` | Dividers, input borders — soft moss |

### Semantic Colors

Map semantic states to Woven Dusk accents:

- **Success:** `#4E9E96` (teal) + checkmark icon
- **Warning:** `#C9924A` (amber) + warning icon
- **Error:** `#C9924A` at higher saturation or a desaturated red variant — always pair with text label
- **Info:** `#8A9E98` (sage) + info icon

### Shadow-as-Border (Dark Surfaces)

Replace traditional CSS borders with shadow borders on dark surfaces:

```css
box-shadow: rgba(235, 230, 220, 0.08) 0px 0px 0px 1px;
```

### Implementation (CSS Variables)

```css
:root {
  --color-bg: #1B2122;
  --color-surface: #222C2A;
  --color-primary: #4E9E96;
  --color-secondary: #C9924A;
  --color-text: #EBE6DC;
  --color-text-muted: #8A9E98;
  --color-border: #2D3D3A;
  --shadow-border: rgba(235, 230, 220, 0.08) 0px 0px 0px 1px;
  --color-focus: #4E9E96;
}
```

### Tailwind Usage

```html
<div class="bg-surface text-text border-border shadow-[var(--shadow-border)] rounded-lg p-4">
  <span class="text-primary font-semibold">Category Label</span>
  <p class="text-text-muted text-sm">Supporting description text.</p>
</div>
```

See `docs/design-system.md` and `docs/skills/woven-dusk-design/SKILL.md` for full guidance.
