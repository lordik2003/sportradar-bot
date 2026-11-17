import os
import json
import urllib.request
import urllib.parse

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

TIER1_TEAMS = [
    "Team Yandex",
    "PARIVISION",
    "Team Spirit",
    "Aurora Gaming",
    "BetBoom Team",
    "Team Liquid",
    "Natus Vincere",
    "Xtreme Gaming",
    "GamerLegion",
    "LGD Gaming",
    "OG",
    "PlayTime",
    "Yellow Submarine",
    "1w Team",
    "MOUZ",
    "Huligani",
    "Yakult Brothers",
    "Team Nemesis",
    "Zero Tenacity",
    "Pipsqueak+4",
]

def get_json(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "SportRadar"}
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))

def normalize(value):
    return str(value or "").lower().replace(" ", "").replace("-", "").replace("_", "")

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": message
    }).encode()

    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=30) as response:
        response.read()

def main():
    teams = get_json("https://api.opendota.com/api/teams")
    matches = get_json("https://api.opendota.com/api/live")

    recognized = {}

    for official_name in TIER1_TEAMS:
        target = normalize(official_name)

        for team in teams:
            name = normalize(team.get("name"))
            tag = normalize(team.get("tag"))

            if target == name or target == tag:
                recognized[official_name] = team
                break

    lines = [
        "🔴 SPORT RADAR",
        "",
        "🎮 DOTA 2 | ДИАГНОСТИКА",
        "",
        f"🏅 Распознано команд: {len(recognized)}/20",
        "",
        "СПИСОК РАСПОЗНАННЫХ:"
    ]

    for name, team in recognized.items():
        lines.append(f"✅ {name} | ID: {team.get('team_id')}")

    missing = [name for name in TIER1_TEAMS if name not in recognized]

    lines += [
        "",
        "НЕ РАСПОЗНАНЫ:",
        ", ".join(missing) if missing else "Нет",
        "",
        f"🌐 Активных матчей: {len(matches)}",
        "",
        "ПОЛЯ ПЕРВЫХ 3 МАТЧЕЙ:"
    ]

    for index, match in enumerate(matches[:3], 1):
        lines.append("")
        lines.append(f"Матч {index}:")

        for key, value in match.items():
            if any(word in key.lower() for word in [
                "team", "name", "id", "league"
            ]):
                if isinstance(value, (str, int, float, bool)) or value is None:
                    lines.append(f"{key}: {value}")

    message = "\n".join(lines)

    if len(message) > 3900:
        message = message[:3900]

    send_telegram(message)

if __name__ == "__main__":
    main()
