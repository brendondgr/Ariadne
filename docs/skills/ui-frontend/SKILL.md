---
name: ui-frontend
description: Use this skill when designing or implementing frontend UI components, pages, dashboards, responsive layouts, visual systems, stack-specific UI libraries, accessibility behavior, typography, colors, motion, and interaction quality.
---

# Frontend Design and UI System

## Structural Dependency

If the user asks to build a full website, dashboard, admin panel, or web application, do not treat this skill as the whole project planner. First follow the `website-architecture` rules so the application structure is defined before visual implementation begins.

For web-facing projects, this skill should also be paired with:

- `accessibility-mobile` for responsive viewport, touch, mobile performance, and mobile SEO checks.
- `ada-compliance` for WCAG/ADA accessibility requirements.

The UI skill should operate after these are known:

- selected app mode
- route map
- page and component hierarchy
- frontend framework and optional UI libraries
- backend/API requirements
- data source expectations
- deployment and runtime assumptions
- design-quality brief or design-system direction

Keep this skill focused on visual design, responsive behavior, accessibility, component polish, and frontend interaction quality.

## Technology Stack Requirement

The user must specify which technology stack to use for implementation. If the stack is missing, actively confirm it before generating UI code.

Supported stack families include, but are not limited to:

- Astro
- SvelteKit
- React/Vite
- React/Next.js
- Flask/Jinja or Flask/HTMX
- Django templates
- API-backed frontend apps

Supported implementation choices include, but are not limited to:

- styling: Tailwind, UnoCSS, SCSS, CSS Modules, vanilla CSS, styled-components
- components: shadcn/ui, Radix UI, Headless UI, native HTML, custom primitives
- data and routing: TanStack Query, TanStack Router, TanStack Table, React Router, framework loaders/actions
- forms: React Hook Form, Zod, framework-native form actions, server-side validation
- motion: Framer Motion/Motion, GSAP, CSS transitions, View Transitions

Do not add optional packages speculatively. Every library must have a clear job and must be recorded in `docs/architecture.md`, `docs/workflow.md`, or `docs/design-system.md`.

## Design Quality Standard

The UI must feel human-designed, intentional, and project-specific. A design looks generated when it relies on default patterns: generic gradients, floating cards, abstract icons, vague copy, fake metrics, oversized heroes, and repeated symmetric sections.

Use `ui/design-quality.md` as the operating standard for web pages and product UI.

## Core Principles

- Purpose and tone: choose a specific visual direction that fits the product, audience, and workflow.
- Project specificity: visual motifs, copy, empty states, data examples, and component names should come from the domain.
- Concrete copy: replace vague claims with exact user actions, outputs, constraints, and outcomes.
- Meaningful imagery: screenshots, product states, diagrams, reports, maps, timelines, datasets, or artifacts should explain something real.
- Design-system consistency: define palette, typography, spacing, radius, shadows, icon style, motion behavior, and component states before building many sections.
- Layout variety: avoid repeating identical card grids; use timelines, diagrams, annotated screenshots, comparison tables, demos, use-case panels, and process maps when they fit.
- Accessibility and mobile quality: follow `ada-compliance` and `accessibility-mobile`; mobile must feel intentionally designed, not just stacked.
- Real states: design loading, empty, error, partial-data, success, permission, long-content, dense-data, and mobile states.
- Animation restraint: motion should explain, guide, or respond. It should not merely decorate.

## Patterns To Avoid

- Default blue/purple neon gradients unless strongly justified by the brand.
- Floating glassmorphism cards used as decoration.
- Abstract glowing orbs, mesh backgrounds, and generic futuristic visuals.
- Generic AI brain, network-node, chat-bubble, or sparkle iconography.
- Fake dashboards and unverifiable metrics.
- Perfectly centered hero sections with no product-specific detail.
- Vague phrases such as "unlock productivity", "AI-powered insights", or "transform your workflow" unless followed by concrete project behavior.
- Every section using the same card grid, heading width, CTA placement, and spacing.

## Component and Asset Index

- [Design Quality and Anti-Generic Rules](ui/design-quality.md)
- [Colors and Themes](ui/colors.md)
- [Typography](ui/typography.md)
- [Layout and Geometry](ui/geometry.md)
- [Motion and Animations](ui/motion.md)
- [Buttons and Interactive Elements](ui/buttons.md)
- [Dropdowns and Selects](ui/dropdowns.md)
- [Modals and Popups](ui/modals.md)
- [Icons System](ui/icons.md)
- [Data Visualization and Graphs](ui/data-viz.md)

## Related Skills

- [Mobile Accessibility and Responsive UX](../accessibility-mobile/SKILL.md)
- [ADA and WCAG Compliance](../ada-compliance/SKILL.md)
