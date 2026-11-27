import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.keitaro.client import KeitaroAPIError, KeitaroClient, KeitaroConnectionError, KeitaroError
from app.routers.dependencies import get_keitaro, log_operation
from app.schemas import CampaignCreate
from app.services import (
    build_geo_stream_payload,
    build_offers_stream_payload,
    resolve_defaults,
)

router = APIRouter(prefix="/api", tags=["campaigns"])

GOOGLE_URL_MARKER = "google"


@router.get("/constants")
def get_constants(keitaro: KeitaroClient = Depends(get_keitaro)):
    """Справочники для интерфейса: домены, группы, источники, офферы."""
    try:
        return {
            "domains": keitaro.get_domains(),
            "groups": keitaro.get_groups(),
            "traffic_sources": keitaro.get_traffic_sources(),
        }
    except KeitaroError as exc:
        raise _map_error(exc) from exc


@router.get("/offers")
def list_offers(keitaro: KeitaroClient = Depends(get_keitaro)):
    try:
        return keitaro.get_offers()
    except KeitaroError as exc:
        raise _map_error(exc) from exc


@router.post("/campaigns")
def create_campaign(
    payload: CampaignCreate,
    db: Session = Depends(get_db),
    keitaro: KeitaroClient = Depends(get_keitaro),
):
    """Создаватор кампаний.

    1. Проверяем, что оффер существует.
    2. Создаём кампанию с доменом, группой и источником.
    3. Поток 1: ловит всех из указанной страны и редиректит на Google.
    4. Поток 2: редиректит на выбранный оффер.
    """
    try:
        keitaro.get_offer(payload.offer_id)
    except KeitaroAPIError as exc:
        if exc.status_code == 404:
            raise HTTPException(404, f"Оффер {payload.offer_id} не найден") from exc
        raise _map_error(exc) from exc

    defaults = resolve_defaults(keitaro)

    try:
        campaign = keitaro.create_campaign(
            name=payload.name,
            domain_ids=defaults["domain_ids"],
            group_ids=defaults["group_ids"],
            traffic_source_id=defaults["traffic_source_id"],
        )
        campaign_id = campaign["id"]
    except KeitaroError as exc:
        raise _map_error(exc) from exc

    try:
        geo_stream = keitaro.create_stream(campaign_id, build_geo_stream_payload(payload.geo_code))
        offers_stream = keitaro.create_stream(campaign_id, build_offers_stream_payload(payload.offer_id))
    except KeitaroError as exc:
        log_operation(db, "create_campaign_streams", "campaign", campaign_id, None, None, False, str(exc))
        raise _map_error(exc) from exc

    log_operation(db, "create_campaign", "campaign", campaign_id, payload.model_dump(), 201, True)

    return {
        "campaign": campaign,
        "streams": [geo_stream, offers_stream],
        "admin_url": keitaro.admin_campaign_url(campaign_id),
    }


@router.get("/campaigns")
def list_campaigns(keitaro: KeitaroClient = Depends(get_keitaro)):
    try:
        return keitaro.get_campaigns()
    except KeitaroError as exc:
        raise _map_error(exc) from exc


@router.get("/campaigns/{campaign_id}")
def get_campaign_detail(
    campaign_id: int,
    keitaro: KeitaroClient = Depends(get_keitaro),
):
    """Кампания с потоками, офферами и именами справочных сущностей."""
    try:
        campaign = keitaro.get_campaign(campaign_id)
        streams = keitaro.get_streams(campaign_id)

        domains = {d["id"]: d for d in keitaro.get_domains()}
        groups = {g["id"]: g for g in keitaro.get_groups()}
        sources = {s["id"]: s for s in keitaro.get_traffic_sources()}

        offer_ids = set()
        for s in streams:
            for o in s.get("offers") or []:
                offer_ids.add(o.get("offer_id"))
        offers = {}
        for oid in offer_ids:
            try:
                offers[oid] = keitaro.get_offer(oid)
            except KeitaroAPIError:
                continue

        return {
            "campaign": campaign,
            "streams": streams,
            "admin_url": keitaro.admin_campaign_url(campaign_id),
            "meta": {
                "domain": (domains.get((campaign.get("domain_ids") or [None])[0], {}) or {}).get("name"),
                "group": (groups.get((campaign.get("group_ids") or [None])[0], {}) or {}).get("name"),
                "traffic_source": (sources.get(campaign.get("traffic_source_id"), {}) or {}).get("name"),
                "offers": offers,
            },
        }
    except KeitaroError as exc:
        raise _map_error(exc) from exc


def _map_error(exc: KeitaroError) -> HTTPException:
    if isinstance(exc, KeitaroAPIError):
        if exc.status_code == 404:
            return HTTPException(404, exc.message)
        return HTTPException(502, exc.message)
    return HTTPException(502, f"Нет связи с Keitaro API: {exc}")
