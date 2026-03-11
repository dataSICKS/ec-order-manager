import os
import requests                                                                                                           


def post_message(text: str, channel: str = None):                                                                       
    token = os.environ.get("SLACK_BOT_TOKEN", "")
    channel = channel or os.environ.get("SLACK_CHANNEL_ID", "")

    r = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {token}"},
        json={"channel": channel, "text": text},
    )
    result = r.json()
    if not result.get("ok"):
        raise Exception(f"Slack error: {result.get('error')}")
    return result