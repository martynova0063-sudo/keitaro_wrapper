import re

from pydantic import BaseModel, field_validator

GEO_CODE_RE = re.compile(r"^[A-Z]{2}$")


class CampaignCreate(BaseModel):
    name: str
    geo_code: str
    offer_id: int

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Название кампании не может быть пустым")
        return v

    @field_validator("geo_code")
    @classmethod
    def geo_code_valid(cls, v: str) -> str:
        v = v.strip().upper()
        if not GEO_CODE_RE.match(v):
            raise ValueError("Гео-код должен состоять из двух латинских букв, например RU, US, GM")
        return v


class OfferAdd(BaseModel):
    offer_id: int
    share: float | None = None
