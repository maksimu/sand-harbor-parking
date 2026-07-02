#!/usr/bin/env python3
"""
Sand Harbor release-time monitor.

Polls all four day-use parking pools every INTERVAL seconds for ~24h and records,
with tight before/after timestamps, the exact moment two things happen per pool:

  WINDOW_ROLL    - Facility.Restrictions.FutureBookingEnds advances by a day
                   (the midnight calendar roll that widens the booking window)
  INVENTORY_OPEN - a specific date's TotalAvailable flips 0 -> N
                   (spots actually become bookable -- the "8 AM" event we want to prove)

Proof for each event = our local Pacific wall-clock at the poll that first saw the
change, the previous poll's timestamp (so the true instant is bracketed between them),
AND the server's own HTTP `Date` header (independent of this machine's clock).

Writes:
  release_proof.log   - human-readable event log (the proof)
  release_poll.jsonl   - every poll's raw snapshot (audit trail)
"""
import json, time, os, sys, urllib.request
from datetime import datetime, timezone
try:
    from zoneinfo import ZoneInfo
    PT = ZoneInfo("America/Los_Angeles")
except Exception:
    PT = None

POOLS = {97: "1-day", 94: "7-day", 95: "30-day", 96: "90-day"}
URL = "https://nevadardr.usedirect.com/NevadaRDR/rdr/search/occupancygrid/{fid}/startdate/{d}/nights/95/0"
INTERVAL = 30                      # seconds between polling rounds
DURATION = 24 * 3600 + 900         # run ~24h (+15 min slack)
HEARTBEAT = 1800                   # log a still-alive line every 30 min

HERE = os.path.dirname(os.path.abspath(__file__))
POLL_LOG = os.path.join(HERE, "release_poll.jsonl")
PROOF_LOG = os.path.join(HERE, "release_proof.log")


def pt_now():
    return datetime.now(PT) if PT else datetime.now(timezone.utc)


def proof(msg):
    line = "%s  %s" % (pt_now().isoformat(timespec="seconds"), msg)
    print(line, flush=True)
    with open(PROOF_LOG, "a") as f:
        f.write(line + "\n")


def fetch(fid):
    d = pt_now().strftime("%Y-%m-%d")
    req = urllib.request.Request(URL.format(fid=fid, d=d), headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        server_date = r.headers.get("Date")          # server clock, independent of this machine
        j = json.load(r)
    fac = j.get("Facility") or {}
    dates = fac.get("Dates") or {}
    avail, reserved = {}, {}
    for v in dates.values():
        dt = v.get("Date")
        avail[dt] = v.get("TotalAvailable") or 0
        reserved[dt] = v.get("ReservationCount") or 0
    ends = ((fac.get("Restrictions") or {}).get("FutureBookingEnds") or "")[:10]
    open_dates = sorted(d for d, a in avail.items() if a > 0)
    return {
        "ends": ends,
        "avail": avail,
        "reserved": reserved,
        "server_date": server_date,
        "openDates": open_dates,
        "maxOpen": open_dates[-1] if open_dates else None,
    }


def main():
    prev = {}
    proof("=== monitor start; interval=%ss; ~24h; pools=%s ===" % (INTERVAL, POOLS))
    start = time.time()
    last_hb = start
    while time.time() - start < DURATION:
        t = pt_now().isoformat(timespec="seconds")
        snap = {"t": t}
        for fid, name in POOLS.items():
            try:
                s = fetch(fid)
            except Exception as e:
                proof("[%s] fetch error: %s" % (name, e))
                continue
            snap[name] = {"ends": s["ends"], "maxOpen": s["maxOpen"],
                          "nOpen": len(s["openDates"]), "server": s["server_date"]}
            p = prev.get(fid)
            if p:
                if s["ends"] and p["ends"] and s["ends"] != p["ends"]:
                    proof("[%s] WINDOW_ROLL   FutureBookingEnds %s -> %s   server=%s   "
                          "(between prev poll %s and now %s)"
                          % (name, p["ends"], s["ends"], s["server_date"], p["t"], t))
                newly = [d for d in s["openDates"] if p["avail"].get(d, 0) == 0]
                for d in newly:
                    proof("[%s] INVENTORY_OPEN  date=%s  avail %s -> %s  reserved=%s  server=%s  "
                          "<< spots became bookable between prev poll %s and now %s >>"
                          % (name, d, p["avail"].get(d, 0), s["avail"][d], s["reserved"].get(d, 0),
                             s["server_date"], p["t"], t))
            s["t"] = t
            prev[fid] = s
        with open(POLL_LOG, "a") as f:
            f.write(json.dumps(snap) + "\n")
        if time.time() - last_hb >= HEARTBEAT:
            last_hb = time.time()
            proof("... alive; open-day counts: " +
                  ", ".join("%s=%s" % (n, snap.get(n, {}).get("nOpen", "?")) for n in POOLS.values()))
        time.sleep(INTERVAL)
    proof("=== monitor end (~24h elapsed) ===")


if __name__ == "__main__":
    main()
