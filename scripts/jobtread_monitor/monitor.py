#!/usr/bin/env python3
"""JobTread weekly project monitor.

Queries JobTread Pave API for a configured list of jobs, renders an
at-a-glance PNG dashboard per job, and emails each dashboard via Gmail
SMTP. Designed to run as a scheduled GitHub Actions workflow.

Required env vars:
  JOBTREAD_GRANT_KEY   JobTread Pave grant key for the target org
  GMAIL_USER           Sender Gmail address
  GMAIL_APP_PASSWORD   Gmail app password (16 chars, no spaces)

Optional env vars:
  MAIL_TO              Comma-separated recipients (default: office@theidealremodeling.com)
  JOB_NUMBERS          Comma-separated job numbers (default: 2026-343,2026-336)
  JOBTREAD_API_URL     Default https://api.jobtread.com/pave
  OUTPUT_DIR           Default /tmp/jobtread
  DRY_RUN              If set to "1", renders PNGs but skips SMTP send

Exit codes:
  0 success, 1 partial/render failure, 2 missing required config
"""

from __future__ import annotations

import os
import smtplib
import ssl
import sys
import textwrap
from datetime import date, datetime
from email.message import EmailMessage
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont


# -------------------- Config --------------------

JOBTREAD_API_URL = os.environ.get("JOBTREAD_API_URL", "https://api.jobtread.com/pave")
GRANT_KEY = os.environ.get("JOBTREAD_GRANT_KEY", "")
GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
MAIL_TO = [e.strip() for e in os.environ.get("MAIL_TO", "office@theidealremodeling.com").split(",") if e.strip()]
JOB_NUMBERS = [n.strip() for n in os.environ.get("JOB_NUMBERS", "2026-343,2026-336").split(",") if n.strip()]
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/tmp/jobtread"))
DRY_RUN = os.environ.get("DRY_RUN") == "1"

TODAY = date.today()
RUN_DATE_LABEL = TODAY.strftime("%B %d, %Y").replace(" 0", " ")

FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


# -------------------- Utilities --------------------

def money(x: float | int | None) -> str:
    return "${:,.2f}".format(x or 0.0)


def fmt_date(s: str | None) -> str:
    if not s:
        return "—"
    try:
        d = datetime.strptime(s.split("T")[0], "%Y-%m-%d").date()
        return d.strftime("%b %d, %Y").replace(" 0", " ")
    except Exception:
        return s


def log(msg: str) -> None:
    print(msg, flush=True)


# -------------------- JobTread API --------------------

def pave(query: dict) -> dict:
    """POST a graph query to JobTread Pave with the configured grant key."""
    body = {"query": query, "grantKey": GRANT_KEY}
    r = requests.post(JOBTREAD_API_URL, json=body, timeout=45)
    if not r.ok:
        raise RuntimeError(f"JobTread HTTP {r.status_code}: {r.text[:400]}")
    data = r.json()
    if isinstance(data, dict) and "errors" in data:
        raise RuntimeError(f"JobTread errors: {data['errors']}")
    if isinstance(data, dict) and "error" in data:
        raise RuntimeError(f"JobTread error: {data['error']}")
    return data


def org_id() -> str:
    return pave({"currentGrant": {"organization": {"id": {}}}})["currentGrant"]["organization"]["id"]


def find_job_core(oid: str, number: str) -> dict | None:
    q = {
        "organization": {
            "$": {"id": oid},
            "jobs": {
                "$": {"where": ["number", number], "size": 1},
                "nodes": {
                    "id": {}, "number": {}, "name": {}, "closedOn": {},
                    "createdAt": {}, "scheduleIsPublished": {},
                    "projectedPriceWithTax": {}, "projectedPrice": {},
                    "projectedCost": {}, "actualCost": {}, "lineItemsUpdatedAt": {},
                    "taskSummary": {
                        "startDate": {}, "endDate": {}, "progress": {},
                        "completed": {}, "started": {}, "unstarted": {},
                    },
                    "location": {"formattedAddress": {}},
                    "documents": {
                        "$": {
                            "size": 100,
                            "group": {
                                "by": ["type", "status"],
                                "aggs": {
                                    "count": {"count": []},
                                    "total": {"sum": "priceWithTax"},
                                    "balance": {"sum": "balance"},
                                    "paid": {"sum": "amountPaid"},
                                },
                            },
                        },
                        "withValues": {},
                    },
                },
            },
        }
    }
    nodes = pave(q)["organization"]["jobs"]["nodes"]
    return nodes[0] if nodes else None


def fetch_job_detail(job_id: str) -> dict:
    q = {
        "job": {
            "$": {"id": job_id},
            "customerDocs": {
                "_": "documents",
                "$": {
                    "where": ["type", "like", "customer%"],
                    "sortBy": [{"field": "createdAt", "order": "desc"}],
                    "size": 30,
                },
                "nodes": {
                    "type": {}, "status": {}, "fullName": {},
                    "issueDate": {}, "dueDate": {}, "createdAt": {},
                    "priceWithTax": {}, "amountPaid": {}, "balance": {},
                    "subject": {},
                },
            },
            "tasks": {
                "$": {"sortBy": [{"field": "startDate", "order": "asc"}], "size": 80},
                "nodes": {
                    "name": {}, "isGroup": {}, "isToDo": {},
                    "progress": {}, "started": {}, "completed": {}, "unstarted": {},
                    "startDate": {}, "endDate": {},
                },
            },
            "files": {
                "$": {"sortBy": [{"field": "createdAt", "order": "desc"}], "size": 6},
                "count": {},
                "nodes": {"name": {}, "createdAt": {}},
            },
            "comments": {
                "$": {"sortBy": [{"field": "createdAt", "order": "desc"}], "size": 3},
                "count": {},
                "nodes": {
                    "createdAt": {}, "message": {}, "isFromEmail": {},
                    "createdByUser": {"name": {}},
                },
            },
        }
    }
    return pave(q)["job"]


# -------------------- Dashboard data prep --------------------

def overdue_tasks(tasks: list[dict]) -> list[dict]:
    out: list[dict] = []
    for t in tasks:
        if t.get("isGroup"):
            continue
        prog = t.get("progress")
        if prog is not None and prog >= 1:
            continue
        ed = t.get("endDate")
        if not ed:
            continue
        try:
            d = datetime.strptime(ed, "%Y-%m-%d").date()
        except Exception:
            continue
        if d < TODAY:
            out.append(t)
    return out


def build_dashboard_data(core: dict, detail: dict) -> dict:
    number = core["number"]
    closed_on = core.get("closedOn")
    is_closed = bool(closed_on)

    contract = float(core.get("projectedPriceWithTax") or 0.0)
    proj_cost = float(core.get("projectedCost") or 0.0)
    actual_raw = core.get("actualCost")
    actual_known = actual_raw is not None
    actual = float(actual_raw or 0.0)
    margin = contract - (actual if actual_known else proj_cost)
    margin_pct = (margin / contract * 100.0) if contract else 0.0

    # Grouped documents
    grouped: dict[tuple[str, str], dict] = {}
    for r in (core.get("documents") or {}).get("withValues") or []:
        grouped[(r.get("type") or "", r.get("status") or "")] = r

    def grp(t: str, s: str) -> tuple[int, float]:
        r = grouped.get((t, s)) or {}
        return int(r.get("count") or 0), float(r.get("total") or 0.0)

    orders = {
        "approved": grp("customerOrder", "approved"),
        "pending": grp("customerOrder", "pending"),
        "denied": grp("customerOrder", "denied"),
    }
    inv_approved = grp("customerInvoice", "approved")
    inv_denied = grp("customerInvoice", "denied")
    inv_paid = 0.0
    inv_balance = 0.0
    for (t, _s), r in grouped.items():
        if t == "customerInvoice":
            inv_paid += float(r.get("paid") or 0.0)
            inv_balance += float(r.get("balance") or 0.0)

    # Customer docs detail for blank-dates count
    blank_dates = 0
    for cd in (detail.get("customerDocs") or {}).get("nodes") or []:
        if cd.get("type") == "customerInvoice" and cd.get("status") != "denied":
            if not cd.get("issueDate") and not cd.get("dueDate"):
                blank_dates += 1

    # Tasks
    task_nodes = (detail.get("tasks") or {}).get("nodes") or []
    overdue = overdue_tasks(task_nodes)
    ts = core.get("taskSummary") or {}
    completed = int(ts.get("completed") or 0)
    started = int(ts.get("started") or 0)
    unstarted = int(ts.get("unstarted") or 0)
    progress = ts.get("progress")  # 0..1 or None
    sched_end = ts.get("endDate")
    sched_published = bool(core.get("scheduleIsPublished"))

    # Files + comments
    files_count = int((detail.get("files") or {}).get("count") or 0)
    files_nodes = (detail.get("files") or {}).get("nodes") or []
    recent_uploads = "; ".join((n.get("name") or "") for n in files_nodes[:3]) or "—"
    comments_count = int((detail.get("comments") or {}).get("count") or 0)
    comments_nodes = (detail.get("comments") or {}).get("nodes") or []
    if comments_nodes:
        c = comments_nodes[0]
        author = ((c.get("createdByUser") or {}).get("name") or "—")
        comments_note = f"latest {fmt_date(c.get('createdAt'))} from {author}"
    else:
        comments_note = "no recent comments"

    # Banner / delay risk
    delay_risk = None
    if not is_closed and overdue:
        t0 = overdue[0]
        delay_risk = f"{t0.get('name')} overdue since {fmt_date(t0.get('endDate'))}."

    # Status cards
    if is_closed:
        budget_label = "ON BUDGET" if actual_known and abs(actual - proj_cost) < 1.0 else "WATCH"
        status_cards = [
            ("Budget", budget_label, "Actual = projected" if actual_known else "Final values", "ok"),
            ("Schedule", "CLOSED", fmt_date(closed_on), "ok"),
            ("Tasks", "NONE OPEN", "Job closed", "ok"),
            ("Orders", "OK", f"{orders['approved'][0]} approved", "ok"),
            ("Invoices", "PAID" if inv_balance == 0 else "OPEN",
             f"{inv_approved[0]} approved", "ok" if inv_balance == 0 else "watch"),
            ("Docs / Msgs", "INFO", f"{files_count} files", "plain"),
        ]
    else:
        tasks_kind = "risk" if overdue else ("watch" if unstarted else "ok")
        tasks_stat = "ACTION NEEDED" if overdue else ("WATCH" if unstarted else "OK")
        tasks_sub = f"{len(overdue)} overdue" if overdue else (f"{started} started" if started else "—")
        inv_kind = "risk" if blank_dates else ("watch" if inv_balance > 0 else "ok")
        inv_stat = "ACTION NEEDED" if blank_dates else ("OPEN" if inv_balance > 0 else "OK")
        inv_sub = f"{blank_dates} blank dates" if blank_dates else f"{inv_approved[0]} approved"
        status_cards = [
            ("Budget", "OK" if actual_known else "WATCH",
             "Tracking" if actual_known else "Actual cost blank",
             "ok" if actual_known else "watch"),
            ("Schedule", "OK" if sched_published else "WATCH",
             "Published" if sched_published else "Not published",
             "ok" if sched_published else "watch"),
            ("Tasks", tasks_stat, tasks_sub, tasks_kind),
            ("Orders", "WATCH" if orders["pending"][0] else "OK",
             f"{orders['approved'][0]} approved", "watch" if orders["pending"][0] else "ok"),
            ("Invoices", inv_stat, inv_sub, inv_kind),
            ("Docs / Msgs", "INFO", f"{files_count} files", "plain"),
        ]

    # KPI 2 ("Schedule")
    if is_closed:
        sched_kpi_value = "CLOSED"
        sched_kpi_sub = f"Closed {fmt_date(closed_on)}"
        sched_kpi_progress = 1.0
        sched_kpi_color = "closed"
    elif progress is not None:
        sched_kpi_value = f"{progress * 100:.1f}%"
        sched_kpi_sub = f"Finish currently {fmt_date(sched_end)}" if sched_end else "No end date set"
        sched_kpi_progress = float(progress)
        sched_kpi_color = "progress"
    else:
        sched_kpi_value = "NO SCHED"
        sched_kpi_sub = "Schedule not set up"
        sched_kpi_progress = 0.0
        sched_kpi_color = "progress"

    # Top items (max 3, delay risk first)
    top_items: list[tuple[str, str]] = []
    if delay_risk:
        top_items.append(("DELAY RISK", delay_risk))
    if is_closed:
        if not top_items:
            top_items.append(("CLOSED", "Complete and fully paid." if inv_balance == 0 else "Closed; check open balance."))
        top_items.append(("MARGIN", f"Realized margin {margin_pct:.1f}% ({money(margin)})."))
    else:
        if blank_dates:
            top_items.append(("INVOICES", f"{blank_dates} draft invoices need issue/due dates."))
        if not sched_published:
            top_items.append(("SCHEDULE", "Schedule is not published yet."))
        if not actual_known:
            top_items.append(("COST WATCH", "Actual cost not populated; margin not fully tracked."))
        if orders["pending"][0]:
            top_items.append(("ORDER WATCH",
                              f"{orders['pending'][0]} pending customer order(s) - {money(orders['pending'][1])}."))
    top_items = top_items[:3] or [("STATUS", "No urgent items this run.")]

    # What changed (point-in-time observations; diff tracking TBD)
    what_changed: list[str] = []
    if is_closed:
        what_changed.append(f"Job is CLOSED ({fmt_date(closed_on)}) and {'fully paid' if inv_balance == 0 else 'has open balance'}.")
        if actual_known:
            what_changed.append(f"Actual cost finalized at {money(actual)}.")
        what_changed.append(f"Realized margin {margin_pct:.1f}% ({money(margin)}).")
    else:
        if delay_risk:
            what_changed.append(delay_risk)
        if progress is not None:
            what_changed.append(f"Schedule progress {progress * 100:.1f}%.")
        if completed or started or unstarted:
            what_changed.append(f"Tasks: {completed} completed, {started} started, {unstarted} unstarted.")
        if blank_dates:
            what_changed.append(f"{blank_dates} draft invoices need issue/due dates.")
    if not what_changed:
        what_changed = ["First dashboard baseline for this job."]

    return {
        "number": number,
        "id": core["id"],
        "location": (core.get("location") or {}).get("formattedAddress") or "—",
        "run_date": RUN_DATE_LABEL,
        "is_closed": is_closed,
        "closed_on": fmt_date(closed_on) if is_closed else "—",
        "contract_value": contract,
        "contract_sub": "Final invoiced total" if is_closed else "Contracted total",
        "projected_cost": proj_cost,
        "actual_cost": actual,
        "actual_known": actual_known,
        "actual_sub": (
            "100% of projected (final)" if is_closed and actual_known
            else (f"{actual / proj_cost * 100:.1f}% of projected" if actual_known and proj_cost
                  else "Not populated")
        ),
        "margin": margin,
        "margin_pct": margin_pct,
        "sched_kpi_value": sched_kpi_value,
        "sched_kpi_sub": sched_kpi_sub,
        "sched_kpi_progress": sched_kpi_progress,
        "sched_kpi_color": sched_kpi_color,
        "sched_published": sched_published,
        "status_cards": status_cards,
        "delay_risk": delay_risk,
        "tasks": {"completed": completed, "started": started, "unstarted": unstarted, "overdue": len(overdue)},
        "tasks_note": (
            "No scheduled tasks; job is closed." if is_closed
            else (f"Overdue: {(overdue[0].get('name') or '')[:34]}" if overdue
                  else "No overdue tasks.")
        ),
        "orders": orders,
        "orders_note": "Approved counts/totals shown above.",
        "invoices": {
            "approved": inv_approved, "paid": inv_paid, "balance": inv_balance,
            "denied": inv_denied, "blank_dates": blank_dates,
        },
        "files_total": files_count,
        "recent_uploads": recent_uploads,
        "comments_total": comments_count,
        "comments_note": comments_note,
        "what_changed": what_changed,
        "top_items": top_items,
        "source_note": (
            f"Source: JobTread project record for Job {number} (ID {core['id']}). "
            "JobTread records do not contain page numbers."
        ),
    }


# -------------------- PNG renderer --------------------

C = {
    "dark": "#111827", "muted": "#6b7280", "line": "#e5e7eb", "edge": "#edf2f7",
    "blue": "#2563eb", "green": "#166534",
    "green_soft": "#ecfdf5", "green_border": "#bbf7d0",
    "amber": "#b45309", "amber_soft": "#fff7ed", "amber_border": "#fed7aa",
    "red": "#991b1b", "red_soft": "#fef2f2", "red_border": "#fecaca",
    "sky_soft": "#f0f9ff", "sky_border": "#bae6fd",
    "panel": "#f8fafc", "white": "#ffffff",
}


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


def _palette(kind: str) -> tuple[str, str, str]:
    if kind == "ok":
        return C["green_soft"], C["green_border"], C["green"]
    if kind == "watch":
        return C["amber_soft"], C["amber_border"], C["amber"]
    if kind == "risk":
        return C["red_soft"], C["red_border"], C["red"]
    return C["white"], C["line"], C["muted"]


def render_dashboard(d: dict, out_path: Path) -> None:
    W, H, m = 1700, 2330, 52
    img = Image.new("RGB", (W, H), "#f3f4f6")
    dr = ImageDraw.Draw(img)

    def rect(xy, fill, outline=None, radius=22, width=2):
        dr.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)

    def text(x, y, s, font, fill=C["dark"], anchor=None):
        dr.text((x, y), str(s), font=font, fill=fill, anchor=anchor)

    f_xs = _font(20); f_sm = _font(24); f_md = _font(28)
    f_title = _font(56, True); f_h = _font(33, True); f_b = _font(27, True)
    f_bsm = _font(23, True); f_kpi = _font(39, True); f_pill = _font(22, True)

    # Header
    rect((m, 38, W - m, 220), C["dark"], radius=24)
    text(m + 36, 72, "JOBTREAD WEEKLY MONITOR", f_bsm, "#cbd5e1")
    text(m + 36, 108, "Job " + d["number"], f_title, "white")
    text(m + 36, 176, d["location"] + "  |  Run date: " + d["run_date"], f_sm, "#d1d5db")
    if d["is_closed"]:
        pill_w = 260
        rect((W - m - pill_w - 24, 84, W - m - 24, 138), "#064e3b", outline="#34d399", radius=16, width=2)
        text(W - m - 24 - pill_w / 2, 111, "CLOSED " + d["closed_on"], f_pill, "#d1fae5", anchor="mm")
    elif d["delay_risk"]:
        pill_w = 280
        rect((W - m - pill_w - 24, 84, W - m - 24, 138), "#7f1d1d", outline="#fca5a5", radius=16, width=2)
        text(W - m - 24 - pill_w / 2, 111, "DELAY RISK FLAGGED", f_pill, "#fee2e2", anchor="mm")

    # Status strip (6 cards)
    y = 250; gap = 18; cw = (W - 2 * m - 5 * gap) // 6
    for i, (lab, stat, sub, kind) in enumerate(d["status_cards"]):
        x = m + i * (cw + gap)
        fill, out, acc = _palette(kind)
        rect((x, y, x + cw, y + 142), fill, out, radius=18)
        text(x + 18, y + 18, lab.upper(), f_xs, acc)
        sf = f_bsm if len(stat) > 8 else f_h
        text(x + 18, y + 58, stat, sf, C["dark"])
        text(x + 18, y + 104, sub, f_xs, C["muted"])

    # Banner (delay risk / closed / active info)
    by = 420
    if d.get("delay_risk"):
        rect((m, by, W - m, by + 96), C["red_soft"], C["red_border"], radius=18, width=3)
        text(m + 28, by + 22, "DELAY RISK", f_b, C["red"])
        text(m + 250, by + 30, d["delay_risk"], f_md, C["dark"])
    elif d["is_closed"]:
        rect((m, by, W - m, by + 96), C["green_soft"], C["green_border"], radius=18, width=2)
        text(m + 28, by + 22, "JOB CLOSED", f_b, C["green"])
        msg = "Completed " + d["closed_on"] + "."
        sub = "Final financials below; no open items or delay risk." if d["invoices"]["balance"] == 0 else "Final financials below; open balance still showing."
        text(m + 250, by + 20, msg, f_md, C["dark"])
        text(m + 250, by + 56, sub, f_sm, C["muted"])
    else:
        rect((m, by, W - m, by + 96), C["sky_soft"], C["sky_border"], radius=18, width=2)
        text(m + 28, by + 22, "ACTIVE", f_b, C["blue"])
        sub = "Schedule "
        sub += "published" if d["sched_published"] else "not published yet"
        if d.get("sched_kpi_value") and d["sched_kpi_value"] not in ("CLOSED", "NO SCHED"):
            sub += f"  |  progress {d['sched_kpi_value']}"
        text(m + 250, by + 20, "Project in progress.", f_md, C["dark"])
        text(m + 250, by + 56, sub, f_sm, C["muted"])

    # KPI row (4 cards)
    ky = 548; kg = 20; kw = (W - 2 * m - 3 * kg) // 4
    kpis = [
        ("Contract Value", money(d["contract_value"]), d["contract_sub"], "plain"),
        ("Schedule", d["sched_kpi_value"], d["sched_kpi_sub"], d["sched_kpi_color"]),
        ("Actual Cost", money(d["actual_cost"]) if d["actual_known"] else "—", d["actual_sub"], "hi"),
        ("Realized Margin" if d["is_closed"] else "Projected Margin",
         money(d["margin"]), f"{d['margin_pct']:.1f}% of contract", "margin"),
    ]
    for i, (lab, val, sub, kind) in enumerate(kpis):
        x = m + i * (kw + kg)
        hi = kind in ("hi", "margin")
        fill = C["amber_soft"] if hi else C["white"]
        out = C["amber_border"] if hi else C["line"]
        rect((x, ky, x + kw, ky + 188), fill, out, radius=20)
        text(x + 24, ky + 22, lab.upper(), f_xs, C["amber"] if hi else C["muted"])
        if kind == "margin":
            val_col = C["green"] if d["margin"] >= 0 else C["red"]
        elif kind == "hi":
            val_col = C["amber"]
        else:
            val_col = C["dark"]
        text(x + 24, ky + 64, val, f_kpi, val_col)
        if kind in ("closed", "progress"):
            bx, byy, bw, bh = x + 24, ky + 126, kw - 48, 16
            rect((bx, byy, bx + bw, byy + bh), C["line"], radius=8)
            pct = max(0.0, min(1.0, d["sched_kpi_progress"]))
            fill_w = max(8, int(bw * pct)) if pct > 0 else 0
            if fill_w > 0:
                bar_color = C["green"] if kind == "closed" else C["blue"]
                rect((bx, byy, bx + fill_w, byy + bh), bar_color, radius=8)
            text(x + 24, ky + 152, sub, f_xs, C["muted"])
        else:
            text(x + 24, ky + 128, sub, f_xs, C["muted"])

    # Budget + Schedule snapshot
    ry = 768; col = (W - 2 * m - 24) // 2; ch = 320
    rect((m, ry, m + col, ry + ch), C["white"], C["line"], radius=20)
    rect((m + col + 24, ry, W - m, ry + ch), C["white"], C["line"], radius=20)

    def lv(x, yy, w, lab, val, color=None):
        text(x, yy, lab, f_sm, C["muted"])
        text(x + w, yy, val, f_b, color or C["dark"], anchor="ra")
        dr.line((x, yy + 42, x + w, yy + 42), fill=C["edge"], width=2)
        return yy + 54

    text(m + 24, ry + 24, "Budget Snapshot", f_h)
    yy = ry + 82
    yy = lv(m + 24, yy, col - 48, "Projected price", money(d["contract_value"]))
    yy = lv(m + 24, yy, col - 48, "Projected cost", money(d["projected_cost"]))
    actual_text = money(d["actual_cost"]) if d["actual_known"] else "Not populated"
    yy = lv(m + 24, yy, col - 48, "Actual cost", actual_text, C["amber"])
    margin_label = "Realized margin" if d["is_closed"] else "Projected margin"
    yy = lv(m + 24, yy, col - 48, margin_label,
            f"{money(d['margin'])}  ({d['margin_pct']:.1f}%)",
            C["green"] if d["margin"] >= 0 else C["red"])

    x2 = m + col + 24
    text(x2 + 24, ry + 24, "Schedule Snapshot", f_h)
    yy = ry + 82
    yy = lv(x2 + 24, yy, col - 48, "Published",
            "Yes" if d["sched_published"] else "No",
            C["green"] if d["sched_published"] else C["amber"])
    if d["is_closed"]:
        yy = lv(x2 + 24, yy, col - 48, "Status", "Closed", C["green"])
        yy = lv(x2 + 24, yy, col - 48, "Closed on", d["closed_on"])
        yy = lv(x2 + 24, yy, col - 48, "Open tasks", "None", C["green"])
    else:
        yy = lv(x2 + 24, yy, col - 48, "Progress", d["sched_kpi_value"])
        yy = lv(x2 + 24, yy, col - 48, "Finish target", d["sched_kpi_sub"].replace("Finish currently ", ""))
        yy = lv(x2 + 24, yy, col - 48, "Overdue tasks",
                str(d["tasks"]["overdue"]),
                C["red"] if d["tasks"]["overdue"] else C["green"])

    # Detail cards: Tasks / Orders / Invoices
    dy = 1120; tg = 24; tw = (W - 2 * m - 2 * tg) // 3; dh = 380
    for i in range(3):
        x = m + i * (tw + tg)
        rect((x, dy, x + tw, dy + dh), C["white"], C["line"], radius=20)

    # Tasks
    x = m; text(x + 24, dy + 24, "Tasks", f_h); yy = dy + 84
    t = d["tasks"]
    for lab, val, color in [
        ("Completed", str(t["completed"]), C["green"]),
        ("Started", str(t["started"]), C["muted"]),
        ("Unstarted", str(t["unstarted"]), C["dark"]),
        ("Overdue", str(t["overdue"]), C["green"] if t["overdue"] == 0 else C["red"]),
    ]:
        text(x + 24, yy, lab, f_sm, C["muted"])
        text(x + tw - 24, yy, val, f_b, color, anchor="ra")
        yy += 46
    yy += 10
    for line in textwrap.wrap(d["tasks_note"], 34):
        text(x + 24, yy, line, f_xs, C["muted"]); yy += 28

    # Orders
    x = m + tw + tg; text(x + 24, dy + 24, "Orders / Change Orders", f_h); yy = dy + 84
    o = d["orders"]
    rows = [
        ("Approved", o["approved"], C["green"]),
        ("Pending", o["pending"], C["amber"]),
        ("Denied", o["denied"], C["red"] if o["denied"][0] else C["muted"]),
    ]
    for lab, (cnt, tot), color in rows:
        text(x + 24, yy, lab, f_sm, color)
        text(x + tw - 24, yy, f"{cnt} / {money(tot)}", f_bsm, C["dark"], anchor="ra")
        dr.line((x + 24, yy + 38, x + tw - 24, yy + 38), fill=C["edge"], width=2)
        yy += 58
    yy += 6
    for line in textwrap.wrap(d["orders_note"], 36):
        text(x + 24, yy, line, f_xs, C["muted"]); yy += 28

    # Invoices
    x = m + 2 * (tw + tg); text(x + 24, dy + 24, "Invoices", f_h); yy = dy + 84
    iv = d["invoices"]
    irows = [
        ("Approved", f"{iv['approved'][0]} / {money(iv['approved'][1])}", C["green"]),
        ("Paid", money(iv["paid"]), C["green"]),
        ("Open balance", money(iv["balance"]), C["green"] if iv["balance"] == 0 else C["red"]),
        ("Denied", f"{iv['denied'][0]} / {money(iv['denied'][1])}",
         C["muted"] if iv["denied"][0] == 0 else C["amber"]),
        ("Blank dates", str(iv["blank_dates"]),
         C["green"] if iv["blank_dates"] == 0 else C["red"]),
    ]
    for lab, val, color in irows:
        text(x + 24, yy, lab, f_sm, color)
        text(x + tw - 24, yy, val, f_bsm, C["dark"], anchor="ra")
        dr.line((x + 24, yy + 34, x + tw - 24, yy + 34), fill=C["edge"], width=2)
        yy += 50

    # Docs / Messages
    gy = 1530; gh = 210
    rect((m, gy, W - m, gy + gh), C["white"], C["line"], radius=20)
    text(m + 24, gy + 24, "Documents / Messages", f_h)
    yy = gy + 84
    for lab, val in [
        ("Files in JobTread", f"{d['files_total']} total"),
        ("Recent uploads", d["recent_uploads"]),
        ("Client/design comments", f"{d['comments_total']} total - {d['comments_note']}"),
    ]:
        text(m + 24, yy, lab, f_sm, C["muted"])
        wrapped = textwrap.wrap(val, 92)
        text(m + 430, yy, wrapped[0] if wrapped else "—", f_bsm, C["dark"])
        dr.line((m + 24, yy + 38, W - m - 24, yy + 38), fill=C["edge"], width=2)
        yy += 52

    # What changed / Top items
    wy = 1770; hw = (W - 2 * m - 24) // 2; wh = 470
    rect((m, wy, m + hw, wy + wh), C["sky_soft"], C["sky_border"], radius=20)
    rect((m + hw + 24, wy, W - m, wy + wh), C["panel"], C["line"], radius=20)

    text(m + 24, wy + 24, "What Changed", f_h); yy = wy + 86
    for item in d["what_changed"][:4]:
        text(m + 24, yy, "•", f_bsm, C["blue"])
        wl = textwrap.wrap(item, 50)
        text(m + 54, yy, wl[0], f_sm, C["dark"])
        if len(wl) > 1:
            yy += 30
            text(m + 54, yy, wl[1], f_sm, C["dark"])
        yy += 54

    ax = m + hw + 48
    text(ax, wy + 24, "Top Items", f_h); yy = wy + 86
    for i, (tag, item) in enumerate(d["top_items"], 1):
        if tag == "DELAY RISK":
            color = C["red"]
        elif tag in ("CLOSED", "MARGIN"):
            color = C["green"]
        else:
            color = C["amber"]
        text(ax, yy, f"{i}.", f_bsm, color)
        text(ax + 42, yy, tag + ":", f_bsm, color)
        yy += 36
        for line in textwrap.wrap(item, 44):
            text(ax + 42, yy, line, f_sm, C["dark"])
            yy += 32
        yy += 22

    # Footer
    text(m, H - 56, d["source_note"], f_xs, C["muted"])

    img.save(out_path)


# -------------------- Email sender --------------------

def send_email(d: dict, png_path: Path) -> None:
    if DRY_RUN:
        log(f"  DRY_RUN: would send {png_path.name} to {MAIL_TO}")
        return

    tag = "DELAY RISK" if d.get("delay_risk") else ("CLOSED" if d["is_closed"] else "Weekly")
    subject = f"JobTread Monitor [{tag}] - Job {d['number']} - {d['run_date']}"

    lines = [
        f"Attached: weekly JobTread dashboard for Job {d['number']}.",
        f"Location: {d['location']}",
        f"Run date: {d['run_date']}",
        "",
        "Top items:",
    ]
    for i, (t, item) in enumerate(d["top_items"], 1):
        prefix = "DELAY RISK: " if t == "DELAY RISK" else f"{t}: "
        lines.append(f"  {i}. {prefix}{item}")
    lines += [
        "",
        d["source_note"],
    ]
    body = "\n".join(lines)

    msg = EmailMessage()
    msg["From"] = GMAIL_USER
    msg["To"] = ", ".join(MAIL_TO)
    msg["Subject"] = subject
    msg.set_content(body)
    with open(png_path, "rb") as f:
        msg.add_attachment(f.read(), maintype="image", subtype="png", filename=png_path.name)

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx, timeout=30) as s:
        s.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        s.send_message(msg)
    log(f"  sent {png_path.name} -> {MAIL_TO}")


# -------------------- main --------------------

def require_config() -> None:
    missing: list[str] = []
    if not GRANT_KEY:
        missing.append("JOBTREAD_GRANT_KEY")
    if not DRY_RUN:
        if not GMAIL_USER:
            missing.append("GMAIL_USER")
        if not GMAIL_APP_PASSWORD:
            missing.append("GMAIL_APP_PASSWORD")
    if missing:
        log(f"ERROR: missing required env vars: {', '.join(missing)}")
        sys.exit(2)


def main() -> int:
    require_config()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log(f"JobTread weekly monitor - {RUN_DATE_LABEL}")
    log(f"Jobs: {', '.join(JOB_NUMBERS)}")
    if DRY_RUN:
        log("DRY_RUN=1 - SMTP send disabled")

    oid = org_id()
    log(f"Organization id: {oid}")

    exit_code = 0
    for number in JOB_NUMBERS:
        log(f"\n[{number}]")
        try:
            core = find_job_core(oid, number)
            if not core:
                log(f"  WARN: job {number} not found - skipping")
                exit_code = max(exit_code, 1)
                continue
            detail = fetch_job_detail(core["id"])
            data = build_dashboard_data(core, detail)
            out = OUTPUT_DIR / f"JobTread_{number}_dashboard_{TODAY.isoformat()}.png"
            render_dashboard(data, out)
            log(f"  rendered {out}")
            send_email(data, out)
        except Exception as e:
            log(f"  ERROR for {number}: {e}")
            exit_code = max(exit_code, 1)

    log("\ndone")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
