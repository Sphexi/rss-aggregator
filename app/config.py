import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class FilterRule:
    type: str  # "keyword" | "regex"
    value: str
    flags: str = ""  # e.g. "i"


@dataclass(frozen=True)
class FeedConfig:
    id: int
    url: str
    filters: List[FilterRule]


@dataclass(frozen=True)
class AppConfig:
    master_patterns: List[FilterRule]
    feeds: List[FeedConfig]


def _parse_rule(obj: Dict[str, Any]) -> FilterRule:
    rtype = (obj.get("type") or "").strip().lower()
    if rtype not in ("keyword", "regex"):
        raise ValueError(f"Invalid rule type: {rtype!r}")

    if rtype == "keyword":
        val = (obj.get("keyword") or "").strip()
        if not val:
            raise ValueError("Keyword rule requires non-empty 'keyword'")
        return FilterRule(type="keyword", value=val)

    pattern = obj.get("pattern")
    if not isinstance(pattern, str) or not pattern.strip():
        raise ValueError("Regex rule requires non-empty 'pattern'")

    flags = (obj.get("flags") or "").strip().lower()
    return FilterRule(type="regex", value=pattern, flags=flags)


def load_config(config_path: str) -> AppConfig:
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    master = [_parse_rule(x) for x in raw.get("master_patterns", [])]

    feeds: List[FeedConfig] = []
    for item in raw.get("urls", []):
        filters = [_parse_rule(x) for x in item.get("filters", [])]
        feeds.append(
            FeedConfig(
                id=item["id"],
                url=item["url"],
                filters=filters,
            )
        )

    return AppConfig(master_patterns=master, feeds=feeds)
