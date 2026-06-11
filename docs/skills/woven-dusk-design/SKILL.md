---
name: woven-dusk-design
description: Woven Dusk design system for the Ariadne webfront. Use when designing or implementing UI colors, typography, components, layout, or visual polish. Dark theme with Geist fonts and shadow-as-border depth.
---

# Woven Dusk Design System

A blend of warmth and technical precision — feels premium without feeling cold. Adapted from Vercel/Geist structural principles with the Woven Dusk dark palette.

## Color Palette

| Role | Hex | CSS Variable |
|------|-----|--------------|
| Background | `#1B2122` | `--color-bg` |
| Surface | `#222C2A` | `--color-surface` |
| Primary accent | `#4E9E96` | `--color-primary` |
| Secondary accent | `#C9924A` | `--color-secondary` |
| Text primary | `#EBE6DC` | `--color-text` |
| Text secondary | `#8A9E98` | `--color-text-muted` |
| Border / divider | `#2D3D3A` | `--color-border` |

The green-undertoned dark background connects to the Ariadne thread motif. Oxidized teal is the primary interactive accent; antique amber adds warmth.

## Typography

- **Primary:** Geist Sans — fallbacks: Arial, Apple Color Emoji, Segoe UI Emoji
- **Monospace:** Geist Mono — fallbacks: ui-monospace, SFMono-Regular, Roboto Mono, Menlo
- **OpenType:** `"liga"` enabled globally on Geist text

### Hierarchy

| Role | Size | Weight | Letter Spacing |
|------|------|--------|----------------|
| Display Hero | 48px | 600 | -2.4px to -2.88px |
| Section Heading | 40px | 600 | -2.4px |
| Card Title | 24px | 600 | -0.96px |
| Body | 16–18px | 400 | normal |
| Button / Link | 14px | 500 | normal |
| Mono Caption | 12–13px | 500 | normal, uppercase for labels |

**Weights:** 400 (body), 500 (UI), 600 (headings). No bold (700) except micro-badges.

## Depth & Shadow-as-Border

On dark surfaces, replace traditional CSS borders with shadow borders:

```css
box-shadow: rgba(235, 230, 220, 0.08) 0px 0px 0px 1px;
```

Multi-layer card stack:

```css
box-shadow:
  rgba(235, 230, 220, 0.08) 0px 0px 0px 1px,
  rgba(0, 0, 0, 0.2) 0px 2px 4px,
  rgba(0, 0, 0, 0.15) 0px 8px 16px -8px;
```

## Focus & Interactive

- **Focus ring:** `2px solid #4E9E96` (oxidized teal)
- **Primary CTA:** background `#4E9E96`, text `#1B2122`
- **Secondary CTA:** transparent with shadow-border, text `#EBE6DC`, amber hover accent
- **Links:** `#4E9E96` with underline

## Components

### Primary Button
- Background: `#4E9E96`
- Text: `#1B2122`
- Padding: 8px 16px
- Radius: 6px

### Ghost Button
- Background: transparent
- Text: `#EBE6DC`
- Shadow-border on dark surface
- Hover: surface color `#222C2A`

### Card
- Background: `#222C2A`
- Shadow-border (no CSS border)
- Radius: 8px
- Title: 24px weight 600, `#EBE6DC`
- Body: 16px weight 400, `#8A9E98`

### Pill Badge
- Background: `rgba(78, 158, 150, 0.15)` (teal tint)
- Text: `#4E9E96`
- Radius: 9999px

## Layout

- Base spacing unit: 8px
- Max content width: ~1200px
- Section padding: 80px+ desktop, 48px mobile
- Border radius scale: 6px (buttons), 8px (cards), 12px (featured), 9999px (badges)

## Responsive Breakpoints

| Name | Width |
|------|-------|
| Mobile | <600px |
| Tablet | 600–1024px |
| Desktop | 1024–1200px |
| Large | >1200px |

## Do's

- Use Geist with negative letter-spacing at display sizes
- Use shadow-as-border instead of traditional CSS borders on dark surfaces
- Apply teal for primary actions, amber for warm secondary accents
- Keep the palette achromatic-warm — no neon or generic gradient heroes
- Follow anti-generic rules in `docs/skills/ui-frontend/ui/design-quality.md`

## Don'ts

- Don't use positive letter-spacing on Geist Sans at display sizes
- Don't use weight 700 on body text
- Don't introduce Ship Red / Preview Pink / Develop Blue workflow colors
- Don't use heavy shadows (>0.2 opacity)
- Don't rely on color alone for status — pair with icons or text

## Implementation Reference

- Tokens: `docs/design-system.md`
- Colors: `docs/skills/ui-frontend/ui/colors.md`
- Typography: `docs/skills/ui-frontend/ui/typography.md`
- Web source: `web/src/styles/tokens.css`
