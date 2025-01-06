"""Tests for ResponseCache."""

from __future__ import annotations

import json
from pathlib import Path

from philiprehberger_web_scraper import Page, ResponseCache


def test_cache_miss(tmp_path: Path) -> None:
    cache = ResponseCache(cache_dir=tmp_path / "cache")
    assert cache.get("https://example.com") is None


def test_cache_put_and_get(tmp_path: Path) -> None:
    cache = ResponseCache(cache_dir=tmp_path / "cache")
    page = Page("https://example.com", "<html><body>Hello</body></html>", 200)
    cache.put(page)

    cached = cache.get("https://example.com")
    assert cached is not None
    assert cached.url == "https://example.com"
    assert cached.status_code == 200
    assert "Hello" in cached.text


def test_cache_different_urls(tmp_path: Path) -> None:
    cache = ResponseCache(cache_dir=tmp_path / "cache")
    page1 = Page("https://a.com", "<p>A</p>", 200)
    page2 = Page("https://b.com", "<p>B</p>", 200)
    cache.put(page1)
    cache.put(page2)

    assert cache.get("https://a.com") is not None
    assert cache.get("https://b.com") is not None
    assert cache.get("https://c.com") is None


def test_cache_clear(tmp_path: Path) -> None:
    cache = ResponseCache(cache_dir=tmp_path / "cache")
    cache.put(Page("https://example.com", "<p>Hi</p>", 200))
    assert cache.get("https://example.com") is not None

    cache.clear()
    assert cache.get("https://example.com") is None


def test_cache_creates_directory(tmp_path: Path) -> None:
    cache_dir = tmp_path / "deeply" / "nested" / "cache"
    cache = ResponseCache(cache_dir=cache_dir)
    assert cache_dir.exists()


def test_cache_stores_json_file(tmp_path: Path) -> None:
    cache = ResponseCache(cache_dir=tmp_path / "cache")
    cache.put(Page("https://example.com", "<p>Data</p>", 200))

    files = list((tmp_path / "cache").glob("*.json"))
    assert len(files) == 1

    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["url"] == "https://example.com"
    assert payload["status_code"] == 200
