# Noteyard Design Canon

This file is the visual source of truth for every public and local UI surface
in this repository. The goal is not to invent a house style from scratch. The
goal is to copy the strongest patterns from proven products and keep the
current repo surfaces aligned with them.

## Product Lens

Noteyard is not a generic AI app, a hosted SaaS, or a marketing-heavy
landing page. It is a copy-first forensic workbench with a public front door
and a local review cockpit.

The design must always optimize for four things, in this order:

1. Minimize cognitive load
2. Look deliberate and premium
3. Feel productized, not like scattered docs
4. Reveal deeper tooling progressively instead of all at once

If a visual choice makes the surface prettier but harder to understand in
10 seconds, it is wrong.

## Reference Stack

Do not trust personal taste over these references.

### Public surfaces

Primary references:

- Apple: stage-like clarity, billboard typography, one idea per section
- Mintlify: documentation-as-product clarity, white-space discipline,
  explanation before feature soup
- Cursor: warm editorial developer-tool tone, premium cream surfaces, humane
  technical storytelling

### Local cockpit surfaces

Primary references:

- Linear: dark control-plane hierarchy, chroma restraint, dense-but-readable
  utility UI
- Raycast: desktop-tool atmosphere, glass depth, local-power-tool confidence

## Surface Split

Treat the repo as two coordinated products.

### 1. Public front door

Files:

- `index.html`
- `proof.html`
- `404.html`
- social preview assets

This layer behaves like an exhibit guide. It must:

- tell the operator where to start
- prove the workflow before explaining integrations
- separate repo-owned truth from platform-owned truth
- keep builder lanes below the first-success path

### 2. Local review cockpit

Files:

- `notes_recovery/apps/dashboard.py`

This layer behaves like a command room. It must:

- start with orientation, not raw data
- expose advanced evidence only after the overview
- keep visual density high but legible
- feel like a serious workstation, not a playful marketing dashboard

## Visual Thesis

### Public surfaces

Warm paper + forensic desk + productized museum route.

The feeling should be:

- calm
- deliberate
- premium
- trustworthy
- slightly editorial

Never:

- startup gradient soup
- generic SaaS card wall
- playful consumer app energy
- loud AI branding

### Cockpit surfaces

Dark review cabin + guided evidence console.

The feeling should be:

- operational
- layered
- desktop-native
- high-signal
- quietly cinematic

Never:

- rainbow metrics dashboard
- cute analytics toy
- over-decorated sci-fi panel
- all panes equally loud

## Typography

### Public surfaces

Use the existing stack:

- display: `SF Pro Display`, then `Inter`
- body: `SF Pro Text`, then `Inter`
- mono: `SF Mono`, then `IBM Plex Mono` / `Menlo`

Rules:

- headlines are short, compressed, and decisive
- body copy is readable in one pass, not essay-like
- one section should not carry multiple competing text sizes
- monospace appears only when it adds operator trust

### Cockpit surfaces

Use:

- interface: `Inter` / system sans
- code labels: `SF Mono`

Rules:

- metrics and labels use strong contrast
- tab labels should read like destinations, not jargon
- paragraphs stay short and subordinate to headings, chips, and data tables

## Color System

### Public surfaces

Base:

- paper background: warm cream
- ink: deep blue-black
- accent: restrained forensic teal
- warm support accent: muted copper

Rules:

- no purple bias
- no multicolor marketing palette
- accent color is for guidance and action, not decoration
- cards should feel like glass-paper sheets, not plastic tiles

### Cockpit surfaces

Base:

- background: near-black blue
- foreground: cold white
- accent: pale cyan / electric blue
- success: muted green

Rules:

- color mostly communicates grouping and state
- avoid more than one strong accent family
- dark surfaces need depth from layers, not from random hue changes

## Composition Rules

### Public surfaces

- first viewport must answer: what is this, who is it for, what do I do first
- hero is a poster, not a collage
- one dominant visual plane per section
- each section gets one job only
- proof path must be visible before builder detail
- long explanations must move into secondary or tertiary layers

### Cockpit surfaces

- always lead with orientation
- the first screen should tell the operator what to open next
- advanced views must live in tabs, drill-downs, or lower zones
- raw tables are allowed only after a headline explains why they matter
- comparison flows appear only after the single-case story is understandable

## Progressive Disclosure Contract

This is the core UX doctrine.

### Public surfaces

Order:

1. What the product is
2. The first-success path
3. How the workflow is shaped
4. Builder lane and integrations
5. Proof / distribution / support references

Never open with:

- host configs
- registry mechanics
- edge-case caveats
- giant documentation shelves

### Cockpit surfaces

Order:

1. Start here
2. Timeline
3. Spotlight
4. Stitched review

Interpretation:

- `Start here` = orientation and proof spine
- `Timeline` = event chronology and source distribution
- `Spotlight` = pattern mining and search-heavy evidence
- `Stitched review` = candidate judgment and operator verdict capture

## Component Rules

### Pills and chips

Use for:

- route signposting
- proof-state hints
- small metadata labels

Do not use them as decorative confetti.

### Cards

Public surfaces:

- cards are allowed, but only when they group one clear idea
- avoid card mosaics with equal visual weight

Cockpit:

- cards exist to separate decision zones, not to turn every table into a box

### Code blocks

- code blocks should feel operational and high-trust
- wrap long commands so keyboard accessibility stays intact
- code should support the narrative, not interrupt it

### Tabs

- tabs should represent actual cognitive phases
- no more than 4-5 top-level tabs without a very strong reason
- active tab contrast must be obvious without relying on color only

## Motion

Motion must be calm and meaningful.

Allowed:

- soft fade-up entrance on public panels
- subtle hover lift on pills and action cards
- gentle section reveal

Avoid:

- perpetual float effects
- parallax for its own sake
- noisy micro-animations
- motion that competes with reading

Respect `prefers-reduced-motion`.

## Writing Rules

- write like an operator guide, not a brand campaign
- explain the first next step in plain language
- separate repo-owned truth from platform-side truth
- avoid generic “AI-powered” rhetoric
- do not stack multiple metaphors in one section

## Anti-Patterns

Never ship any of the following:

- generic SaaS hero with three random feature cards
- colorful dashboard-card wallpaper
- documentation wall with no route
- dark mode that feels gaming-oriented instead of operational
- giant dense paragraphs above the fold
- equal emphasis on every section
- public copy that sounds more certain than the proof boundary allows

## Acceptance Checklist

Before calling a UI surface done, verify:

- the first screen explains the next action in under 10 seconds
- the strongest action is visually obvious
- builder details are downstream of operator understanding
- contrast is strong enough for long reading
- code blocks and scrollable regions remain keyboard-safe
- decorative elements can be removed without collapsing hierarchy
- the surface still feels productized when read as plain text

## Implementation Mapping

### Public HTML pages

- use `assets/site.css` as the shared token and component layer
- keep `index.html`, `proof.html`, and `404.html` visually related
- preserve required discovery tokens and public-proof wording

### Streamlit cockpit

- inject a shared theme layer before rendering
- keep data logic untouched unless UX truly requires logic change
- prefer structural re-ordering over new forensic features

## Final Rule

When in doubt, copy the proven products harder and simplify one more step.
Beauty here comes from confidence, sequencing, and restraint, not novelty.
