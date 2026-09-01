# BANZAI FPL Season 2 — Rules used by v4.0

## Prize pot — 5,000 THB

| Prize | Share | THB |
|---|---:|---:|
| 🏆 League 1st | 30% | 1,500 |
| 🥈 League 2nd | 20% | 1,000 |
| 🥉 League 3rd | 10% | 500 |
| ⭐ Highest GW MVP | 10% | 500 |
| 💰 Highest Team Value | 10% | 500 |
| © Total Captain Points | 10% | 500 |
| 🎯 Highest Gameweek Point | 10% | 500 |

Each manager can win **up to 2 prizes**. If a category leader has already reached the cap, the prize passes only to the category's next eligible ranking (#2 candidate). Exact top ties in special categories remain **Tie pending** unless the league defines a tiebreak.

## Highest GW MVP

Every completed GW, the manager(s) with the highest FPL GW `points` receives one MVP win. Tied top GW scores receive a shared MVP win. The season prize is led by the manager with the most MVP wins.

## Captain points

Uses the final multiplier in completed-GW picks. This handles normal captain x2, Triple Captain x3, and vice-captain promotion when FPL assigns the vice multiplier.

## Monthly penalty scoring

**Transfer hits are included.**

The authoritative penalty score is the official FPL net score calculated as the change in `total_points` from the prior GW. The dashboard separately retains:

- raw GW `points`;
- `event_transfers_cost` (-4, -8, etc.);
- any official adjustment difference;
- official net penalty score.

This ensures transfer deductions are included exactly once.

### GW count → penalty teams + monthly pool

| GWs | Teams penalized | Pool |
|---:|---:|---:|
| 2 | 2 | 265 THB |
| 3 | 3 | 395 THB |
| 4 | 3 | 530 THB |
| 5 | 4 | 660 THB |
| 6 | 5 | 790 THB |

### 2026–27 schedule

| Month | GWs | Count | Teams | Pool |
|---|---|---:|---:|---:|
| Aug 2026 | GW1–GW2 | 2 | 2 | 265 |
| Sep 2026 | GW3–GW5 | 3 | 3 | 395 |
| Oct 2026 | GW6–GW9 | 4 | 3 | 530 |
| Nov 2026 | GW10–GW12 | 3 | 3 | 395 |
| Dec 2026 | GW13–GW18 | 6 | 5 | 790 |
| Jan 2027 | GW19–GW23 | 5 | 4 | 660 |
| Feb 2027 | GW24–GW27 | 4 | 3 | 530 |
| Mar 2027 | GW28–GW30 | 3 | 3 | 395 |
| Apr 2027 | GW31–GW33 | 3 | 3 | 395 |
| May 2027 | GW34–GW38 | 5 | 4 | 660 |

Penalty split:

`Penalty = monthly pool × manager gap / total gap of penalized managers`

Integer THB uses largest-remainder rounding so the monthly payments sum exactly to the configured pool.

The configured penalty schedule totals **5,015 THB**, 15 THB above the 5,000 THB prize target. v4 keeps that difference visible as an audit item and does not silently change a rule.
