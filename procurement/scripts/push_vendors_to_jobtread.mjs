#!/usr/bin/env node
// push_vendors_to_jobtread.mjs
//
// Bulk-imports a vendor CSV into JobTread via the Pave API.
// Requires Node 18+ (built-in fetch); no npm install needed.
//
// The Pave `createAccount` schema only accepts a small set of fields on input:
// organizationId, name, type. Contact info (emails, phones), trade, and notes
// are NOT accepted here — set them via the JobTread UI or a follow-up
// per-vendor mutation once the shells exist. This script preserves the source
// CSV so nothing is lost.
//
// CSV columns expected (extras are ignored):
//   vendor_name (required)
//   account_emails, account_phones, trade, notes, w9_status, coi_expires
//
// Usage:
//   export JT_GRANT_KEY=<your JobTread grant key>
//   node push_vendors_to_jobtread.mjs vendors.csv --verify   # auth check only
//   node push_vendors_to_jobtread.mjs vendors.csv --test     # push ONE vendor
//   node push_vendors_to_jobtread.mjs vendors.csv --all      # push everything
//
// The script treats "already exists" errors as skips (marked D in the ticker),
// so it is safe to re-run against the same CSV.

import { readFileSync } from "node:fs";

const grantKey = process.env.JT_GRANT_KEY;
if (!grantKey) {
  console.error("ERROR: set JT_GRANT_KEY env var");
  process.exit(1);
}
const [csvPath, mode] = process.argv.slice(2);
if (!csvPath || !mode) {
  console.error("Usage: node push_vendors_to_jobtread.mjs <csv> --verify|--test|--all");
  process.exit(1);
}

const PAVE_URL = "https://api.jobtread.com/pave";

async function pave(query) {
  const res = await fetch(PAVE_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  const text = await res.text();
  let json;
  try { json = JSON.parse(text); } catch { json = { raw: text }; }
  return { status: res.status, body: json };
}

// --- Step 1: verify auth ---
const verify = await pave({
  "$": { grantKey },
  currentGrant: {
    id: {},
    user: { name: {} },
    organization: { id: {}, name: {} },
  },
});
if (verify.status !== 200 || verify.body.errors) {
  console.error("Auth check failed:");
  console.error(JSON.stringify(verify.body, null, 2));
  process.exit(1);
}
const orgId = verify.body?.currentGrant?.organization?.id;
const orgName = verify.body?.currentGrant?.organization?.name;
console.log(`Authenticated. Organization: ${orgName} (${orgId})`);
if (mode === "--verify") process.exit(0);

// --- Parse CSV ---
function parseCsv(text) {
  const rows = [];
  let i = 0, field = "", row = [], inQ = false;
  while (i < text.length) {
    const c = text[i];
    if (inQ) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i += 2; continue; }
      if (c === '"') { inQ = false; i++; continue; }
      field += c; i++; continue;
    }
    if (c === '"') { inQ = true; i++; continue; }
    if (c === ",") { row.push(field); field = ""; i++; continue; }
    if (c === "\r") { i++; continue; }
    if (c === "\n") { row.push(field); rows.push(row); row = []; field = ""; i++; continue; }
    field += c; i++;
  }
  if (field || row.length) { row.push(field); rows.push(row); }
  const headers = rows.shift();
  return rows.filter((r) => r.some((v) => v.trim())).map((r) => {
    const o = {};
    headers.forEach((h, idx) => (o[h] = r[idx] ?? ""));
    return o;
  });
}
const rows = parseCsv(readFileSync(csvPath, "utf8"));
console.log(`Loaded ${rows.length} vendor rows from ${csvPath}`);

function buildCreateAccount(v) {
  const input = {
    organizationId: orgId,
    name: v.vendor_name,
    type: "vendor",
  };
  return {
    "$": { grantKey },
    createAccount: {
      "$": input,
      createdAccount: { id: {}, name: {} },
    },
  };
}

async function pushOne(v) {
  const q = buildCreateAccount(v);
  const res = await pave(q);
  return { name: v.vendor_name, status: res.status, body: res.body };
}

if (mode === "--test") {
  const testRow = rows[0];
  console.log(`\nTest push: ${testRow.vendor_name}`);
  const r = await pushOne(testRow);
  console.log(`HTTP ${r.status}`);
  console.log(JSON.stringify(r.body, null, 2));
  process.exit(r.body.errors ? 1 : 0);
}

if (mode !== "--all") {
  console.error(`Unknown mode: ${mode}`);
  process.exit(1);
}

// --- Batch push, one at a time with a small delay ---
let ok = 0, fail = 0, skipped = 0;
const failures = [], skips = [];
for (const v of rows) {
  const r = await pushOne(v);
  const dup = JSON.stringify(r.body || {}).includes("already exists");
  const errored = (r.status !== 200 || r.body.errors) && !dup;
  if (dup) { skipped++; skips.push(r.name); process.stdout.write("D"); }
  else if (errored) { fail++; failures.push({ name: r.name, status: r.status, body: r.body }); process.stdout.write("F"); }
  else { ok++; process.stdout.write("."); }
  await new Promise((res) => setTimeout(res, 200)); // 5/sec cap
}
console.log(`\n\nDone. ok=${ok} skipped(dup)=${skipped} fail=${fail}`);
if (skips.length) {
  console.log(`\nDuplicates skipped: ${skips.join(", ")}`);
}
if (failures.length) {
  console.log("\nFailures:");
  for (const f of failures.slice(0, 10)) {
    console.log(`  ${f.name}: HTTP ${f.status}`);
    console.log(`    ${JSON.stringify(f.body).slice(0, 300)}`);
  }
  if (failures.length > 10) console.log(`  ... +${failures.length - 10} more`);
}
