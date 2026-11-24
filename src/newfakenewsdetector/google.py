import json

import httpx
from pydantic import ValidationError

from .models import Evidence, Language, Match, Stance, normalize_claim

ENDPOINT = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
MAX_RESPONSE_SIZE = 512_000
RATINGS: dict[str, Stance] = {
    "true": "supported",
    "correct": "supported",
    "사실": "supported",
    "사실임": "supported",
    "false": "refuted",
    "incorrect": "refuted",
    "fake": "refuted",
    "사실 아님": "refuted",
    "전혀 사실 아님": "refuted",
    "거짓": "refuted",
    "mixture": "mixed",
    "mixed": "mixed",
    "partly true": "mixed",
    "절반의 사실": "mixed",
}


class LookupUnavailable(Exception):
    """The external lookup did not return a usable response."""


def text_field(obj: dict, key: str) -> str:
    value = obj.get(key)
    return value.strip() if isinstance(value, str) else ""


def reviews_for(item: dict) -> tuple[Evidence, ...]:
    results = []
    reviews = item.get("claimReview", [])
    if not isinstance(reviews, list):
        return ()
    for review in reviews[:10]:
        if not isinstance(review, dict):
            continue
        publisher = review.get("publisher")
        if not isinstance(publisher, dict):
            continue
        rating = text_field(review, "textualRating")
        lang = text_field(review, "languageCode").lower().split("-")[0]
        try:
            evidence = Evidence(
                publisher=text_field(publisher, "name") or text_field(publisher, "site"),
                title=text_field(review, "title") or text_field(item, "text"),
                url=text_field(review, "url"),
                date=text_field(review, "reviewDate").split("T", 1)[0] or None,
                original_rating=rating or None,
                stance=RATINGS.get(normalize_claim(rating).casefold())
                if lang in {"ko", "en"}
                else None,
            )
        except ValidationError:
            continue
        if evidence not in results:
            results.append(evidence)
    return tuple(results)


class GoogleFactChecks:
    def __init__(self, key: str, client: httpx.Client):
        self._key = key
        self._client = client

    def search(self, claim: str, language: Language) -> list[Match]:
        try:
            with self._client.stream(
                "GET",
                ENDPOINT,
                params={"query": claim, "languageCode": language, "pageSize": 10},
                headers={"X-Goog-Api-Key": self._key},
            ) as response:
                response.raise_for_status()
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_SIZE:
                        raise LookupUnavailable
                payload = json.loads(body)
        except (httpx.HTTPError, ValueError):
            raise LookupUnavailable from None

        claims = payload.get("claims", []) if isinstance(payload, dict) else None
        if not isinstance(claims, list) or (isinstance(payload, dict) and "error" in payload):
            raise LookupUnavailable

        matches = []
        for item in claims[:10]:
            if not isinstance(item, dict):
                continue
            text = text_field(item, "text")
            evidence = reviews_for(item)
            if text and evidence:
                matches.append(
                    Match(
                        claim=text,
                        match="exact"
                        if normalize_claim(text) == normalize_claim(claim)
                        else "related",
                        provider="google",
                        evidence=evidence,
                    )
                )
        return matches
