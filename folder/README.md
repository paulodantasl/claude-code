# Ideal Dental Construction — One-Page Folder

A print-ready, single-page marketing folder (flyer) for **Ideal Dental
Construction**, built to highlight the company's dental buildout process.

## Files
| File | Purpose |
|------|---------|
| `ideal-dental-construction-folder.html` | Source. Self-contained — no external fonts, images, or CDNs. |
| `ideal-dental-construction-folder.pdf`  | Print-ready export, US Letter (8.5 × 11 in), full-bleed backgrounds. |
| `preview.png` | Rendered preview image. |

## Design — harmonized to the Ideal brand
- **Colors:** Navy `#1c366c` (primary) + Slate gray `#7f7f80` (secondary),
  plus white and light navy tints. Sourced from the company's brand profile.
- **Typography:** a single clean sans-serif system (web-safe), matching a
  modern construction/dental website. No serif, no decorative accent color.
- **Logo:** navy "I" monogram + wordmark — a *typographic stand-in*. Drop in
  the official logo asset to replace `.mark` / `.wordmark` in the header.
- **Layout:** header → hero → **Our Building Process** (5-stage centerpiece) →
  What We Build / Why Ideal → consultation CTA.

## Content sourced
Company name, Tampa HQ address, licenses (CGC1537480 · MRSR5016), website, and
email reflect the live business details. The 5-step process and service list
describe a standard dental buildout workflow — adjust copy as needed.

## Regenerate the PDF
```bash
chromium --headless --no-sandbox --no-pdf-header-footer \
  --print-to-pdf=ideal-dental-construction-folder.pdf \
  ideal-dental-construction-folder.html
```
Or simply open the HTML in any browser and **Print → Save as PDF** (set margins
to *None*, enable *Background graphics*).
