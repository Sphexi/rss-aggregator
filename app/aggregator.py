import datetime as dt
import logging
import re
import time
from dataclasses import dataclass
from typing import List, Optional

import feedparser
import requests
from feedgen.feed import FeedGenerator

from .config import AppConfig, FilterRule, FeedConfig

log = logging.getLogger("rss_aggregator")


@dataclass(frozen=True)
class AggregatedItem:
    link: str
    title: str
    summary: str
    content: str
    published: dt.datetime
    guid: str


def _utc_from_struct_time(st):
    if not st:
        return None
    try:
        return dt.datetime(*st[:6], tzinfo=dt.timezone.utc)
    except Exception:
        return None


def _pick_published(entry):
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        d = _utc_from_struct_time(entry.get(key))
        if d:
            return d
    return None


def _compile_rule(rule: FilterRule):
    flags = 0
    if "i" in rule.flags:
        flags |= re.IGNORECASE
    if "m" in rule.flags:
        flags |= re.MULTILINE
    if "s" in rule.flags:
        flags |= re.DOTALL
    return re.compile(rule.value, flags=flags)


def _matches_any(text: str, rules: List[FilterRule]) -> bool:
    if not rules:
        return True
    if not text:
        return False

    for r in rules:
        if r.type == "keyword":
            if r.value.lower() in text.lower():
                return True
        else:
            pat = _compile_rule(r)
            if pat.search(text):
                return True
    return False


class RssAggregator:
    def __init__(self, config: AppConfig, user_agent: str, max_items: int = 15):
        self.config = config
        self.user_agent = user_agent
        self.max_items = max_items
        self.current_items: List[AggregatedItem] = []
        self.last_refresh_message = "never"
        self.last_refresh_ok = False
        self.last_refresh_utc: Optional[dt.datetime] = None

    def refresh(self):
        log.info("Starting refresh cycle")
        start = time.time()
        try:
            items: List[AggregatedItem] = []
            seen_links = set()

            for feed in self.config.feeds:
                log.info(f"Fetching feed id={feed.id} url={feed.url}")
                resp = requests.get(
                    feed.url,
                    headers={"User-Agent": self.user_agent},
                    timeout=10,
                )
                resp.raise_for_status()
                parsed = feedparser.parse(resp.content)

                for entry in parsed.entries:
                    link = (entry.get("link") or "").strip()
                    if not link:
                        continue

                    published = _pick_published(entry)
                    if not published:
                        continue

                    title = (entry.get("title") or "").strip()
                    summary = (entry.get("summary") or "").strip()

                    content = ""
                    if entry.get("content"):
                        content = entry["content"][0].get("value", "").strip()

                    blob = "\n".join([x for x in (title, summary, content) if x])

                    if not _matches_any(blob, feed.filters):
                        continue
                    if not _matches_any(blob, self.config.master_patterns):
                        continue

                    if link in seen_links:
                        continue
                    seen_links.add(link)

                    guid = entry.get("id") or link

                    items.append(
                        AggregatedItem(
                            link=link,
                            title=title or link,
                            summary=summary,
                            content=content,
                            published=published,
                            guid=guid,
                        )
                    )

            items.sort(key=lambda x: x.published, reverse=True)
            self.current_items = items[: self.max_items]

            self.last_refresh_ok = True
            self.last_refresh_utc = dt.datetime.now(dt.timezone.utc)
            self.last_refresh_message = f"OK - {len(self.current_items)} items"

            log.info(self.last_refresh_message)

        except Exception as e:
            self.last_refresh_ok = False
            self.last_refresh_utc = dt.datetime.now(dt.timezone.utc)
            self.last_refresh_message = f"FAILED - {e}"
            log.exception("Refresh failed")

        log.info(f"Refresh cycle complete in {time.time() - start:.2f}s")

    def build_rss_xml(self, title: str, description: str, link: str):
        fg = FeedGenerator()
        fg.title(title)
        fg.description(description)
        fg.link(href=link, rel="alternate")
        fg.language("en")

        for item in self.current_items:
            fe = fg.add_entry()
            fe.id(item.guid)
            fe.title(item.title)
            fe.link(href=item.link)
            fe.pubDate(item.published)
            fe.description(item.summary or item.content or "")

        return fg.rss_str(pretty=True)
