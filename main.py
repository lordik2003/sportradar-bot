
import os
import json
import re
import urllib.request
from datetime import datetime, timezone, timedelta

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = str(os.environ["TELEGRAM_CHAT_ID"])

BASE = "https://api.opendota.com/api"
SCHEDULE_URL = "https://dota.haglund.dev/v1/matches"
MOSCOW = timezone(timedelta(hours=3))
STATE_FILE = "state.json"

TEAMS = {
    "Team Yandex": ["Team Yandex", "Yandex"],
    "PARIVISION": ["PARIVISION", "PARI"],
    "Team Spirit": ["Team Spirit", "TSpirit"],
    "Aurora Gaming": ["Aurora Gaming", "Aurora"],
    "BetBoom Team": ["BetBoom Team", "BetBoom", "BB"],
    "Team Liquid": ["Team Liquid", "Liquid"],
    "Natus Vincere": ["Natus Vincere", "NAVI"],
    "Xtreme Gaming": ["Xtreme Gaming", "XG"],
    "GamerLegion": ["GamerLegion", "GL"],
    "LGD Gaming": ["LGD Gaming", "LGD"],
    "OG": ["OG"],
    "PlayTime": ["PlayTime", "PTime"],
    "Yellow Submarine": ["Yellow Submarine", "YeS"],
    "1w Team": ["1w Team", "1w"],
    "MOUZ": ["MOUZ"],
    "Huligani": ["Huligani", "HULI"],
    "Yakult Brothers": ["Yakult Brothers", "YkBros"],
    "Team Nemesis": ["Team Nemesis", "Nemesis", "Nem"],
    "Zero Tenacity": ["Zero Tenacity", "Z10"],
    "Pipsqueak+4": ["Pipsqueak+4", "Pips+4"],
}

KNOWN_IDS = {
    "Team Yandex": 9823272,
    "PARIVISION": 9824702,
    "Team Spirit": 7119388,
    "Aurora Gaming": 9467224,
    "BetBoom Team": 8255888,
    "Team Liquid": 2163,
    "Natus Vincere": 36,
    "Xtreme Gaming": 8261500,
    "GamerLegion": 9964962,
    "LGD Gaming": 15,
    "OG": 2586976,
    "PlayTime": 10020555,
    "Yellow Submarine": 8145157,
    "MOUZ": 161707,
    "Huligani": 10149530,
    "Team Nemesis": 9691969,
    "Pipsqueak+4": 10150633,
}

LOOKUP = {}
for official, aliases in TEAMS.items():
    for alias in aliases:
        LOOKUP[re.sub(r"[^a-z0-9]", "", alias.lower())] = official


def normalize(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def canonical(name):
    return LOOKUP.get(normalize(name))


def api(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "SportRadar/1.0"}
    )
    with urllib.request.urlopen(req, timeout=35) as response:
        return json.loads(response.read().decode("utf-8"))


def telegram(method, data):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not result.get("ok"):
        raise RuntimeError(str(result))
    return result.get("result")


def send(message, keyboard=None):
    data = {"chat_id": CHAT_ID, "text": message}
    if keyboard:
        data["reply_markup"] = {"inline_keyboard": keyboard}
    telegram("sendMessage", data)


def answer_callback(callback_id):
    try:
        telegram("answerCallbackQuery", {
            "callback_query_id": callback_id
        })
    except Exception:
        pass


def state_load():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
        state.setdefault("offset", 0)
        state.setdefault("sent", {})
        state.setdefault("matches", [])
        return state
    except Exception:
        return {"offset": 0, "sent": {}, "matches": []}


def state_save(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def main_keyboard():
    return [
        [
            {"text": "🔴 Live", "callback_data": "live"},
            {"text": "📅 Расписание", "callback_data": "schedule"}
        ],
        [
            {"text": "🏆 Команды Tier 1", "callback_data": "teams"},
            {"text": "📊 Статистика", "callback_data": "stats"}
        ]
    ]


def back_keyboard():
    return [[{
        "text": "⬅️ Главное меню",
        "callback_data": "home"
    }]]


def get_team_ids():
    result = dict(KNOWN_IDS)
    try:
        teams = api(BASE + "/teams")
        for team in teams:
            official = canonical(team.get("name")) or canonical(team.get("tag"))
            if official and team.get("team_id"):
                result[official] = team["team_id"]
    except Exception as error:
        print("Ошибка обновления ID команд:", error)
    return result


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def format_date(value):
    return value.astimezone(MOSCOW).strftime("%d.%m.%Y %H:%M МСК")


def get_schedule():
    data = api(SCHEDULE_URL)
    now = datetime.now(timezone.utc)
    result = []

    for match in data:
        pair = match.get("teams") or []
        if len(pair) != 2:
            continue

        a = canonical((pair[0] or {}).get("name"))
        b = canonical((pair[1] or {}).get("name"))

        if not a or not b or a == b:
            continue

        start = parse_date(match.get("startsAt"))
        if not start:
            continue

        if start < now - timedelta(hours=2):
            continue
        if start > now + timedelta(days=7):
            continue

        key = str(match.get("id") or match.get("hash") or "")
        if not key:
            continue

        result.append({
            "key": key,
            "a": a,
            "b": b,
            "start": start.isoformat(),
            "league": match.get("leagueName") or "Турнир не указан",
            "format": match.get("matchType") or "Формат не указан"
        })

    result.sort(key=lambda x: x["start"])
    return result


def get_live():
    data = api(BASE + "/live")
    result = []

    for match in data:
        a = canonical(match.get("team_name_radiant"))
        b = canonical(match.get("team_name_dire"))

        if not a or not b or a == b:
            continue

        result.append({
            "a": a,
            "b": b,
            "score_a": match.get("radiant_score", "?"),
            "score_b": match.get("dire_score", "?"),
            "time": match.get("game_time", 0),
            "league": match.get("league_name") or "Турнир не указан"
        })

    return result


def team_history(team_id):
    if not team_id:
        return []

    data = api(f"{BASE}/teams/{team_id}/matches")
    if not isinstance(data, list):
        return []

    data.sort(
        key=lambda x: x.get("start_time", 0),
        reverse=True
    )

    result = []

    for match in data:
        win = match.get("team_win")

        if win is None and "radiant_win" in match:
            win = match.get("radiant_win") == match.get("radiant")

        if win is None:
            continue

        result.append({
            "id": match.get("match_id"),
            "win": bool(win),
            "time": match.get("start_time", 0)
        })

        if len(result) >= 30:
            break

    return result


def win_rate(history):
    if not history:
        return None
    wins = sum(1 for item in history if item["win"])
    return (wins + 1) / (len(history) + 2)


def analyze(a, b, ids):
    id_a = ids.get(a)
    id_b = ids.get(b)

    if not id_a or not id_b:
        return "Недостаточно данных для анализа этих команд."

    try:
        hist_a = team_history(id_a)
        hist_b = team_history(id_b)
    except Exception as error:
        print("Ошибка истории:", error)
        return "Не удалось загрузить историю матчей."

    if len(hist_a) < 3 or len(hist_b) < 3:
        return (
            "Недостаточно истории для надёжного прогноза.\n"
            f"{a}: {len(hist_a)} матчей\n"
            f"{b}: {len(hist_b)} матчей\n\n"
            "🎯 Вердикт: ПРОПУСК"
        )

    rate_a = win_rate(hist_a)
    rate_b = win_rate(hist_b)

    difference = rate_a - rate_b
    p_a = max(0.30, min(0.70, 0.50 + difference * 0.55))
    p_b = 1 - p_a

    p_series_a = p_a ** 2 * (3 - 2 * p_a)
    p_series_b = 1 - p_series_a

    p_over = 2 * p_a * p_b
    p_under = 1 - p_over

    markets = [
        (f"Победа {a}", p_series_a),
        (f"Победа {b}", p_series_b),
        (f"Победа {a} на карте", p_a),
        (f"Победа {b} на карте", p_b),
        ("Тотал карт больше 2.5", p_over),
        ("Тотал карт меньше 2.5", p_under)
    ]

    best_name, best_probability = max(
        markets,
        key=lambda item: item[1]
    )

    if best_probability < 0.60 or min(len(hist_a), len(hist_b)) < 5:
        verdict = "ПРОПУСК"
    else:
        verdict = best_name

    def pct(value):
        return f"{value * 100:.1f}%"

    wins_a = sum(x["win"] for x in hist_a[:10])
    wins_b = sum(x["win"] for x in hist_b[:10])

    return "\n".join([
        f"📊 АНАЛИЗ: {a} — {b}",
        "",
        "📈 ПОСЛЕДНИЕ МАТЧИ",
        f"{a}: {wins_a}/{min(10, len(hist_a))} побед",
        f"{b}: {wins_b}/{min(10, len(hist_b))} побед",
        "",
        "🎯 ОЦЕНКА РЫНКОВ",
        f"Победа {a}: {pct(p_series_a)}",
        f"Победа {b}: {pct(p_series_b)}",
        "",
        f"Карта: {a}: {pct(p_a)}",
        f"Карта: {b}: {pct(p_b)}",
        "",
        f"Тотал больше 2.5 карт: {pct(p_over)}",
        f"Тотал меньше 2.5 карт: {pct(p_under)}",
        "",
        "🏆 ЛУЧШИЙ ВАРИАНТ ПО МОДЕЛИ",
        verdict,
        "",
        "⚠️ Это предварительная статистическая оценка.",
        "Драфт, составы и коэффициенты букмекера не учитываются.",
        "Вероятность не гарантирует выигрыш."
    ])


def show_home():
    send(
        "🔴 SPORT RADAR\n\n"
        "🎮 DOTA 2 | ГЛАВНОЕ МЕНЮ\n\n"
        "Выбери раздел:",
        main_keyboard()
    )


def show_schedule(state):
    matches = get_schedule()
    state["matches"] = matches[:10]

    if not matches:
        send(
            "📅 Предстоящих матчей Tier 1 пока не найдено.",
            back_keyboard()
        )
        return

    rows = []
    text = "📅 РАСПИСАНИЕ DOTA 2\n\n"

    for i, match in enumerate(state["matches"]):
        start = parse_date(match["start"])
        text += (
            f"{i+1}. {match['a']} — {match['b']}\n"
            f"🕒 {format_date(start)}\n"
            f"🏆 {match['league']}\n"
            f"🎮 {match['format']}\n\n"
        )
        rows.append([{
            "text": f"📊 Анализ: {match['a']} — {match['b']}",
            "callback_data": f"analyze:{i}"
        }])

    rows.append([{
        "text": "⬅️ Главное меню",
        "callback_data": "home"
    }])

    send(text[:3900], rows)


def show_live():
    matches = get_live()

    if not matches:
        send(
            "🔴 LIVE DOTA 2\n\n"
            "Пока не удалось распознать live-матчи Tier 1.\n"
            "Источник может не передавать названия команд.",
            back_keyboard()
        )
        return

    text = "🔴 LIVE DOTA 2\n\n"

    for item in matches[:10]:
        seconds = item["time"] if isinstance(item["time"], int) else 0
        clock = f"{seconds // 60:02d}:{seconds % 60:02d}"

        text += (
            f"⚔️ {item['a']} — {item['b']}\n"
            f"📊 {item['score_a']} : {item['score_b']}\n"
            f"⏱ {clock}\n"
            f"🏆 {item['league']}\n\n"
        )

    send(text[:3900], back_keyboard())


def show_teams():
    text = "🏆 КОМАНДЫ TIER 1\n\n"
    for i, name in enumerate(TEAMS, 1):
        text += f"{i}. {name}\n"
    send(text, back_keyboard())


def show_stats():
    try:
        schedule = get_schedule()
        live = get_live()

        text = (
            "📊 СТАТИСТИКА SPORT RADAR\n\n"
            f"🏅 Команд в фильтре: {len(TEAMS)}\n"
            f"📅 Матчей в расписании: {len(schedule)}\n"
            f"🔴 Распознано live-матчей: {len(live)}"
        )
    except Exception:
        text = "Не удалось обновить статистику. Попробуй позже."

    send(text, back_keyboard())


def process_update(update, state, ids):
    if "message" in update:
        message = update["message"]

        if str(message.get("chat", {}).get("id")) != CHAT_ID:
            return

        command = message.get("text", "").strip().lower()

        if command in ["/start", "/menu", "меню"]:
            show_home()
        else:
            send("Используй меню SportRadar:", main_keyboard())

    if "callback_query" in update:
        query = update["callback_query"]
        data = query.get("data", "")
        answer_callback(query["id"])

        if data == "home":
            show_home()

        elif data == "schedule":
            try:
                show_schedule(state)
            except Exception as error:
                print(error)
                send("Не удалось загрузить расписание.", back_keyboard())

        elif data == "live":
            try:
                show_live()
            except Exception as error:
                print(error)
                send("Не удалось загрузить live-данные.", back_keyboard())

        elif data == "teams":
            show_teams()

        elif data == "stats":
            show_stats()

        elif data.startswith("analyze:"):
            try:
                index = int(data.split(":")[1])
                match = state["matches"][index]
                start = parse_date(match["start"])

                result = analyze(
                    match["a"],
                    match["b"],
                    ids
                )

                send(
                    f"⚔️ {match['a']} — {match['b']}\n"
                    f"🕒 {format_date(start)}\n"
                    f"🏆 {match['league']}\n\n"
                    f"{result}",
                    back_keyboard()
                )
            except Exception as error:
                print("Ошибка анализа:", error)
                send(
                    "Не удалось построить анализ матча.",
                    back_keyboard()
                )


def main():
    state = state_load()

    try:
        ids = get_team_ids()
    except Exception:
        ids = dict(KNOWN_IDS)

    updates = telegram("getUpdates", {
        "offset": state["offset"] + 1,
        "timeout": 0,
        "allowed_updates": ["message", "callback_query"]
    })

    for update in updates:
        process_update(update, state, ids)
        state["offset"] = max(
            state["offset"],
            update["update_id"]
        )

    state_save(state)
    print("SportRadar: проверка завершена.")


if __name__ == "__main__":
    main()
