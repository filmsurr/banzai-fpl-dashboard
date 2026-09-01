#!/usr/bin/env python3
"""BANZAI FPL Season 2 — clean analytics updater (v4.0).

League: 218355
Outputs: dashboard_data.js
Dependencies: Python standard library only.

Monthly penalty scoring uses OFFICIAL NET FPL points. The authoritative net GW
score is the change in total_points between Gameweeks. Raw GW points and
transfer-hit cost are retained separately for audit.
"""
from __future__ import annotations

import json
import math
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "rules_config.json"
DATA_FILE = ROOT / "dashboard_data.js"
CACHE_DIR = ROOT / ".fpl_cache"
BASE = "https://fantasy.premierleague.com/api"
USER_AGENT = "Mozilla/5.0 BANZAI-FPL-Dashboard/4.0"
REFRESH_ALL = "--refresh-all" in sys.argv


def load_config():
    cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    mapping = cfg["penalty_rules_by_gw_count"]
    cursor = 1
    normalized = []
    for raw in cfg["penalty_schedule"]:
        p = dict(raw)
        count = int(p["gw_count"])
        if str(count) not in mapping:
            raise ValueError(f"No penalty rule configured for {count} GWs")
        rule = mapping[str(count)]
        p["start_gw"] = cursor
        p["end_gw"] = cursor + count - 1
        p["penalty_teams"] = int(rule["penalty_teams"])
        p["penalty_pool_thb"] = int(rule["penalty_pool_thb"])
        normalized.append(p)
        cursor += count
    if cursor - 1 != 38:
        raise ValueError(f"Penalty schedule covers {cursor-1} GWs, expected 38")
    cfg["penalty_schedule"] = normalized
    return cfg


CONFIG = load_config()
LEAGUE_ID = int(CONFIG["league_id"])


def api_get(path: str, retries: int = 3):
    url = path if path.startswith("http") else BASE + path
    last = None
    for attempt in range(1, retries + 1):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urlopen(req, timeout=30) as res:
                return json.loads(res.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
            if attempt < retries:
                time.sleep(1.0 * attempt)
    raise RuntimeError(f"FPL API request failed: {url} — {last}")


def cached_get(path: str, name: str):
    CACHE_DIR.mkdir(exist_ok=True)
    f = CACHE_DIR / name
    if f.exists() and not REFRESH_ALL:
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    data = api_get(path)
    f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def get_bootstrap():
    data = api_get("/bootstrap-static/")
    names = {p["id"]: p.get("web_name") or f"Player {p['id']}" for p in data.get("elements", [])}
    events = data.get("events", [])
    finalized = [
        e["id"] for e in events
        if e.get("finished") and (e.get("data_checked") is True or "data_checked" not in e)
    ]
    # Fallback for API seasons where data_checked is absent/lagging.
    if not finalized:
        finalized = [e["id"] for e in events if e.get("finished")]
    latest = max(finalized) if finalized else 0
    processing = []
    for e in events:
        if e["id"] > latest and (e.get("is_current") or e.get("finished") or e.get("is_next")):
            processing.append({
                "gw": e["id"], "name": e.get("name"), "finished": bool(e.get("finished")),
                "data_checked": e.get("data_checked"), "is_current": bool(e.get("is_current")),
            })
    return names, latest, processing


def get_league():
    page = 1
    all_rows = []
    meta = None
    while True:
        data = api_get(f"/leagues-classic/{LEAGUE_ID}/standings/?page_standings={page}")
        if meta is None:
            meta = data.get("league", {})
        standings = data.get("standings", {})
        all_rows.extend(standings.get("results", []))
        if not standings.get("has_next"):
            break
        page += 1
    if not all_rows:
        raise RuntimeError("League standings returned no managers")
    managers = []
    for r in all_rows:
        managers.append({
            "manager_id": r["entry"],
            "manager": r.get("player_name") or f"Entry {r['entry']}",
            "team": r.get("entry_name") or "",
            "league_rank": r.get("rank"),
            "league_last_rank": r.get("last_rank"),
            "league_total": r.get("total"),
            "league_gw_points": r.get("event_total"),
        })
    managers.sort(key=lambda m: (m.get("league_rank") or 9999, m["manager"]))
    return meta or {}, managers


def get_histories(managers, latest_gw):
    rows = []
    for i, m in enumerate(managers, start=1):
        print(f"[History {i}/{len(managers)}] {m['manager']}")
        data = api_get(f"/entry/{m['manager_id']}/history/")
        previous_total = 0
        for gw in sorted(data.get("current", []), key=lambda x: x.get("event", 0)):
            event = int(gw.get("event", 0) or 0)
            if event <= 0 or event > latest_gw:
                continue
            raw = int(gw.get("points", 0) or 0)
            transfer_cost = int(gw.get("event_transfers_cost", 0) or 0)
            total = int(gw.get("total_points", 0) or 0)
            net = total - previous_total
            expected_net = raw - transfer_cost
            adjustment = net - expected_net
            previous_total = total
            rows.append({
                "manager_id": m["manager_id"], "manager": m["manager"], "team": m["team"],
                "gw": event,
                "gw_points": raw,
                "transfer_cost": transfer_cost,
                "net_gw_points": net,
                "score_adjustment": adjustment,
                "total_points": total,
                "overall_rank": gw.get("overall_rank"),
                "team_value": round((gw.get("value") or 0) / 10, 1),
                "bank": round((gw.get("bank") or 0) / 10, 1),
                "transfers": gw.get("event_transfers", 0),
                "points_on_bench": gw.get("points_on_bench", 0),
            })
    return rows


def get_live_points(gw):
    data = cached_get(f"/event/{gw}/live/", f"live_gw_{gw}.json")
    return {x["id"]: int(x.get("stats", {}).get("total_points", 0) or 0) for x in data.get("elements", [])}


def get_captain_data(managers, latest_gw, player_names):
    rows = []
    for gw in range(1, latest_gw + 1):
        print(f"[Captain] GW{gw}")
        live = get_live_points(gw)
        for m in managers:
            mid = m["manager_id"]
            try:
                picks_data = cached_get(f"/entry/{mid}/event/{gw}/picks/", f"picks_{mid}_gw_{gw}.json")
                picks = picks_data.get("picks", [])
                multiplied = [p for p in picks if int(p.get("multiplier", 0) or 0) > 1]
                if multiplied:
                    effective = max(multiplied, key=lambda p: int(p.get("multiplier", 0) or 0))
                    source = "vice_captain" if effective.get("is_vice_captain") and not effective.get("is_captain") else "captain"
                    multiplier = int(effective.get("multiplier", 0) or 0)
                else:
                    effective = next((p for p in picks if p.get("is_captain")), None)
                    source = "captain_no_show"
                    multiplier = 0
                if not effective:
                    continue
                pid = effective["element"]
                raw = int(live.get(pid, 0) or 0)
                rows.append({
                    "manager_id": mid, "manager": m["manager"], "gw": gw,
                    "player_id": pid, "captain": player_names.get(pid, f"Player {pid}"),
                    "captain_source": source, "raw_points": raw, "multiplier": multiplier,
                    "captain_points": raw * multiplier, "chip": picks_data.get("active_chip"),
                })
            except Exception as exc:
                print(f"  Warning: captain data unavailable for {m['manager']} GW{gw}: {exc}")
    return rows


def latest_rows(history, gw):
    return {r["manager_id"]: r for r in history if r["gw"] == gw}


def ranked(managers, values, extras=None):
    out = []
    for m in managers:
        mid = m["manager_id"]
        if mid not in values:
            continue
        out.append({
            "manager_id": mid, "manager": m["manager"], "team": m["team"],
            "value": values[mid], "extra": (extras or {}).get(mid),
        })
    out.sort(key=lambda r: (r["value"], r["manager"]), reverse=True)
    for i, r in enumerate(out, 1):
        r["metric_rank"] = i
    return out


def cumulative_captain(rows, through_gw):
    totals = {}
    for r in rows:
        if r["gw"] <= through_gw:
            totals[r["manager_id"]] = totals.get(r["manager_id"], 0) + r["captain_points"]
    return totals


def best_gw(history, through_gw):
    result = {}
    for r in history:
        if r["gw"] > through_gw:
            continue
        old = result.get(r["manager_id"])
        if old is None or r["gw_points"] > old["value"]:
            result[r["manager_id"]] = {"value": r["gw_points"], "gw": r["gw"]}
    return result


def mvp_summary(history, managers, through_gw):
    counts = {m["manager_id"]: 0 for m in managers}
    history_out = []
    for gw in range(1, through_gw + 1):
        rows = [r for r in history if r["gw"] == gw]
        if not rows:
            continue
        top = max(r["gw_points"] for r in rows)
        winners = [r for r in rows if r["gw_points"] == top]
        for w in winners:
            counts[w["manager_id"]] += 1
        history_out.append({
            "gw": gw, "score": top, "shared": len(winners) > 1,
            "winners": [{"manager_id": w["manager_id"], "manager": w["manager"], "team": w["team"]} for w in winners],
        })
    return counts, history_out


def reward_object(defn, ranking, unit="pts", decimals=0):
    leader = ranking[0] if ranking else None
    next_ = ranking[1] if len(ranking) > 1 else None
    gap = None if not leader or not next_ else round(leader["value"] - next_["value"], decimals)
    tie = bool(leader and next_ and leader["value"] == next_["value"])
    return {
        "key": defn["key"], "icon": defn["icon"], "title": defn["label"],
        "short_title": defn["short_label"], "definition": defn["definition"],
        "percent": defn["percent"], "amount_thb": defn["amount_thb"], "priority": defn["priority"],
        "unit": unit, "decimals": decimals, "leader": leader, "next": next_, "gap": gap,
        "tie_at_top": tie, "ranking": ranking,
    }


def allocate_prizes(rewards):
    cap = int(CONFIG["max_prizes_per_manager"])
    max_candidates = int(CONFIG["pass_down_candidates"])
    counts = {}
    names = {}
    for reward in sorted(rewards, key=lambda r: (-r["amount_thb"], r["priority"])):
        if reward["tie_at_top"] and not reward["key"].startswith("season_"):
            reward["allocation"] = {"status": "tie_pending", "winner": None, "source_rank": None, "reason": "Top metric is tied; no tiebreak rule is configured."}
            continue
        selected = None
        skipped = []
        for idx, c in enumerate(reward["ranking"][:max_candidates], 1):
            if counts.get(c["manager_id"], 0) < cap:
                selected = c
                source_rank = idx
                break
            skipped.append(c["manager"])
        if not selected:
            reward["allocation"] = {"status": "unallocated", "winner": None, "source_rank": None, "reason": f"Top {max_candidates} candidates have reached the {cap}-prize cap."}
            continue
        mid = selected["manager_id"]
        counts[mid] = counts.get(mid, 0) + 1
        names.setdefault(mid, []).append(reward["short_title"])
        if source_rank == 1:
            status, reason = "direct", "Metric leader is eligible."
        else:
            status = "pass_down"
            reason = f"Prize passed to #2 because {', '.join(skipped)} reached the {cap}-prize cap."
        reward["allocation"] = {"status": status, "winner": selected, "source_rank": source_rank, "reason": reason}
    return counts, names


def exact_split(pool, rows):
    total_gap = sum(max(0, r["gap"]) for r in rows)
    if total_gap <= 0:
        return [0] * len(rows)
    raw = [pool * max(0, r["gap"]) / total_gap for r in rows]
    base = [math.floor(x) for x in raw]
    remaining = int(pool - sum(base))
    order = sorted(range(len(rows)), key=lambda i: (raw[i] - base[i], rows[i]["gap"]), reverse=True)
    for i in order[:remaining]:
        base[i] += 1
    return base


def penalty_period(history, managers, latest_gw, period):
    if latest_gw < period["start_gw"]:
        return None
    through = min(latest_gw, period["end_gw"])
    raw = {m["manager_id"]: 0 for m in managers}
    hits = {m["manager_id"]: 0 for m in managers}
    net = {m["manager_id"]: 0 for m in managers}
    adjustments = {m["manager_id"]: 0 for m in managers}
    for r in history:
        if period["start_gw"] <= r["gw"] <= through:
            mid = r["manager_id"]
            raw[mid] += int(r["gw_points"])
            hits[mid] += int(r["transfer_cost"])
            net[mid] += int(r["net_gw_points"])
            adjustments[mid] += int(r["score_adjustment"])
    ranking = ranked(managers, net)
    for row in ranking:
        mid = row["manager_id"]
        row.update({"raw_points": raw[mid], "transfer_hits": hits[mid], "net_points": net[mid], "score_adjustment": adjustments[mid]})
    if not ranking:
        return None
    top = ranking[0]["value"]
    n = min(int(period["penalty_teams"]), len(ranking))
    bottom = sorted(ranking, key=lambda r: (r["value"], r["manager"]))[:n]
    for r in bottom:
        r["gap"] = max(0, top - r["value"])
    payments = exact_split(int(period["penalty_pool_thb"]), bottom)
    for r, pay in zip(bottom, payments):
        r["penalty_pay_thb"] = pay
        r["projected_pay_thb"] = pay
    at_risk = sorted(bottom, key=lambda r: (r["projected_pay_thb"], r["gap"]), reverse=True)
    ids = {r["manager_id"] for r in bottom}
    safe = [r for r in ranking if r["manager_id"] not in ids]
    safe_line = min(safe, key=lambda r: r["value"]) if safe else None
    for r in at_risk:
        r["points_to_safety"] = None if safe_line is None else max(0, safe_line["value"] - r["value"] + 1)
    projected = latest_gw < period["end_gw"]
    return {
        "month": period["month"], "year": period["year"], "label": f"{period['month']} {period['year']}",
        "start_gw": period["start_gw"], "end_gw": period["end_gw"], "gw_count": period["gw_count"],
        "gw_completed": through - period["start_gw"] + 1,
        "penalty_pool_thb": period["penalty_pool_thb"], "penalty_teams": n,
        "projected": projected, "finalized": not projected, "status_label": "PROJECTED" if projected else "FINAL",
        "top_score": top, "top_names": [r["manager"] for r in ranking if r["value"] == top],
        "at_risk": at_risk, "safe_line": safe_line, "monthly_ranking": ranking,
        "score_basis": "Official net FPL GW points after transfer-hit deductions",
        "formula": "Penalty = monthly pool × player gap ÷ total gap of penalized teams",
    }


def penalty_system(history, managers, latest_gw):
    periods, finalized, current = [], [], None
    for p in CONFIG["penalty_schedule"]:
        calc = penalty_period(history, managers, latest_gw, p)
        if not calc:
            continue
        periods.append(calc)
        if calc["finalized"]:
            finalized.append(calc)
        if p["start_gw"] <= latest_gw <= p["end_gw"]:
            current = calc
    summary = {m["manager_id"]: {"manager_id":m["manager_id"],"manager":m["manager"],"team":m["team"],"times_penalized":0,"total_penalty_thb":0,"months":[],"current_projected_thb":0,"current_risk":False} for m in managers}
    for p in finalized:
        for r in p["at_risk"]:
            s = summary[r["manager_id"]]
            s["times_penalized"] += 1
            s["total_penalty_thb"] += r["penalty_pay_thb"]
            s["months"].append({"month":p["month"],"year":p["year"],"pay_thb":r["penalty_pay_thb"]})
    if current and current["projected"]:
        for r in current["at_risk"]:
            s = summary[r["manager_id"]]
            s["current_projected_thb"] = r["projected_pay_thb"]
            s["current_risk"] = True
    rows = list(summary.values())
    for r in rows:
        r["projected_total_thb"] = r["total_penalty_thb"] + r["current_projected_thb"]
    rows.sort(key=lambda r:(r["total_penalty_thb"],r["times_penalized"],r["current_projected_thb"],r["manager"]), reverse=True)
    for i,r in enumerate(rows,1): r["penalty_rank"] = i
    target = int(CONFIG["total_prize_target_thb"])
    collected = sum(int(p["penalty_pool_thb"]) for p in finalized)
    projected_pool = int(current["penalty_pool_thb"]) if current and current["projected"] else 0
    return {
        "current": current, "periods": periods, "finalized_periods": finalized, "manager_summary": rows,
        "pool": {"collected_thb":collected,"projected_current_month_thb":projected_pool,"projected_after_current_thb":collected+projected_pool,"target_thb":target,"remaining_thb":max(0,target-collected),"progress_pct":round(collected/target*100,1) if target else 0},
    }


def build_dashboard(meta, managers, history, captain_rows, latest_gw, processing):
    current = latest_rows(history, latest_gw)
    previous = latest_rows(history, latest_gw - 1)
    manager_by_id = {m["manager_id"]:m for m in managers}

    # Official league ordering/rank movement from league standings endpoint.
    standings_base = sorted(managers, key=lambda m:(m.get("league_rank") or 9999,m["manager"]))
    season_ranking = []
    for m in standings_base:
        h = current.get(m["manager_id"])
        if not h: continue
        season_ranking.append({"manager_id":m["manager_id"],"manager":m["manager"],"team":m["team"],"value":h["total_points"],"extra":f"League #{m.get('league_rank')}","metric_rank":m.get("league_rank")})

    captain_now = cumulative_captain(captain_rows, latest_gw)
    best_now_data = best_gw(history, latest_gw)
    best_now = {mid:v["value"] for mid,v in best_now_data.items()}
    best_extra = {mid:f"GW{v['gw']}" for mid,v in best_now_data.items()}
    value_now = {mid:r["team_value"] for mid,r in current.items()}
    mvp_now, mvp_history = mvp_summary(history, managers, latest_gw)

    def season_candidates(start):
        out = season_ranking[start:]
        for i,r in enumerate(out,1): r = r
        return out

    defs = {p["key"]:p for p in CONFIG["prizes"]}
    rewards = [
        reward_object(defs["season_1"], season_candidates(0)),
        reward_object(defs["season_2"], season_candidates(1)),
        reward_object(defs["season_3"], season_candidates(2)),
        reward_object(defs["gw_mvp"], ranked(managers, mvp_now), unit="MVPs"),
        reward_object(defs["team_value"], ranked(managers, value_now), unit="£m", decimals=1),
        reward_object(defs["captain"], ranked(managers, captain_now)),
        reward_object(defs["highest_gw"], ranked(managers, best_now, best_extra)),
    ]
    prize_counts, prize_names = allocate_prizes(rewards)
    penalties = penalty_system(history, managers, latest_gw)
    penalty_by_id = {r["manager_id"]:r for r in penalties["manager_summary"]}
    latest_captain = {r["manager_id"]:r for r in captain_rows if r["gw"] == latest_gw}

    scoreboard = []
    leader_total = season_ranking[0]["value"] if season_ranking else 0
    for m in standings_base:
        mid = m["manager_id"]
        h = current.get(mid)
        if not h: continue
        b = best_now_data.get(mid,{})
        p = penalty_by_id.get(mid,{})
        lc = latest_captain.get(mid,{})
        rank = int(m.get("league_rank") or 9999)
        last_rank = m.get("league_last_rank")
        rank_change = None if last_rank is None else int(last_rank) - rank
        scoreboard.append({
            "rank":rank,"last_rank":last_rank,"rank_change":rank_change,"manager_id":mid,"manager":m["manager"],"team":m["team"],
            "gw_points":h["gw_points"],"net_gw_points":h["net_gw_points"],"transfer_cost":h["transfer_cost"],"total_points":h["total_points"],"gap_to_leader":leader_total-h["total_points"],
            "captain_points":captain_now.get(mid,0),"latest_captain":lc.get("captain"),"latest_captain_points":lc.get("captain_points"),"latest_captain_raw_points":lc.get("raw_points"),"latest_captain_multiplier":lc.get("multiplier"),
            "gw_mvp_wins":mvp_now.get(mid,0),"best_gw_points":b.get("value"),"best_gw":b.get("gw"),"team_value":h["team_value"],
            "prize_count":prize_counts.get(mid,0),"prizes":prize_names.get(mid,[]),"prize_cap_reached":prize_counts.get(mid,0)>=int(CONFIG["max_prizes_per_manager"]),
            "times_penalized":p.get("times_penalized",0),"total_penalty_thb":p.get("total_penalty_thb",0),"current_projected_penalty_thb":p.get("current_projected_thb",0),"projected_total_penalty_thb":p.get("projected_total_thb",0),
        })
    scoreboard.sort(key=lambda r:r["rank"])

    projected_prizes=[]
    for r in sorted(rewards,key=lambda x:x["priority"]):
        a=r.get("allocation") or {}
        projected_prizes.append({"key":r["key"],"icon":r["icon"],"title":r["short_title"],"amount_thb":r["amount_thb"],"metric_leader":r.get("leader"),"projected_owner":a.get("winner"),"allocation_status":a.get("status"),"allocation_reason":a.get("reason")})

    prize_total = sum(int(p["amount_thb"]) for p in CONFIG["prizes"])
    penalty_schedule_total = sum(int(p["penalty_pool_thb"]) for p in CONFIG["penalty_schedule"])
    return {
        "status":"ok","version":"4.0","brand_name":CONFIG["brand_name"],"season":CONFIG["season"],
        "league":{"id":LEAGUE_ID,"name":meta.get("name") or CONFIG["brand_name"]},
        "latest_gw":latest_gw,"processing_events":processing,"manager_count":len(managers),
        "total_pot_thb":CONFIG["total_prize_target_thb"],"max_prizes_per_manager":CONFIG["max_prizes_per_manager"],
        "rewards":rewards,"projected_prizes":projected_prizes,"standings":scoreboard,"season_top3":scoreboard[:3],
        "weekly_mvp_history":mvp_history,"penalty_system":penalties,"penalty_schedule":CONFIG["penalty_schedule"],
        "pool_status":penalties["pool"],
        "rules_audit":{"prize_total_thb":prize_total,"penalty_schedule_total_thb":penalty_schedule_total,"penalty_vs_prize_variance_thb":penalty_schedule_total-prize_total,"penalty_score_basis":"Official net total_points delta; transfer hits shown separately"},
        "updated_at":datetime.now(timezone.utc).isoformat(),
    }


def parse_existing_data():
    if not DATA_FILE.exists(): return None
    try:
        text=DATA_FILE.read_text(encoding="utf-8")
        m=re.search(r"window\.FPL_DASHBOARD_DATA\s*=\s*(\{.*\})\s*;?\s*$",text,re.S)
        return json.loads(m.group(1)) if m else None
    except Exception:
        return None


def canonical_without_timestamp(data):
    if data is None: return None
    copy=json.loads(json.dumps(data,ensure_ascii=False))
    copy.pop("updated_at",None)
    return copy


def write_data(data):
    existing=parse_existing_data()
    if canonical_without_timestamp(existing)==canonical_without_timestamp(data):
        print("NO CHANGE: dashboard data is already current.")
        return False
    DATA_FILE.write_text("window.FPL_DASHBOARD_DATA = "+json.dumps(data,ensure_ascii=False,separators=(",",":"))+";\n",encoding="utf-8")
    return True


def main():
    print("="*70)
    print(f"{CONFIG['brand_name']} — CLEAN DASHBOARD UPDATE v4.0")
    print(f"League ID: {LEAGUE_ID}")
    print("="*70)
    try:
        player_names, latest_gw, processing = get_bootstrap()
        if latest_gw <= 0:
            raise RuntimeError("No finalized Gameweek is available yet")
        meta, managers = get_league()
        print(f"League: {meta.get('name', LEAGUE_ID)} | Managers: {len(managers)} | Latest finalized: GW{latest_gw}")
        if processing:
            print("FPL processing status:", ", ".join(f"GW{x['gw']}" for x in processing))
        history = get_histories(managers, latest_gw)
        captain_rows = get_captain_data(managers, latest_gw, player_names)
        data = build_dashboard(meta, managers, history, captain_rows, latest_gw, processing)
        changed = write_data(data)
        print("SUCCESS:", "dashboard_data.js updated" if changed else "no dashboard change required")
        return 0
    except Exception as exc:
        print("ERROR:", exc)
        # Preserve the last good live dashboard_data.js if one already exists.
        if not DATA_FILE.exists():
            fallback={"status":"error","version":"4.0","brand_name":CONFIG["brand_name"],"season":CONFIG["season"],"league":{"id":LEAGUE_ID,"name":CONFIG["brand_name"]},"error":str(exc),"updated_at":datetime.now(timezone.utc).isoformat()}
            DATA_FILE.write_text("window.FPL_DASHBOARD_DATA = "+json.dumps(fallback,ensure_ascii=False)+";\n",encoding="utf-8")
        return 1


if __name__ == "__main__":
    sys.exit(main())
