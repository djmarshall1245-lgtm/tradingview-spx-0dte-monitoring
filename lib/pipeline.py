"""Clinical-trial pipeline watch — health-sector catalyst tracker. [OBSERVE only]

Polls ClinicalTrials.gov API v2 for the trials of sponsors mapped to
health-sector tickers, snapshots the fields that move a stock, and DIFFS
against the last run so you see WHAT CHANGED, not just what exists.

Why a diff and not a feed: CT.gov's LastUpdatePostDate tells you a record was
touched; it does not tell you a Phase 3 slipped two quarters or flipped to
TERMINATED. Those are the tradeable events, and only a stored snapshot
surfaces them.

Source: https://clinicaltrials.gov/api/v2/studies  (free, no API key).
Stdlib only — no new dependency. Every number here is [TOOL]-sourced from
that endpoint; nothing is inferred.

Watch map is config-driven (config.yaml -> pipeline_watch), so tickers and
sponsor strings change without touching code.

  python run.py --pipeline              # poll + diff vs last snapshot
  python run.py --pipeline --since 30   # only records CT.gov touched in 30d
  python -m lib.pipeline LLY VRTX       # ad-hoc subset
"""
from __future__ import annotations

import json
import pathlib
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import date, timedelta

API = "https://clinicaltrials.gov/api/v2/studies"
UA = "spx-0dte-monitor/1.0 (pipeline watch; contact via repo)"

# Leaf fields we track. Requested from the API and pulled back out of the
# nested protocolSection by leaf name, so a schema reshuffle can't break us.
FIELDS = [
    "NCTId", "BriefTitle", "OverallStatus", "Phase",
    "LastUpdatePostDate", "PrimaryCompletionDate", "CompletionDate",
    "EnrollmentCount", "LeadSponsorName",
]

# Ticker -> CT.gov LeadSponsorName strings. Sponsors register under legal
# entity names, not tickers, and big pharma files under subsidiaries (Merck
# as "Merck Sharp & Dohme", J&J as "Janssen"), so this map is the join.
DEFAULT_WATCH = {
    "LLY":  ["Eli Lilly and Company"],
    "NVO":  ["Novo Nordisk A/S"],
    "MRK":  ["Merck Sharp & Dohme LLC"],
    "PFE":  ["Pfizer"],
    "ABBV": ["AbbVie"],
    "JNJ":  ["Janssen Research & Development, LLC", "Johnson & Johnson"],
    "AMGN": ["Amgen"],
    "BMY":  ["Bristol-Myers Squibb"],
    "GILD": ["Gilead Sciences"],
    "VRTX": ["Vertex Pharmaceuticals Incorporated"],
    "REGN": ["Regeneron Pharmaceuticals"],
    "MRNA": ["ModernaTX, Inc."],
}

# Status transitions that are read-through-to-the-stock events. Everything
# else (a title edit, a contact change) is noise and stays out of the report.
_BAD_STATUS = {"TERMINATED", "SUSPENDED", "WITHDRAWN"}
_GOOD_STATUS = {"COMPLETED", "ACTIVE_NOT_RECRUITING"}


@dataclass
class Study:
    nct: str
    ticker: str
    sponsor: str
    title: str
    status: str | None
    phase: str | None
    last_update: str | None
    primary_completion: str | None
    completion: str | None
    enrollment: int | None


def _find(node, key):
    """First value stored under `key` anywhere in CT.gov's nested response.

    Path-aware by design: the three date structs each hold a leaf literally
    named "date", so a flattened leaf-name grab would collapse
    lastUpdatePostDate, primaryCompletionDate and completionDate into one
    value. We search for the DISTINCT container key and unwrap it below.
    """
    if isinstance(node, dict):
        if key in node:
            return node[key]
        for v in node.values():
            got = _find(v, key)
            if got is not None:
                return got
    elif isinstance(node, list):
        for v in node:
            got = _find(v, key)
            if got is not None:
                return got
    return None


def _unwrap(val, leaf):
    """{'date': '2027-06-30', 'type': ...} -> '2027-06-30'; list -> first item."""
    if isinstance(val, dict):
        return val.get(leaf)
    if isinstance(val, list):
        return val[0] if val else None
    return val


# field -> (container keys to search, leaf inside the container if it's a struct).
# Both the documented PascalCase names and the camelCase keys the API actually
# returns are accepted, so either response shape populates the record.
_PATHS = {
    "NCTId":                 (("nctId", "NCTId"), None),
    "BriefTitle":            (("briefTitle", "BriefTitle"), None),
    "OverallStatus":         (("overallStatus", "OverallStatus"), None),
    "Phase":                 (("phases", "phase", "Phase"), None),
    "LastUpdatePostDate":    (("lastUpdatePostDateStruct", "LastUpdatePostDate"), "date"),
    "PrimaryCompletionDate": (("primaryCompletionDateStruct", "PrimaryCompletionDate"), "date"),
    "CompletionDate":        (("completionDateStruct", "CompletionDate"), "date"),
    "EnrollmentCount":       (("enrollmentInfo", "EnrollmentCount"), "count"),
    "LeadSponsorName":       (("leadSponsor", "LeadSponsorName"), "name"),
}


def _get(node, field):
    keys, leaf = _PATHS[field]
    for k in keys:
        val = _find(node, k)
        if val is not None:
            return _unwrap(val, leaf) if leaf else _unwrap(val, None)
    return None


def _fetch(sponsor, since_days=None, page_size=200, max_pages=10):
    """All studies for one sponsor, optionally only those updated recently."""
    params = {
        "query.term": f'AREA[LeadSponsorName]"{sponsor}"',
        "fields": ",".join(FIELDS),
        "pageSize": str(page_size),
        "countTotal": "true",
    }
    if since_days:
        cutoff = (date.today() - timedelta(days=int(since_days))).isoformat()
        params["filter.advanced"] = f"AREA[LastUpdatePostDate]RANGE[{cutoff},MAX]"

    out, token, pages = [], None, 0
    while pages < max_pages:
        q = dict(params)
        if token:
            q["pageToken"] = token
        req = urllib.request.Request(f"{API}?{urllib.parse.urlencode(q)}",
                                     headers={"User-Agent": UA,
                                              "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.loads(r.read().decode())
        out.extend(body.get("studies", []))
        token = body.get("nextPageToken")
        pages += 1
        if not token:
            break
    return out


def _to_study(node, ticker, sponsor):
    enroll = _get(node, "EnrollmentCount")
    return Study(
        nct=_get(node, "NCTId") or "",
        ticker=ticker,
        sponsor=sponsor,
        title=(_get(node, "BriefTitle") or "")[:120],
        status=_get(node, "OverallStatus"),
        phase=_get(node, "Phase"),
        last_update=_get(node, "LastUpdatePostDate"),
        primary_completion=_get(node, "PrimaryCompletionDate"),
        completion=_get(node, "CompletionDate"),
        enrollment=int(enroll) if str(enroll).isdigit() else None,
    )


def pull(watch=None, since_days=None):
    """Live pull for every ticker in the watch map. Returns (studies, errors)."""
    watch = watch or DEFAULT_WATCH
    studies, errors = [], []
    for ticker, sponsors in watch.items():
        for sponsor in sponsors:
            try:
                for node in _fetch(sponsor, since_days):
                    s = _to_study(node, ticker, sponsor)
                    if s.nct:
                        studies.append(s)
            except Exception as e:                      # never fake data on failure
                errors.append(f"{ticker} / {sponsor}: {type(e).__name__}: {str(e)[:120]}")
    return studies, errors


# ── snapshot + diff ──────────────────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS trials (
    nct TEXT PRIMARY KEY, ticker TEXT, sponsor TEXT, title TEXT,
    status TEXT, phase TEXT, last_update TEXT,
    primary_completion TEXT, completion TEXT, enrollment INTEGER,
    first_seen TEXT, last_seen TEXT
);
"""


def _conn():
    from lib import db
    c = db.connect()
    c.executescript(SCHEMA)
    return c


def diff(studies, conn=None, asof=None):
    """Compare a live pull against the stored snapshot. Returns change dicts.

    Only material changes are emitted: NEW trial, status transition, phase
    change, primary-completion slip/pull-in, enrollment resize.
    """
    conn = conn or _conn()
    asof = asof or date.today().isoformat()
    changes = []
    for s in studies:
        prior = conn.execute("SELECT * FROM trials WHERE nct=?", (s.nct,)).fetchone()
        if prior is None:
            changes.append({"kind": "NEW", "ticker": s.ticker, "nct": s.nct,
                            "phase": s.phase, "status": s.status,
                            "detail": s.title})
        else:
            if prior["status"] != s.status:
                sev = ("bearish" if s.status in _BAD_STATUS else
                       "bullish" if s.status in _GOOD_STATUS else "info")
                changes.append({"kind": "STATUS", "ticker": s.ticker, "nct": s.nct,
                                "phase": s.phase, "severity": sev,
                                "detail": f"{prior['status']} -> {s.status}"})
            if prior["phase"] != s.phase:
                changes.append({"kind": "PHASE", "ticker": s.ticker, "nct": s.nct,
                                "phase": s.phase,
                                "detail": f"{prior['phase']} -> {s.phase}"})
            if prior["primary_completion"] != s.primary_completion:
                old, new = prior["primary_completion"], s.primary_completion
                dirn = "SLIP" if (old or "") < (new or "") else "PULL-IN"
                changes.append({"kind": f"PRIMARY-COMPLETION {dirn}",
                                "ticker": s.ticker, "nct": s.nct, "phase": s.phase,
                                "severity": "bearish" if dirn == "SLIP" else "bullish",
                                "detail": f"{old} -> {new}"})
            if prior["enrollment"] and s.enrollment and prior["enrollment"] != s.enrollment:
                pct = 100.0 * (s.enrollment - prior["enrollment"]) / prior["enrollment"]
                if abs(pct) >= 10:
                    changes.append({"kind": "ENROLLMENT", "ticker": s.ticker,
                                    "nct": s.nct, "phase": s.phase,
                                    "detail": f"{prior['enrollment']} -> {s.enrollment} "
                                              f"({pct:+.0f}%)"})
        conn.execute(
            """INSERT INTO trials (nct,ticker,sponsor,title,status,phase,last_update,
                                   primary_completion,completion,enrollment,
                                   first_seen,last_seen)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(nct) DO UPDATE SET
                 ticker=excluded.ticker, sponsor=excluded.sponsor,
                 title=excluded.title, status=excluded.status, phase=excluded.phase,
                 last_update=excluded.last_update,
                 primary_completion=excluded.primary_completion,
                 completion=excluded.completion, enrollment=excluded.enrollment,
                 last_seen=excluded.last_seen""",
            (s.nct, s.ticker, s.sponsor, s.title, s.status, s.phase, s.last_update,
             s.primary_completion, s.completion, s.enrollment, asof, asof))
    conn.commit()
    return changes



def _count(term_param, since_days=None):
    """Total matching records for one query, without paging through them."""
    params = dict(term_param, pageSize="1", countTotal="true")
    if since_days:
        cutoff = (date.today() - timedelta(days=int(since_days))).isoformat()
        params["filter.advanced"] = f"AREA[LastUpdatePostDate]RANGE[{cutoff},MAX]"
    req = urllib.request.Request(f"{API}?{urllib.parse.urlencode(params)}",
                                 headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode()).get("totalCount", 0)


def probe(watch=None, since_days=None):
    """Report per-sponsor-string hit counts. Run this when adding a ticker.

    A sponsor string that silently returns 0 contributes nothing and is
    invisible in the aggregate total — that is exactly how the JNJ map was
    wrong for two runs. This makes the miss loud.

    Compares two query modes:
      exact  AREA[LeadSponsorName]"..."  — what pull() uses; strict
      spons  query.spons=...             — CT.gov's own sponsor search; looser,
                                           catches subsidiaries you did not name
    """
    watch = watch or DEFAULT_WATCH
    print(f"PROBE — sponsor-string hit counts"
          + (f" (updated last {since_days}d)" if since_days else " (all time)"))
    print(f"{'ticker':<7}{'exact':>7}{'spons':>8}  sponsor string")
    for ticker, sponsors in watch.items():
        for s in sponsors:
            try:
                ex = _count({"query.term": f'AREA[LeadSponsorName]"{s}"'}, since_days)
            except Exception as e:
                ex = f"ERR:{type(e).__name__}"
            try:
                sp = _count({"query.spons": s}, since_days)
            except Exception as e:
                sp = f"ERR:{type(e).__name__}"
            flag = "  <-- ZERO, string does not match" if ex == 0 else ""
            print(f"{ticker:<7}{str(ex):>7}{str(sp):>8}  {s}{flag}")


def report(watch=None, since_days=None, asof=None):
    """Human-readable diff block for the brief. Late-phase changes lead."""
    watch = watch or DEFAULT_WATCH
    studies, errors = pull(watch, since_days)
    first_run = _conn().execute("SELECT COUNT(*) c FROM trials").fetchone()["c"] == 0
    changes = diff(studies, asof=asof)

    lines = [f"⑥ PIPELINE WATCH — ClinicalTrials.gov  [TOOL] {API}",
             f"   {len(studies)} trial records across {len(watch)} tickers"
             + (f", updated in last {since_days}d" if since_days else "")]
    if errors:
        lines.append("   FETCH ERRORS (data missing, NOT assumed unchanged):")
        lines += [f"     ! {e}" for e in errors]
    if first_run:
        lines.append("   FIRST RUN — baseline stored. Everything reads NEW; "
                     "real diffs start next run.")
        return "\n".join(lines)
    if not changes:
        lines.append("   no material changes since last snapshot")
        return "\n".join(lines)

    def rank(c):
        late = 0 if (c.get("phase") or "").upper() in ("PHASE3", "PHASE2|PHASE3") else 1
        return (late, 0 if c.get("severity") in ("bearish", "bullish") else 1, c["ticker"])

    for c in sorted(changes, key=rank):
        sev = f" [{c['severity']}]" if c.get("severity") else ""
        lines.append(f"   {c['ticker']:<5} {c['kind']}{sev} {c.get('phase') or '-'} "
                     f"{c['nct']}: {c['detail']}")
    lines.append("   Trial data is a CATALYST tell, not a trade trigger — "
                 "confirm with flow/GEX before sizing anything.")
    return "\n".join(lines)


def _config_watch():
    """Prefer config.yaml's map over the module default, so the CLI and
    `run.py --pipeline` always probe/pull the SAME list."""
    try:
        import yaml
        cfg = yaml.safe_load(
            (pathlib.Path(__file__).resolve().parent.parent / "config.yaml").read_text())
        return (cfg or {}).get("pipeline_watch") or DEFAULT_WATCH
    except Exception:
        return DEFAULT_WATCH


if __name__ == "__main__":
    import sys
    argv = sys.argv[1:]
    args = [a for a in argv if not a.startswith("-")]
    since = next((a.split("=", 1)[1] for a in argv if a.startswith("--since=")), None)
    base = _config_watch()
    w = {t: base[t] for t in args if t in base} or base
    if "--probe" in argv:
        probe(w, since)
    else:
        print(report(w, since))
