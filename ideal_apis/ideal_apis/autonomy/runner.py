from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from ideal_apis.autonomy.probes import all_probe_commands, probe_kwargs_for, _settings_has_key
from ideal_apis.exceptions import APIRequestError, MissingAPIKeyError
from ideal_apis.registry import CommandSpec

ProbeStatus = Literal["ok", "skipped", "failed"]


@dataclass
class ProbeResult:
    group: str
    name: str
    tier: int
    status: ProbeStatus
    requires_key: bool
    elapsed_ms: int
    message: str = ""
    sample: Any = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if d.get("sample") is not None and not isinstance(d["sample"], (dict, list, str, int, float, bool, type(None))):
            d["sample"] = str(d["sample"])[:200]
        return d


@dataclass
class HealthReport:
    ran_at: str
    total: int
    ok: int
    skipped: int
    failed: int
    results: list[ProbeResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ran_at": self.ran_at,
            "summary": {
                "total": self.total,
                "ok": self.ok,
                "skipped": self.skipped,
                "failed": self.failed,
            },
            "results": [r.to_dict() for r in self.results],
        }

    def failed_results(self) -> list[ProbeResult]:
        return [r for r in self.results if r.status == "failed"]


def _summarize(result: Any) -> Any:
    if result is None:
        return None
    if isinstance(result, dict):
        if "results" in result and isinstance(result["results"], list):
            return {"count": len(result["results"]), "keys": list(result.keys())[:6]}
        if "data" in result:
            data = result["data"]
            if isinstance(data, dict):
                return {"keys": list(data.keys())[:6]}
        return {"keys": list(result.keys())[:8]}
    if isinstance(result, list):
        return {"count": len(result), "type": "list"}
    if isinstance(result, bytes):
        return {"bytes": len(result)}
    return str(result)[:120]


def _probe_command_inner(cmd: CommandSpec) -> ProbeResult:
    start = time.perf_counter()
    if cmd.requires_key and not _settings_has_key(cmd):
        return ProbeResult(
            group=cmd.group,
            name=cmd.name,
            tier=cmd.tier,
            status="skipped",
            requires_key=True,
            elapsed_ms=0,
            message="missing API key — set env var from ideal-api keys",
        )

    kwargs = probe_kwargs_for(cmd)
    if cmd.group == "productivity" and cmd.name == "clockify-projects":
        return ProbeResult(
            group=cmd.group,
            name=cmd.name,
            tier=cmd.tier,
            status="skipped",
            requires_key=True,
            elapsed_ms=0,
            message="needs workspace_id from clockify-workspaces probe first",
        )

    try:
        result = cmd.handler(**kwargs)
        elapsed = int((time.perf_counter() - start) * 1000)
        return ProbeResult(
            group=cmd.group,
            name=cmd.name,
            tier=cmd.tier,
            status="ok",
            requires_key=cmd.requires_key,
            elapsed_ms=elapsed,
            message="ok",
            sample=_summarize(result),
        )
    except MissingAPIKeyError as exc:
        return ProbeResult(
            group=cmd.group,
            name=cmd.name,
            tier=cmd.tier,
            status="skipped",
            requires_key=True,
            elapsed_ms=int((time.perf_counter() - start) * 1000),
            message=str(exc),
        )
    except APIRequestError as exc:
        return ProbeResult(
            group=cmd.group,
            name=cmd.name,
            tier=cmd.tier,
            status="failed",
            requires_key=cmd.requires_key,
            elapsed_ms=int((time.perf_counter() - start) * 1000),
            message=f"HTTP {exc.status_code}: {exc.detail[:160]}",
        )
    except Exception as exc:
        return ProbeResult(
            group=cmd.group,
            name=cmd.name,
            tier=cmd.tier,
            status="failed",
            requires_key=cmd.requires_key,
            elapsed_ms=int((time.perf_counter() - start) * 1000),
            message=str(exc)[:200],
        )


def probe_command(cmd: CommandSpec, *, timeout_s: float = 45.0) -> ProbeResult:
    """Run one probe with a wall-clock timeout so health sweeps cannot hang."""
    if timeout_s <= 0:
        return _probe_command_inner(cmd)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_probe_command_inner, cmd)
        try:
            return future.result(timeout=timeout_s)
        except FuturesTimeout:
            return ProbeResult(
                group=cmd.group,
                name=cmd.name,
                tier=cmd.tier,
                status="failed",
                requires_key=cmd.requires_key,
                elapsed_ms=int(timeout_s * 1000),
                message=f"timeout after {int(timeout_s)}s",
            )


def run_health_check(
    *,
    tier: int | None = None,
    fail_fast: bool = False,
    verbose: bool = False,
    timeout_s: float = 45.0,
    parallel: bool = True,
    max_workers: int = 6,
) -> HealthReport:
    """Run live probes for every registry command (autonomous health check)."""
    commands = all_probe_commands(tier=tier)
    results: list[ProbeResult] = []
    by_key: dict[tuple[str, str], ProbeResult] = {}

    def _run_one(cmd: CommandSpec) -> ProbeResult:
        if verbose:
            import sys
            print(f"Probing {cmd.group}/{cmd.name}...", file=sys.stderr, flush=True)
        return probe_command(cmd, timeout_s=timeout_s)

    if parallel and len(commands) > 1:
        workers = min(max_workers, len(commands))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_run_one, cmd): cmd for cmd in commands}
            for future in as_completed(futures):
                cmd = futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = ProbeResult(
                        group=cmd.group,
                        name=cmd.name,
                        tier=cmd.tier,
                        status="failed",
                        requires_key=cmd.requires_key,
                        elapsed_ms=0,
                        message=str(exc)[:200],
                    )
                by_key[(cmd.group, cmd.name)] = result
                if fail_fast and result.status == "failed":
                    for pending in futures:
                        pending.cancel()
                    break
        results = [by_key[(c.group, c.name)] for c in commands if (c.group, c.name) in by_key]
    else:
        for cmd in commands:
            result = _run_one(cmd)
            results.append(result)
            if fail_fast and result.status == "failed":
                break

    ok = sum(1 for r in results if r.status == "ok")
    skipped = sum(1 for r in results if r.status == "skipped")
    failed = sum(1 for r in results if r.status == "failed")
    return HealthReport(
        ran_at=datetime.now(timezone.utc).isoformat(),
        total=len(results),
        ok=ok,
        skipped=skipped,
        failed=failed,
        results=results,
    )


def write_health_report(report: HealthReport, path: str | None = None) -> str:
    from pathlib import Path

    out = Path(path) if path else Path(__file__).resolve().parents[2] / "data/output/health_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return str(out)
