import json, re, urllib.request
from pathlib import Path
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
URL = "https://roadway.yahoo.co.jp/traffic/road/3100090/list"
ICS = ["苫小牧東", "沼ノ端西", "沼ノ端東", "苫東中央", "厚真", "鵡川", "日高富川", "日高門別", "日高厚賀", "新冠"]
def parse(html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    stamp = re.search(r"(\d{1,2})月\s*(\d{1,2})日\s*(\d{1,2})時\s*(\d{1,2})分\s*現在", text)
    if not stamp: raise ValueError("source timestamp missing")
    now = datetime.now(timezone(timedelta(hours=9)))
    month, day, hour, minute = map(int, stamp.groups())
    issued = now.replace(month=month, day=day, hour=hour, minute=minute, second=0, microsecond=0)
    if issued > now + timedelta(days=1): issued = issued.replace(year=issued.year-1)
    if abs((now-issued).total_seconds()) > 3600: raise ValueError("stale source")
    items = []
    for direction in ["上り", "下り"]:
        heading = next((h for h in soup.find_all(re.compile("^h[1-6]$")) if re.fullmatch(r"日高道\s*[（(]"+direction+r"[）)]", h.get_text(strip=True))), None)
        if heading is None: raise ValueError("direction missing")
        nodes = []
        for node in heading.next_siblings:
            if getattr(node, "name", "") in ["h1","h2"]: break
            nodes.append(node)
        block = BeautifulSoup("".join(map(str,nodes)), "html.parser")
        rows = block.select("table tr")
        found = False
        for row in rows:
            cells = [c.get_text(" ",strip=True) for c in row.find_all("td")]
            if not cells: continue
            found = True
            section_cells = 2 if len(cells) >= 4 else 1
            route = " ".join(cells[:section_cells])
            positions = [ICS.index(n) for n in ICS if n in route]
            if not positions: raise ValueError("unknown section")
            if max(positions) < 1: continue
            items.append({"direction":direction,"section":route,"restriction":"／".join(cells[section_cells:])})
        if not found and "現在、通行止め・規制情報はありません。" not in block.get_text(): raise ValueError("unrecognized restrictions")
    return {"status":"ok","sourceAt":issued.isoformat(),"items":items}
if __name__ == "__main__":
    try:
        request = urllib.request.Request(URL, headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(request,timeout=30) as response: result = parse(response.read().decode("utf-8"))
    except Exception as error:
        print(type(error).__name__, str(error))
        result = {"status":"unknown","items":[],"error":str(error)}
    result.update(checkedAt=datetime.now(timezone.utc).isoformat(), source=URL)
    Path("data").mkdir(exist_ok=True)
    Path("data/hidaka-road.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
