#!/usr/bin/env node
// plans_registry.mjs
//
// Local key/value store mapping a JobTread Job ID to the shareable Google
// Drive URL for that project's `_BID_SET/` folder. Reads/writes a JSON file
// in the procurement/ directory next to this script. The file is git-ignored
// (real project URLs are not code).
//
// Usage:
//   node plans_registry.mjs set <jobtread_job_id> <drive_url>
//   node plans_registry.mjs get <jobtread_job_id>
//   node plans_registry.mjs revised <jobtread_job_id>      # bump plans_revised_at
//   node plans_registry.mjs list
//
// Node 18+ (uses ESM + node:fs).

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REGISTRY_PATH = join(HERE, "..", "plans_registry.json");

function load() {
  if (!existsSync(REGISTRY_PATH)) return {};
  return JSON.parse(readFileSync(REGISTRY_PATH, "utf8"));
}

function save(reg) {
  writeFileSync(REGISTRY_PATH, JSON.stringify(reg, null, 2) + "\n");
}

function validateDriveUrl(url) {
  if (!/^https:\/\/(drive|docs)\.google\.com\//.test(url)) {
    throw new Error(`Not a Google Drive URL: ${url}`);
  }
}

const [cmd, jobId, urlArg] = process.argv.slice(2);

if (cmd === "set") {
  if (!jobId || !urlArg) {
    console.error("Usage: plans_registry.mjs set <jobtread_job_id> <drive_url>");
    process.exit(1);
  }
  validateDriveUrl(urlArg);
  const reg = load();
  const now = new Date().toISOString();
  reg[jobId] = {
    plans_url: urlArg,
    set_at: reg[jobId]?.set_at ?? now,
    plans_revised_at: now,
  };
  save(reg);
  console.log(`Recorded ${jobId} -> ${urlArg}`);
} else if (cmd === "get") {
  if (!jobId) {
    console.error("Usage: plans_registry.mjs get <jobtread_job_id>");
    process.exit(1);
  }
  const reg = load();
  const entry = reg[jobId];
  if (!entry) {
    console.error(`No registry entry for job ${jobId}`);
    process.exit(2);
  }
  process.stdout.write(entry.plans_url);
} else if (cmd === "revised") {
  if (!jobId) {
    console.error("Usage: plans_registry.mjs revised <jobtread_job_id>");
    process.exit(1);
  }
  const reg = load();
  if (!reg[jobId]) {
    console.error(`No registry entry for job ${jobId} — set it first.`);
    process.exit(2);
  }
  reg[jobId].plans_revised_at = new Date().toISOString();
  save(reg);
  console.log(`Marked ${jobId} plans as revised at ${reg[jobId].plans_revised_at}`);
} else if (cmd === "list") {
  const reg = load();
  const rows = Object.entries(reg);
  if (!rows.length) {
    console.log("(empty)");
    process.exit(0);
  }
  for (const [id, entry] of rows) {
    console.log(`${id}\t${entry.plans_url}\trevised ${entry.plans_revised_at}`);
  }
} else {
  console.error("Usage: plans_registry.mjs set|get|revised|list [args]");
  process.exit(1);
}
