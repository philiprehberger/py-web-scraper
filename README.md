# philiprehberger-web-scraper

Lightweight web scraper with rate limiting and CSS selectors.

## Install

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

## Features

- Built-in rate limiting (token bucket)
- Retry with backoff on 429/5xx errors
- CSS selector API wrapping BeautifulSoup
- Crawl mode with same-domain filtering
- Link and image extraction
- CSV and JSON export helpers

## Options

```python
Scraper(
    rate_limit=2.0,        # max requests/second
    retry_attempts=3,      # retries on failure
    retry_delay=1.0,       # base delay between retries
    timeout=30.0,          # request timeout
    headers={...},         # custom headers
)
```

## License

MIT
