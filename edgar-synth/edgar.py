"""Phase 1: EDGAR getcurrent watcher.

Polls https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent (Atom) at a
tight cadence, dedupes by accession number, filters to target forms and the
trading universe. SEC fair-access rules: declared User-Agent, <10 req/s total.
"""
import re
import time
import html
import json
import logging
import xml.etree.ElementTree as ET

import requests

log = logging.getLogger("edgar")
ATOM_NS = "{http://www.w3.org/2005/Atom}"
FEED_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


class Throttle:
    """Global min-interval between SEC requests (fair access)."""

    def __init__(self, min_interval=0.15):
        self.min_interval = min_interval
        self._last = 0.0

    def wait(self):
        delta = time.monotonic() - self._last
        if delta < self.min_interval:
            time.sleep(self.min_interval - delta)
        self._last = time.monotonic()


class EdgarWatcher:
    def __init__(self, user_agent, target_forms, feed_count=100, feed_timeout=30):
        if "CHANGE_ME" in user_agent:
            raise SystemExit("Set sec_user_agent in config.yaml (SEC requires a declared identity).")
        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent
        self.target_forms = set(target_forms)
        self.feed_count = feed_count
        self.feed_timeout = feed_timeout
        self.throttle = Throttle()
        self.seen = set()          # accession numbers
        self._first_poll = True

    # ---- CIK <-> ticker map -------------------------------------------------
    def load_cik_map(self):
        """Returns {cik_int: ticker} from SEC's official mapping file."""
        self.throttle.wait()
        r = self.session.get(TICKERS_URL, timeout=30)
        r.raise_for_status()
        data = r.json()
        return {int(v["cik_str"]): v["ticker"].upper() for v in data.values()}

    # ---- feed polling -------------------------------------------------------
    def poll(self):
        """One poll of the getcurrent feed. Returns list of NEW entry dicts."""
        params = {
            "action": "getcurrent", "type": "", "company": "",
            "dateb": "", "owner": "include",
            "count": self.feed_count, "output": "atom",
        }
        self.throttle.wait()
        try:
            r = self.session.get(FEED_URL, params=params, timeout=self.feed_timeout)
            r.raise_for_status()
        except requests.RequestException as e:
            log.warning("feed poll failed: %s", e)
            return []
        entries = self._parse_atom(r.text)
        fresh = []
        for e in entries:
            if e["accession"] in self.seen:
                continue
            self.seen.add(e["accession"])
            if not self._first_poll:            # don't fire on backlog at startup
                fresh.append(e)
        self._first_poll = False
        if len(self.seen) > 50000:              # bound memory on long runs
            self.seen = set(list(self.seen)[-25000:])
        return fresh

    def _parse_atom(self, text):
        out = []
        try:
            root = ET.fromstring(text)
        except ET.ParseError as e:
            log.warning("atom parse error: %s", e)
            return out
        for entry in root.findall(f"{ATOM_NS}entry"):
            title = (entry.findtext(f"{ATOM_NS}title") or "").strip()
            updated = (entry.findtext(f"{ATOM_NS}updated") or "").strip()
            cat = entry.find(f"{ATOM_NS}category")
            form = cat.get("term", "").strip() if cat is not None else ""
            link_el = entry.find(f"{ATOM_NS}link")
            link = link_el.get("href", "") if link_el is not None else ""
            eid = entry.findtext(f"{ATOM_NS}id") or ""
            m = re.search(r"accession-number=([\d-]+)", eid)
            accession = m.group(1) if m else eid
            cm = re.search(r"\((\d{7,10})\)", title)
            cik = int(cm.group(1)) if cm else None
            out.append({
                "accession": accession, "form": form, "cik": cik,
                "title": html.unescape(title), "link": link, "filed_at": updated,
            })
        return out

    def is_target(self, entry):
        return entry["form"] in self.target_forms

    # ---- document fetch (for triage) ---------------------------------------
    def fetch_primary_text(self, entry, max_chars=12000):
        """Fetch the filing's primary document and return stripped text."""
        cik, acc = entry["cik"], entry["accession"]
        if not cik or not acc:
            return ""
        acc_nodash = acc.replace("-", "")
        base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nodash}"
        self.throttle.wait()
        try:
            r = self.session.get(f"{base}/index.json", timeout=self.feed_timeout)
            r.raise_for_status()
            items = r.json().get("directory", {}).get("item", [])
        except (requests.RequestException, json.JSONDecodeError) as e:
            log.warning("index fetch failed %s: %s", acc, e)
            return ""
        name = pick_primary_doc(items)
        if not name:
            return ""
        self.throttle.wait()
        try:
            r = self.session.get(f"{base}/{name}", timeout=self.feed_timeout)
            r.raise_for_status()
        except requests.RequestException as e:
            log.warning("doc fetch failed %s/%s: %s", acc, name, e)
            return ""
        return strip_html(r.text)[:max_chars]


def pick_primary_doc(items):
    """Pick the filed primary document from an index.json item list.

    Heuristic: largest .htm/.html/.txt that is NOT an EDGAR-generated
    artifact. Crucially skips R<n>.htm — the XBRL viewer's rendered
    reports (R1.htm = cover page). Picking those sent the triage LLM
    cover-page metadata instead of the 8-K body (EMPD/PNNT, 2026-07-06).
    Returns the file name, or None.
    """
    docs = []
    for i in items:
        name = i.get("name", "")
        low = name.lower()
        if not low.endswith((".htm", ".html", ".txt")):
            continue
        if "index" in low:                      # -index.html, index-headers
            continue
        if re.fullmatch(r"r\d+\.htm", low):     # XBRL viewer renderings
            continue
        docs.append(i)
    if not docs:
        return None
    docs.sort(key=lambda i: int(i.get("size") or 0), reverse=True)
    return docs[0]["name"]


def strip_html(raw):
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    return re.sub(r"\s+", " ", raw).strip()
