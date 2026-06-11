# Design System — Woven Dusk

Canonical design tokens for the Ariadne webfront. Full guidance lives in `docs/skills/woven-dusk-design/SKILL.md`.

## Color Palette

| Token | Role | Hex |
|-------|------|-----|
| `--color-bg` | Background | `#1B2122` |
| `--color-surface` | Surface | `#222C2A` |
| `--color-primary` | Primary accent | `#4E9E96` |
| `--color-secondary` | Secondary accent | `#C9924A` |
| `--color-text` | Text primary | `#EBE6DC` |
| `--color-text-muted` | Text secondary | `#8A9E98` |
| `--color-border` | Border / divider | `#2D3D3A` |

## CSS Variables

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
  --shadow-elevation: rgba(0, 0, 0, 0.2) 0px 2px 4px;
  --color-focus: #4E9E96;
}
```

## Tailwind Extension

```js
// tailwind.config.js (reference)
colors: {
  bg: '#1B2122',
  surface: '#222C2A',
  primary: '#4E9E96',
  secondary: '#C9924A',
  text: '#EBE6DC',
  'text-muted': '#8A9E98',
  border: '#2D3D3A',
}
```

## Typography

- **Sans:** Geist Sans — display sizes use negative letter-spacing (-2.4px at 48px).
- **Mono:** Geist Mono — code labels, technical captions.
- **Weights:** 400 (body), 500 (UI), 600 (headings).

## Depth

Use shadow-as-border on dark surfaces instead of traditional CSS borders:

```css
box-shadow: rgba(235, 230, 220, 0.08) 0px 0px 0px 1px;
```

## Focus

Focus ring: `2px solid #4E9E96` (oxidized teal).

## Related Skills

- `docs/skills/woven-dusk-design/SKILL.md` — full design guidance
- `docs/skills/ui-frontend/ui/colors.md` — color implementation details
- `docs/skills/ui-frontend/ui/typography.md` — type scale
- `docs/skills/ui-frontend/ui/design-quality.md` — anti-generic quality bar
