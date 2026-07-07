"""Offline tests: atom parsing, html strip, synthesis scoring, paperlog roundtrip."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import edgar
import synthesis
import paperlog
import triage

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


def test_pick_primary_doc():
    # Real directory listings from 2026-07-06 filings that triaged blind:
    # the largest .htm is EDGAR's XBRL-viewer cover-page rendering (R1.htm),
    # NOT the filed 8-K. pick_primary_doc must skip viewer artifacts.
    empd = [  # 0001683168-26-005307 (EMPD)
        {"name": "R1.htm", "size": "41338"},
        {"name": "MetaLinks.json", "size": "39129"},
        {"name": "empery_8k.htm", "size": "34767"},
        {"name": "empd-20260706_lab.xml", "size": "34239"},
        {"name": "0001683168-26-005307-xbrl.zip", "size": "18668"},
        {"name": "empery_ex0401.htm", "size": "16204"},
        {"name": "empery_ex9901.htm", "size": "7418"},
        {"name": "report.css", "size": "2767"},
        {"name": "Show.js", "size": "1085"},
        {"name": "FilingSummary.xml", "size": "1621"},
        {"name": "0001683168-26-005307-index.html", "size": "0"},
        {"name": "0001683168-26-005307.txt", "size": "0"},
    ]
    pnnt = [  # 0001171843-26-004478 (PNNT)
        {"name": "MetaLinks.json", "size": "41781"},
        {"name": "R1.htm", "size": "36641"},
        {"name": "gnw-20250101_lab.xml", "size": "35956"},
        {"name": "f8k_063026.htm", "size": "18901"},
        {"name": "exh_991.htm", "size": "3860"},
        {"name": "report.css", "size": "2767"},
        {"name": "0001171843-26-004478-index.html", "size": "0"},
    ]
    assert edgar.pick_primary_doc(empd) == "empery_8k.htm", edgar.pick_primary_doc(empd)
    assert edgar.pick_primary_doc(pnnt) == "f8k_063026.htm", edgar.pick_primary_doc(pnnt)
    # R42.htm-style financial-report pages must be skipped too
    assert edgar.pick_primary_doc(
        [{"name": "R42.htm", "size": "99999"}, {"name": "abc_8k.htm", "size": "10"}]
    ) == "abc_8k.htm"
    # nothing usable -> None
    assert edgar.pick_primary_doc([{"name": "R1.htm", "size": "5"}]) is None
    print("pick_primary_doc OK")


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
        self.feed_timeout = 30


def test_truncated_json_repair():
    # Simulates the GETY case: valid JSON cut off mid-string at ~char 469
    full = '{"direction": "bear", "conviction": 8, "reason": "Company disclosed going-concern language in amended 8-K filing, indicating substantial doubt about ability to continue operations", "items": ["Item 2.02", "going-concern"]}'
    # Truncate mid-reason string (like MiniMax M3 did at char 469)
    truncated = full[:120]  # cuts mid-string in "reason"

    # _repair_json should either fix it or return None — never raise
    result = triage._repair_json(truncated)
    if result is not None:
        assert "direction" in result
        assert "conviction" in result
        print(f"  repair succeeded: conv={result['conviction']}, dir={result['direction']}")
    else:
        print("  repair returned None (acceptable)")

    # Fully valid JSON parses fine through _repair_json
    valid = '{"direction": "bull", "conviction": 7, "reason": "debt retired", "items": ["8-K"]}'
    assert triage._repair_json(valid) is not None
    assert triage._repair_json(valid)["conviction"] == 7

    # Truncation after a complete key-value but missing closing brace
    partial = '{"direction": "bear", "conviction": 6, "reason": "dilution"'
    result2 = triage._repair_json(partial)
    if result2 is not None:
        assert result2["direction"] == "bear"
        assert result2["conviction"] == 6
        print(f"  partial repair succeeded: {result2}")

    # Garbage input returns None
    assert triage._repair_json("not json at all") is None
    assert triage._repair_json("") is None

    print("truncated_json_repair OK")


if __name__ == "__main__":
    test_atom_parse()
    test_dedupe_and_startup_backlog()
    test_strip_html()
    test_pick_primary_doc()
    test_synthesis()
    test_paperlog()
    test_truncated_json_repair()
    print("ALL TESTS PASSED")
