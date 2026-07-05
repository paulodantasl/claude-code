# New Commercial Construction (Florida)

Sector reference for ground-up commercial work (retail, office, industrial/flex,
medical office) in Florida. Builds on `florida-code.md`, `estimating-methodology.md`,
and `csi-divisions.md` — this file covers only what **changes** for this sector; do not
re-derive wind/flood/HVHZ or markup mechanics here, cross-reference them.

---

## 1. What changes vs. the default pipeline

| Stage | Commercial-new deltas |
|-------|----------------------|
| **Takeoff** | Full site/civil takeoff (Div 31/32/33) is real money, not an afterthought. Quantify utility extensions to point of connection, retention/detention ponds, and paving/striping incl. **accessible stalls at 12 ft + 5 ft aisle (FL 553.5041)**. Separate shell vs. tenant-improvement quantities from day one. |
| **Procurement** | Delegated-design trades (trusses, precast/tilt, curtain wall, Div 21, Div 28) need **design-build subs with engineer-sealed submittals** — prequalify for engineering capacity, not just install price. Long-lead: switchgear, RTUs, elevators, storefront/curtain wall with FL#/NOA. |
| **Scope** | Draw the **core & shell / warm shell / turnkey** line explicitly (see §7). Assign fire alarm (28) vs. sprinkler (21) vs. fire pump/FDC interfaces. Assign SWPPP maintenance, threshold-inspector cost, special-inspections cost, impact fees — each to exactly one party. |
| **Estimate** | Div 01 built from schedule and staffing, **never a bare %** — 12–24 month durations make GCs the swing item. Carry escalation on long-lead packages. Price delegated-design engineering inside each sub's number. |
| **Proposal** | Qualifications must state: who pays impact/mobility fees, threshold inspection, special inspections, builder's risk; TI exclusions; utility connection/tap fees; permit fees by AHJ valuation. SOV per AIA G702/G703. |
| **Audit** | Check $/SF against sector bands (§9), fire protection priced (21 AND 28), threshold inspection carried if triggered, sales tax on materials, no double-markup of design-build subs, every division priced or excluded. |

---

## 2. Code & classification (FBC-Building)

- Commercial new work runs under **FBC-Building** (current 8th Edition 2023 — confirm
  edition on the code-summary sheet, per `florida-code.md`).
- **Occupancy classification** drives everything: B (office), M (mercantile), A
  (assembly), S/F (storage/factory), I (institutional). **Mixed-use** buildings use
  separated or non-separated provisions (FBC Ch. 5) — separated occupancies add **rated
  assemblies** (walls, floor/ceiling, opening protectives, firestopping) that are
  routinely missed in takeoff.
- **Construction type economics** — type is chosen to make allowable area/height work
  at lowest cost. Know the usual pairings:

| Type | Typical use | Cost posture |
|------|-------------|--------------|
| **II-B** (noncombustible, unrated) | Tilt-wall / CMU + steel joist retail, industrial, big-box | Cheapest $/SF for large single-story footprints; sprinkler usually buys the area increase |
| **II-A / I-B** | Mid-rise office, medical | Rated structure — fireproofing (SFRM/intumescent) appears in Div 07/09; real cost adder |
| **III-B** | CMU shell, combustible interior | Small commercial infill |
| **V-B** (combustible, unrated) | Small strip retail, single-story office | Lowest absolute cost but area-limited; wood in commercial raises insurance |

- Flag when a design sits near an allowable-area limit — a late occupancy or area change
  can force a type upgrade (fireproofing, rated glazing) that blows the estimate.

### Threshold building inspections (FL 553.79 / 553.71)

- **Trigger (verified):** building **greater than 3 stories or 50 ft in height**, OR
  **assembly occupancy exceeding 5,000 SF in area AND occupant content greater than
  500 persons**.
- Requires a **special (threshold) inspector** working to a structural inspection plan
  by the EOR, approved **before permit issuance**.
- **Who pays (verified, FL 553.79):** the **fee owner** selects and pays the threshold
  inspector (inspector answers to the enforcing agency). Confirm the bid documents
  don't shift it to the GC — if silent, qualify it as owner cost.
- Schedule impact: threshold inspections gate shoring/reshoring removal and structural
  milestones — build into the schedule, not just the price.

### Accessibility — FBC-Accessibility + ADA (they differ)

- Baseline is the federal **2010 ADA Standards**; Florida layers **enhanced provisions
  (FL 553.501–.513)** on top. Two that cost real money:
  - **Vertical accessibility (FL 553.509):** access to **all levels**, even where ADA
    would exempt the elevator (limited exceptions: mechanical/unoccupiable spaces,
    non-public spaces housing ≤5 persons; waivers possible). A 2-story building ADA
    might exempt can still need an elevator/LULA in Florida — check before excluding Div 14.
  - **Accessible parking (FL 553.5041):** each accessible space **12 ft wide + 5 ft
    access aisle**, on an accessible route; federal counts apply where stricter.
    Affects striping, signage, curb ramps, and total stall yield on tight sites.
- **Path of travel:** accessible route from public way/transit/parking to entrance —
  site concrete, detectable warnings, ramp rails, cross-slopes ≤2%. A civil takeoff
  item, not an architectural afterthought.

### Fire protection

- **Div 21 sprinklers are normally IN scope** on commercial new work (area increases
  and occupancy usually demand them) — wet system, standpipes if height triggers,
  **FDC**, and a **fire pump** if street pressure won't carry the demand (get a flow
  test; if none exists, flag as RFI/assumption).
- **Div 28 fire alarm** is a separate delegated-design package — don't let it fall
  between the electrician and the sprinkler sub.
- Governing code: **Florida Fire Prevention Code, 8th Edition (2023)** — Florida
  editions of **NFPA 1 and NFPA 101 (2021)**, adopted triennially by the State Fire
  Marshal under **FL 633.202** (verified).
- **The AHJ fire marshal is a separate reviewer** from the building official: separate
  plan review, separate fees, separate inspections, and often underground fire-line
  work by a licensed fire-line contractor (Div 21 vs. Div 33 scope-gap — assign it).

---

## 3. Site / civil weight (heavier than any interior sector)

| Item | Rule / authority | Estimator action |
|------|------------------|------------------|
| **SWPPP / NPDES CGP** | FDEP Construction Generic Permit — required at **≥1 acre disturbed** (or <1 acre within a common plan) (verified). SWPPP before NOI; NOI ≥2 days before construction. | Price BMPs, silt fence, inlet protection, weekly + post-rain inspections, NOI/NOT fees, turbidity monitoring. Assign SWPPP maintenance to one party. |
| **FDOT driveway/connection permit** | **FL 335.18–.187** + Rules 14-96/14-97 F.A.C. (verified) — any connection to a state road. | Turn lanes, signal mods, MOT on state ROW = big dollars; confirm who carries. County/city roads have their own ROW permits. |
| **ERP (water management district)** | **FL Ch. 373 Part IV** (verified) — stormwater management system, wetland impacts; issued by the WMD or FDEP. 2024 statewide stormwater rule update in effect (verified). | Usually owner/civil-engineer obtained pre-bid — confirm status. Drives pond volumes, control structures, wetland mitigation credits (owner cost, verify). |
| **Utility extensions** | Local utility / franchise | Offsite main extensions, lift stations, tap/connection/meter fees — get the utility's letter; fees are frequently owner-paid but bid docs vary. |
| **FDEP water/sewer main permits** | FDEP water main extension permit + wastewater collection permit (**62-555 / 62-604 F.A.C.**) — usually engineer-obtained, confirm status. | GC performs the work: price bacteriological sampling, pressure testing, and schedule the FDEP clearance letter — mains cannot go in service (and no CO) without it. |
| **Impact / mobility fees** | Local ordinance under **FL 163.31801** (Impact Fee Act, verified: dual rational nexus, 90-day notice before increases, no retroactive application to pending permits). | Can run **six to seven figures**. Usually owner-paid at permit — **verify who pays** and exclude explicitly if not carried. |
| **Platting / SDP** | Local ordinance | Site development plan approval and plat recording gate the building permit — 3–12+ month timelines; align escalation and GC duration to realistic NTP. |

---

## 4. Energy & commissioning

- **FBC-Energy Conservation** compliance path: prescriptive/performance IECC-based path
  or the **ASHRAE 90.1** alternative; **COMcheck** is the standard documentation tool
  accepted by most AHJs. Cite the edition from the code-summary sheet.
- Envelope, lighting power density, and fenestration U/SHGC interact with impact-glazing
  selections (see `florida-code.md` §3) — the wind-rated product must ALSO hit the
  energy numbers; price the product that satisfies both.
- **Commissioning (Cx):** FBC-Energy requires mechanical/lighting-controls commissioning
  above equipment-capacity thresholds (per C408 — verify thresholds and edition with
  AHJ). Confirm whether the **owner hires the CxA** or the GC carries it; carry
  functional-testing labor, TAB coordination, and Cx documentation in Div 01/23 either way.

## 5. Delegated design registry (estimate the engineering)

Each of these is a **design-build sub + engineer-sealed submittal**. The engineering is
inside the sub's price only if you told them so — say it in every bid solicitation.

| Package | Div | Sealed deliverable |
|---------|-----|--------------------|
| Wood/steel trusses | 06/05 | Truss engineering pkg, layout, permanent bracing |
| Precast / tilt-wall panels | 03 | Panel design, lifting/bracing engineering, embed plan |
| Pre-engineered metal building | 13 | Frame engineering, sealed reaction loads, FL# panel/fastener approvals |
| Curtain wall / storefront | 08 | Wind-load engineering to C&C pressures + FL#/NOA |
| Fire suppression | 21 | Hydraulic calcs, NFPA 13 shop drawings (fire marshal review) |
| Fire alarm | 28 | Battery calcs, device layout, NFPA 72 (fire marshal review) |
| Deep foundations / shoring (if used) | 31 | Pile/shoring design per geotech |

Also carry: deferred-submittal permit fees, EOR review cycles (schedule), and the
special-inspection hooks each package triggers.

## 6. Special inspections (FBC Ch. 17)

- Structural steel (welds/bolts), concrete (placement, strength), masonry, deep
  foundations, sprayed fireproofing, post-installed anchors — a **special inspections
  program** separate from (and additional to) threshold inspection.
- **Commonly owner-carried** through their testing lab/materials engineer, but bid
  documents shift it often — **verify who carries**; if GC-carried, price it in Div 01
  (testing & inspection) from the Statement of Special Inspections, not as an allowance
  guess.
- Private Provider inspections (FL 553.791) can compress schedule — see
  `florida-code.md` §5; a GC cost if used.

---

## 7. Core & shell vs. warm shell vs. turnkey

| Delivery | Included | Typically EXCLUDED (state it) |
|----------|----------|-------------------------------|
| **Cold / core & shell** | Structure, envelope, roof, core (stairs, elevators, restrooms at core, main risers), site | Tenant HVAC distribution, interior partitions/finishes, tenant electrical beyond house panel, ceilings, sprinkler drops (heads turned up), storefront on tenant bays sometimes |
| **Warm shell** | Cold shell + conditioned space (RTUs set, primary duct), lighting, sprinkler distribution, restrooms, ceiling grid sometimes | Tenant partitions/finishes, tenant-specific MEP, millwork, low-voltage |
| **Turnkey / build-to-suit** | Everything to occupancy incl. TI | OFCI equipment final connections, FF&E, IT/AV, signage (often), security fit-out |

- **Tenant coordination** is a real Div 01 cost on multi-tenant shells: demising-wall
  standards, tenant design criteria enforcement, utility metering splits, and the CO vs.
  shell-permit sequencing (shell CO/CC first, TI permits after). Define which permit
  path the bid covers.
- Sprinkler note: shell bids usually carry heads-up coverage per NFPA 13; TI relocations
  by tenant — say so.

---

## 8. Sector-specific division emphasis

| Div | Direction | Commonly missed in this sector |
|-----|-----------|-------------------------------|
| 01 | **Grows** | Longer duration staffing; tenant coordination; testing/special inspections; SWPPP maintenance; Cx support; project signage/fencing on open sites; hurricane-season prep/demob cycles (secure site, brace panels, lay down crane); post-storm dewatering/SWPPP restoration; weather days beyond A201 baseline |
| 03 | **Grows** (tilt/II-B) | Panel engineering, lifting inserts, crane mob, temporary braces + brace-footing removal, panel joint sealants (07 interface), dock pits/ramps |
| 05 | Grows | Joist/deck on tilt jobs, embeds furnished-vs-set, roof-screen framing, bollards |
| 07 | Grows | Fireproofing on rated types; panel/tilt joint sealants; roof system with FL#/NOA and enhanced perimeter zones; firestopping at rated demising walls |
| 08 | Grows | Delegated curtain wall/storefront engineering; impact glazing per WBDR; automatic entrances; hollow-metal at service areas |
| 09 | Shrinks (shell) | Level of finish stops at core — define exposed-structure paint, shell-only GWB |
| 10 | Appears | Fire-extinguisher cabinets in shell, exterior signage blocking/power, knox box |
| 13 | Appears (industrial/flex) | PEMB delegated frame engineering (sealed reactions to EOR for foundations), anchor bolts furnished-vs-set (03/13 gap), insulation/liner system vs. Div 07 split |
| 14 | Appears | Elevator even at 2 stories (**FL 553.509** vertical accessibility) — check before excluding |
| 21 | **In scope** | Fire pump + flow test, FDC, underground fire line (21/33 gap), heads-up shell coverage |
| 22/23/26 | Shell-split | House vs. tenant metering; stub-outs capped at tenant bays; empty conduit/pathways for tenants; RTU curbs (07/23 gap) |
| 25/27/28 | Appears | Fire alarm delegated design; empty low-voltage pathways; access control rough-in at core doors |
| 31 | **Grows** | Dewatering, muck removal, building pad certification, termite treatment, import/export haul |
| 32 | **Grows** | Heavy-duty vs. standard paving sections, dumpster enclosures, site lighting bases (26 gap), accessible route hardscape, irrigation + landscape code minimums (local ordinance) |
| 33 | **Grows** | Offsite extensions, lift station, FDC/fire-line, duct banks, utility company fees vs. contractor work split |

---

## 9. Markup & commercial posture

| Item | Commercial-new norm | Notes |
|------|--------------------|-------|
| Contract form | **AIA A101 (lump sum) / A102 (GMP w/ shared savings) + A201 general conditions** | Read supplementary conditions for risk shifts (weather days, concealed conditions) |
| Retainage — private | **10% dropping to 5% at 50% complete** (market norm, contractual — no FL statutory cap on private; verify contract) | Negotiate release at substantial completion |
| Retainage — public (FL) | **Capped at 5%** throughout (**FL 218.735** local / **FL 255.078** state; SB 346, eff. 7/1/2023 — verified) | Doesn't apply to contracts ≤ $200,000 or some federally funded work |
| Bonds — public | **FL 255.05**: bond required above **$200k**. State work: not required at ≤$100k; agencies may waive $100k–$200k (DMS delegation). Local government work: awarding authority MAY waive at ≤$200k but can still require a bond at any amount — confirm bid docs. ~1–3% sliding scale | Private: per contract only |
| GC/GR (Div 01) | **6–10% of direct cost** typical at this scale — below the base **8–15%** band in `estimating-methodology.md` §4 because commercial-new direct-cost denominators are large; **always build it from schedule + staffing** | Absolute Div 01 dollars are HIGHER than interior work: full-time super, PM, PE, safety on 12–24 mo durations |
| OH&P | **5–8%** on mid-size competitive-bid commercial — low end of the base **5–15%** band per `estimating-methodology.md` §5; higher on small/negotiated | Never double-markup subs |
| Insurance | GL + **builder's risk** (~0.5–1.5%); confirm **OCIP/CCIP wrap** — if wrapped, back insurance OUT of sub quotes | Wind/named-storm deductibles are large in FL; note who owns the deductible |
| Escalation | Explicit line on 12–24 mo schedules — index long-lead (gear, RTUs, glazing) to delivery dates | Not a hidden contingency; show it |
| Payment terms | Monthly SOV billing (G702/G703); private prompt pay **FL 715.12** (owner pays within 14 days of due date unless contract modifies; interest thereafter — verified); public per FL Prompt Payment Act | Pay-when-paid clauses common — flag |
| LDs | Common on retail/build-to-suit (tenant lease triggers) — price schedule risk or negotiate grace | Ask for mutual delay relief |
| Lien law | **FL Ch. 713** applies on private commercial: NTO within **45 days** of first furnishing; claim of lien within **90 days** of final furnishing (verified) | Public work: bond claims under 255.05 instead |
| Sales tax | Contractor consumes materials — 6% + county surtax on materials (see `florida-code.md` §5) | |
| Davis-Bacon | **Federal**, not FL — applies only if federal funds are in the project; FL has no state prevailing-wage law for private work | Check funding sources on "private" deals with public money |

### Estimating posture — $/SF reasonableness bands (directional, 2025–26 FL market; verify with current quotes)

| Building type | Band (hard cost) |
|---------------|------------------|
| Shell retail (strip, tilt/CMU) | ~$140–220/SF shell |
| Industrial / tilt-wall warehouse | ~$90–150/SF shell |
| Office, mid-rise core & shell | ~$250–400/SF |
| Medical office / outpatient (turnkey) | ~$350–550/SF |

HVHZ, coastal wind, poor soils, and site-heavy parcels push above these bands — see
`florida-code.md`. Auditor: flag anything outside the band and explain why.

---

## 10. Sector red flags / deal-breakers checklist

- [ ] No geotech report on a tilt-wall or heavy-slab job (pad certification, dewatering, deep foundations unknown).
- [ ] Threshold-trigger geometry (>3 stories / >50 ft / big assembly) with no threshold inspection carried by anyone.
- [ ] Bid docs silent on **impact/mobility fees** or utility connection fees — six-figure hole.
- [ ] ERP / SDP / plat not yet approved but schedule assumes immediate NTP.
- [ ] 2-story building with no elevator and no FL 553.509 waiver in hand.
- [ ] No fire-flow test data and no fire pump in the documents.
- [ ] "Shell" undefined — no tenant/landlord scope matrix; TI boundary ambiguous.
- [ ] OCIP/CCIP mentioned but sub quotes not de-scoped for insurance.
- [ ] Delegated-design packages with no design-build sub identified (fire alarm is the usual orphan).
- [ ] LDs with no schedule float and permit timeline outside GC control.
- [ ] Federal funding in the stack with no Davis-Bacon wage rates in the labor pricing.
- [ ] Pay-when-paid + long owner draw cycle on a thin-margin lump sum.
- [ ] Schedule spans hurricane season(s) with no weather-day definition in supplementary conditions and no storm-prep money in Div 01.

## 11. Deliverable additions (beyond the standard bid package)

- **Landlord/tenant scope matrix** (core & shell / warm shell boundary, item by item).
- **Permit & fee schedule**: building permit, fire, ERP status, FDOT/ROW, impact fees — with who-pays column.
- **Delegated design register**: package, sub, engineer, deferred-submittal status.
- **Special inspections & testing matrix** (who hires the lab, what's inspected, cost carrier) incl. threshold inspection if triggered.
- **Long-lead procurement log** with escalation exposure by package (gear, RTUs, glazing, elevator, joists).
- **Preliminary SOV** (G703 format) and cash-flow curve.
- **Alternates**: shell vs. warm-shell upgrades, paving section, roof warranty term.
- **Qualifications**: TI exclusions, owner-paid fees, flow-test assumption, soils assumptions, wind/impact product basis (FL#/NOA).

## 12. Open items to confirm per job

1. AHJ + FBC edition on code-summary sheet; HVHZ or WBDR? (per `florida-code.md`)
2. Occupancy/type and margin to allowable area — any late-change exposure?
3. Threshold building? Who pays the inspector (should be owner per FL 553.79 — confirm docs)?
4. Elevator required by FL 553.509 vertical accessibility, or waiver obtained?
5. Fire flow test / fire pump need; underground fire-line scope owner (21 vs. 33).
6. ERP, SDP, plat, FDOT connection — permit status and realistic NTP date.
7. Impact/mobility fees, utility tap/connection fees — amounts and payer.
8. Special inspections + materials testing — owner's lab or GC-carried?
9. Shell definition and tenant coordination obligations; permit path (shell CC then TI?).
10. OCIP/CCIP or GC-provided builder's risk; named-storm deductible owner.
11. Retainage terms (private: contract; public: 5% cap FL 218.735/255.078) and bond requirement (FL 255.05 thresholds on public).
12. Funding sources — any federal money (Davis-Bacon, federal retainage carve-outs)?
13. Cx scope and CxA employer; COMcheck path and edition.
14. LDs, milestones, and tenant lease dates driving them.
15. How many hurricane seasons does the schedule span; weather-day clause vs. NOAA-normal baseline; who owns storm-prep and named-storm deductible costs?
