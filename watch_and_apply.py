#!/usr/bin/env python3
"""
Watch for the daily "release" (each pool's booking window edge advancing a day),
capture the exact time with proof, then patch the dashboards' RELEASE_HOUR_PT /
RELEASE_MIN_PT to the proven Pacific time, write a findings file, and push to main.

Fully autonomous: start it detached and walk away. If no roll is seen within the
watch window it exits WITHOUT changing anything (never guesses).
"""
import json, os, re, time, subprocess, urllib.request
from datetime import datetime, timezone, timedelta
try:
    from zoneinfo import ZoneInfo
    PT = ZoneInfo("America/Los_Angeles")
except Exception:
    PT = None

POOLS = {97: "1-day", 94: "7-day", 95: "30-day", 96: "90-day"}
URL = "https://nevadardr.usedirect.com/NevadaRDR/rdr/search/occupancygrid/{fid}/startdate/{d}/nights/95/0"
INTERVAL = 30
WATCH_SECONDS = 3 * 3600 + 600      # ~3h
GRACE = 420                          # after 1st roll, collect other pools rolling near it
HEARTBEAT = 1800

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "watch_apply.log")
FINDINGS = os.path.join(HERE, "RELEASE_TIME_FINDINGS.md")
GIT_NAME, GIT_EMAIL = "Maksim Ustinov", "maksimu@gmail.com"


def now_pt():
    return datetime.now(PT) if PT else datetime.now(timezone.utc)


def log(msg):
    line = "%s  %s" % (now_pt().isoformat(timespec="seconds"), msg)
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def poll(fid):
    d = now_pt().strftime("%Y-%m-%d")
    req = urllib.request.Request(URL.format(fid=fid, d=d), headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        server_date = r.headers.get("Date")
        j = json.load(r)
    fac = j.get("Facility") or {}
    ends = ((fac.get("Restrictions") or {}).get("FutureBookingEnds") or "")[:10]
    dates = fac.get("Dates") or {}
    avail = {v.get("Date"): (v.get("TotalAvailable") or 0) for v in dates.values()}
    reserved = {v.get("Date"): (v.get("ReservationCount") or 0) for v in dates.values()}
    return {"ends": ends, "avail": avail, "reserved": reserved, "server_date": server_date}


def run_git(args):
    p = subprocess.run(["git", "-C", HERE] + args, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def patch_file(path, h, m):
    with open(path) as f:
        c = f.read()
    c2 = re.sub(r"const RELEASE_HOUR_PT\s*=\s*\d+;", "const RELEASE_HOUR_PT = %d;" % h, c)
    c2 = re.sub(r"const RELEASE_MIN_PT\s*=\s*\d+;", "const RELEASE_MIN_PT = %d;" % m, c2)
    if c2 != c:
        with open(path, "w") as f:
            f.write(c2)
        return True
    return False


def apply_and_push(rolls):
    # earliest release estimate drives the countdown ("next day to open")
    ests = []
    for name, r in rolls.items():
        mid = r["prev_dt"] + (r["detect_dt"] - r["prev_dt"]) / 2   # midpoint of the 30s bracket
        if mid.second >= 30:
            mid = mid + timedelta(minutes=1)
        r["est"] = mid.replace(second=0, microsecond=0)            # round to nearest minute
        ests.append(r["est"])
    release = min(ests)
    h, m = release.hour, release.minute
    log("APPLYING release time = %02d:%02d PT (earliest of %d pools)" % (h, m, len(rolls)))

    changed = []
    for fn in ("index.html", "3d.html"):
        p = os.path.join(HERE, fn)
        if os.path.exists(p) and patch_file(p, h, m):
            changed.append(fn)
    log("patched: %s" % changed)

    # findings / proof file
    lines = ["# Sand Harbor — proven daily release time\n",
             "Detected automatically by `watch_and_apply.py` watching each pool's booking-window",
             "edge (`FutureBookingEnds`) advance. Each event is bracketed between two 30-second",
             "polls and corroborated by the reservation server's own `Date` header.\n",
             "**Applied release time (drives the countdown): %02d:%02d Pacific** (earliest across pools)\n" % (h, m),
             "| Pool | window edge | before → after | detected (PT, ±30s) | server clock | est. release |",
             "|---|---|---|---|---|---|"]
    for name in ["1-day", "7-day", "30-day", "90-day"]:
        r = rolls.get(name)
        if not r:
            lines.append("| %s | — | (no roll seen in watch window) | — | — | — |" % name)
            continue
        lines.append("| %s | edge | %s → %s | between %s and %s | %s | **%s** |" % (
            name, r["from"], r["to"], r["prev_dt"].isoformat(timespec="seconds"),
            r["detect_dt"].isoformat(timespec="seconds"), r["server_date"], r["est"].strftime("%H:%M")))
    lines.append("\nNew far date at detection (corroboration it became bookable, not just window-widened):")
    for name in ["1-day", "7-day", "30-day", "90-day"]:
        r = rolls.get(name)
        if r:
            lines.append("- **%s**: %s → avail %s, reserved %s" % (name, r["new_date"], r["new_avail"], r["new_reserved"]))
    lines.append("\n_Generated %s._\n" % now_pt().isoformat(timespec="seconds"))
    with open(FINDINGS, "w") as f:
        f.write("\n".join(lines) + "\n")

    add = ["RELEASE_TIME_FINDINGS.md", "monitor_release_time.py", "watch_and_apply.py"]
    if "index.html" in changed:
        add.append("index.html")
    run_git(["add"] + add)
    summary = ", ".join("%s@%s" % (n, r["est"].strftime("%H:%M")) for n, r in rolls.items())
    msg = ("Set proven daily release time to %02d:%02d Pacific\n\n"
           "Detected by watching each pool's FutureBookingEnds advance (see\n"
           "RELEASE_TIME_FINDINGS.md for the timestamped proof + server clock).\n"
           "Per-pool: %s\n\n"
           "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>" % (h, m, summary))
    rc, out = run_git(["-c", "user.name=%s" % GIT_NAME, "-c", "user.email=%s" % GIT_EMAIL, "commit", "-m", msg])
    log("git commit rc=%d %s" % (rc, out[-300:]))
    if rc == 0:
        rc2, out2 = run_git(["push", "origin", "main"])
        log("git push rc=%d %s" % (rc2, out2[-300:]))
    else:
        log("commit failed; leaving changes staged for manual push")


def main():
    log("=== watcher start; interval=%ss; watch~%.1fh; pools=%s ===" % (INTERVAL, WATCH_SECONDS/3600, POOLS))
    base = {}
    prev_ends = {}
    prev_dt = {}
    rolls = {}
    start = time.time()
    last_hb = start
    apply_deadline = None
    while time.time() - start < WATCH_SECONDS:
        t = now_pt()
        for fid, name in POOLS.items():
            if name in rolls:
                continue
            try:
                s = poll(fid)
            except Exception as e:
                log("[%s] poll error: %s" % (name, e))
                continue
            ends = s["ends"]
            if fid not in base:
                if not ends:
                    continue
                base[fid] = ends
                prev_ends[fid] = ends
                prev_dt[fid] = t
                log("[%s] baseline window edge = %s" % (name, ends))
                continue
            if ends and base[fid] and ends > base[fid]:
                new_dates = sorted(d for d in s["avail"] if d > base[fid])
                nd = new_dates[0] if new_dates else ends
                rolls[name] = {"from": base[fid], "to": ends, "prev_dt": prev_dt[fid], "detect_dt": t,
                               "server_date": s["server_date"], "new_date": nd,
                               "new_avail": s["avail"].get(nd, 0), "new_reserved": s["reserved"].get(nd, 0)}
                log("[%s] *** WINDOW ROLL *** %s -> %s  detected between %s and %s  server=%s  (new %s avail=%s)"
                    % (name, base[fid], ends, prev_dt[fid].isoformat(timespec="seconds"),
                       t.isoformat(timespec="seconds"), s["server_date"], nd, s["avail"].get(nd, 0)))
                if apply_deadline is None:
                    apply_deadline = time.time() + GRACE
                    log("first roll seen; collecting other pools for %ss before applying" % GRACE)
            else:
                prev_ends[fid] = ends
                prev_dt[fid] = t
        if apply_deadline and (time.time() >= apply_deadline or len(rolls) == len(POOLS)):
            log("applying (rolls=%s)" % list(rolls.keys()))
            try:
                apply_and_push(rolls)
            except Exception as e:
                log("apply error: %s" % e)
            log("=== watcher done (applied) ===")
            return
        if time.time() - last_hb >= HEARTBEAT:
            last_hb = time.time()
            log("... alive; rolls so far: %s" % (list(rolls.keys()) or "none"))
        time.sleep(INTERVAL)
    log("=== watcher end: no window roll detected in watch window; NO changes made ===")


if __name__ == "__main__":
    main()
