
import os
import json
import html
import urllib.request
import urllib.parse

API = "https://api.opendota.com/api"

# Наш предварительный список Tier 1
TIER1_TEAMS = {
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
    "PlayTime": ["PlayTime"],
    "Yellow Submarine": ["Yellow Submarine", "YeS"],
    "1w Team": ["1w Team", "1w"],
    "MOUZ": ["MOUZ"],
    "Huligani": ["Huligani"],
    "Yakult Brothers": ["Yakult Brothers", "YkBros"],
    "Team Nemesis": ["Team Nemesis", "Nemesis"],
    "Zero Tenacity": ["Zero Tenacity", "Z10"],
    "Pipsqueak+4": ["Pipsqueak+4", "Pips+4"],
}


def normalize(value):
    return "".join(
        c.lower() for c in str(value or "") if c.isalnum()
    )


def api_get(path):
    request = urllib.request.Request(
        API + path,
        headers={"User-Agent": "SportRadar/1.0"}
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def get_team_directory():
    teams = api_get("/teams")

    aliases = {}
    for official, names in TIER1_TEAMS.items():
        for name in names:
            aliases[normalize(name)] = official

    result = {}

    for team in teams:
        if not isinstance(team, dict):
            continue

        team_id = team.get("team_id")
        if not team_id:
            continue

        for value in (team.get("name"), team.get("tag")):
            official = aliases.get(normalize(value))

            if official:
                result[int(team_id)] = official
                break

    return result


def get_live_matches():
    matches = api_get("/live")

    if not isinstance(matches, list):
        raise ValueError("Ошибка получения матчей")

    return matches


def get_team(match, side, directory):
    team_id = match.get(side + "_team_id")

    if team_id:
        try:
            return directory.get(int(team_id))
        except (TypeError, ValueError):
            pass

    return None


def format_gold(lead):
    if lead is None:
        return "Нет данных о золоте"

    if lead > 0:
        return "Radiant впереди на " + format(lead, ",").replace(",", " ") + " золота"

    if lead < 0:
        return "Dire впереди на " + format(abs(lead), ",").replace(",", " ") + " золота"

    return "Равенство по золоту"


def format_match(match, radiant, dire):
    score = (
        str(match.get("radiant_score", 0))
        + ":"
        + str(match.get("dire_score", 0))
    )

    seconds = max(0, int(match.get("game_time", 0)))
    game_time = f"{seconds // 60:02d}:{seconds % 60:02d}"

    league = html.escape(
        str(match.get("league_name") or "Турнир не указан")
    )

    match_id = html.escape(str(match.get("match_id", "—")))

    return (
        "⚔️ <b>" + html.escape(radiant)
        + " — " + html.escape(dire) + "</b>\n"
        "🏆 " + league + "\n"
        "📊 Счёт: <b>" + score + "</b>\n"
        "⏱ Время: " + game_time + "\n"
        "💰 " + html.escape(
            format_gold(match.get("radiant_lead"))
        ) + "\n"
        "🆔 Матч: <code>" + match_id + "</code>"
    )


def send_telegram(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        raise ValueError("Не настроены секреты Telegram")

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true"
    }).encode()

    request = urllib.request.Request(url, data=data)

    with urllib.request.urlopen(request, timeout=20) as response:
        result = json.loads(response.read().decode("utf-8"))

    if not result.get("ok"):
        raise RuntimeError("Ошибка отправки Telegram")


def main():
    directory = get_team_directory()
    matches = get_live_matches()

    tier_matches = []

    for match in matches:
        radiant = get_team(match, "radiant", directory)
        dire = get_team(match, "dire", directory)

        # Обе команды должны быть из нашего списка.
        if radiant and dire:
            tier_matches.append((match, radiant, dire))

    header = (
        "🔴 <b>SPORT RADAR</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🎮 <b>DOTA 2 | TIER 1</b>\n"
        "🏅 Команд распознано: "
        + str(len(directory)) + "/20\n"
        "🌐 Активных матчей: "
        + str(len(matches)) + "\n"
        "🎯 Матчей Tier 1: "
        + str(len(tier_matches)) + "\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
    )

    if not tier_matches:
        message = header + (
            "😴 <b>Матчей между командами Tier 1 сейчас нет.</b>\n\n"
            "Следующая проверка примерно через час."
        )
    else:
        cards = []

        for match, radiant, dire in tier_matches[:8]:
            cards.append(format_match(match, radiant, dire))

        message = header + "\n\n━━━━━━━━━━━━━━━━━━\n\n".join(cards)

        if len(tier_matches) > 8:
            message += (
                "\n\n━━━━━━━━━━━━━━━━━━\n"
                "Ещё матчей: " + str(len(tier_matches) - 8)
            )

    send_telegram(message)

    print(
        "Dota 2: найдено матчей Tier 1:",
        len(tier_matches)
    )


if __name__ == "__main__":
    main()
