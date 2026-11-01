import json, os, time, urllib.request, urllib.parse, subprocess, wave, tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

with open("data/morning-briefing.json", encoding="utf-8") as f:
    data = json.load(f)
items = data.get("items", [])
if not items:
    raise SystemExit("朝刊のニュースがありません")
stamp = datetime.fromisoformat(data["updatedAt"].replace("Z", "+00:00")).astimezone(ZoneInfo("Asia/Tokyo"))
now = datetime.now(ZoneInfo("Asia/Tokyo"))
weather_text = "平取の天気は取得できませんでした。画面の天気欄をご確認ください。"
try:
    url = "https://api.open-meteo.com/v1/forecast?latitude=42.58&longitude=142.13&current_weather=true&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=Asia%2FTokyo"
    with urllib.request.urlopen(url, timeout=20) as response:
        forecast = json.load(response)
    current = forecast["current_weather"]
    daily = forecast["daily"]
    temp = float(current["temperature"])
    code = int(current["weathercode"])
    conditions = {0:"快晴", 1:"晴れ", 2:"晴れ時々くもり", 3:"くもり", 45:"霧", 48:"霧", 51:"霧雨", 53:"霧雨", 55:"霧雨", 56:"凍る霧雨", 57:"凍る霧雨", 61:"雨", 63:"雨", 65:"強い雨", 66:"凍る雨", 67:"凍る雨", 71:"雪", 73:"雪", 75:"強い雪", 77:"雪", 80:"にわか雨", 81:"にわか雨", 82:"激しいにわか雨", 85:"にわか雪", 86:"激しいにわか雪", 95:"雷雨", 96:"ひょうを伴う雷雨", 99:"ひょうを伴う雷雨"}
    condition = conditions.get(code, "天気の種類は不明")
    high, low = daily["temperature_2m_max"][0], daily["temperature_2m_min"][0]
    rain = daily["precipitation_probability_max"][0]
    weather_text = f"平取の天気です。音声作成時の天気は{condition}、気温は{temp:g}度です。今日の予想最高気温は{high:g}度、最低気温は{low:g}度、降水確率の最大は{rain}パーセントです。天気は変わることがありますので、最新の予報もご確認ください。" 
except Exception as error:
    print(f"天気情報の取得に失敗: {error}")
print(weather_text)
weekday = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"][now.weekday()]
texts = [f"こんにちは。今日の平取ラジオです。今日は{now.year}年{now.month}月{now.day}日、{weekday}です。{weather_text} 北海道朝刊をお届けします。ニュースは{stamp.month}月{stamp.day}日、{stamp.hour}時{stamp.minute}分時点の情報です。"]
for i, item in enumerate(items, 1):
    text = f"{i}つ目のニュース。{item.get('title', '')}。{item.get('summary', '')}"
    if item.get("analysis"):
        text += " ここからは生活への影響や分析です。" + item["analysis"]
    if item.get("source"):
        text += " 情報源は、" + item["source"] + "です。"
    texts.append(text)
texts.append("以上、今日の平取ラジオでした。情報は更新されることがあります。詳しくはニュース欄をご確認ください。")
base = "http://127.0.0.1:50021"
for attempt in range(120):
    try:
        urllib.request.urlopen(base + "/version", timeout=2)
        break
    except Exception:
        time.sleep(2)
else:
    raise SystemExit("VOICEVOXエンジンが起動しませんでした")
os.makedirs("data", exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
    paths = []
    for i, text in enumerate(texts):
        params = urllib.parse.urlencode({"text": text.replace("平取", "びらとり"), "speaker": 3})
        req = urllib.request.Request(base + "/audio_query?" + params, data=b"", method="POST")
        with urllib.request.urlopen(req, timeout=120) as res:
            query = res.read()
        req = urllib.request.Request(base + "/synthesis?speaker=3", data=query, headers={"Content-Type":"application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=300) as res:
            audio = res.read()
        path = os.path.join(tmp, f"{i:03}.wav")
        with open(path, "wb") as out:
            out.write(audio)
        paths.append(path)
    combined = os.path.join(tmp, "combined.wav")
    with wave.open(paths[0], "rb") as first:
        params = first.getparams()
    chapter_titles = ["オープニング・平取の天気"] + [str(item.get("title") or f"ニュース {i}") for i, item in enumerate(items, 1)] + ["エンディング"]
    chapters = []
    frames_elapsed = 0
    with wave.open(combined, "wb") as out:
        out.setparams(params)
        for title, path in zip(chapter_titles, paths):
            with wave.open(path, "rb") as part:
                if part.getparams()[:3] != params[:3] or part.getparams()[4:] != params[4:]:
                    raise SystemExit("音声形式が一致しません")
                chapters.append({"title": title, "start": round(frames_elapsed / params.framerate, 3)})
                frames_elapsed += part.getnframes()
                out.writeframes(part.readframes(part.getnframes()))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", combined, "-codec:a", "libmp3lame", "-b:a", "64k", "data/morning-radio.mp3"], check=True)
with open("data/morning-radio.json", "w", encoding="utf-8") as f:
    json.dump({"updatedAt": data["updatedAt"], "voice": "VOICEVOX:ずんだもん", "generatedAt": now.isoformat(), "audio": "morning-radio.mp3", "chapters": chapters}, f, ensure_ascii=False, indent=2)
