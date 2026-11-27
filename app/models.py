from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class OperationLog(Base):
    """Локальный журнал операций обёртки к Keitaro API.

    Требование ТЗ по стеку: SQLAlchemy. Каждый вызов внешнего API
    с фиксируемым результатом оседает здесь — удобно для отладки.
    """

    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    request_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ok: Mapped[bool] = mapped_column(default=True)
    response_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
