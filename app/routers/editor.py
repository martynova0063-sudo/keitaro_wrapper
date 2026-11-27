from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.keitaro.client import KeitaroAPIError, KeitaroClient, KeitaroConnectionError, KeitaroError
from app.routers.dependencies import get_keitaro, log_operation
from app.schemas import OfferAdd
from app.services import (
    LogicError,
    add_offer_to_list,
    find_offers_stream,
    remove_offer_from_list,
    with_percent,
)

router = APIRouter(prefix="/api", tags=["editor"])


@router.get("/campaigns/{campaign_id}/offers")
def list_campaign_offers(
    campaign_id: int,
    keitaro: KeitaroClient = Depends(get_keitaro),
):
    """Список офферов потока кампании с весами и процентами."""
    try:
        streams = keitaro.get_streams(campaign_id)
        stream = find_offers_stream(streams)
        if stream is None:
            return {"stream": None, "offers": [], "total_weight": 0}

        offers = with_percent(stream.get("offers") or [])

        names: dict[int, str] = {}
        for o in offers:
            try:
                names[o["offer_id"]] = keitaro.get_offer(o["offer_id"]).get("name")
            except KeitaroAPIError:
                names[o["offer_id"]] = f"оффер #{o['offer_id']}"

        for o in offers:
            o["name"] = names.get(o["offer_id"], f"оффер #{o['offer_id']}")

        return {
            "stream": stream,
            "offers": offers,
            "total_weight": sum(float(o.get("share") or 0) for o in offers),
        }
    except KeitaroError as exc:
        raise _map_error(exc) from exc


@router.post("/campaigns/{campaign_id}/offers")
def add_offer(
    campaign_id: int,
    payload: OfferAdd,
    db: Session = Depends(get_db),
    keitaro: KeitaroClient = Depends(get_keitaro),
):
    """Добавить оффер в поток кампании.

    Внутри: GET /campaigns/{id}/streams → найден landings-поток →
    расширенный список офферов уходит в PUT /streams/{id} целиком,
    потому что поле offers заменяет состав полностью.
    """
    try:
        keitaro.get_offer(payload.offer_id)
    except KeitaroAPIError as exc:
        if exc.status_code == 404:
            raise HTTPException(404, f"Оффер {payload.offer_id} не найден") from exc
        raise _map_error(exc) from exc

    try:
        stream = _must_offers_stream(keitaro, campaign_id)
        offers = add_offer_to_list(stream.get("offers") or [], payload.offer_id, payload.share)
        keitaro.update_stream(stream["id"], {"offers": offers})
    except LogicError as exc:
        raise HTTPException(409, str(exc)) from exc
    except KeitaroError as exc:
        raise _map_error(exc) from exc

    log_operation(db, "add_offer", "stream", stream["id"], {"offers": offers}, 200, True)
    return {"stream_id": stream["id"], "offers": with_percent(offers)}


@router.delete("/campaigns/{campaign_id}/offers/{offer_id}")
def remove_offer(
    campaign_id: int,
    offer_id: int,
    db: Session = Depends(get_db),
    keitaro: KeitaroClient = Depends(get_keitaro),
):
    """Удалить оффер из потока кампании.

    Оффер действительно исключается из потока (не «зануление доли»),
    его доля перераспределяется между оставшимися пропорционально
    их весам — так проценты в интерфейсе остаются верными.
    Если оффер был последним, offers-поток выключается.
    """
    try:
        stream = _must_offers_stream(keitaro, campaign_id)
        new_offers, removed = remove_offer_from_list(stream.get("offers") or [], offer_id)

        if new_offers:
            keitaro.update_stream(stream["id"], {"offers": new_offers})
        else:
            # последний оффер удалён — поток без офферов не нужен
            try:
                keitaro.update_stream(stream["id"], {"offers": []})
            except KeitaroAPIError:
                pass  # API не позволяет пустой поток — просто выключаем
            keitaro.disable_stream(stream["id"])
    except LogicError as exc:
        raise HTTPException(404, str(exc)) from exc
    except KeitaroError as exc:
        raise _map_error(exc) from exc

    log_operation(db, "remove_offer", "stream", stream["id"], {"removed": removed}, 200, True)
    return {"stream_id": stream["id"], "offers": with_percent(new_offers), "removed": removed}


def _must_offers_stream(keitaro: KeitaroClient, campaign_id: int) -> dict:
    streams = keitaro.get_streams(campaign_id)
    stream = find_offers_stream(streams)
    if stream is None:
        raise LogicError(f"У кампании {campaign_id} нет потока с офферами")
    return stream


def _map_error(exc: KeitaroError) -> HTTPException:
    if isinstance(exc, KeitaroAPIError):
        if exc.status_code == 404:
            return HTTPException(404, exc.message)
        return HTTPException(502, exc.message)
    return HTTPException(502, f"Нет связи с Keitaro API: {exc}")
