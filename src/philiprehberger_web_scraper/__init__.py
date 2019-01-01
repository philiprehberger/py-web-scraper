"""Lightweight web scraper with rate limiting and CSS selectors."""

from __future__ import annotations

import csv
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

__all__ = ["Scraper", "Page", "Element"]


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
    ) -> None:
        self._limiter = _RateLimiter(rate_limit)
        self._retry_attempts = retry_attempts
        self._retry_delay = retry_delay
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(headers or {})
        if "User-Agent" not in self._session.headers:
            self._session.headers["User-Agent"] = "philiprehberger-web-scraper/0.1.0"

    def get(self, url: str) -> Page:
        """Fetch a single page."""
        self._limiter.wait()

        last_error: Exception | None = None
        for attempt in range(self._retry_attempts):
            try:
                response = self._session.get(url, timeout=self._timeout)
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < self._retry_attempts - 1:
                        time.sleep(self._retry_delay * (2 ** attempt))
                        continue
                return Page(url, response.text, response.status_code)
            except requests.RequestException as e:
                last_error = e
                if attempt < self._retry_attempts - 1:
                    time.sleep(self._retry_delay * (2 ** attempt))

        raise last_error or RuntimeError(f"Failed to fetch {url}")

    def get_json(self, url: str) -> Any:
        """Fetch JSON from a URL."""
        self._limiter.wait()
        response = self._session.get(url, timeout=self._timeout)
        response.raise_for_status()
        return response.json()

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
    def export_csv(data: list[dict], path: str | Path) -> None:
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
