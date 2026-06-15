"""Tests for ResponseCache."""

from __future__ import annotations

import json
import os
import time
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


def test_cache_ttl_returns_fresh(tmp_path: Path) -> None:
    cache = ResponseCache(cache_dir=tmp_path / "cache", ttl=60.0)
    cache.put(Page("https://example.com", "<p>Fresh</p>", 200))

    cached = cache.get("https://example.com")
    assert cached is not None
    assert "Fresh" in cached.text


def test_cache_ttl_expires(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache = ResponseCache(cache_dir=cache_dir, ttl=0.05)
    cache.put(Page("https://example.com", "<p>Stale</p>", 200))

    time.sleep(0.1)
    assert cache.get("https://example.com") is None
    # Expired file is removed
    assert list(cache_dir.glob("*.json")) == []


def test_cache_ttl_zero_always_expires(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache = ResponseCache(cache_dir=cache_dir, ttl=0)
    cache.put(Page("https://example.com", "<p>X</p>", 200))
    # Backdate the file so any positive age exceeds ttl=0
    path = next(cache_dir.glob("*.json"))
    past = time.time() - 1
    os.utime(path, (past, past))
    assert cache.get("https://example.com") is None


def test_cache_no_ttl_keeps_indefinitely(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache = ResponseCache(cache_dir=cache_dir)  # ttl=None default
    cache.put(Page("https://example.com", "<p>Keep</p>", 200))
    # Backdate well into the past
    path = next(cache_dir.glob("*.json"))
    very_old = time.time() - 365 * 24 * 3600
    os.utime(path, (very_old, very_old))
    assert cache.get("https://example.com") is not None
