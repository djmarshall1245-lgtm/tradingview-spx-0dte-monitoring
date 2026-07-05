"""Offline tests: atom parsing, html strip, synthesis scoring, paperlog roundtrip."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import edgar
import synthesis
import paperlog

SAMPLE_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Latest Filings</title>
  <entry>
    <title>8-K - LUCID GROUP, INC. (0001811210) (Filer)</title>
    <link rel="alternate" type="text/html"
     href="https://www.sec.gov/Archives/edgar/data/1811210/000181121026000042-index.htm"/>
    <summary type="html">&lt;b&gt;Filed:&lt;/b&gt; 2026-07-02</summary>
    <updated>2026-07-02T16:05:03-04:00</updated>
    <category scheme="https://www.sec.gov/" label="form type" term="8-K"/>
    <id>urn:tag:sec.gov,2008:accession-number=0001811210-26-000042</id>
  </entry>
  <entry>
    <title>SC 13D - SOME ACTIVIST LP (0009999999) (Filed by)</title>
    <link rel="alternate" type="text/html" href="https://example"/>
    <updated>2026-07-02T16:06:00-04:00</updated>
    <category scheme="https://www.sec.gov/" label="form type" term="SC 13D"/>
    <id>urn:tag:sec.gov,2008:accession-number=0009999999-26-000007</id>
  </entry>
  <entry>
    <title>4 - DOE JOHN (0001234567) (Reporting)</title>
    <link rel="alternate" type="text/html" href="https://example"/>
    <updated>2026-07-02T16:06:10-04:00</updated>
    <category scheme="https://www.sec.gov/" label="form type" term="4"/>
    <id>urn:tag:sec.gov,2008:accession-number=0001234567-26-000099</id>
  </entry>
</feed>"""


def test_atom_parse():
    w = EdgarNoInit()
    entries = w._parse_atom(SAMPLE_ATOM)
    assert len(entries) == 3
    e0 = entries[0]
    assert e0["form"] == "8-K"
    assert e0["cik"] == 1811210
    assert e0["accession"] == "0001811210-26-000042"
    assert w.is_target(entries[0]) and w.is_target(entries[1])
    assert not w.is_target(entries[2])           # Form 4 filtered
    print("atom parse OK")


def test_dedupe_and_startup_backlog():
    w = EdgarNoInit()
    first = [e for e in w._parse_atom(SAMPLE_ATOM)]
    for e in first:
        w.seen.add(e["accession"])
    w._first_poll = False
    again = [e for e in w._parse_atom(SAMPLE_ATOM) if e["accession"] not in w.seen]
    assert again == []
    print("dedupe OK")


def test_strip_html():
    out = edgar.strip_html("<html><style>x{}</style><b>Item&nbsp;1.01</b>  Entry into <i>agreement</i></html>")
    assert out == "Item 1.01 Entry into agreement", out
    print("strip_html OK")


def test_synthesis():
    cfg = {"w_conviction": 0.5, "w_short": 0.3, "w_flow": 0.2}
    # bull filing, hard-to-borrow, call-skewed flow -> high score
    s1, b1 = synthesis.score(cfg,
                             {"direction": "bull", "conviction": 9},
                             {"fee_rate": 0.45},
                             {"skew": 0.8, "alert_count": 12})
    assert s1 > 80, (s1, b1)
    # neutral always zero
    s2, _ = synthesis.score(cfg, {"direction": "neutral", "conviction": 9},
                            {"fee_rate": 0.45}, {"skew": 0.8, "alert_count": 12})
    assert s2 == 0.0
    # bear filing on already-crowded short gets damped short factor
    s3, b3 = synthesis.score(cfg, {"direction": "bear", "conviction": 8},
                             {"fee_rate": 0.60}, {"skew": -0.5, "alert_count": 5})
    assert b3["short"] == 0.0, b3
    print(f"synthesis OK (bull={s1}, neutral={s2}, bear={s3})")


def test_paperlog(tmp="test_signals.db"):
    if os.path.exists(tmp):
        os.remove(tmp)
    pl = paperlog.PaperLog(tmp)
    entry = {"accession": "0001-26-01", "filed_at": "2026-07-02T16:05:03-04:00",
             "form": "8-K", "cik": 1811210, "title": "LUCID GROUP, INC."}
    pl.record(entry, "LCID", {"direction": "bull", "conviction": 8, "reason": "test"},
              {"short": 0.9, "flow": 0.8}, 82.0, alerted=True, price_alert=6.08)
    row = pl.db.execute("SELECT ticker, score, alerted FROM signals").fetchone()
    assert row == ("LCID", 82.0, 1), row
    os.remove(tmp)
    print("paperlog OK")


class EdgarNoInit(edgar.EdgarWatcher):
    """Skip network-touching __init__ pieces for offline tests."""
    def __init__(self):
        self.target_forms = {"8-K", "8-K/A", "SC 13D", "SC 13D/A", "S-3",
                             "424B5", "SC TO-T", "SC 14D9"}
        self.seen = set()
        self._first_poll = True


if __name__ == "__main__":
    test_atom_parse()
    test_dedupe_and_startup_backlog()
    test_strip_html()
    test_synthesis()
    test_paperlog()
    print("ALL TESTS PASSED")
