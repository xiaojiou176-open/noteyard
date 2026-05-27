# Asset Inventory

This directory stores tracked source assets for the GitHub-native storefront.

## Files

- `readme/hero-public-demo.png`
  - Purpose: reviewed raster export used by the live README proof block
  - Source: exported from `readme/hero-public-demo.svg`
  - Update when: the SVG source changes, or when the README proof story changes
- `readme/hero-public-demo.svg`
  - Purpose: editable source for the README proof block
  - Source: derived from the tracked public-safe demo artifacts under
    `notes_recovery/resources/demo/`
  - Update when: the public demo narrative, AI proof language, or case tree
    proof changes
- `social/social-preview.png`
  - Purpose: upload-ready raster export for the GitHub custom social preview
  - Source: exported from `social/social-preview.svg`
  - Update when: the SVG source changes
- `social/social-preview.svg`
  - Purpose: editable source for a future GitHub custom social preview upload
  - Source: derived from the same public-safe demo proof, plus the canonical
    one-line positioning
  - Update when: the README punchline or proof block changes
- `brand/noteyard-mark.svg`
  - Purpose: editable source for the Pages/site icon and small brand mark
  - Source: repo-owned vector artwork aligned with the landing-page palette
  - Update when: the landing-page palette or product mark changes
- `brand/favicon-32.png`
  - Purpose: raster favicon export for browser tabs
  - Source: exported from `brand/noteyard-mark.svg`
  - Update when: the SVG source changes
- `brand/apple-touch-icon.png`
  - Purpose: iOS and Safari home-screen icon export
  - Source: exported from `brand/noteyard-mark.svg`
  - Update when: the SVG source changes
- `brand/icon-192.png`
  - Purpose: web app manifest icon export
  - Source: exported from `brand/noteyard-mark.svg`
  - Update when: the SVG source changes
- `brand/icon-512.png`
  - Purpose: high-resolution web app manifest icon export
  - Source: exported from `brand/noteyard-mark.svg`
  - Update when: the SVG source changes

## Rules

- Keep these assets aligned with the current root-level public contract.
- Keep the proof language aligned with the current repo reality:
  copy-first recovery first, AI review second, MCP protocol access third.
- Do not add screenshots or visuals that imply a live Pages/docs site unless
  that surface has been explicitly cut over and verified.
- Do not replace these files with untracked external URLs.

## Storefront Checklist

- Re-export the PNG whenever the SVG source changes.
- Review the PNG at full resolution before treating it as upload-ready.
- Do not use Quick Look thumbnail export as the final release path for
  `social-preview.svg`; it produces a square thumbnail instead of the intended
  1280x640 social card.
- Re-export the social preview through a browser-render or other full-frame SVG
  raster path so the PNG keeps the intended 1280x640 aspect ratio.
- Keep the social preview copy aligned with the live README punchline, the
  current release truth, the public proof page, and the current AI/MCP proof
  story.
- Upload the custom social preview from the GitHub repository Settings UI; this
  remains a GitHub-managed step instead of a tracked repo-side fact.
- Treat Topics, the uploaded social preview, and release asset presence as
  GitHub Settings / release-page checks, not repo-side facts.
- If a release-facing bundle is attached, use the synthetic public demo or a
  redacted public-safe export only, and keep any bundled AI proof synthetic.
