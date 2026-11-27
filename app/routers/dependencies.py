from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.keitaro.client import KeitaroClient
from app.models import OperationLog


def get_keitaro():
    client = KeitaroClient(
        base_url=get_settings().keitaro_base_url,
        api_key=get_settings().keitaro_api_key,
    )
    try:
        yield client
    finally:
        client.close()


def log_operation(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: str | int | None,
    request_payload: dict | None,
    status_code: int | None,
    ok: bool,
    response_snippet: str | None = None,
) -> None:
    db.add(
        OperationLog(
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            request_payload=str(request_payload) if request_payload else None,
            status_code=status_code,
            ok=ok,
            response_snippet=(response_snippet or "")[:1000],
        )
    )
    db.commit()
