"""Lightweight web scraper with rate limiting and CSS selectors."""

from __future__ import annotations

import csv
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

__all__ = [
    "Scraper",
    "Page",
    "Element",
    "ResponseCache",
    "extract_table",
]


class Element:
    """Wrapper around a BeautifulSoup Tag with a cleaner API."""

    def __init__(self, tag: Tag) -> None:
        self._tag = tag

    @property
    def text(self) -> str:
        return self._tag.get_text(strip=True)

    @property
    def html(self) -> str:
        return str(self._tag)

    def attr(self, name: str, default: str | None = None) -> str | None:
        val = self._tag.get(name)
        if isinstance(val, list):
            return " ".join(val)
        return val or default

    def select_one(self, selector: str) -> Element | None:
        tag = self._tag.select_one(selector)
        return Element(tag) if tag else None

    def select_all(self, selector: str) -> list[Element]:
        return [Element(t) for t in self._tag.select(selector)]

    def __str__(self) -> str:
        return self.text


class Page:
    """A fetched web page with CSS selector support."""

    def __init__(self, url: str, html: str, status_code: int) -> None:
        self.url = url
        self.status_code = status_code
        self._soup = BeautifulSoup(html, "html.parser")

    @property
    def title(self) -> str | None:
        tag = self._soup.find("title")
        return tag.get_text(strip=True) if tag else None

    @property
    def text(self) -> str:
        return self._soup.get_text(separator=" ", strip=True)

    def select_one(self, selector: str) -> Element | None:
        tag = self._soup.select_one(selector)
        return Element(tag) if tag else None

    def select_all(self, selector: str) -> list[Element]:
        return [Element(t) for t in self._soup.select(selector)]

    def links(self, absolute: bool = True) -> list[str]:
        """Get all links on the page."""
        result = []
        for a in self._soup.find_all("a", href=True):
            href = a["href"]
            if absolute:
                href = urljoin(self.url, href)
            result.append(href)
        return result

    def images(self, absolute: bool = True) -> list[str]:
        """Get all image URLs on the page."""
        result = []
        for img in self._soup.find_all("img", src=True):
            src = img["src"]
            if absolute:
                src = urljoin(self.url, src)
            result.append(src)
        return result


def extract_table(page: Page, selector: str = "table") -> list[dict[str, str]]:
    """Extract an HTML table into a list of dicts.

    Uses the first ``<tr>`` of the matched table as header keys.  Each
    subsequent ``<tr>`` becomes a dict mapping header -> cell text.

    Args:
        page: A fetched :class:`Page` object.
        selector: CSS selector that matches a ``<table>`` element.

    Returns:
        A list of dictionaries, one per data row.
    """
    tag = page._soup.select_one(selector)
    if tag is None:
        return []

    rows = tag.find_all("tr")
    if len(rows) < 2:
        return []

    headers: list[str] = []
    for cell in rows[0].find_all(["th", "td"]):
        headers.append(cell.get_text(strip=True))

    data: list[dict[str, str]] = []
    for row in rows[1:]:
        cells = row.find_all(["td", "th"])
        row_dict: dict[str, str] = {}
        for idx, cell in enumerate(cells):
            key = headers[idx] if idx < len(headers) else f"col_{idx}"
            row_dict[key] = cell.get_text(strip=True)
        data.append(row_dict)

    return data


class ResponseCache:
    """Disk-backed response cache to avoid redundant HTTP requests.

    Cached pages are stored as JSON files keyed by a SHA-256 hash of the URL.
    """

    def __init__(self, cache_dir: str | Path = ".scraper_cache") -> None:
        self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _key(self, url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()

    def get(self, url: str) -> Page | None:
        """Return a cached :class:`Page` for *url*, or ``None``."""
        path = self._dir / f"{self._key(url)}.json"
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return Page(
            url=payload["url"],
            html=payload["html"],
            status_code=payload["status_code"],
        )

    def put(self, page: Page) -> None:
        """Store *page* in the cache."""
        path = self._dir / f"{self._key(page.url)}.json"
        payload = {
            "url": page.url,
            "html": str(page._soup),
            "status_code": page.status_code,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def clear(self) -> None:
        """Remove all cached responses."""
        for f in self._dir.glob("*.json"):
            f.unlink()


class _RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, rate: float) -> None:
        self._rate = rate  # requests per second
        self._min_interval = 1.0 / rate if rate > 0 else 0
        self._last_request = 0.0

    def wait(self) -> None:
        if self._min_interval <= 0:
            return
        now = time.monotonic()
        elapsed = now - self._last_request
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request = time.monotonic()


class Scraper:
    """Web scraper with rate limiting, retry, and CSS selector extraction."""

    def __init__(
        self,
        rate_limit: float = 2.0,
        retry_attempts: int = 3,
        retry_delay: float = 1.0,
        timeout: float = 30.0,
        headers: dict[str, str] | None = None,
        respect_robots: bool = False,
        cache: ResponseCache | None = None,
        proxies: list[str] | None = None,
    ) -> None:
        self._limiter = _RateLimiter(rate_limit)
        self._retry_attempts = retry_attempts
        self._retry_delay = retry_delay
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(headers or {})
        if "User-Agent" not in self._session.headers:
            self._session.headers["User-Agent"] = "philiprehberger-web-scraper/0.2.0"
        self._cache = cache
        self._proxies: list[str] = list(proxies) if proxies else []
        self._proxy_index: int = 0

    def _next_proxy(self) -> dict[str, str] | None:
        """Return the next proxy dict for requests, or ``None``."""
        if not self._proxies:
            return None
        proxy = self._proxies[self._proxy_index % len(self._proxies)]
        self._proxy_index += 1
        return {"http": proxy, "https": proxy}

    def get(self, url: str) -> Page:
        """Fetch a single page.

        Results are served from cache when a :class:`ResponseCache` is
        configured and the URL has been fetched before.  Transient errors
        (HTTP 429 and 503) trigger automatic retry with exponential backoff.
        """
        if self._cache is not None:
            cached = self._cache.get(url)
            if cached is not None:
                return cached

        self._limiter.wait()

        last_error: Exception | None = None
        for attempt in range(self._retry_attempts):
            try:
                proxy = self._next_proxy()
                response = self._session.get(
                    url,
                    timeout=self._timeout,
                    proxies=proxy,  # type: ignore[arg-type]
                )
                if response.status_code in (429, 503) or response.status_code >= 500:
                    if attempt < self._retry_attempts - 1:
                        time.sleep(self._retry_delay * (2 ** attempt))
                        continue
                page = Page(url, response.text, response.status_code)
                if self._cache is not None:
                    self._cache.put(page)
                return page
            except requests.RequestException as e:
                last_error = e
                if attempt < self._retry_attempts - 1:
                    time.sleep(self._retry_delay * (2 ** attempt))

        raise last_error or RuntimeError(f"Failed to fetch {url}")

    def get_json(self, url: str) -> Any:
        """Fetch JSON from a URL."""
        self._limiter.wait()
        proxy = self._next_proxy()
        response = self._session.get(
            url,
            timeout=self._timeout,
            proxies=proxy,  # type: ignore[arg-type]
        )
        response.raise_for_status()
        return response.json()

    def follow_links(
        self,
        start_url: str,
        selector: str,
        max_pages: int = 50,
    ) -> Iterator[Page]:
        """Follow links matching *selector* across paginated content.

        Fetches *start_url*, then repeatedly follows the first link matching
        *selector* until no match is found or *max_pages* is reached.

        Args:
            start_url: The first page to fetch.
            selector: CSS selector for the "next" link element.
            max_pages: Maximum number of pages to yield.
        """
        url: str | None = start_url
        visited: set[str] = set()
        pages_yielded = 0

        while url and url not in visited and pages_yielded < max_pages:
            visited.add(url)
            try:
                page = self.get(url)
            except Exception:
                break

            yield page
            pages_yielded += 1

            next_el = page.select_one(selector)
            if next_el:
                href = next_el.attr("href")
                url = urljoin(page.url, href) if href else None
            else:
                url = None

    def crawl(
        self,
        start_url: str,
        max_pages: int = 50,
        same_domain: bool = True,
        next_selector: str | None = None,
    ) -> Iterator[Page]:
        """Crawl pages starting from a URL.

        Args:
            start_url: Starting URL.
            max_pages: Maximum pages to crawl.
            same_domain: Only follow links on the same domain.
            next_selector: CSS selector for the "next page" link.
        """
        visited: set[str] = set()
        queue: list[str] = [start_url]
        domain = urlparse(start_url).netloc
        pages_yielded = 0

        while queue and pages_yielded < max_pages:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)

            try:
                page = self.get(url)
            except Exception:
                continue

            yield page
            pages_yielded += 1

            if next_selector:
                next_link = page.select_one(next_selector)
                if next_link:
                    href = next_link.attr("href")
                    if href:
                        next_url = urljoin(url, href)
                        if next_url not in visited:
                            queue.append(next_url)
            else:
                for link in page.links():
                    if link in visited:
                        continue
                    if same_domain and urlparse(link).netloc != domain:
                        continue
                    queue.append(link)

    @staticmethod
    def export_csv(data: list[dict[str, Any]], path: str | Path) -> None:
        """Export list of dicts to CSV."""
        if not data:
            return
        path = Path(path)
        headers = list(data[0].keys())
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(data)

    @staticmethod
    def export_json(data: Any, path: str | Path, indent: int = 2) -> None:
        """Export data to JSON."""
        Path(path).write_text(json.dumps(data, indent=indent, default=str, ensure_ascii=False))
