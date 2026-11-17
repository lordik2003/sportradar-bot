import os
import json
import urllib.request
import urllib.parse
import urllib.error


def get_live_matches():
    url = "https://api.opendota.com/api/live"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "SportRadar/1.0"}
    )

    with urllib.request.urlopen(request, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def format_time(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def send_telegram(text):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        raise ValueError("Не настроены секреты Telegram")

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text
    }).encode()

    request = urllib.request.Request(url, data=data)

    with urllib.request.urlopen(request, timeout=20) as response:
        result = json.loads(response.read().decode("utf-8"))

    if not result.get("ok"):
        raise RuntimeError("Telegram не принял сообщение")


def main():
    matches = get_live_matches()

    if not isinstance(matches, list):
        raise ValueError("Неожиданный формат данных OpenDota")

    if not matches:
        message = "SportRadar — Dota 2\n\nСейчас активных матчей в источнике нет."
    else:
        lines = [
            "SportRadar — Dota 2",
            "",
            f"Найдено матчей: {len(matches)}",
            ""
        ]

        for match in matches[:8]:
            radiant = match.get("radiant_name") or "Radiant"
            dire = match.get("dire_name") or "Dire"

            score = (
                f"{match.get('radiant_score', 0)}:"
                f"{match.get('dire_score', 0)}"
            )

            game_time = format_time(
                match.get("game_time", match.get("game_time_seconds", 0))
            )

            lines.extend([
                f"{radiant} — {dire}",
                f"Счёт: {score} | Время: {game_time}",
                f"Зрители: {match.get('spectators', 0)}",
                ""
            ])

        message = "\n".join(lines)

    send_telegram(message)
    print("Проверка Dota 2 завершена успешно.")


if __name__ == "__main__":
    main()
