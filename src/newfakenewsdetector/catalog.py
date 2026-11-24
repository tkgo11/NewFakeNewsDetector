import re
from importlib.resources import files
from pathlib import Path

from pydantic import TypeAdapter

from .models import CatalogEntry, Language, Match, normalize_claim

MIN_RELATED_SCORE = 0.42
RELATED_LIMIT = 4
catalog_schema = TypeAdapter(list[CatalogEntry])


def features(text: str) -> tuple[set[str], set[str]]:
    tokens = set(re.findall(r"[^\W_]+", text.casefold()))
    compact = "".join(re.findall(r"[^\W_]+", text.casefold()))
    grams = {compact[i : i + 3] for i in range(len(compact) - 2)}
    return tokens, grams


def dice(left: set[str], right: set[str]) -> float:
    total = len(left) + len(right)
    return 2 * len(left & right) / total if total else 0.0


class Catalog:
    def __init__(self, entries: list[CatalogEntry]):
        self._index = [
            (entry, normalize_claim(entry.claim), features(normalize_claim(entry.claim)))
            for entry in entries
        ]

    @classmethod
    def load(cls, extra: Path | None = None) -> "Catalog":
        bundled = files("newfakenewsdetector").joinpath("data", "catalog.json")
        entries = catalog_schema.validate_json(bundled.read_bytes())
        if extra is not None:
            entries.extend(catalog_schema.validate_json(extra.read_bytes()))
        return cls(entries)

    def search(self, claim: str, language: Language) -> list[Match]:
        normalized = normalize_claim(claim)
        words, grams = features(normalized)
        exact = []
        related = []
        for entry, key, (entry_words, entry_grams) in self._index:
            if entry.language != language:
                continue
            if key == normalized:
                exact.append(
                    Match(
                        claim=entry.claim,
                        match="exact",
                        provider="catalog",
                        evidence=entry.evidence,
                    )
                )
                continue
            score = 0.35 * dice(words, entry_words) + 0.65 * dice(grams, entry_grams)
            if score >= MIN_RELATED_SCORE:
                related.append((score, entry))

        related.sort(key=lambda item: (-item[0], item[1].claim))
        return exact + [
            Match(claim=entry.claim, match="related", provider="catalog", evidence=entry.evidence)
            for _, entry in related[:RELATED_LIMIT]
        ]
