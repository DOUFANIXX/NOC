---
name: NOC Performance System
colors:
  surface: '#0b1326'
  surface-dim: '#0b1326'
  surface-bright: '#31394d'
  surface-container-lowest: '#060e20'
  surface-container-low: '#131b2e'
  surface-container: '#171f33'
  surface-container-high: '#222a3d'
  surface-container-highest: '#2d3449'
  on-surface: '#dae2fd'
  on-surface-variant: '#c2c6d8'
  inverse-surface: '#dae2fd'
  inverse-on-surface: '#283044'
  outline: '#8c90a1'
  outline-variant: '#424656'
  surface-tint: '#b3c5ff'
  primary: '#b3c5ff'
  on-primary: '#002b75'
  primary-container: '#0066ff'
  on-primary-container: '#f8f7ff'
  inverse-primary: '#0054d6'
  secondary: '#b7c8e1'
  on-secondary: '#213145'
  secondary-container: '#3a4a5f'
  on-secondary-container: '#a9bad3'
  tertiary: '#ffb59d'
  on-tertiary: '#5d1900'
  tertiary-container: '#cc4204'
  on-tertiary-container: '#fff6f4'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#dae1ff'
  primary-fixed-dim: '#b3c5ff'
  on-primary-fixed: '#001849'
  on-primary-fixed-variant: '#003fa4'
  secondary-fixed: '#d3e4fe'
  secondary-fixed-dim: '#b7c8e1'
  on-secondary-fixed: '#0b1c30'
  on-secondary-fixed-variant: '#38485d'
  tertiary-fixed: '#ffdbd0'
  tertiary-fixed-dim: '#ffb59d'
  on-tertiary-fixed: '#390c00'
  on-tertiary-fixed-variant: '#832600'
  background: '#0b1326'
  on-background: '#dae2fd'
  surface-variant: '#2d3449'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 30px
    fontWeight: '700'
    lineHeight: 38px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-base:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
  data-mono:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.01em
  label-caps:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  gutter: 16px
  margin: 24px
---

## Brand & Style

This design system is engineered for high-stakes, 24/7 network monitoring environments where cognitive load management is paramount. The brand personality is **authoritative, vigilant, and precise**, favoring functional efficiency over decorative elements. 

The visual style follows a **Corporate Modern** aesthetic with elements of **Minimalism**. It utilizes a "Dark-First" philosophy to reduce eye strain during long shifts, while maintaining a rigorous structural grid. The emotional response is one of "calm control"—the UI stays out of the way until an anomaly requires immediate, decisive action. Aesthetics are driven by data density and legibility, ensuring that critical alerts are never obscured by visual noise.

## Colors

The palette is optimized for a **Dark-First** implementation using deep slates and charcols to create a recessive background that allows colorful status indicators to pop. 

- **Primary Blue:** A high-contrast, "Trustworthy Blue" used for actions, primary selections, and active states.
- **Surface Strategy:** In dark mode, the primary background uses `background_dark`, while elevated containers (cards, tables) use `surface_dark`. 
- **Semantic Logic:** Status colors are high-chroma to ensure they pass WCAG AA accessibility standards against dark backgrounds. 
- **Light Mode:** The light mode alternative flips the logic to a `Slate-50` background with `White` surfaces, maintaining the same primary and semantic accents to ensure brand continuity.

## Typography

The system utilizes **Inter** across all levels due to its exceptional legibility at small sizes and high x-height. 

- **Data Density:** For tabular data and technical metrics, the system uses a slightly tighter `data-mono` variant of Inter (leveraging its tabular num features) to ensure numbers align vertically for quick scanning.
- **Hierarchy:** Bold, uppercase labels are used for table headers and category descriptors to differentiate them clearly from live data.
- **Optimization:** Line heights are kept tight (approx 1.2x - 1.4x) to maximize the amount of information visible on a single 1080p or 4K NOC dashboard without scrolling.

## Layout & Spacing

This design system employs a **Fluid Grid** model with a 12-column structure, optimized for widescreen monitor arrays. 

- **Density:** We use a 4px baseline shift. Most internal components use `8px` or `12px` padding to maintain high information density while preventing visual clumping.
- **Navigation:** A collapsed-first side navigation (64px width) expands to 240px, maximizing real estate for the primary data console.
- **Responsive Behavior:** On ultra-wide displays, content containers should use a `max-width` of 1920px to maintain readability, centering the layout within the viewport.

## Elevation & Depth

To maintain a "Modern Enterprise" feel, the system avoids heavy shadows. Depth is communicated through **Tonal Layering** and **Low-Contrast Outlines**.

- **Z-Index Layers:** The background is the lowest layer. Surface cards sit 1-step lighter than the background.
- **Borders:** In dark mode, surfaces are defined by a 1px `border_dark` rather than shadows. This creates a crisp, technical blueprint aesthetic.
- **Drawers & Modals:** Only top-level overlays (like "Detail Drawers" for node inspection) receive an **Ambient Shadow**: a 15% opacity black shadow with a 20px blur to separate the operational layer from the monitoring layer.
- **Active State:** Active or hovered rows in tables use a subtle primary-tinted background bleed (e.g., Primary at 8% opacity).

## Shapes

The shape language is **Soft (0.25rem)**, prioritizing a professional and engineered feel over the "bubbly" appearance of consumer apps.

- **Components:** Standard buttons, input fields, and status badges use the 4px (`0.25rem`) radius.
- **Large Elements:** Summary cards and detail drawers may use up to 8px (`0.5rem`) to provide a subtle distinction for container boundaries.
- **Consistency:** Never use fully rounded "pill" shapes for buttons or status indicators, as they consume too much horizontal padding in high-density tables.

## Components

- **Sophisticated Tables:** The core of the design system. Rows should be 36px-40px high. Columns use "Safe Workflow" cues: if a metric is critical, the text or a 4px left-border indicator should reflect the semantic color.
- **Status Badges:** Compact, rectangular badges with a subtle background tint (15%) and high-contrast foreground text.
- **Summary Cards with Sparklines:** Top-level metrics cards featuring a large value and a 48px high trend sparkline using the primary or semantic color.
- **Side Navigation:** Icon-centric with tooltips for the collapsed state, transitioning to labeled links when expanded.
- **Detail Drawers:** Right-aligned slide-out panels for "Drill-down" actions, allowing the user to keep the main table in view while inspecting a specific node.
- **Alert Patterns:** Toast notifications appear in the top-right, color-coded by severity, requiring manual dismissal for "Critical" levels to ensure operator acknowledgement.
- **Inputs:** Understated, using a 1px border. Focus states are indicated by a 2px Primary Blue glow to provide a "Safe" and clear focus ring.