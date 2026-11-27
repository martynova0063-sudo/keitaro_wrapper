"""Бизнес-логика обёртки: сборка кампаний и редактирование офферов."""

from typing import Any

from app.config import get_settings
from app.keitaro.client import KeitaroClient


class LogicError(Exception):
    pass


def resolve_defaults(keitaro: KeitaroClient) -> dict[str, Any]:
    """Домен, группа и источник кампании.

    Пытаемся найти сущности FORTESTS через API (это «живые» значения),
    при неудаче откатываемся на id по умолчанию из настроек.
    """
    settings = get_settings()

    domain_ids = [settings.default_domain_id]
    try:
        domains = keitaro.get_domains()
        found = [d for d in domains if str(d.get("name", "")).upper() == "FORTESTS"]
        if found:
            domain_ids = [found[0]["id"]]
    except Exception:
        pass

    group_ids = [settings.default_group_id]
    try:
        groups = keitaro.get_groups()
        found = [g for g in groups if str(g.get("name", "")).upper() == "FORTESTS"]
        if found:
            group_ids = [found[0]["id"]]
    except Exception:
        pass

    traffic_source_id = settings.default_traffic_source_id
    try:
        sources = keitaro.get_traffic_sources()
        found = [s for s in sources if str(s.get("name", "")).upper() == "FORTESTS"]
        if found:
            traffic_source_id = found[0]["id"]
    except Exception:
        pass

    return {"domain_ids": domain_ids, "group_ids": group_ids, "traffic_source_id": traffic_source_id}


def build_geo_stream_payload(geo_code: str) -> dict[str, Any]:
    """Поток «все из страны geo_code → Google»."""
    return {
        "name": f"Geo {geo_code}",
        "type": "regular",
        "schema": "redirect",
        "action_type": "http",
        "action_payload": get_settings().google_url,
        "filters": [{"name": "country", "mode": "accept", "payload": [geo_code]}],
    }


def build_offers_stream_payload(offer_id: int) -> dict[str, Any]:
    """Поток «редирект на выбранный оффер»."""
    return {
        "name": "Offers",
        "type": "default",
        "schema": "landings",
        "offers": [{"offer_id": offer_id, "share": 100, "state": "active"}],
    }


def find_offers_stream(streams: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Поток, в котором живут офферы кампании (schema: landings)."""
    for stream in streams:
        if stream.get("schema") == "landings":
            return stream
    return None


def add_offer_to_list(
    offers: list[dict[str, Any]], offer_id: int, share: float | None
) -> list[dict[str, Any]]:
    """Добавить оффер в состав потока. Доли — это веса, проценты считаем на выводе."""
    if any(o.get("offer_id") == offer_id for o in offers):
        raise LogicError("Этот оффер уже есть в кампании")

    new_offers = [{"offer_id": o["offer_id"], "share": o["share"], "state": o.get("state", "active")} for o in offers]
    if share is None:
        # равная доля со всеми существующими; если список пуст — 100
        share = round(100 / (len(new_offers) + 1), 4) if new_offers else 100
    new_offers.append({"offer_id": offer_id, "share": share, "state": "active"})
    return new_offers


def remove_offer_from_list(
    offers: list[dict[str, Any]], offer_id: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Удалить оффер из состава потока и перераспределить его долю
    между оставшимися пропорционально их весам.

    Возвращает (новый список, удалённый оффер). Если после удаления
    список пуст — кампания остаётся только с гео-потоком; вызывающий
    код должен выключить offers-поток.
    """
    target = next((o for o in offers if o.get("offer_id") == offer_id), None)
    if target is None:
        raise LogicError("Оффер не найден в кампании")

    remaining = [
        {"offer_id": o["offer_id"], "share": o["share"], "state": o.get("state", "active")}
        for o in offers
        if o.get("offer_id") != offer_id
    ]

    if remaining:
        removed_share = float(target.get("share") or 0)
        total = sum(float(o["share"] or 0) for o in remaining)
        if total > 0:
            for o in remaining:
                o["share"] = round(float(o["share"]) + removed_share * float(o["share"]) / total, 4)
        else:
            # все оставшиеся веса нулевые — делим поровну
            equal = round(removed_share / len(remaining), 4)
            for o in remaining:
                o["share"] = equal
    return remaining, target


def with_percent(offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Считаем проценты из весов: это те самые «верные цифры» в интерфейсе."""
    total = sum(float(o.get("share") or 0) for o in offers)
    result = []
    for o in offers:
        weight = float(o.get("share") or 0)
        percent = round(weight / total * 100, 1) if total > 0 else 0.0
        result.append({**o, "percent": percent})
    return result
