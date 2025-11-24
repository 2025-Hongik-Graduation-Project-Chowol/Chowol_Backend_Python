import os
import requests

PAPAGO_CLIENT_ID = os.environ.get("PAPAGO_CLIENT_ID")
PAPAGO_CLIENT_SECRET = os.environ.get("PAPAGO_CLIENT_SECRET")

def papago_translate(text, source, target):
    url = "https://papago.apigw.ntruss.com/nmt/v1/translation"

    headers = {
        "X-NCP-APIGW-API-KEY-ID": PAPAGO_CLIENT_ID,
        "X-NCP-APIGW-API-KEY": PAPAGO_CLIENT_SECRET,
    }

    data = {
        "source": source,
        "target": target,
        "text": text,
    }

    res = requests.post(url, headers=headers, data=data)

    if res.status_code != 200:
        print("Papago error:", res.text)
        return "[번역 실패]"

    return res.json()["message"]["result"]["translatedText"]
