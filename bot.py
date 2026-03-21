import os
from datetime import date
from typing import Any, Dict, List, Optional

import redis
import requests


WB_URL = "https://common-api.wildberries.ru/api/communications/v2/news"
LAST_ID_KEY = "wb_news:last_id"
REQUEST_TIMEOUT = 30
MAX_NEWS_PER_RUN = 10


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} not set")
    return value


WB_TOKEN = require_env("WB_TOKEN")
TG_BOT_TOKEN = require_env("TG_BOT_TOKEN")
TG_CHAT_ID = require_env("TG_CHAT_ID")
REDIS_URL = require_env("REDIS_URL")


def get_redis_client() -> redis.Redis:
    return redis.from_url(REDIS_URL, decode_responses=True)


def get_last_id(rdb: redis.Redis) -> Optional[int]:
    value = rdb.get(LAST_ID_KEY)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def set_last_id(rdb: redis.Redis, news_id: int) -> None:
    rdb.set(LAST_ID_KEY, news_id)


def get_wb_news_by_date(from_date: str) -> List[Dict[str, Any]]:
    headers = {"Authorization": WB_TOKEN}
    params = {"from": from_date}

    response = requests.get(WB_URL, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    payload = response.json()
    if payload.get("error"):
        raise RuntimeError(f"WB API error: {payload}")

    return payload.get("data", [])


def get_wb_news_by_from_id(from_id: int) -> List[Dict[str, Any]]:
    headers = {"Authorization": WB_TOKEN}
    params = {"fromID": from_id}

    response = requests.get(WB_URL, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
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

    response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()


def escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def format_news(item: Dict[str, Any]) -> str:
    news_id = item.get("id", "")
    header = escape_html(str(item.get("header", "Без заголовка")))
    content = escape_html(str(item.get("content", "")))
    news_date = escape_html(str(item.get("date", "")))

    if len(content) > 3000:
        content = content[:3000] + "..."

    return (
        f"<b>{header}</b>\n\n"
        f"{content}\n\n"
        f"📅 {news_date}\n"
        f"🆔 {news_id}"
    )


def bootstrap_last_id(rdb: redis.Redis) -> None:
    today = date.today().isoformat()
    items = get_wb_news_by_date(today)

    if not items:
        print("Bootstrap: новостей за сегодня нет, last_id не установлен")
        return

    max_id = max(int(item.get("id", 0)) for item in items)
    set_last_id(rdb, max_id)
    print(f"Bootstrap complete. last_id={max_id}")


def get_new_items(rdb: redis.Redis) -> List[Dict[str, Any]]:
    last_id = get_last_id(rdb)

    if last_id is None:
        bootstrap_last_id(rdb)
        return []

    items = get_wb_news_by_from_id(last_id)
    if not items:
        return []

    normalized: List[Dict[str, Any]] = []
    for item in items:
        try:
            item_id = int(item.get("id", 0))
        except (TypeError, ValueError):
            continue

        if item_id > last_id:
            normalized.append(item)

    normalized.sort(key=lambda x: int(x.get("id", 0)))
    return normalized


def main() -> None:
    print("WB news check started")
    rdb = get_redis_client()

    items = get_new_items(rdb)
    if not items:
        print("Новых новостей нет")
        return

    items_to_send = items[:MAX_NEWS_PER_RUN]
    print(f"Найдено новых новостей: {len(items)}. Отправим: {len(items_to_send)}")

    max_sent_id = get_last_id(rdb) or 0

    for item in items_to_send:
        item_id = int(item["id"])
        message = format_news(item)
        send_telegram_message(message)
        print(f"Отправлена новость ID={item_id}")

        if item_id > max_sent_id:
            max_sent_id = item_id

    set_last_id(rdb, max_sent_id)
    print(f"Updated last_id={max_sent_id}")
    print("Done")


if __name__ == "__main__":
    main()
