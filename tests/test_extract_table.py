"""Tests for extract_table helper."""

from __future__ import annotations

from philiprehberger_web_scraper import Page, extract_table


TABLE_HTML = """
<html><body>
<table id="prices">
  <tr><th>Product</th><th>Price</th><th>Stock</th></tr>
  <tr><td>Widget</td><td>$9.99</td><td>42</td></tr>
  <tr><td>Gadget</td><td>$19.99</td><td>7</td></tr>
</table>
</body></html>
"""


def test_extract_table_basic() -> None:
    page = Page("https://example.com", TABLE_HTML, 200)
    rows = extract_table(page, "table#prices")
    assert len(rows) == 2
    assert rows[0] == {"Product": "Widget", "Price": "$9.99", "Stock": "42"}
    assert rows[1] == {"Product": "Gadget", "Price": "$19.99", "Stock": "7"}


def test_extract_table_default_selector() -> None:
    page = Page("https://example.com", TABLE_HTML, 200)
    rows = extract_table(page)
    assert len(rows) == 2


def test_extract_table_no_match() -> None:
    page = Page("https://example.com", "<html><body><p>No table</p></body></html>", 200)
    rows = extract_table(page, "table")
    assert rows == []


def test_extract_table_header_only() -> None:
    html = "<html><body><table><tr><th>A</th><th>B</th></tr></table></body></html>"
    page = Page("https://example.com", html, 200)
    rows = extract_table(page)
    assert rows == []


def test_extract_table_extra_cols() -> None:
    """Rows with more cells than headers get col_N fallback keys."""
    html = """
    <table>
      <tr><th>Name</th></tr>
      <tr><td>Alpha</td><td>Extra</td></tr>
    </table>
    """
    page = Page("https://example.com", html, 200)
    rows = extract_table(page)
    assert len(rows) == 1
    assert rows[0]["Name"] == "Alpha"
    assert rows[0]["col_1"] == "Extra"


def test_extract_table_th_in_body() -> None:
    """Tables that use <th> in body rows are handled."""
    html = """
    <table>
      <tr><th>Key</th><th>Value</th></tr>
      <tr><th>color</th><td>blue</td></tr>
    </table>
    """
    page = Page("https://example.com", html, 200)
    rows = extract_table(page)
    assert rows == [{"Key": "color", "Value": "blue"}]
