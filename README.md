# Sand Harbor Parking Availability

A single-file live dashboard for **Sand Harbor** (Lake Tahoe Nevada State Park)
day-use parking. It pulls live data straight from the reservation system's API —
**no server, no install, no scraping.**

![pools: 1 / 7 / 30 / 90 days in advance](https://img.shields.io/badge/pools-1%20%C2%B7%207%20%C2%B7%2030%20%C2%B7%2090%20days-2ea44f)

---

## How to run / access it

You have three options, easiest first:

### 1. Just open the file (simplest)
Download `index.html` and **double-click it**. It opens in your browser and loads
live availability. That's it — nothing to install.

To get the file from this repo: click `index.html` above → the **Download raw file**
button, or clone the repo (see below).

### 2. Host it free on GitHub Pages (best for phones)
This makes the dashboard available at a public URL you can bookmark on any phone:

1. On GitHub, go to **Settings → Pages**.
2. Under **Build and deployment → Source**, pick **Deploy from a branch**.
3. Branch: **`main`**, folder: **`/ (root)`** → **Save**.
4. Wait ~1 minute. Your dashboard will be live at:
   **`https://maksimu.github.io/sand-harbor-parking/`**

Bookmark that link on your phone's home screen and it works like an app.

### 3. Clone and serve locally
```bash
git clone https://github.com/maksimu/sand-harbor-parking.git
cd sand-harbor-parking
python3 -m http.server 8777
# then open http://localhost:8777
```

> Opening the file directly (option 1) works fine — the reservation API allows
> browser requests from any origin, so no local server is required.

---

## What the dashboard shows

- A summary of **every upcoming date that currently has open parking spots**, as
  clickable chips.
- A color-coded calendar for each of the four booking pools
  (🟢 open · 🟡 almost gone · 🔴 sold out · ⬜ not released yet).
- An **"Only show open dates"** filter and a **60-second auto-refresh** toggle.
- Click any open date to jump straight to that pool's booking page on
  reservenevada.com.

---

## How their system works (the confusing part, explained)

reservenevada.com runs on the **UseDirect "RDR"** platform. The Sand Harbor page
(`#!park/17/95`) is **place 17 = Sand Harbor State Park**, and the catch is that the
*same parking lot* is sold through **four separate inventory pools**, each opening
reservations on a different rolling window:

| Facility ID | Pool                | Spots |
|-------------|---------------------|-------|
| 97          | 1 day in advance    | 75    |
| 94          | 7 days in advance   | 50    |
| 95          | 30 days in advance  | 100   |
| 96          | 90 days in advance  | 200   |
| 49          | Group Day Use Area  | —     |

Each morning, a new day's worth of spots is released at the far edge of each window.
That's why open dates cluster near the **90-day edge** (book way ahead) or
**tomorrow** (last-minute), and the middle is almost always sold out.

---

## The API (no key required, CORS-open)

Base: `https://nevadardr.usedirect.com/NevadaRDR/rdr/`

- **Per-date availability** (what this dashboard uses):
  `GET search/occupancygrid/{facilityId}/startdate/{YYYY-MM-DD}/nights/{N}/0`
  → `Facility.Dates[*]` with `Date`, `TotalAvailable`, `ReservationCount`,
  `UnitCount`. `TotalAvailable > 0` means bookable.
- **Park + facility list:**
  `POST search/place` with `{"PlaceId":17,"StartDate":"YYYY-MM-DD","Nights":1}`
- **Facility detail:** `GET fd/facilities/{facilityId}`

Quick test:
```bash
curl -s "https://nevadardr.usedirect.com/NevadaRDR/rdr/search/occupancygrid/96/startdate/2026-06-22/nights/95/0" | python3 -m json.tool
```

---

## Possible next step

A background monitor that **texts or emails you the moment a specific target date
opens** (e.g. "alert me when any Saturday in August frees up"). The API makes this
trivial — poll `occupancygrid` on a schedule and notify on `TotalAvailable > 0`.
