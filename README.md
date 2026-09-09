# Async Web Crawler

An asynchronous web crawler built with Python, `aiohttp`, and Beautiful Soup.
It extracts page headings, first paragraphs, outgoing links, and image URLs,
then writes the collected data to `report.json`.

## Requirements

- Python 3.13+
- `uv`

Install dependencies with:

```bash
uv sync
```

## Usage

```bash
uv run main.py BASE_URL MAX_CONCURRENCY MAX_PAGES
```

For example:

```bash
uv run main.py https://learnwebscraping.dev/practice/ecommerce/ 3 20
```

The crawler prints progress and creates a sorted, formatted `report.json` file.

## Tests

```bash
uv run python -m unittest -v
```
