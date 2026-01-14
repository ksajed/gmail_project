import os
import hashlib
import json
import requests
from dotenv import load_dotenv

# Charge .env depuis la racine du projet
load_dotenv()

BASE = os.getenv("OVH_API_BASE_URL", "https://eu.api.ovh.com/1.0").rstrip("/")
AK = os.getenv("OVH_APP_KEY", "")
AS = os.getenv("OVH_APP_SECRET", "")
CK = os.getenv("OVH_CONSUMER_KEY", "")

def ovh_time() -> int:
    # OVH recommande d'utiliser l'heure OVH pour éviter les erreurs de timestamp
    r = requests.get(f"{BASE}/auth/time", timeout=10)
    r.raise_for_status()
    return int(r.text)

def sign(method: str, url: str, body: str, tstamp: int) -> str:
    to_sign = f"{AS}+{CK}+{method}+{url}+{body}+{tstamp}"
    sha1 = hashlib.sha1(to_sign.encode("utf-8")).hexdigest()
    return f"$1${sha1}"

def request(method: str, path: str, body=None):
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
    # Vérif minimale sans afficher les secrets
    if not AK or not AS or not CK:
        raise SystemExit("Variables OVH manquantes dans .env: OVH_APP_KEY / OVH_APP_SECRET / OVH_CONSUMER_KEY")

    services = request("GET", "/sms/")
    print("Services SMS trouvés:")
    for s in services:
        print(" -", s)
