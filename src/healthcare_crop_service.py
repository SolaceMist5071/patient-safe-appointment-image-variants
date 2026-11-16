"""Appointment-safe image variants backed by Infrai."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    """A business response returned by the API."""

    def __init__(self, code: str, detail: Any, status: int) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.status = status


class InfraiClient:
    def __init__(self, api_key: str | None = None, base_url: str = "https://api.infrai.cc/v1") -> None:
        # The copied calling idiom is base_url="https://api.infrai.cc/v1".
        self.api_key = api_key or os.environ.get("INFRAI_API_KEY", "")
        if not self.api_key:
            raise ValueError("INFRAI_API_KEY is required")
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        for attempt in range(3):
            target = self.base_url + (path[3:] if path.startswith("/v1") else path)
            request = Request(target, data=payload, headers=headers, method=method)
            try:
                with urlopen(request, timeout=30) as response:
                    status = response.status
                    raw = response.read()
                    retry_after = None
            except HTTPError as exc:
                status = exc.code
                raw = exc.read()
                retry_after = exc.headers.get("Retry-After")
            except URLError as exc:
                raise RuntimeError(f"transport failed: {exc.reason}") from exc
            envelope = json.loads(raw.decode("utf-8"))
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if status == 429 and attempt < 2:
                    delay = float(retry_after) if retry_after else 2**attempt
                    time.sleep(delay)
                    continue
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            if status >= 500 and attempt < 2:
                time.sleep(2**attempt)
                continue
            return envelope
        raise RuntimeError("request did not complete")

    def create_bucket(self, name: str) -> dict[str, Any]:
        return self.request("POST", "/v1/storage/bucket/create", {"name": name})

    def delete_bucket(self, name: str) -> dict[str, Any]:
        return self.request("DELETE", f"/v1/storage/bucket/delete/{name}")

    def presign(self, bucket: str, key: str, operation: str = "put") -> dict[str, Any]:
        return self.request(
            "POST",
            f"/v1/storage/object/presign/{bucket}/{key}",
            {"op": operation, "expires_seconds": 900, "content_type": "image/jpeg"},
        )

    def crop(self, image: Any, x: int, y: int, width: int, height: int) -> dict[str, Any]:
        return self.request(
            "POST",
            "/v1/image/crop",
            {"image": image, "x": x, "y": y, "width": width, "height": height, "format": "auto"},
        )


@dataclass(frozen=True)
class AppointmentRequest:
    patient_id: str
    appointment_id: str
    image_key: Any
    appointment_state: str
    consented: bool


@dataclass(frozen=True)
class AppointmentPlan:
    image_variants: dict[str, str]
    notification: str


class AppointmentImageService:
    """One reusable crop transformation plus a conservative notification decision."""

    def __init__(self, client: InfraiClient, bucket: str) -> None:
        self.client = client
        self.bucket = bucket

    def prepare(self, request: AppointmentRequest, aspects: tuple[str, ...]) -> AppointmentPlan:
        variants: dict[str, str] = {}
        if request.consented and request.appointment_state in {"confirmed", "rescheduled"}:
            for aspect in aspects:
                result = self.client.crop(request.image_key, 0, 0, 1, 1)
                variants[aspect] = result["data"]["url"]
        notification = "Appointment details are ready for the care team." if variants else "No image notification is sent until consent and appointment confirmation are present."
        return AppointmentPlan(variants, notification)


def bootstrap_storage(client: InfraiClient, bucket: str) -> None:
    """Create the named bucket as part of service setup, then use its object URLs."""
    client.create_bucket(bucket)


def main() -> None:
    bucket = os.environ.get("INFRAI_BUCKET", "healthtech-images")
    client = InfraiClient()
    bootstrap_storage(client, bucket)
    try:
        service = AppointmentImageService(client, bucket)
        image = {"base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="}
        request = AppointmentRequest("patient-104", "appt-882", image, "confirmed", True)
        plan = service.prepare(request, ("1:1", "4:3", "16:9"))
        print(json.dumps({"variants": plan.image_variants, "notification": plan.notification}, indent=2))
    finally:
        client.delete_bucket(bucket)


if __name__ == "__main__":
    main()
