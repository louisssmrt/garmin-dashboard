"""
build_data.py - Dump Supabase data into dashboard/data.json for the standalone HTML dashboard.

Usage :
  python build_data.py            # 90 derniers jours
  python build_data.py --days 180 # fenetre custom
"""

import os
import sys
import json
import argparse
import requests
from datetime import date, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
}


def sb_get(table, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    r = requests.get(url, headers=HEADERS, params=params or {})
    if r.status_code != 200:
        raise Exception(f"Supabase error {r.status_code}: {r.text[:300]}")
    return r.json()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=90)
    args = p.parse_args()

    today = date.today()
    since = today - timedelta(days=args.days)

    print(f"[build_data] fenetre : {since} -> {today} ({args.days} jours)")

    activities = sb_get(
        "activities",
        {
            "activity_date": f"gte.{since.isoformat()}",
            "order": "activity_date.desc,start_time.desc",
            "limit": "1000",
        },
    )
    print(f"[build_data] activities : {len(activities)}")

    metrics = sb_get(
        "daily_metrics",
        {
            "metric_date": f"gte.{since.isoformat()}",
            "order": "metric_date.desc",
            "limit": "1000",
        },
    )
    print(f"[build_data] daily_metrics : {len(metrics)}")

    payload = {
        "generated_at": f"{today.isoformat()}",
        "window_days": args.days,
        "since": since.isoformat(),
        "today": today.isoformat(),
        "activities": activities,
        "metrics": metrics,
        "goals": [
            {
                "name": "Semi-marathon",
                "date": "2026-05-31",
                "target_time": "1h30",
                "target_pace_sec_km": 4 * 60 + 16,
                "sport": "running",
            },
            {
                "name": "Trail Cote d'Opale 25 km",
                "date": "2026-09-13",
                "target_time": "Gestion",
                "target_pace_sec_km": None,
                "sport": "running",
            },
            {
                "name": "Marathon de Lille",
                "date": "2026-10-25",
                "target_time": "3h15",
                "target_pace_sec_km": 4 * 60 + 37,
                "sport": "running",
            },
            {
                "name": "10 km",
                "date": None,
                "target_time": "sub 40 min",
                "target_pace_sec_km": 3 * 60 + 59,
                "sport": "running",
            },
        ],
        "pace_zones": [
            {"name": "Recup", "pace_min": "5:45", "pace_max": "6:00", "hr": "< 140"},
            {"name": "Endurance fondamentale (Z2)", "pace_min": "5:10", "pace_max": "5:25", "hr": "145-160"},
            {"name": "Endurance haute (allure marathon)", "pace_min": "4:55", "pace_max": "5:05", "hr": "160-170"},
            {"name": "Allure spe semi 1h30", "pace_min": "4:15", "pace_max": "4:18", "hr": "170-178"},
            {"name": "Seuil", "pace_min": "3:48", "pace_max": "3:52", "hr": "180-185"},
            {"name": "VMA longue", "pace_min": "3:15", "pace_max": "3:18", "hr": "185+"},
            {"name": "VMA courte", "pace_min": "3:00", "pace_max": "3:08", "hr": "FC max"},
        ],
    }

    out = Path(__file__).resolve().parent / "data.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"[build_data] ecrit -> {out}")


if __name__ == "__main__":
    main()
