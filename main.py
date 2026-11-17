import os
import json
import urllib.request
import urllib.parse


def get_live_matches():
    url = "https://api.opendota.com/api/live"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "SportRadar/1.0"}
    )

    with urllib.request.urlopen(request, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def send_telegram(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        raise ValueError("Не настроены секреты Telegram")

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": message
    }).encode()

    request = urllib.request.Request(url, data=data)

    with urllib.request.urlopen(request, timeout=20) as response:
        result = json.loads(response.read().decode("utf-8"))

    if not result.get("ok"):
        raise RuntimeError("Ошибка отправки Telegram")


def get_team_name(match, side):
    team = match.get(f"{side}_team")

    if isinstance(team, dict):
        return team.get("name") or team.get("tag") or side.capitalize()

    return match.get(f"{side}_name") or side.capitalize()


def main():
    matches = get_live_matches()

    if not isinstance(matches, list):
        raise ValueError("Ошибка получения матчей")

    lines = [
        "SportRadar | Dota 2",
        "",
        f"Активных матчей: {len(matches)}",
        ""
    ]

    if not matches:
        lines.append("Сейчас активных матчей нет.")

    for match in matches[:8]:
        radiant = get_team_name(match, "radiant")
        dire = get_team_name(match, "dire")

        match_id = match.get("match_id", "нет данных")
        league = match.get("league_name") or "Лига не указана"

        score = (
            f"{match.get('radiant_score', 0)}:"
            f"{match.get('dire_score', 0)}"
        )

        seconds = max(0, int(match.get("game_time", 0)))
        game_time = f"{seconds // 60}:{seconds % 60:02d}"

        lead = match.get("radiant_lead")
        advantage = (
            f"Преимущество Radiant: {lead} золота"
            if lead is not None
            else "Преимущество по золоту: нет данных"
        )

        players = match.get("players") or []
        names = [
            player.get("name")
            for player in players
            if isinstance(player, dict) and player.get("name")
        ]

        lines.extend([
            f"{radiant} — {dire}",
            f"Матч ID: {match_id}",
            f"Лига: {league}",
            f"Счёт: {score} | Время: {game_time}",
            advantage,
            "Игроки: " + (", ".join(names[:5]) if names else "нет данных"),
            ""
        ])

    message = "\n".join(lines)

    send_telegram(message)
    print("Проверка Dota 2 завершена.")


if __name__ == "__main__":
    main()
