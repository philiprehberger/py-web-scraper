# philiprehberger-web-scraper

[![Tests](https://github.com/philiprehberger/py-web-scraper/actions/workflows/publish.yml/badge.svg)](https://github.com/philiprehberger/py-web-scraper/actions/workflows/publish.yml)
[![PyPI version](https://img.shields.io/pypi/v/philiprehberger-web-scraper.svg)](https://pypi.org/project/philiprehberger-web-scraper/)
[![Last updated](https://img.shields.io/github/last-commit/philiprehberger/py-web-scraper)](https://github.com/philiprehberger/py-web-scraper/commits/main)

Lightweight web scraper with rate limiting and CSS selectors.

## Installation

```bash
pip install philiprehberger-web-scraper
```

## Usage

```python
from philiprehberger_web_scraper import Scraper

scraper = Scraper(rate_limit=2.0, retry_attempts=3)

# Fetch a single page
page = scraper.get("https://example.com")
titles = page.select_all("h2.title")
link = page.select_one("a.next")
all_links = page.links()

# Extract data
for el in page.select_all(".product"):
    print(el.select_one(".name").text)
    print(el.select_one("a").attr("href"))

# Crawl multiple pages
for page in scraper.crawl("https://example.com/blog", max_pages=20):
    for article in page.select_all("article"):
        print(article.select_one("h2").text)

# Export
Scraper.export_csv(data, "output.csv")
Scraper.export_json(data, "output.json")
```

### Retry with Backoff

Transient HTTP errors (429 and 503) are retried automatically with exponential backoff. Configure the number of attempts and base delay:

```python
from philiprehberger_web_scraper import Scraper

scraper = Scraper(retry_attempts=5, retry_delay=2.0)
page = scraper.get("https://example.com/api")
```

### Response Caching

Cache fetched pages to disk so repeated requests for the same URL skip the network entirely:

```python
from philiprehberger_web_scraper import Scraper, ResponseCache

cache = ResponseCache(cache_dir=".scraper_cache")
scraper = Scraper(cache=cache)

page = scraper.get("https://example.com")  # fetches from network
page = scraper.get("https://example.com")  # served from disk cache

cache.clear()  # remove all cached responses
```

### Cache TTL

Expire cached entries after a number of seconds. Stale files are deleted on the next read so the cache directory does not grow unbounded:

```python
from philiprehberger_web_scraper import ResponseCache

cache = ResponseCache(cache_dir=".scraper_cache", ttl=3600)  # 1 hour
```

### Table Extraction

Pull an HTML table into a list of dicts using `extract_table()`. Use `extract_tables()` to pull every matching table on the page:

```python
from philiprehberger_web_scraper import Scraper, extract_table, extract_tables

scraper = Scraper()
page = scraper.get("https://example.com/data")

# First matching table
rows = extract_table(page, "table#prices")
# [{"Product": "Widget", "Price": "$9.99"}, ...]

# All tables on the page
all_tables = extract_tables(page, "table")
# [[{...}, ...], [{...}, ...]]
```

### Following Paginated Links

Use `follow_links()` to crawl paginated content by following a CSS-selected link on each page:

```python
from philiprehberger_web_scraper import Scraper

scraper = Scraper()
for page in scraper.follow_links("https://example.com/page/1", "a.next-page", max_pages=10):
    for item in page.select_all(".result"):
        print(item.text)
```

### Proxy Rotation

Distribute requests across multiple proxies by passing a list of proxy URLs:

```python
from philiprehberger_web_scraper import Scraper

scraper = Scraper(proxies=[
    "http://proxy1:8080",
    "http://proxy2:8080",
    "http://proxy3:8080",
])
page = scraper.get("https://example.com")  # uses proxy1
page = scraper.get("https://example.com/2")  # uses proxy2
```

### Rotating User Agents

Rotate the `User-Agent` header round-robin across requests:

```python
from philiprehberger_web_scraper import Scraper

scraper = Scraper(user_agents=[
    "Mozilla/5.0 (X11; Linux x86_64) Firefox/130.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) Safari/17.5",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/127.0.0.0",
])
page = scraper.get("https://example.com")  # uses agent #1
page = scraper.get("https://example.com/2")  # uses agent #2
```

## API

| Function / Class | Description |
|------------------|-------------|
| `Scraper(rate_limit, retry_attempts, retry_delay, timeout, headers, cache, proxies, user_agents)` | Web scraper with rate limiting, retry, caching, proxy rotation, and User-Agent rotation |
| `Scraper.get(url)` | Fetch a single page with retry and optional caching |
| `Scraper.get_json(url)` | Fetch JSON from a URL |
| `Scraper.follow_links(start_url, selector, max_pages)` | Follow paginated links matching a CSS selector |
| `Scraper.crawl(start_url, max_pages, same_domain, next_selector)` | Crawl pages starting from a URL |
| `Scraper.export_csv(data, path)` | Export list of dicts to CSV |
| `Scraper.export_json(data, path, indent)` | Export data to JSON |
| `Page` | A fetched web page with `select_one()`, `select_all()`, `links()`, `images()`, and `title`/`text` properties |
| `Element` | Wrapper around a parsed element with `text`, `html`, `attr()`, `select_one()`, `select_all()` |
| `ResponseCache(cache_dir, ttl=None)` | Disk-backed response cache with optional TTL; `get()`, `put()`, and `clear()` methods |
| `extract_table(page, selector)` | Extract the first matching HTML table into a list of dicts |
| `extract_tables(page, selector)` | Extract every matching HTML table; returns a list of row-dict lists |

## Development

```bash
pip install -e .
python -m pytest tests/ -v
```

## Support

If you find this project useful:

⭐ [Star the repo](https://github.com/philiprehberger/py-web-scraper)

🐛 [Report issues](https://github.com/philiprehberger/py-web-scraper/issues?q=is%3Aissue+is%3Aopen+label%3Abug)

💡 [Suggest features](https://github.com/philiprehberger/py-web-scraper/issues?q=is%3Aissue+is%3Aopen+label%3Aenhancement)

❤️ [Sponsor development](https://github.com/sponsors/philiprehberger)

🌐 [All Open Source Projects](https://philiprehberger.com/open-source-packages)

💻 [GitHub Profile](https://github.com/philiprehberger)

🔗 [LinkedIn Profile](https://www.linkedin.com/in/philiprehberger)

## License

[MIT](LICENSE)
