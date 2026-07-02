# Sand Harbor — proven daily release time

Detected automatically by `watch_and_apply.py` watching each pool's booking-window
edge (`FutureBookingEnds`) advance. Each event is bracketed between two 30-second
polls and corroborated by the reservation server's own `Date` header.

**Applied release time (drives the countdown): 08:00 Pacific** (earliest across pools)

| Pool | window edge | before → after | detected (PT, ±30s) | server clock | est. release |
|---|---|---|---|---|---|
| 1-day | edge | 2026-07-02 → 2026-07-03 | between 2026-07-02T07:59:45-07:00 and 2026-07-02T08:00:15-07:00 | Thu, 02 Jul 2026 15:00:15 GMT | **08:00** |
| 7-day | edge | 2026-07-08 → 2026-07-09 | between 2026-07-02T07:59:45-07:00 and 2026-07-02T08:00:15-07:00 | Thu, 02 Jul 2026 15:00:15 GMT | **08:00** |
| 30-day | edge | 2026-07-31 → 2026-08-01 | between 2026-07-02T07:59:45-07:00 and 2026-07-02T08:00:15-07:00 | Thu, 02 Jul 2026 15:00:16 GMT | **08:00** |
| 90-day | edge | 2026-09-29 → 2026-09-30 | between 2026-07-02T07:59:45-07:00 and 2026-07-02T08:00:15-07:00 | Thu, 02 Jul 2026 15:00:16 GMT | **08:00** |

New far date at detection (corroboration it became bookable, not just window-widened):
- **1-day**: 2026-07-03 → avail 66, reserved 0
- **7-day**: 2026-07-09 → avail 49, reserved 0
- **30-day**: 2026-08-01 → avail 93, reserved 0
- **90-day**: 2026-09-30 → avail 200, reserved 0

_Generated 2026-07-02T08:00:16-07:00._

