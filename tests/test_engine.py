import json

import httpx
import pytest
from pydantic import ValidationError

from newfakenewsdetector.catalog import Catalog
from newfakenewsdetector.engine import Engine
from newfakenewsdetector.google import GoogleFactChecks
from newfakenewsdetector.models import CheckRequest

CLAIM = "항생제는 감기 바이러스를 치료한다."


@pytest.fixture
def catalog():
    return Catalog.load()


@pytest.mark.parametrize(
    ("claim", "verdict", "language"),
    [
        (CLAIM, "refuted", "ko"),
        ("항생제는  감기 바이러스를 치료한다", "refuted", "ko"),
        ("지구 자전축의 기울기가 계절 변화의 원인이다.", "supported", "ko"),
        ("Pluto was reclassified as a dwarf planet in 2006.", "supported", "en"),
        ("Pluto was reclassified as a dwarf planet in 2008.", "insufficient", "en"),
        ("항생제는 감기 바이러스를 치료하지 않는다.", "insufficient", "ko"),
        ("항생제는 감기 바이러스를 치료한다?", "insufficient", "ko"),
        ("서울에 새로운 상점이 열렸다는 주장이다.", "insufficient", "ko"),
    ],
)
def test_verdict_requires_matching_claim(catalog, claim, verdict, language):
    result = Engine(catalog).check(CheckRequest(claim=claim))
    assert result.verdict == verdict
    assert result.language == language
    assert result.online_status == "off"
    if verdict == "insufficient":
        assert all(match.match == "related" for match in result.matches)


def test_changed_date_is_related_without_inheriting_the_rating(catalog):
    result = Engine(catalog).check(
        CheckRequest(claim="Pluto was reclassified as a dwarf planet in 2008.")
    )
    assert result.verdict == "insufficient"
    assert result.matches[0].match == "related"
    assert "2006" in result.matches[0].claim


@pytest.mark.parametrize("claim", ["단어", "!" * 50, "x" * 501, "서울에\x00가게가 열렸다."])
def test_invalid_claims_are_rejected(claim):
    with pytest.raises(ValidationError):
        CheckRequest(claim=claim)


def test_korean_news_claim_links_review_and_primary_reference(catalog):
    claim = "2026년 8월 26일 네팔 홍수는 중국이 건설한 댐의 붕괴로 발생했다."
    result = Engine(catalog).check(CheckRequest(claim=claim))
    assert result.verdict == "refuted"
    articles = result.matches[0].evidence
    assert {source.url.host for source in articles} == {"factcheckkorea.afp.com", "www.usgs.gov"}
    assert articles[1].stance is None


def test_additional_catalog_preserves_conflicting_sources(tmp_path):
    path = tmp_path / "local.json"
    path.write_text(
        json.dumps(
            [
                {
                    "claim": CLAIM,
                    "language": "ko",
                    "evidence": [
                        {
                            "url": "https://example.org/review",
                            "publisher": "Test publisher",
                            "title": "Test evidence",
                            "stance": "supported",
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )
    result = Engine(Catalog.load(path)).check(CheckRequest(claim=CLAIM))
    assert result.verdict == "conflicting"
    assert {m.evidence[0].publisher for m in result.matches} == {"CDC", "Test publisher"}


def test_key_is_required_for_optional_lookup(catalog):
    result = Engine(catalog).check(CheckRequest(claim=CLAIM, online=True))
    assert result.online_status == "unconfigured"
    assert result.verdict == "refuted"


def google_payload(claim, rating, language="ko"):
    return {
        "claims": [
            {
                "text": claim,
                "claimReview": [
                    {
                        "publisher": {"name": "Test Fact Check"},
                        "title": "Original review",
                        "url": "https://example.org/facts",
                        "reviewDate": "2025-01-01T00:00:00Z",
                        "textualRating": rating,
                        "languageCode": language,
                    },
                    {"url": "javascript:alert(1)", "publisher": {"name": "Invalid"}},
                ],
            }
        ]
    }


def test_opt_in_controls_remote_request_and_preserves_review(catalog):
    def send(request):
        outgoing.append(request)
        assert request.url.host == "factchecktools.googleapis.com"
        assert request.url.params["query"] == CLAIM
        assert request.url.params["languageCode"] == "ko"
        assert request.headers["x-goog-api-key"] == "test-key"
        assert "test-key" not in str(request.url)
        return httpx.Response(200, json=google_payload(CLAIM, "사실"))

    outgoing = []
    with httpx.Client(transport=httpx.MockTransport(send)) as client:
        engine = Engine(catalog, GoogleFactChecks("test-key", client))
        assert engine.check(CheckRequest(claim=CLAIM)).verdict == "refuted"
        assert not outgoing
        result = engine.check(CheckRequest(claim=CLAIM, online=True))
    assert len(outgoing) == 1
    assert result.verdict == "conflicting"
    assert result.online_status == "searched"
    google_match = next(match for match in result.matches if match.provider == "google")
    assert len(google_match.evidence) == 1
    assert google_match.evidence[0].original_rating == "사실"
    assert google_match.evidence[0].date.isoformat() == "2025-01-01"


@pytest.mark.parametrize(
    ("reviewed_claim", "rating", "language", "verdict"),
    [
        ("The park opens at 10 a.m.", "False", "en-US", "refuted"),
        ("The park opens at 10 a.m.", "Partly true", "en", "mixed"),
        ("The park opens at 10 a.m.", "Needs context", "en", "review_found"),
        ("The park opens at 10 a.m.", "False", "", "review_found"),
        ("The park opens at 11 a.m.", "False", "en", "insufficient"),
    ],
)
def test_google_match_uses_only_explicit_rating(reviewed_claim, rating, language, verdict, catalog):
    response = httpx.Response(200, json=google_payload(reviewed_claim, rating, language))
    with httpx.Client(transport=httpx.MockTransport(lambda _: response)) as client:
        engine = Engine(catalog, GoogleFactChecks("test-key", client))
        result = engine.check(CheckRequest(claim="The park opens at 10 a.m.", online=True))
    assert result.verdict == verdict
    assert result.matches[0].evidence[0].original_rating == rating


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(429),
        httpx.Response(200, content=b"<html>"),
        httpx.Response(200, json={"claims": {}}),
        httpx.Response(200, content=b"x" * 512_001),
    ],
)
def test_failed_lookups_preserve_local_evidence(catalog, response):
    with httpx.Client(transport=httpx.MockTransport(lambda _: response)) as client:
        engine = Engine(catalog, GoogleFactChecks("test-key", client))
        result = engine.check(CheckRequest(claim=CLAIM, online=True))
    assert result.verdict == "refuted"
    assert result.online_status == "unavailable"
