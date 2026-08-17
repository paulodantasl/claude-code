# SunLife / Advantage Dental+ — Wesley Chapel TI takeoff

| | |
|--|--|
| JobTread job | **2026-374** `22PaqftN7Gtd` |
| Org | `22P6bRn5p6Pn` |
| Account | SunLife `22PaqfmQebkE` |
| Address | 27151 Halter Loop, Wesley Chapel, FL (Pasco) |
| Permit | COMALT-2026-000467 |
| Sector | Dental **tenant improvement** in existing retail shell |

## Deliverables

- `takeoff.md` — CSI quantities + QA block
- `takeoff_seed.csv` — estimator seed (cost columns blank)
- `overlays/` — geometry verification PNGs
- `plans/` — local PDF extracts / renders
- `jobtread_parameters_final.json` — full 36-param Pave payload (normalized)
- `scripts/build_takeoff_params.py` — param builder

## Calibrated JobTread sheets (prefer)

| Plan id | Sheet | Scale (pt/m) |
|---------|-------|--------------|
| `22PcWyeHswAz` | A0 Life Safety | 29.527559 (⅛″) |
| `22PcWycUvzh8` | A1 Dim / RCP | 44.2913386 (3/16″) |
| `22PcWyeHu4rs` | A2 Furniture | 44.2913386 |
| `22PcWyfwvkcA` | A6 Finish | 44.2913386 |
| `22PcWyfwwtK4` | P1 Plumbing | (see plan) |
| `22PcWyfwwtK5` | M1 Mechanical | |
| `22PcWyfww9WT` | MEP6 Demo | |
| `22PcZFNDh9hW` | E2 Lighting | |
| `22PcZFND5gQL` | E1 Power | |
| `22PcZFNCS3ut` | FP1 Fire | |

## Open RFIs (top)

1. Suite **2,797 SF** (A0) vs permit **2,999 RSF**
2. **HW** geometry re-trace + **HWR**
3. **Vent** live 196.3 vs prior 238.1 label
4. E1 receptacle/switch counts; fire alarm devices; lead lining; duct per-size

## Note on JobTread state

`updateJob.parameters` is **FULL REPLACE**. Always read-merge-write.

**Live geometry (read-back verified):** HVAC×46, fixtures×21, J-boxes×31, doors 10+3, ops×7, T-1/CONC/VCT areas.

**Values-only (geom in `jobtread_parameters_final.json`, MCP ~15KB batch limit):** plumbing W/CW/CA/VAC/V, partitions 418.1 LF, lighting×121. HW remains advisory (RFI).
