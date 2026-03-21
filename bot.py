import os
import json
import html
from datetime import date

import requests

STATE_FILE = "state.json"
WB_URL = "https://common-api.wildberries.ru/api/communications/v2/news"

WB_TOKEN = os.getenv("WB_TOKEN")
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")


def load_state():
    if not os.path.exists(STATE_FILE):
        return {"last_id": None}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_news(params):
    headers = {"Authorization": WB_TOKEN}
    response = requests.get(WB_URL, headers=headers, params=params, timeout=30)
    response.raise_for_status()

    payload = response.json()
    if payload.get("error"):
        raise RuntimeError(payload.get("errorText", "WB API error"))

    return payload.get("data", [])


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    response = requests.post(
        url,
        json={
            "chat_id": TG_CHAT_ID,
            "text": text[:4000],
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    response.raise_for_status()


def build_message(item):
    header = html.escape(str(item.get("header", "Без заголовка")))
    content = html.escape(str(item.get("content", "")))
    news_date = str(item.get("date", ""))
    news_id = item.get("id", "")

    if len(content) > 2500:
        content = content[:2500] + "..."

    message = (
        f"🆕 <b>{header}</b>\n\n"
        f"📅 {news_date}\n"
        f"🆔 {news_id}\n\n"
        f"{content}"
    )
    return message


def main():
    if not WB_TOKEN:
        raise ValueError("WB_TOKEN not set")
    if not TG_BOT_TOKEN:
        raise ValueError("TG_BOT_TOKEN not set")
    if not TG_CHAT_ID:
        raise ValueError("TG_CHAT_ID not set")

    state = load_state()
    last_id = state.get("last_id")

    if last_id:
        news = get_news({"fromID": last_id})
    else:
        today = date.today().isoformat()
        news = get_news({"from": today})

    if not news:
        print("Нет новостей")
        return

    new_items = [item for item in news if not last_id or item.get("id", 0) > last_id]
    new_items.sort(key=lambda x: x.get("id", 0))

    if not new_items:
        print("Новых новостей нет")
        return

    for item in new_items:
        message = build_message(item)
        send_telegram(message)
        print(f"Отправлено: {item.get('id')}")
        last_id = item.get("id")

    state["last_id"] = last_id
    save_state(state)
    print(f"last_id обновлён: {last_id}")


if __name__ == "__main__":
    main()
