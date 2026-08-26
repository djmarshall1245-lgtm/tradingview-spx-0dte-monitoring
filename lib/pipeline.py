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


def _fetch(sponsor, since_days=None, page_size=200, max_pages=10, mode="exact"):
    """All studies for one sponsor, optionally only those updated recently.

    mode="exact" uses CT.gov's own sponsor search, which also catches
    subsidiaries and co-sponsored trials. Measured on this watchlist it
    returns 25-100% MORE records than the strict name match (MRK 85 -> 127,
    GILD 12 -> 26 on a 14d window), which is why it is the default: a
    catalyst you never see is worse than one you filter out.

    mode="exact" is the strict AREA[LeadSponsorName] match -- lead sponsor
    only, no collaborators. Use it when attribution matters more than
    coverage. Set via config.yaml -> pipeline.query_mode.
    """
    params = {
        ("query.spons" if mode == "spons" else "query.term"):
            sponsor if mode == "spons" else f'AREA[LeadSponsorName]"{sponsor}"',
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


def pull(watch=None, since_days=None, mode="exact"):
    """Live pull for every ticker in the watch map. Returns (studies, errors).

    A trial can surface under more than one sponsor string (J&J files across
    several Janssen entities); dedupe on NCTId so it is counted once.
    """
    watch = watch or DEFAULT_WATCH
    studies, errors, seen = [], [], set()
    for ticker, sponsors in watch.items():
        for sponsor in sponsors:
            try:
                for node in _fetch(sponsor, since_days, mode=mode):
                    s = _to_study(node, ticker, sponsor)
                    if s.nct and s.nct not in seen:
                        seen.add(s.nct)
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
            flag = ""
            if ex == 0:
                if since_days:
                    # A zero in a WINDOW only means no recent updates. Confirm
                    # against all-time before calling the string broken --
                    # reading a windowed zero as a bad name sent this map on a
                    # wrong-turn once already.
                    alltime = _count({"query.term": f'AREA[LeadSponsorName]"{s}"'})
                    flag = ("  <-- no updates in window (string OK, "
                            f"{alltime} all-time)") if alltime else \
                           "  <-- ZERO all-time, string does not match"
                else:
                    flag = "  <-- ZERO all-time, string does not match"
            print(f"{ticker:<7}{str(ex):>7}{str(sp):>8}  {s}{flag}")


def report(watch=None, since_days=None, asof=None, mode="exact", max_lines=25):
    """Human-readable diff block for the brief. Late-phase changes lead."""
    watch = watch or DEFAULT_WATCH
    studies, errors = pull(watch, since_days, mode)
    first_run = _conn().execute("SELECT COUNT(*) c FROM trials").fetchone()["c"] == 0
    changes = diff(studies, asof=asof)

    lines = [f"⑥ PIPELINE WATCH — ClinicalTrials.gov  [TOOL] {API}",
             f"   {len(studies)} trial records across {len(watch)} tickers "
             f"(match: {mode})"
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

    # A NEW record on an early-phase or observational trial is not news --
    # 150 undifferentiated lines is how a real signal gets scrolled past. Any
    # CHANGE to an existing trial stays, at every phase: a terminated Phase 1
    # still tells you something.
    LATE = ("PHASE3", "PHASE4", "PHASE2|PHASE3")
    material = [c for c in changes
                if c["kind"] != "NEW" or (c.get("phase") or "").upper() in LATE]
    suppressed = len(changes) - len(material)

    def rank(c):
        return (0 if c["kind"] != "NEW" else 1,                       # changes first
                0 if (c.get("phase") or "").upper() in LATE else 1,   # then late phase
                0 if c.get("severity") in ("bearish", "bullish") else 1,
                c["ticker"])

    shown = sorted(material, key=rank)[:max_lines]
    for c in shown:
        sev = f" [{c['severity']}]" if c.get("severity") else ""
        lines.append(f"   {c['ticker']:<5} {c['kind']}{sev} {c.get('phase') or '-'} "
                     f"{c['nct']}: {c['detail'][:95]}")
    if len(material) > len(shown):
        lines.append(f"   ... +{len(material) - len(shown)} more material changes "
                     f"(raise pipeline.max_lines to see them)")
    if suppressed:
        lines.append(f"   ({suppressed} new early-phase/observational trials not shown "
                     f"— late-phase only)")
    lines.append("   Trial data is a CATALYST tell, not a trade trigger — "
                 "confirm with flow/GEX before sizing anything.")
    return "\n".join(lines)


def _config_watch():
    """Prefer config.yaml over module defaults, so the CLI and
    `run.py --pipeline` always use the SAME list and query mode."""
    try:
        import yaml
        cfg = yaml.safe_load(
            (pathlib.Path(__file__).resolve().parent.parent / "config.yaml").read_text())
        return ((cfg or {}).get("pipeline_watch") or DEFAULT_WATCH,
                ((cfg or {}).get("pipeline") or {}).get("query_mode", "exact"))
    except Exception:
        return DEFAULT_WATCH, "exact"


if __name__ == "__main__":
    import sys
    argv = sys.argv[1:]
    args = [a for a in argv if not a.startswith("-")]
    since = next((a.split("=", 1)[1] for a in argv if a.startswith("--since=")), None)
    base, mode = _config_watch()
    unknown = [a for a in args if a not in base]
    if unknown:
        # Falling back to the full map here would answer a question about one
        # ticker with data about twelve others, and look like a valid result.
        sys.exit(f"Not in pipeline_watch: {', '.join(unknown)}\n"
                 f"Tracked: {', '.join(base)}\n"
                 f"Add it to config.yaml -> pipeline_watch first.")
    w = {a: base[a] for a in args} or base
    if "--probe" in argv:
        probe(w, since)
    else:
        print(report(w, since, mode=mode))
