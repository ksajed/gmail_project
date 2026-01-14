import os, hashlib, json, requests
from dotenv import load_dotenv
load_dotenv()

BASE = os.getenv("OVH_API_BASE_URL", "https://eu.api.ovh.com/1.0").rstrip("/")
AK = os.getenv("OVH_APP_KEY", "")
AS = os.getenv("OVH_APP_SECRET", "")
CK = os.getenv("OVH_CONSUMER_KEY", "")
SERVICE = os.getenv("OVH_SMS_SERVICE_NAME", "")

def ovh_time():
    r = requests.get(f"{BASE}/auth/time", timeout=10)
    r.raise_for_status()
    return int(r.text)

def sign(method, url, body, tstamp):
    to_sign = f"{AS}+{CK}+{method}+{url}+{body}+{tstamp}"
    return "$1$" + hashlib.sha1(to_sign.encode("utf-8")).hexdigest()

def request(method, path, body=None):
    method = method.upper()
    url = f"{BASE}{path}"
    body_str = ""
    if body is not None:
        body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    tstamp = ovh_time()
    headers = {
        "Content-Type": "application/json",
        "X-Ovh-Application": AK,
        "X-Ovh-Consumer": CK,
        "X-Ovh-Timestamp": str(tstamp),
        "X-Ovh-Signature": sign(method, url, body_str, tstamp),
    }
    r = requests.request(method, url, data=(body_str if body_str else None), headers=headers, timeout=20)
    if not r.ok:
        raise SystemExit(f"Erreur OVH {r.status_code}: {r.text}")
    return r.json()

if __name__ == "__main__":
    if not (AK and AS and CK and SERVICE):
        raise SystemExit("Variables manquantes (.env): OVH_APP_KEY/SECRET/CONSUMER_KEY/OVH_SMS_SERVICE_NAME")
    senders = request("GET", f"/sms/{SERVICE}/senders")
    print("Senders:")
    for s in senders:
        print(" -", s)
