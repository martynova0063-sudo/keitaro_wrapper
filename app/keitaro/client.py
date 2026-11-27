"""Обёртка над Keitaro Admin API.

Поля запросов и ответов — как в официальной документации:
https://admin-api.docs.keitaro.io/

Клиент синхронный (httpx) — эндпоинты FastAPI выполняются в
threadpool, этого более чем достаточно для объёмов обёртки.
"""

from typing import Any

import httpx


class KeitaroError(Exception):
    """Базовая ошибка обёртки."""


class KeitaroConnectionError(KeitaroError):
    """Сеть недоступна / таймаут."""


class KeitaroAPIError(KeitaroError):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Keitaro API вернул {status_code}: {message}")


class KeitaroClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0):
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Api-Key": api_key, "Content-Type": "application/json"},
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    # ------------------------------------------------------------------ core

    def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        try:
            resp = self._client.request(method, path, json=json, params=params)
        except httpx.HTTPError as exc:
            raise KeitaroConnectionError(str(exc)) from exc

        if resp.status_code >= 400:
            detail = _extract_detail(resp)
            raise KeitaroAPIError(resp.status_code, detail)

        if resp.status_code == 204 or not resp.content:
            return None
        try:
            return resp.json()
        except ValueError as exc:
            raise KeitaroAPIError(resp.status_code, "не-JSON ответ API") from exc

    # ------------------------------------------------------------- campaigns

    def get_campaigns(self, offset: int = 0, limit: int = 100) -> Any:
        return self._request("GET", "/campaigns", params={"offset": offset, "limit": limit})

    def get_campaign(self, campaign_id: int) -> Any:
        return self._request("GET", f"/campaigns/{campaign_id}")

    def create_campaign(
        self,
        name: str,
        domain_ids: list[int],
        group_ids: list[int],
        traffic_source_id: int,
    ) -> Any:
        payload = {
            "name": name,
            "domain_ids": domain_ids,
            "group_ids": group_ids,
            "traffic_source_id": traffic_source_id,
            "state": "active",
        }
        return self._request("POST", "/campaigns", json=payload)

    def update_campaign(self, campaign_id: int, payload: dict[str, Any]) -> Any:
        return self._request("PUT", f"/campaigns/{campaign_id}", json=payload)

    def delete_campaign(self, campaign_id: int) -> Any:
        return self._request("DELETE", f"/campaigns/{campaign_id}")

    def enable_campaign(self, campaign_id: int) -> Any:
        return self._request("POST", f"/campaigns/{campaign_id}/enable")

    def disable_campaign(self, campaign_id: int) -> Any:
        return self._request("POST", f"/campaigns/{campaign_id}/disable")

    # --------------------------------------------------------------- streams

    def get_streams(self, campaign_id: int) -> Any:
        return self._request("GET", f"/campaigns/{campaign_id}/streams")

    def get_stream(self, stream_id: int) -> Any:
        return self._request("GET", f"/streams/{stream_id}")

    def create_stream(self, campaign_id: int, payload: dict[str, Any]) -> Any:
        payload = {"campaign_id": campaign_id, **payload}
        return self._request("POST", "/streams", json=payload)

    def update_stream(self, stream_id: int, payload: dict[str, Any]) -> Any:
        return self._request("PUT", f"/streams/{stream_id}", json=payload)

    def delete_stream(self, stream_id: int) -> Any:
        return self._request("DELETE", f"/streams/{stream_id}")

    def enable_stream(self, stream_id: int) -> Any:
        return self._request("POST", f"/streams/{stream_id}/enable")

    def disable_stream(self, stream_id: int) -> Any:
        return self._request("POST", f"/streams/{stream_id}/disable")

    # ------------------------------------------------------------ каталоги

    def get_offers(self) -> Any:
        return self._request("GET", "/offers")

    def get_offer(self, offer_id: int) -> Any:
        return self._request("GET", f"/offers/{offer_id}")

    def get_groups(self) -> Any:
        return self._request("GET", "/groups", params={"type": "campaigns"})

    def get_domains(self) -> Any:
        return self._request("GET", "/domains")

    def get_traffic_sources(self) -> Any:
        return self._request("GET", "/traffic_sources")

    # --------------------------------------------------------------- helpers

    def admin_campaign_url(self, campaign_id: int) -> str:
        root = str(self._client.base_url).removesuffix("/admin_api/v1")
        return f"{root}/admin/#!/campaign.editor/{campaign_id}"


def _extract_detail(resp: httpx.Response) -> str:
    try:
        data = resp.json()
    except ValueError:
        return resp.text[:500] or resp.reason_phrase
    if isinstance(data, dict):
        return str(data.get("detail") or data.get("message") or data)[:500]
    return str(data)[:500]
