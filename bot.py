import os
import json
import requests
from datetime import date

STATE_FILE = "state.json"

WB_URL = "https://common-api.wildberries.ru/api/communications/v2/news"

WB_TOKEN = os.getenv("WB_TOKEN")
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")


def load_state():
    if not os.path.exists(STATE_FILE):
        return {"last_id": None}
    with open(STATE_FILE, "r") as f:
        return json.load(f)


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def get_news(params):
    headers = {"Authorization": WB_TOKEN}
    r = requests.get(WB_URL, headers=headers, params=params)
    r.raise_for_status()
    return r.json().get("data", [])


def send_tg(text):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": TG_CHAT_ID,
        "text": text[:4000],
    })


def main():
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

    new_items = [n for n in news if not last_id or n["id"] > last_id]
    new_items.sort(key=lambda x: x["id"])

    for item in new_items:
        text = f"{item['header']}\n\n{item['content'][:3000]}"
        send_tg(text)
        print("Отправлено:", item["id"])
        last_id = item["id"]

    state["last_id"] = last_id
    save_state(state)


if __name__ == "__main__":
    main()
