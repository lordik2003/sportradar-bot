
import os
import json
import re
import urllib.request
from datetime import datetime, timezone, timedelta

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

MOSCOW = timezone(timedelta(hours=3))
STATE_FILE = "state.json"

# Предварительный список топ-20 Tier 1.
# Короткие теги нужны для распознавания названий из разных источников.
TIER1_ALIASES = {
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


def normalize(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


TEAM_LOOKUP = {}

for official, aliases in TIER1_ALIASES.items():
    for alias in aliases:
        TEAM_LOOKUP[normalize(alias)] = official


def canonical_team(name):
    return TEAM_LOOKUP.get(normalize(name))


def get_json(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "SportRadar/1.0"}
    )

    with urllib.request.urlopen(request, timeout=40) as response:
        return json.loads(response.read().decode("utf-8"))


def send_telegram(message):
    import urllib.parse

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": message
    }).encode()

    request = urllib.request.Request(url, data=data)

    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))

    if not result.get("ok"):
        raise RuntimeError("Telegram не подтвердил отправку сообщения")


def load_state():
    if not os.path.exists(STATE_FILE):
        return {"initialized": False, "sent": {}}

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            state = json.load(file)

        if not isinstance(state.get("sent"), dict):
            state["sent"] = {}

        return state

    except Exception:
        return {"initialized": False, "sent": {}}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)


def parse_time(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except (ValueError, TypeError):
        return None


def moscow_time(value):
    return value.astimezone(MOSCOW).strftime("%d.%m.%Y в %H:%M")


def get_scheduled_matches(now):
    data = get_json("https://dota.haglund.dev/v1/matches")

    if not isinstance(data, list):
        raise RuntimeError("Неожиданный формат расписания")

    found = []
    pairs = set()

    for match in data:
        teams = match.get("teams") or []

        if len(teams) != 2:
            continue

        name_a = (teams[0] or {}).get("name")
        name_b = (teams[1] or {}).get("name")

        team_a = canonical_team(name_a)
        team_b = canonical_team(name_b)

        # Обе команды должны входить в Tier 1.
        if not team_a or not team_b or team_a == team_b:
            continue

        start = parse_time(match.get("startsAt"))

        if not start:
            continue

        # Не показываем старые матчи и слишком дальнее расписание.
        if start < now - timedelta(hours=2):
            continue

        if start > now + timedelta(days=7):
            continue

        match_key = str(
            match.get("id") or match.get("hash") or ""
        )

        if not match_key:
            continue

        pair = tuple(sorted([team_a, team_b]))
        pairs.add(pair)

        found.append({
            "key": "schedule:" + match_key,
            "start": start,
            "team_a": team_a,
            "team_b": team_b,
            "league": match.get("leagueName") or "Турнир не указан",
            "match_type": match.get("matchType") or "",
            "stream": match.get("streamUrl")
        })

    found.sort(key=lambda item: item["start"])

    return found, pairs


def get_live_matches(scheduled_pairs):
    data = get_json("https://api.opendota.com/api/live")

    if not isinstance(data, list):
        return []

    found = []

    for match in data:
        team_a = canonical_team(match.get("team_name_radiant"))
        team_b = canonical_team(match.get("team_name_dire"))

        # Если OpenDota не передала названия, матч не классифицируем.
        if not team_a or not team_b or team_a == team_b:
            continue

        pair = tuple(sorted([team_a, team_b]))

        # Не дублируем встречу, уже найденную в расписании.
        if pair in scheduled_pairs:
            continue

        match_id = match.get("match_id")

        if not match_id:
            continue

        found.append({
            "key": "live:" + str(match_id),
            "team_a": team_a,
            "team_b": team_b,
            "score_a": match.get("radiant_score", "?"),
            "score_b": match.get("dire_score", "?"),
            "game_time": match.get("game_time"),
            "league": match.get("league_name") or "Турнир не указан"
        })

    return found


def main():
    now = datetime.now(timezone.utc)
    state = load_state()
    sent = state["sent"]

    # Удаляем старые записи, чтобы файл не рос бесконечно.
    cutoff = (now - timedelta(days=30)).timestamp()

    sent = {
        key: value
        for key, value in sent.items()
        if isinstance(value, (int, float)) and value >= cutoff
    }

    scheduled, scheduled_pairs = get_scheduled_matches(now)
    live = get_live_matches(scheduled_pairs)

    new_scheduled = [
        item for item in scheduled
        if item["key"] not in sent
    ][:12]

    new_live = [
        item for item in live
        if item["key"] not in sent
    ][:8]

    lines = [
        "🔴 SPORT RADAR",
        "",
        "🎮 DOTA 2 | TIER 1",
        "",
        f"🏅 Команд в фильтре: {len(TIER1_ALIASES)}/20",
        f"📅 Матчей в расписании: {len(scheduled)}",
        f"🔥 Распознано live-матчей: {len(live)}",
        ""
    ]

    if new_live:
        lines.append("🔴 НОВЫЕ LIVE-МАТЧИ")
        lines.append("")

        for item in new_live:
            game_time = item["game_time"]

            if isinstance(game_time, (int, float)):
                minutes = int(game_time) // 60
                seconds = int(game_time) % 60
                game_clock = f"{minutes:02d}:{seconds:02d}"
            else:
                game_clock = "неизвестно"

            lines.extend([
                f"⚔️ {item['team_a']} — {item['team_b']}",
                f"📊 Счёт: {item['score_a']} : {item['score_b']}",
                f"⏱️ Время игры: {game_clock}",
                f"🏆 {item['league']}",
                ""
            ])

    if new_scheduled:
        lines.append("📅 НОВЫЕ МАТЧИ ПО РАСПИСАНИЮ")
        lines.append("")

        for item in new_scheduled:
            lines.extend([
                f"⚔️ {item['team_a']} — {item['team_b']}",
                f"🕒 {moscow_time(item['start'])} МСК",
                f"🏆 {item['league']}",
                f"🎮 {item['match_type'] or 'Формат не указан'}"
            ])

            if item["stream"]:
                lines.append(f"📺 {item['stream']}")

            lines.append("")

    if not new_live and not new_scheduled:
        if not state.get("initialized"):
            lines.extend([
                "✅ SportRadar подключён.",
                "Новые матчи Tier 1 будут приходить автоматически.",
                "",
                "Повторные уведомления об одной игре отключены."
            ])
        else:
            save_state({
                "initialized": True,
                "sent": sent
            })
            print("Новых матчей нет. Уведомления не отправлялись.")
            return

    message = "\n".join(lines)

    if len(message) > 3900:
        message = message[:3900]

    # Сначала отправляем сообщение, затем сохраняем отметки.
    send_telegram(message)

    for item in new_scheduled + new_live:
        sent[item["key"]] = now.timestamp()

    save_state({
        "initialized": True,
        "sent": sent
    })

    print("SportRadar: проверка завершена.")


if __name__ == "__main__":
    main()
