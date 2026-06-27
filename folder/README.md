# Ideal Dental Construction — One-Page Folder

A print-ready, single-page marketing folder (flyer) for **Ideal Dental
Construction**, built to highlight the company's dental buildout process.

## Files
| File | Purpose |
|------|---------|
| `ideal-dental-construction-folder.html` | Source. Self-contained — no external fonts, images, or CDNs. |
| `ideal-dental-construction-folder.pdf`  | Print-ready export, US Letter (8.5 × 11 in), full-bleed backgrounds. |
| `preview.png` | Rendered preview image. |

## Design — matched to the official brand
- **Colors** (sampled directly from the logo):
  Teal `#176C75` (primary / structure) + Gold `#F6BE1A` (accent / energy),
  plus white and light-teal tints.
- **Logo:** the official Ideal Dental Construction logo, embedded in the
  header (`assets/logo.png`, trimmed from the supplied artwork).
  `assets/logo-transparent.png` is a transparent-background variant.
- **Typography:** a clean sans-serif system for body/headings, complementing
  the logo's own custom lettering.
- **Layout:** header → hero → **Our Building Process** (5-stage centerpiece,
  alternating teal/gold nodes) → What We Build / Why Ideal → consultation CTA.

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
