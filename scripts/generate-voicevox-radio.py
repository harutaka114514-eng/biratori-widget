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
    url = "https://api.open-meteo.com/v1/forecast?latitude=42.58&longitude=142.13&current_weather=true&timezone=Asia%2FTokyo"
    with urllib.request.urlopen(url, timeout=20) as response:
        current = json.load(response)["current_weather"]
    temp = float(current["temperature"])
    weather_text = f"平取の気温は{temp}度です。この天気は音声作成時の情報です。"
except Exception:
    pass
texts = [f"こんにちは。今日の平取ラジオです。{weather_text} 北海道朝刊をお届けします。ニュースは{stamp.month}月{stamp.day}日、{stamp.hour}時{stamp.minute}分時点の情報です。"]
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
        params = urllib.parse.urlencode({"text": text, "speaker": 3})
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
    with wave.open(combined, "wb") as out:
        out.setparams(params)
        for path in paths:
            with wave.open(path, "rb") as part:
                if part.getparams()[:3] != params[:3] or part.getparams()[4:] != params[4:]:
                    raise SystemExit("音声形式が一致しません")
                out.writeframes(part.readframes(part.getnframes()))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", combined, "-codec:a", "libmp3lame", "-b:a", "64k", "data/morning-radio.mp3"], check=True)
with open("data/morning-radio.json", "w", encoding="utf-8") as f:
    json.dump({"updatedAt": data["updatedAt"], "voice": "VOICEVOX:ずんだもん", "generatedAt": now.isoformat(), "audio": "morning-radio.mp3"}, f, ensure_ascii=False, indent=2)
