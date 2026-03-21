import json
import os
import time
from datetime import date
from typing import Any, Dict, List, Optional

import requests

WB_TOKEN = "YOUR_WB_TOKEN"
TG_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
TG_CHAT_ID = "YOUR_CHAT_ID"

WB_URL = "https://common-api.wildberries.ru/api/communications/v2/news"
STATE_FILE = "state.json"


def load_state() -> Dict[str, Any]:
    if not os.path.exists(STATE_FILE):
        return {"last_id": None}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state: Dict[str, Any]) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_wb_news(from_date: Optional[str] = None, from_id: Optional[int] = None) -> List[Dict[str, Any]]:
    headers = {
        "Authorization": WB_TOKEN
    }

    params = {}
    if from_id is not None:
        params["fromID"] = from_id
    elif from_date is not None:
        params["from"] = from_date
    else:
        raise ValueError("Нужно передать from_date или from_id")

    response = requests.get(WB_URL, headers=headers, params=params, timeout=30)
    response.raise_for_status()

    payload = response.json()
    if payload.get("error"):
        raise RuntimeError(f"WB API error: {payload}")

    return payload.get("data", [])


def send_telegram_message(text: str) -> None:
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()


def format_news_item(item: Dict[str, Any]) -> str:
    news_id = item.get("id")
    header = item.get("header", "Без заголовка")
    content = item.get("content", "")
    news_date = item.get("date", "")

    if len(content) > 1000:
        content = content[:1000] + "..."

    return (
        f"<b>{header}</b>\n"
        f"ID: {news_id}\n"
        f"Дата: {news_date}\n\n"
        f"{content}"
    )


def bootstrap_last_id() -> int:
    today = date.today().isoformat()
    items = get_wb_news(from_date=today)

    if not items:
        return 0

    max_id = max(item.get("id", 0) for item in items)
    return max_id


def check_and_send_news() -> None:
    state = load_state()
    last_id = state.get("last_id")

    if last_id is None:
        last_id = bootstrap_last_id()
        state["last_id"] = last_id
        save_state(state)
        print(f"Инициализация завершена. last_id={last_id}")
        return

    items = get_wb_news(from_id=last_id)

    if not items:
        print("Новых новостей нет")
        return

    # На всякий случай сортируем по id
    items = sorted(items, key=lambda x: x.get("id", 0))

    max_id = last_id
    sent_count = 0

    for item in items:
        news_id = item.get("id", 0)
        if news_id <= last_id:
            continue

        text = format_news_item(item)
        send_telegram_message(text)
        sent_count += 1

        if news_id > max_id:
            max_id = news_id

        time.sleep(1)

    state["last_id"] = max_id
    save_state(state)

    print(f"Отправлено новостей: {sent_count}, новый last_id={max_id}")


if __name__ == "__main__":
    check_and_send_news()
