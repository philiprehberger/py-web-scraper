"""Tests for Page and Element classes."""

from __future__ import annotations

from philiprehberger_web_scraper import Element, Page


SAMPLE_HTML = """
<html>
<head><title>Test Page</title></head>
<body>
  <h1>Hello</h1>
  <p class="intro">Welcome to the site.</p>
  <a href="/about">About</a>
  <a href="https://other.com/ext">External</a>
  <img src="/logo.png" />
  <img src="https://cdn.example.com/pic.jpg" />
  <div class="item">
    <span class="name">Widget</span>
    <a href="/widget">Link</a>
  </div>
</body>
</html>
"""


def test_page_title() -> None:
    page = Page("https://example.com", SAMPLE_HTML, 200)
    assert page.title == "Test Page"


def test_page_title_missing() -> None:
    page = Page("https://example.com", "<html><body>No title</body></html>", 200)
    assert page.title is None


def test_page_text() -> None:
    page = Page("https://example.com", SAMPLE_HTML, 200)
    assert "Hello" in page.text
    assert "Welcome to the site." in page.text


def test_page_select_one() -> None:
    page = Page("https://example.com", SAMPLE_HTML, 200)
    el = page.select_one("p.intro")
    assert el is not None
    assert el.text == "Welcome to the site."


def test_page_select_one_missing() -> None:
    page = Page("https://example.com", SAMPLE_HTML, 200)
    assert page.select_one("div.nonexistent") is None


def test_page_select_all() -> None:
    page = Page("https://example.com", SAMPLE_HTML, 200)
    links = page.select_all("a")
    assert len(links) == 3


def test_page_links_absolute() -> None:
    page = Page("https://example.com", SAMPLE_HTML, 200)
    links = page.links(absolute=True)
    assert "https://example.com/about" in links
    assert "https://other.com/ext" in links


def test_page_links_relative() -> None:
    page = Page("https://example.com", SAMPLE_HTML, 200)
    links = page.links(absolute=False)
    assert "/about" in links


def test_page_images_absolute() -> None:
    page = Page("https://example.com", SAMPLE_HTML, 200)
    images = page.images(absolute=True)
    assert "https://example.com/logo.png" in images
    assert "https://cdn.example.com/pic.jpg" in images


def test_page_images_relative() -> None:
    page = Page("https://example.com", SAMPLE_HTML, 200)
    images = page.images(absolute=False)
    assert "/logo.png" in images


def test_element_text() -> None:
    page = Page("https://example.com", SAMPLE_HTML, 200)
    el = page.select_one("h1")
    assert el is not None
    assert el.text == "Hello"


def test_element_html() -> None:
    page = Page("https://example.com", SAMPLE_HTML, 200)
    el = page.select_one("h1")
    assert el is not None
    assert "<h1>" in el.html


def test_element_attr() -> None:
    page = Page("https://example.com", SAMPLE_HTML, 200)
    el = page.select_one("a")
    assert el is not None
    assert el.attr("href") == "/about"


def test_element_attr_default() -> None:
    page = Page("https://example.com", SAMPLE_HTML, 200)
    el = page.select_one("h1")
    assert el is not None
    assert el.attr("data-foo", "fallback") == "fallback"


def test_element_select_one_nested() -> None:
    page = Page("https://example.com", SAMPLE_HTML, 200)
    item = page.select_one("div.item")
    assert item is not None
    name = item.select_one("span.name")
    assert name is not None
    assert name.text == "Widget"


def test_element_select_all_nested() -> None:
    page = Page("https://example.com", SAMPLE_HTML, 200)
    item = page.select_one("div.item")
    assert item is not None
    children = item.select_all("*")
    assert len(children) >= 2


def test_element_str() -> None:
    page = Page("https://example.com", SAMPLE_HTML, 200)
    el = page.select_one("h1")
    assert el is not None
    assert str(el) == "Hello"
