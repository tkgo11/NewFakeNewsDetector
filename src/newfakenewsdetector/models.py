import re
import unicodedata
from datetime import date as CalendarDate
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, field_validator

MAX_CLAIM_LENGTH = 500
ClaimText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=8, max_length=MAX_CLAIM_LENGTH)
]
Language = Literal["ko", "en"]
Stance = Literal["supported", "refuted", "mixed"]
Verdict = Literal["supported", "refuted", "mixed", "conflicting", "review_found", "insufficient"]
ProviderState = Literal["off", "unconfigured", "searched", "unavailable"]
Nonempty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1500)]


def normalize_claim(text: str) -> str:
    text = " ".join(unicodedata.normalize("NFC", text).split())
    return re.sub(r"(?<=[^\W_])\.$", "", text)


class CheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    claim: ClaimText
    language: Literal["auto", "ko", "en"] = "auto"
    online: bool = False

    @field_validator("claim")
    @classmethod
    def validate_claim(cls, text: str) -> str:
        if sum(char.isalnum() for char in text) < 4:
            raise ValueError("Use a written claim with at least four letters or digits.")
        if any(
            unicodedata.category(char) in {"Cc", "Cs"} and char not in "\r\n\t" for char in text
        ):
            raise ValueError("The claim contains unsupported control characters.")
        return text


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    publisher: Nonempty
    title: Nonempty
    url: HttpUrl
    date: CalendarDate | None = None
    summary: Nonempty | None = None
    original_rating: Nonempty | None = None
    stance: Stance | None = None

    @field_validator("url")
    @classmethod
    def safe_reference(cls, url: HttpUrl) -> HttpUrl:
        if url.username is not None or url.password is not None:
            raise ValueError("Evidence URLs must not contain credentials.")
        return url


class CatalogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    claim: ClaimText
    language: Language
    evidence: Annotated[tuple[Evidence, ...], Field(min_length=1, max_length=10)]


class Match(BaseModel):
    claim: str
    match: Literal["exact", "related"]
    provider: Literal["catalog", "google"]
    evidence: tuple[Evidence, ...]


class CheckResult(BaseModel):
    claim: str
    language: Language
    verdict: Verdict
    online_status: ProviderState
    matches: list[Match]
