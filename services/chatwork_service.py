import os
import requests                                                                                                           


def post_message(text: str, room_id: str = None):                                                                       
    token = os.environ.get("CHATWORK_API_TOKEN", "")
    room_id = room_id or os.environ.get("CHATWORK_ROOM_ID", "")
    mention_ids = os.environ.get("CHATWORK_MENTION_IDS", "")

    mentions = "".join([f"[To:{uid.strip()}]" for uid in mention_ids.split(",") if uid.strip()])
    body = f"{mentions}\n{text}" if mentions else text

    r = requests.post(
        f"https://api.chatwork.com/v2/rooms/{room_id}/messages",
        headers={"X-ChatWorkToken": token},
        data={"body": body},
    )
    r.raise_for_status()
    return r.json()