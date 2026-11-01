#!/usr/bin/env python3
"""Update the official Japanese national holiday calendar."""
import csv
import datetime
import io
import json
from pathlib import Path
from urllib.request import Request, urlopen

URL = "https://www8.cao.go.jp/chosei/shukujitsu/syukujitsu.csv"
request = Request(URL, headers={"User-Agent": "Mozilla/5.0 biratori-widget"})
with urlopen(request, timeout=30) as response:
    raw = response.read(500_000).decode("cp932")
rows = csv.reader(io.StringIO(raw))
next(rows)
holidays = {}
for row in rows:
    if len(row) < 2 or not row[0].strip() or not row[1].strip():
        continue
    date = datetime.datetime.strptime(row[0].strip(), "%Y/%m/%d").date()
    holidays[date.isoformat()] = row[1].strip()
year = datetime.datetime.now(datetime.timezone.utc).year
if len(holidays) < 500 or not all(f"{y}-01-01" in holidays for y in (year - 1, year)):
    raise ValueError("Incomplete official holiday data; existing data retained")
path = Path("data/japanese-holidays.json")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(holidays, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
