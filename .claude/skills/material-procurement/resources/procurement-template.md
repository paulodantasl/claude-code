# Procurement / Buyout — {{PROJECT_NAME}}

| Field | Value |
|-------|-------|
| Project | {{PROJECT_NAME}} |
| Location / AHJ | {{CITY, COUNTY, FL}} |
| Sourced by | procurement-specialist |
| Date of pricing | {{DATE}} — **prices are point-in-time; re-verify before commitment** |
| Basis | takeoff.md / lineitems.csv ({{N}} materials) |

## Price-provenance legend (read this first)

| Tag | Meaning |
|-----|---------|
| **PUB-RETAIL** | Public list/retail price from a live page (Home Depot, Lowe's, SupplyHouse, etc.). Real contractor buyout usually **lower** (trade discount). |
| **PUB-TRADE** | Published trade/contractor price from a distributor page (no login needed). |
| **MKT** | Marketplace/aggregator listing — ballpark only. |
| **QUOTE-REQ** | No public price exists — material is quote-based. Sheet is **RFQ-ready** (right supplier + exact product); a formal quote is required. |
| **NO-DATA** | Live search found nothing usable — direct RFQ required; supplier named if known. |

> Every priced row carries a **source URL + access date**. A row without a URL is not a real price — it is a budgetary estimate and is tagged as such.

## Executive buyout summary

- **Live-priced materials:** {{X}} of {{N}}.  **Quote-required:** {{Y}}.  **No live data:** {{Z}}.
- **Sourced value** (where found) vs prior **budgetary**: ${{___}} vs ${{___}} ({{+/-%}}).
- **Longest-lead items (order first):** {{e.g., impact windows 12–16 wk; switchgear 30+ wk; trusses 6–8 wk}}.
- **Biggest price risks / volatility:** {{lumber, steel, copper, fuel surcharge, post-storm spikes}}.
- **FL product-approval gaps:** {{any specified envelope product lacking a valid FL# / Miami-Dade NOA}}.

## Sourcing by CSI division

> One row per buyable material. Capture supplier + location, exact product/SKU/model, price
> + unit + provenance tag, source URL + date, availability, **lead time**, FL approval
> (envelope items), confidence, and a recommended buy.

### Div {{NN}} — {{Division name}}
| Material (spec) | Supplier (location) | Product / SKU | Price | Unit | Tag | Source (URL · date) | Avail. | Lead time | FL# / NOA | Conf. | Recommendation |
|---|---|---|---:|---|---|---|---|---|---|---|---|
| {{6" CMU 8×8×16}} | {{Distributor, City FL}} | {{ASTM C-90}} | {{$x.xx}} | EA | PUB-TRADE | {{url · 2026-06-19}} | {{in stock}} | {{1–2 wk}} | n/a | med | {{buy here}} |

## Long-lead buyout schedule (order-by priority)

| Rank | Material | Lead time | Order-by (vs NTP) | Why it's critical |
|---|---|---|---|---|
| 1 | {{Impact windows/doors}} | {{12–16 wk}} | {{at NTP}} | {{drives dry-in + CO}} |

## RFQ-required list (no public price — send these out)

- {{Ready-mix concrete 5,000 psi — RFQ to {{local batch plants}}}}
- {{Rebar fab — RFQ to {{rebar fabricators}}}}
- {{Impact window/door package — RFQ to {{PGT/CGI/ES Windows dealers}} (confirm FL#)}}
- {{Trusses — RFQ to {{truss mfr}} with the S-series layout}}
- {{HVAC equipment — RFQ to {{distributor}} by model/tonnage}}

## Assumptions & notes

- {{Published prices are list/retail unless tagged PUB-TRADE; typical trade discount {{range}} not yet applied — confirm at RFQ.}}
- {{Freight/pickup, fuel surcharge, minimum-order, and tax handled per the estimate's markup section.}}
- {{Prices captured {{DATE}}; commodity prices (lumber/steel/copper) move weekly.}}

## procurement.csv schema (hand-off to the estimator)

```
division,item,spec,supplier,location,product_or_sku,unit_price,unit,price_type,source_url,source_date,availability,lead_time,fl_approval,confidence,recommendation
```
