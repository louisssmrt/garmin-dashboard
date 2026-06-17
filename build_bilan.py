"""
build_bilan.py - Construit bilan-data.json pour la page de bilan hebdo visuelle (bilan.html).

Calcule la partie MECANIQUE du bilan (KPIs, volumes, charge, metriques moy, delta S vs S-1,
seances marquantes) depuis Supabase, et liste les seances planifiees lues sur iCloud.

La partie JUGEMENT (verdict, suivi du plan conforme/ecart/pas faite, punch, a retenir, risque)
est ecrite par Claude dans un fichier bilan-narrative.json a la racine du dashboard, et
fusionnee ici. Si le fichier n'existe pas, on met des placeholders.

Usage :
  python build_bilan.py --start 2026-06-12 --end 2026-06-17
  python build_bilan.py                      # par defaut : 7 derniers jours glissants
"""

import os
import sys
import json
import argparse
import requests
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY")
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}

# discipline -> couleur (alignee charte dashboard)
SPORT_META = {
    "running": ("Course", "run"),
    "treadmill_running": ("Course", "run"),
    "trail_running": ("Course", "run"),
    "road_biking": ("Velo", "bike"),
    "cycling": ("Velo", "bike"),
    "virtual_ride": ("Velo", "bike"),
    "lap_swimming": ("Natation", "swim"),
    "open_water_swimming": ("Natation", "swim"),
    "strength_training": ("Muscu", "strength"),
}


def sb_get(table, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    r = requests.get(url, headers=HEADERS, params=params or {})
    if r.status_code != 200:
        raise Exception(f"Supabase error {r.status_code}: {r.text[:300]}")
    return r.json()


def discipline(act_type):
    return SPORT_META.get(act_type, ("Autre", "other"))


def is_bike_training(a):
    """Velo > 10 km = entrainement, sinon trajet."""
    d = a.get("distance_meters") or 0
    return d >= 10000


def fmt_dur(seconds):
    if not seconds:
        return "-"
    s = int(seconds)
    h, m = s // 3600, (s % 3600) // 60
    return f"{h}h{m:02d}" if h else f"{m} min"


def fmt_pace(sec_km):
    if not sec_km:
        return None
    s = int(sec_km)
    return f"{s // 60}'{s % 60:02d}/km"


def window_stats(activities):
    """Agrege par discipline sur une fenetre d'activites."""
    agg = {}
    bike_trajets = {"count": 0, "dist_km": 0.0}
    for a in activities:
        name, color = discipline(a["activity_type"])
        if color == "bike" and not is_bike_training(a):
            bike_trajets["count"] += 1
            bike_trajets["dist_km"] += (a.get("distance_meters") or 0) / 1000
            continue
        e = agg.setdefault(name, {
            "name": name, "color": color, "count": 0,
            "dist_km": 0.0, "dur_s": 0, "load": 0.0,
        })
        e["count"] += 1
        e["dist_km"] += (a.get("distance_meters") or 0) / 1000
        e["dur_s"] += a.get("duration_seconds") or 0
        e["load"] += a.get("training_load") or 0
    return agg, bike_trajets


def avg(vals):
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 1) if vals else None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--start", type=str, default=None)
    p.add_argument("--end", type=str, default=None)
    args = p.parse_args()

    today = date.today()
    end = datetime.strptime(args.end, "%Y-%m-%d").date() if args.end else today
    start = datetime.strptime(args.start, "%Y-%m-%d").date() if args.start else end - timedelta(days=6)
    span = (end - start).days + 1

    # fenetre precedente de meme duree, pour le delta
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=span - 1)

    print(f"[build_bilan] fenetre : {start} -> {end} ({span}j) | precedente : {prev_start} -> {prev_end}")

    acts = sb_get("activities", {
        "activity_date": f"gte.{prev_start.isoformat()}",
        "order": "start_time.asc", "limit": "500",
    })
    cur = [a for a in acts if start.isoformat() <= a["activity_date"] <= end.isoformat()]
    prev = [a for a in acts if prev_start.isoformat() <= a["activity_date"] <= prev_end.isoformat()]

    metrics = sb_get("daily_metrics", {
        "metric_date": f"gte.{prev_start.isoformat()}",
        "order": "metric_date.asc", "limit": "200",
    })
    m_cur = [m for m in metrics if start.isoformat() <= m["metric_date"] <= end.isoformat()]
    m_prev = [m for m in metrics if prev_start.isoformat() <= m["metric_date"] <= prev_end.isoformat()]

    # --- volumes par discipline ---
    agg, bike_trajets = window_stats(cur)
    disciplines = []
    total_dur_s = 0
    total_load = 0.0
    for name in ["Course", "Velo", "Natation", "Muscu"]:
        e = agg.get(name, {"name": name, "color": SPORT_META_color(name), "count": 0, "dist_km": 0.0, "dur_s": 0, "load": 0.0})
        total_dur_s += e["dur_s"]
        total_load += e["load"]
        disciplines.append({
            "name": e["name"], "color": e["color"], "count": e["count"],
            "dist_km": round(e["dist_km"], 1), "dur": fmt_dur(e["dur_s"]),
            "dur_s": e["dur_s"], "load": round(e["load"]),
        })

    # --- jours OFF ---
    active_days = {a["activity_date"] for a in cur}
    off_days = [
        (start + timedelta(days=i)).isoformat()
        for i in range(span)
        if (start + timedelta(days=i)).isoformat() not in active_days
    ]

    # --- metriques cle ---
    def metric_block(rows):
        return {
            "readiness": avg([r.get("training_readiness_score") for r in rows]),
            "resting_hr": avg([r.get("resting_hr") for r in rows]),
            "sleep_score": avg([r.get("sleep_score") for r in rows]),
            "stress": avg([r.get("stress_avg") for r in rows]),
            "hrv_balanced": sum(1 for r in rows if r.get("hrv_status") == "BALANCED"),
            "hrv_total": len(rows),
            "bb_high": avg([r.get("body_battery_high") for r in rows]),
            "bb_low": avg([r.get("body_battery_low") for r in rows]),
            "rhr_min": min([r["resting_hr"] for r in rows if r.get("resting_hr")], default=None),
        }

    cur_m = metric_block(m_cur)
    prev_m = metric_block(m_prev)

    # --- courses : allure par seance ---
    run_sessions = []
    for a in cur:
        _, color = discipline(a["activity_type"])
        if color == "run":
            run_sessions.append({
                "date": a["activity_date"],
                "dist_km": round((a.get("distance_meters") or 0) / 1000, 2),
                "dur": fmt_dur(a.get("duration_seconds")),
                "pace": fmt_pace(a.get("avg_pace_sec_km")),
                "hr": a.get("avg_hr"),
            })

    # --- seances marquantes (charge > 100 ou TE aero > 4) ---
    marquantes = []
    for a in cur:
        load = a.get("training_load") or 0
        te = a.get("aerobic_te") or 0
        if load > 100 or te > 4:
            name, color = discipline(a["activity_type"])
            marquantes.append({
                "date": a["activity_date"], "name": name, "color": color,
                "title": a.get("title"),
                "dist_km": round((a.get("distance_meters") or 0) / 1000, 2),
                "dur": fmt_dur(a.get("duration_seconds")),
                "load": round(load), "te_aero": round(te, 1),
                "te_anaero": round(a.get("anaerobic_te") or 0, 1),
                "elev": round(a.get("elevation_gain") or 0),
                "hr": a.get("avg_hr"), "max_hr": a.get("max_hr"),
                "avg_speed": round(a.get("avg_speed_kmh") or 0, 1),
            })
    marquantes.sort(key=lambda x: -x["load"])
    marquantes = marquantes[:3]

    # --- seances planifiees iCloud ---
    planned = []
    try:
        sys.path.insert(0, str(ROOT))
        from read_calendar import get_events
        days_back = (today - start).days + 1
        events = get_events(days_forward=1, days_back=max(days_back, 1))
        for e in events:
            s = e["start"]
            d = s.date() if hasattr(s, "date") else datetime.fromisoformat(str(s)[:10]).date()
            if start <= d <= end and e["calendar"] != "Anniversaires":
                summ = e["summary"]
                low = summ.lower()
                if any(k in low for k in ["footing", "course", "velo", "vélo", "nat", "muscu", "sl ", "sortie longue", "seuil", "allure", "norveg", "norvég", "off", "strides", "vma", "sweet"]):
                    planned.append({"date": d.isoformat(), "label": summ})
    except Exception as ex:
        print(f"[build_bilan] iCloud non lu : {ex}")

    # --- narrative (ecrit par Claude) ---
    narr_path = Path(__file__).resolve().parent / "bilan-narrative.json"
    if narr_path.exists():
        narrative = json.loads(narr_path.read_text(encoding="utf-8"))
    else:
        narrative = {
            "verdict_emoji": "🟢",
            "verdict_title": "Bilan a rediger",
            "verdict_sub": "Lance Claude pour ecrire le verdict.",
            "plan_rows": [],
            "plan_summary": "",
            "highlights": [],
            "to_remember": "",
            "risk_level": "ok",
            "risk_text": "",
            "next_week": "",
        }

    fr_months = ["", "janvier", "février", "mars", "avril", "mai", "juin",
                 "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    period_label = f"{start.day} - {end.day} {fr_months[end.month]} {end.year}"

    payload = {
        "generated_at": today.isoformat(),
        "period": {"start": start.isoformat(), "end": end.isoformat(), "label": period_label, "span": span},
        "totals": {
            "sessions": len(cur),
            "dur": fmt_dur(total_dur_s),
            "dur_hours": round(total_dur_s / 3600, 1),
            "load": round(total_load),
        },
        "disciplines": disciplines,
        "bike_trajets": {"count": bike_trajets["count"], "dist_km": round(bike_trajets["dist_km"], 1)},
        "off_days": off_days,
        "metrics": cur_m,
        "metrics_prev": prev_m,
        "run_sessions": run_sessions,
        "marquantes": marquantes,
        "planned": planned,
        "narrative": narrative,
    }

    out = Path(__file__).resolve().parent / "bilan-data.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"[build_bilan] ecrit -> {out}")
    print(f"[build_bilan] {len(cur)} activites, {len(planned)} seances planifiees, {len(off_days)} jours OFF")


def SPORT_META_color(name):
    return {"Course": "run", "Velo": "bike", "Natation": "swim", "Muscu": "strength"}.get(name, "other")


if __name__ == "__main__":
    main()
