# Fixtures

Synthetic project documents used to regression-test the parsing + chat flow.

For Phase 0 we ship only this README and a generator script (`make-fixtures.ts`)
so the repo stays small. The script fabricates a tiny PDF spec excerpt and a
spreadsheet bid, then writes them to `./out/`.

## Generate locally

```bash
pnpm --filter @procurement/db exec tsx ../../fixtures/make-fixtures.ts
```

Then upload `./out/concrete-spec-excerpt.pdf` as a `spec` and
`./out/concrete-bid-vendor-a.xlsx` as a `bid` from the project UI.

## Phase 1 plan

When we add bid comparison and compliance, this directory will hold:

- `concrete-spec.pdf` (~20 pages with a real-looking Division 03 excerpt)
- `addendum-01.pdf` (changes one mix design value)
- `bid-vendor-a.xlsx`, `bid-vendor-b.xlsx` (with line-item differences)
- `compliance/` (signed COIs, SDS for an admixture, a warranty letter)
- `expected/` (golden-key JSONs for matrix cells, compliance gaps)

The eval harness in `tests/eval/` will diff agent output against the golden keys.
