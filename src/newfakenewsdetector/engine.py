import os
import re
from pathlib import Path
from typing import Protocol

from .catalog import Catalog
from .google import LookupUnavailable
from .models import CheckRequest, CheckResult, Language, Match, ProviderState, Verdict


class ReviewSearch(Protocol):
    def search(self, claim: str, language: Language) -> list[Match]: ...


def configured_catalog() -> Catalog:
    extra = os.environ.get("FAKENEWS_CATALOG")
    return Catalog.load(Path(extra) if extra else None)


def detect_language(claim: str) -> Language:
    return "ko" if re.search(r"[가-힣ㄱ-ㅎㅏ-ㅣ\u1100-\u11ff]", claim) else "en"


def decide(matches: list[Match]) -> Verdict:
    exact = [match for match in matches if match.match == "exact"]
    stances = {source.stance for match in exact for source in match.evidence if source.stance}
    if len(stances) > 1:
        return "conflicting"
    if stances:
        return stances.pop()
    return "review_found" if exact else "insufficient"


class Engine:
    def __init__(self, catalog: Catalog, provider: ReviewSearch | None = None):
        self.catalog = catalog
        self.provider = provider

    def check(self, request: CheckRequest) -> CheckResult:
        language = (
            detect_language(request.claim) if request.language == "auto" else request.language
        )
        matches = self.catalog.search(request.claim, language)
        online_status: ProviderState = "off"
        if request.online:
            online_status = "unconfigured"
            if self.provider is not None:
                try:
                    matches.extend(self.provider.search(request.claim, language))
                    online_status = "searched"
                except LookupUnavailable:
                    online_status = "unavailable"
        matches.sort(key=lambda match: match.match != "exact")
        return CheckResult(
            claim=request.claim,
            language=language,
            verdict=decide(matches),
            online_status=online_status,
            matches=matches,
        )
