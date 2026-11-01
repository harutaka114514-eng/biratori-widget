import json, os, time, urllib.request, urllib.parse, subprocess, wave, tempfile, random
from datetime import datetime, timedelta
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
    url = "https://api.open-meteo.com/v1/forecast?latitude=42.58&longitude=142.13&current_weather=true&hourly=temperature_2m,weathercode,precipitation_probability,precipitation,wind_speed_10m,wind_gusts_10m&wind_speed_unit=ms&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=Asia%2FTokyo"
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
    hourly = forecast.get("hourly", {})
    points = []
    for index, value in enumerate(hourly.get("time", [])):
        try:
            when = datetime.fromisoformat(value).replace(tzinfo=ZoneInfo("Asia/Tokyo"))
            if now <= when <= now + timedelta(hours=24):
                points.append(index)
        except (ValueError, TypeError):
            continue
    def hourly_values(name):
        values = hourly.get(name, [])
        return [values[i] for i in points if i < len(values) and isinstance(values[i], (int, float)) and not isinstance(values[i], bool)]
    temperatures = hourly_values("temperature_2m")
    codes = hourly_values("weathercode")
    probabilities = hourly_values("precipitation_probability")
    precipitation = hourly_values("precipitation")
    winds = hourly_values("wind_speed_10m")
    gusts = hourly_values("wind_gusts_10m")
    notices = []
    if any(c in (95,96,97,99) for c in codes):
        notices.append("今後24時間に雷雨の予報があります。外出前に最新の気象情報を確認し、雷が聞こえたら安全な建物内に避難しましょう。")
    if any(c in (56,57,66,67) for c in codes):
        notices.append("凍る雨や霧雨の予報があります。路面が凍結するおそれがあるため、移動は慎重に。")
    if any(c in (75,86) for c in codes):
        notices.append("強い雪の予報があります。視界や道路状況を確認し、移動に余裕を持ちましょう。")
    elif any(c in (71,73,77,85) for c in codes):
        notices.append("雪の予報があります。足元と交通情報を確認し、移動には余裕を持ちましょう。")
    if winds and max(winds) >= 10 or gusts and max(gusts) >= 15:
        notices.append("風が強まる予報です。屋外の飛ばされやすい物や、運転中の横風に注意しましょう。")
    if any(c in (65,82) for c in codes) or precipitation and max(precipitation) >= 10:
        notices.append("雨が強まる予報です。冠水しやすい場所を避け、最新の気象情報を確認しましょう。")
    elif any(c in (51,53,55,61,63,80,81) for c in codes) or any(p >= 60 for p in probabilities):
        notices.append("雨の予報、または降水確率が高い時間があります。雨具を用意しておくと安心です。")
    if any(c in (45,48) for c in codes):
        notices.append("霧の予報があります。車の運転は視界に気を配り、車間距離を十分に取りましょう。")
    if temperatures and min(temperatures) <= -10:
        notices.append("厳しい冷え込みの予報です。防寒と水道の凍結防止に気を配りましょう。")
    elif temperatures and min(temperatures) <= 0:
        notices.append("氷点下の予報があります。濡れた路面などの凍結に注意してください。")
    elif temperatures and min(temperatures) <= 5:
        notices.append("冷え込みに備えて、暖かい上着があると安心です。")
    if temperatures and max(temperatures) >= 35:
        notices.append("大変厳しい暑さの予報です。無理な外出を控え、冷房とこまめな水分補給を心がけましょう。")
    elif temperatures and max(temperatures) >= 30:
        notices.append("真夏日となる予報です。水分を取り、涼しい場所で休憩しましょう。")
    elif temperatures and max(temperatures) >= 28:
        notices.append("暑さに備え、水分補給と涼しい場所での休憩を心がけましょう。")
    if temperatures and max(temperatures) - min(temperatures) >= 10:
        notices.append("気温差が大きくなる予報です。脱ぎ着しやすい服装で調整しましょう。")
    if notices:
        weather_text += " 今後24時間の予報に基づく注意です。" + "".join(notices[:4])

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
try:
    with open("data/radio-seasonal-notes.json", encoding="utf-8") as notes_file:
        notes = json.load(notes_file)
    season = "spring" if 3 <= now.month <= 5 else "summer" if 6 <= now.month <= 8 else "autumn" if 9 <= now.month <= 11 else "winter"
    options = notes["food"][now.month - 1] + notes["nature"][season] + notes["home"][season]
    title, note = random.choice(options)
    ending = f"最後に季節の小ネタです。{title}。{note} "
except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
    print(f"季節の小ネタを取得できませんでした: {error}")
    ending = ""
texts.append(ending + "以上、今日の平取ラジオでした。情報は更新されることがあります。詳しくはニュース欄をご確認ください。")
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
    chapter_titles = ["オープニング・平取の天気"] + [str(item.get("title") or f"ニュース {i}") for i, item in enumerate(items, 1)] + ["季節の小ネタ・エンディング"]
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
