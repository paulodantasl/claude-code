# Florida Construction Reference

Shared knowledge base for the takeoff / scope / estimating / audit agents.
**Default jurisdiction is Florida.** Always confirm the actual Authority Having
Jurisdiction (AHJ) from the documents (title block, code-summary sheet, permit
forms) and note it. If a project is outside Florida, say so explicitly and adjust.

---

## 1. Florida Building Code (FBC)

- Florida operates under the **Florida Building Code**, currently the **8th Edition
  (2023)**, based on the I-Codes (IBC/IRC). Verify the edition on the code-summary
  sheet; older drawings may cite the 7th Edition (2020).
- Volumes: FBC-**Building**, FBC-**Residential**, FBC-**Existing Building**,
  FBC-**Mechanical**, FBC-**Plumbing**, FBC-**Fuel Gas**, FBC-**Energy Conservation**,
  FBC-**Accessibility** (Florida amends the 2017 ADA), and the **Florida Fire
  Prevention Code** (NFPA-based, enforced by the State Fire Marshal / local FD).
- The code-summary sheet (usually G-series) states occupancy classification,
  construction type (I-A … V-B), allowable area/height, sprinkler status, occupant
  load, and the governing wind/flood criteria. **Read it first** — it frames the
  entire scope.

## 2. High-Velocity Hurricane Zone (HVHZ)

- **HVHZ = Miami-Dade County and Broward County.** Triggers the strictest provisions
  in the FBC (Chapters 16-Hi, 17-Hi, etc.).
- In the HVHZ, products exposed to wind/debris generally require a **Miami-Dade NOA
  (Notice of Acceptance)**. Statewide, products may instead carry a **Florida Product
  Approval number (FL#)**. Roofing, windows, doors, storefront, skylights, shutters,
  soffit, siding, and attachments all need approvals — **estimate the approved product,
  not the cheapest generic one.**
- HVHZ also drives enhanced inspections, testing (TAS 201/202/203 impact & cyclic),
  and tighter detailing. It raises cost materially vs. inland.

## 3. Wind Load

- Design per **ASCE 7** (the edition referenced by the FBC). Drawings list the
  **ultimate design wind speed (V_ult)** and **risk category (I–IV)**.
- Typical V_ult: ~**170–185 mph** in HVHZ/coastal South FL, ~**150–170 mph** along
  much of the coast, ~**130–150 mph** inland. Higher speed → heavier connections,
  thicker glazing, more anchorage.
- **Windborne Debris Region (WBDR):** within ~1 mi of coast where V_ult ≥ 130 mph (or
  ≥ 140 mph elsewhere). Requires **impact-resistant glazing or approved shutters**
  (large-missile below 30 ft, small-missile above). This is a frequent scope-and-cost
  driver — confirm whether impact glazing OR shutters are specified.
- Distinguish **MWFRS** (main wind-force resisting system) from **Components &
  Cladding (C&C)** pressures — C&C governs windows, doors, roofing, soffit.

## 4. Flood (FEMA / NFIP)

- Coastal FL has extensive **Special Flood Hazard Areas**. Zones: **VE** (coastal high
  hazard, wave action), **AE/A** (1% annual flood), **X** (outside). Drawings/civil
  give the **Base Flood Elevation (BFE)** and the **Design Flood Elevation (DFE = BFE +
  freeboard)**; many FL communities require **1–2 ft freeboard**.
- Cost/scope drivers: elevated structure, **flood vents** (AE) or **breakaway walls**
  (VE), flood-damage-resistant materials below DFE, no mechanical/electrical below DFE,
  stem-wall vs. pile foundations. Confirm zone and DFE from the civil/architectural set.

## 5. Other Florida-specific scope drivers

- **Subterranean termite protection** is required (soil chemical treatment or approved
  alternative) for new construction — a real, often-missed line item (Div 31 / 07).
- **FBC-Energy** compliance: envelope, fenestration U-factor/SHGC, duct sealing, blower
  door / duct leakage testing on many projects.
- **Threshold buildings** (FL Statute 553.71/553.79): generally > 3 stories or > 50 ft,
  or assembly > 5,000 sf / occupant load > 500. Require a **Special Inspector
  (threshold inspection)** — a budgeted cost, usually owner- or GC-carried.
- **Private Provider inspections** (FL 553.791) — an alternative to AHJ inspectors;
  sometimes used to accelerate schedule (a GC cost).
- **Contractor licensing (DBPR):** CGC (Certified General), CBC (Building), CRC
  (Residential), plus specialty licenses (electrical, mechanical, plumbing, roofing,
  pool, etc.). Affects who can legally self-perform vs. must subcontract.
- **Florida sales tax on materials:** for real-property improvement contracts the
  contractor is generally the **consumer** of materials and pays sales tax (state **6%**
  + **county discretionary surtax**, ~0.5–1.5%). **Tax materials, not the marked-up
  contract price.** (Retail sale + installation can differ — note the contract type.)
- **Construction lien law (FL Ch. 713):** Notice to Owner, lien rights, conditional/
  unconditional releases. Not a takeoff item but belongs in proposal qualifications.
- **Public-work bonds (FL 255.05 "Little Miller Act"):** payment & performance bonds
  required on most public projects; private per contract.
- **Soils:** high water table, sandy/organic (muck) soils, and limestone/cap rock are
  common. Expect **dewatering**, possible **muck removal / soil stabilization**, and on
  poor soils **deep foundations** (auger-cast or helical piles). Look for a geotech
  report; if absent, flag as an assumption/RFI.
- **Impact fees & concurrency:** local (transportation, schools, parks, utilities) — can
  be large; usually owner-carried but confirm who pays in the bid documents.
- **Hurricane detailing:** roof-to-wall straps/clips, continuous load path, secondary
  water barrier / sealed roof deck, rated soffit — verify these are carried.

## 6. Plan-set discipline keys (sheet prefixes)

`G` General · `C` Civil · `L` Landscape · `S` Structural · `A` Architectural ·
`I` Interiors · `Q` Equipment · `F`/`FP` Fire Protection · `P` Plumbing ·
`M` Mechanical · `E` Electrical · `T`/`LV` Technology/Low-Voltage · `FA` Fire Alarm.

**Always reconcile drawings against the specs and incorporate every addendum.**
Convention: **drawings govern quantity, specifications govern quality**; follow the
order-of-precedence clause in the bid documents when they conflict, and raise an RFI
rather than guessing.
