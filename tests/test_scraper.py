"""Tests for Scraper — retry, caching, proxy rotation, follow_links."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, PropertyMock

import requests

from philiprehberger_web_scraper import Page, ResponseCache, Scraper


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(
    status_code: int = 200,
    text: str = "<html><body>OK</body></html>",
) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.text = text
    return resp


# ---------------------------------------------------------------------------
# Retry with backoff
# ---------------------------------------------------------------------------


class TestRetry:
    """Retry logic on transient HTTP errors."""

    @patch("time.sleep")
    @patch("requests.Session.get")
    def test_retry_on_429(self, mock_get: MagicMock, mock_sleep: MagicMock) -> None:
        mock_get.side_effect = [
            _mock_response(429, "Rate limited"),
            _mock_response(200, "<p>OK</p>"),
        ]
        scraper = Scraper(rate_limit=0, retry_attempts=3, retry_delay=1.0)
        page = scraper.get("https://example.com")

        assert page.status_code == 200
        assert mock_get.call_count == 2

    @patch("time.sleep")
    @patch("requests.Session.get")
    def test_retry_on_503(self, mock_get: MagicMock, mock_sleep: MagicMock) -> None:
        mock_get.side_effect = [
            _mock_response(503, "Unavailable"),
            _mock_response(200, "<p>OK</p>"),
        ]
        scraper = Scraper(rate_limit=0, retry_attempts=3, retry_delay=1.0)
        page = scraper.get("https://example.com")

        assert page.status_code == 200

    @patch("time.sleep")
    @patch("requests.Session.get")
    def test_retry_exhausted_returns_last(
        self, mock_get: MagicMock, mock_sleep: MagicMock
    ) -> None:
        mock_get.return_value = _mock_response(503, "Down")
        scraper = Scraper(rate_limit=0, retry_attempts=2, retry_delay=0.1)
        page = scraper.get("https://example.com")

        assert page.status_code == 503

    @patch("time.sleep")
    @patch("requests.Session.get")
    def test_retry_on_request_exception(
        self, mock_get: MagicMock, mock_sleep: MagicMock
    ) -> None:
        mock_get.side_effect = [
            requests.ConnectionError("timeout"),
            _mock_response(200, "<p>Recovered</p>"),
        ]
        scraper = Scraper(rate_limit=0, retry_attempts=3, retry_delay=0.1)
        page = scraper.get("https://example.com")

        assert page.status_code == 200

    @patch("time.sleep")
    @patch("requests.Session.get")
    def test_retry_raises_after_all_failures(
        self, mock_get: MagicMock, mock_sleep: MagicMock
    ) -> None:
        mock_get.side_effect = requests.ConnectionError("down")
        scraper = Scraper(rate_limit=0, retry_attempts=2, retry_delay=0.1)

        try:
            scraper.get("https://example.com")
            assert False, "Should have raised"
        except requests.ConnectionError:
            pass

    @patch("time.sleep")
    @patch("requests.Session.get")
    def test_exponential_backoff_delays(
        self, mock_get: MagicMock, mock_sleep: MagicMock
    ) -> None:
        mock_get.side_effect = [
            _mock_response(429),
            _mock_response(429),
            _mock_response(200, "<p>OK</p>"),
        ]
        scraper = Scraper(rate_limit=0, retry_attempts=3, retry_delay=2.0)
        scraper.get("https://example.com")

        sleep_calls = [c.args[0] for c in mock_sleep.call_args_list]
        assert 2.0 in sleep_calls  # 2.0 * 2^0
        assert 4.0 in sleep_calls  # 2.0 * 2^1


# ---------------------------------------------------------------------------
# Caching integration
# ---------------------------------------------------------------------------


class TestCaching:
    """Response caching via Scraper."""

    @patch("time.sleep")
    @patch("requests.Session.get")
    def test_cache_avoids_second_request(
        self, mock_get: MagicMock, mock_sleep: MagicMock, tmp_path: Path
    ) -> None:
        mock_get.return_value = _mock_response(200, "<p>Cached</p>")
        cache = ResponseCache(cache_dir=tmp_path / "cache")
        scraper = Scraper(rate_limit=0, cache=cache)

        page1 = scraper.get("https://example.com")
        page2 = scraper.get("https://example.com")

        assert mock_get.call_count == 1
        assert page2.status_code == 200
        assert "Cached" in page2.text

    @patch("time.sleep")
    @patch("requests.Session.get")
    def test_cache_miss_fetches(
        self, mock_get: MagicMock, mock_sleep: MagicMock, tmp_path: Path
    ) -> None:
        mock_get.return_value = _mock_response(200, "<p>Fresh</p>")
        cache = ResponseCache(cache_dir=tmp_path / "cache")
        scraper = Scraper(rate_limit=0, cache=cache)

        page = scraper.get("https://example.com")
        assert mock_get.call_count == 1
        assert "Fresh" in page.text


# ---------------------------------------------------------------------------
# Proxy rotation
# ---------------------------------------------------------------------------


class TestProxyRotation:
    """Proxy rotation across requests."""

    @patch("time.sleep")
    @patch("requests.Session.get")
    def test_proxies_rotate(self, mock_get: MagicMock, mock_sleep: MagicMock) -> None:
        mock_get.return_value = _mock_response(200, "<p>OK</p>")
        proxies = ["http://proxy1:8080", "http://proxy2:8080", "http://proxy3:8080"]
        scraper = Scraper(rate_limit=0, proxies=proxies)

        scraper.get("https://a.com")
        scraper.get("https://b.com")
        scraper.get("https://c.com")
        scraper.get("https://d.com")  # wraps to proxy1

        calls = mock_get.call_args_list
        assert calls[0].kwargs.get("proxies") == {"http": "http://proxy1:8080", "https": "http://proxy1:8080"}
        assert calls[1].kwargs.get("proxies") == {"http": "http://proxy2:8080", "https": "http://proxy2:8080"}
        assert calls[2].kwargs.get("proxies") == {"http": "http://proxy3:8080", "https": "http://proxy3:8080"}
        assert calls[3].kwargs.get("proxies") == {"http": "http://proxy1:8080", "https": "http://proxy1:8080"}

    @patch("time.sleep")
    @patch("requests.Session.get")
    def test_no_proxies(self, mock_get: MagicMock, mock_sleep: MagicMock) -> None:
        mock_get.return_value = _mock_response(200, "<p>OK</p>")
        scraper = Scraper(rate_limit=0)

        scraper.get("https://example.com")
        assert mock_get.call_args.kwargs.get("proxies") is None

    @patch("time.sleep")
    @patch("requests.Session.get")
    def test_proxy_used_in_get_json(
        self, mock_get: MagicMock, mock_sleep: MagicMock
    ) -> None:
        resp = _mock_response(200)
        resp.json.return_value = {"key": "value"}
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        scraper = Scraper(rate_limit=0, proxies=["http://p:1234"])
        result = scraper.get_json("https://api.example.com/data")

        assert result == {"key": "value"}
        assert mock_get.call_args.kwargs.get("proxies") == {"http": "http://p:1234", "https": "http://p:1234"}


# ---------------------------------------------------------------------------
# follow_links
# ---------------------------------------------------------------------------


class TestFollowLinks:
    """follow_links pagination helper."""

    @patch("time.sleep")
    @patch("requests.Session.get")
    def test_follow_links_basic(
        self, mock_get: MagicMock, mock_sleep: MagicMock
    ) -> None:
        page1_html = '<html><body><p>Page 1</p><a class="next" href="/page2">Next</a></body></html>'
        page2_html = '<html><body><p>Page 2</p><a class="next" href="/page3">Next</a></body></html>'
        page3_html = "<html><body><p>Page 3</p></body></html>"

        mock_get.side_effect = [
            _mock_response(200, page1_html),
            _mock_response(200, page2_html),
            _mock_response(200, page3_html),
        ]

        scraper = Scraper(rate_limit=0)
        pages = list(scraper.follow_links("https://example.com/page1", "a.next"))

        assert len(pages) == 3
        assert "Page 1" in pages[0].text
        assert "Page 3" in pages[2].text

    @patch("time.sleep")
    @patch("requests.Session.get")
    def test_follow_links_max_pages(
        self, mock_get: MagicMock, mock_sleep: MagicMock
    ) -> None:
        pages_html = [
            '<html><body>Page 1<a class="next" href="/page2">Next</a></body></html>',
            '<html><body>Page 2<a class="next" href="/page3">Next</a></body></html>',
            '<html><body>Page 3<a class="next" href="/page4">Next</a></body></html>',
        ]
        mock_get.side_effect = [_mock_response(200, h) for h in pages_html]

        scraper = Scraper(rate_limit=0)
        pages = list(
            scraper.follow_links("https://example.com/page1", "a.next", max_pages=2)
        )
        assert len(pages) == 2

    @patch("time.sleep")
    @patch("requests.Session.get")
    def test_follow_links_no_next(
        self, mock_get: MagicMock, mock_sleep: MagicMock
    ) -> None:
        mock_get.return_value = _mock_response(200, "<html><body>End</body></html>")
        scraper = Scraper(rate_limit=0)
        pages = list(scraper.follow_links("https://example.com", "a.next"))

        assert len(pages) == 1

    @patch("time.sleep")
    @patch("requests.Session.get")
    def test_follow_links_avoids_revisit(
        self, mock_get: MagicMock, mock_sleep: MagicMock
    ) -> None:
        """A page linking back to itself should not cause an infinite loop."""
        html = '<html><body><a class="next" href="/self">Loop</a></body></html>'
        mock_get.return_value = _mock_response(200, html)

        scraper = Scraper(rate_limit=0)
        pages = list(
            scraper.follow_links("https://example.com/self", "a.next", max_pages=10)
        )
        assert len(pages) == 1


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------


class TestExport:
    """CSV and JSON export."""

    def test_export_csv(self, tmp_path: Path) -> None:
        data = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        path = tmp_path / "out.csv"
        Scraper.export_csv(data, path)
        content = path.read_text()
        assert "a,b" in content
        assert "1,2" in content

    def test_export_csv_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.csv"
        Scraper.export_csv([], path)
        assert not path.exists()

    def test_export_json(self, tmp_path: Path) -> None:
        data = {"key": "value"}
        path = tmp_path / "out.json"
        Scraper.export_json(data, path)
        assert '"key"' in path.read_text()
