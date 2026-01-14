import hashlib
import json
import requests
from django.conf import settings


class OvhSmsBackend:
    def __init__(self):
        self.base_url = getattr(settings, "OVH_API_BASE_URL", "https://eu.api.ovh.com/1.0").rstrip("/")
        self.app_key = settings.OVH_APP_KEY
        self.app_secret = settings.OVH_APP_SECRET
        self.consumer_key = settings.OVH_CONSUMER_KEY
        self.service_name = settings.OVH_SMS_SERVICE_NAME

        # Tant que "SAJED" est en validation, on utilise senderForResponse=True
        self.sender = getattr(settings, "OVH_SMS_SENDER", "").strip()
        self.sender_for_response = bool(getattr(settings, "OVH_SENDER_FOR_RESPONSE", True))

    def _ovh_time(self) -> int:
        r = requests.get(f"{self.base_url}/auth/time", timeout=10)
        r.raise_for_status()
        return int(r.text)

    def _signature(self, method: str, url: str, body_str: str, tstamp: int) -> str:
        to_sign = f"{self.app_secret}+{self.consumer_key}+{method}+{url}+{body_str}+{tstamp}"
        sha1 = hashlib.sha1(to_sign.encode("utf-8")).hexdigest()
        return f"$1${sha1}"

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        method = method.upper()
        url = f"{self.base_url}{path}"

        body_str = ""
        if body is not None:
            body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)

        tstamp = self._ovh_time()
        sig = self._signature(method, url, body_str, tstamp)

        headers = {
            "Content-Type": "application/json",
            "X-Ovh-Application": self.app_key,
            "X-Ovh-Consumer": self.consumer_key,
            "X-Ovh-Timestamp": str(tstamp),
            "X-Ovh-Signature": sig,
        }

        r = requests.request(method, url, data=(body_str if body_str else None), headers=headers, timeout=20)
        if not r.ok:
            raise RuntimeError(f"OVH API {r.status_code}: {r.text}")
        return r.json()

    def send(self, to_e164: str, text: str) -> dict:
        payload = {
            "receivers": [to_e164],
            "message": text,
            "priority": "high",
        }

        if self.sender:
            payload["sender"] = self.sender
        elif self.sender_for_response:
            payload["senderForResponse"] = True

        raw = self._request("POST", f"/sms/{self.service_name}/jobs", payload)

        message_id = ""
        if isinstance(raw, dict) and raw.get("ids"):
            message_id = str(raw["ids"][0])

        return {"message_id": message_id, "raw": raw}
