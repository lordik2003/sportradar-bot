import os
import urllib.parse
import urllib.request
import urllib.error


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        raise ValueError("Не настроены секреты Telegram")

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": "SportRadar запущен! Связь с Telegram работает."
    }).encode()

    request = urllib.request.Request(url, data=data)

    with urllib.request.urlopen(request, timeout=20) as response:
        print(response.read().decode())


if __name__ == "__main__":
    main()
