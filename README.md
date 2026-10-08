![SiteLens — a brass survey instrument exploring linked pages across a midnight atlas](readme-assets/cover.png)

# SiteLens

**Collect a website’s headings, links, and images into a structured JSON report.**

Start with a URL and follow links on the same network location. A fixed worker pool shares a bounded frontier while visited-page tracking prevents duplicate work. The crawler extracts page data and writes it in URL order to `report.json`.

## <img src="readme-assets/run.svg" width="24" height="24" alt=""> Start a crawl

Requires **Python 3.13+** and **uv**.

```bash
./launch https://learnwebscraping.dev/practice/ecommerce/ 3 20 --delay 0.5
```

```text
uv run main.py BASE_URL [MAX_CONCURRENCY] [MAX_PAGES]
```

The launcher prepares the Python environment with uv automatically. Run `./launch` without arguments to enter a URL interactively. It works from any directory when invoked by absolute path. You can also use `uv run main.py` with the same arguments.

Defaults are **5 workers** and **100 scheduled URLs**. Use positive integers. Failed fetches count toward the scheduled URL limit, so the report may contain fewer pages. The command reports crawl progress and writes `report.json` in the current directory. It fetches the seed only once, without dumping its HTML.

```bash
./launch https://example.com 3 50 --max-depth 2 --delay 0.5 --output reports/pages.json --errors reports/errors.json
```

| Option | Behavior |
| --- | --- |
| `--output PATH` | Sorted JSON page report; creates parent directories |
| `--errors PATH` | Optional sorted JSON list of failed URLs and errors |
| `--max-depth N` | Limit link hops from the seed; `0` fetches only the seed |
| `--delay SECONDS` | Minimum interval between request starts across all workers |
| `--timeout SECONDS` | Per-request timeout; default 30 seconds |
| `--retries N` | Retry transient connection failures, timeouts, and selected HTTP errors; default 2 |
| `--max-bytes N` | Maximum decoded response-body bytes; default 2,000,000 |
| `--quiet` | Hide per-page progress; retain final summary |
| `--ignore-robots` | Explicitly disable robots.txt checks |

Robots.txt is checked by default, including before following redirects. A missing file (404) allows crawling; other HTTP failures, redirects on robots.txt, or connection errors block the crawl. A declared `Crawl-delay` raises the configured request interval. Parsing uses Python's [RobotFileParser](https://docs.python.org/3/library/urllib.robotparser.html); this is not a complete implementation of every robots directive.

Redirects are followed only within the original network location and relative links use the final page URL. The original report field names are preserved. Report replacement is atomic, so a failed serialization leaves an existing report intact. A run with no successful pages returns exit status 1; partial success returns 0 and failures are available through `--errors`. Ctrl+C returns 130 and closes workers and connections; interrupted crawls do not write a new report.

## <img src="readme-assets/design.svg" width="24" height="24" alt=""> Follow the links, keep the structure

![Crawler workflow: seed, concurrent fetch, extraction, JSON](readme-assets/workflow.svg)

| Report field | Content |
| --- | --- |
| `url` | Page URL |
| `heading` | First `h1`, falling back to `h2` |
| `first_paragraph` | First paragraph in `main`, or in the page if `main` is absent |
| `outgoing_links` | Links resolved against the page URL |
| `image_urls` | Image sources resolved against the page URL |

![Report produced by the project extractor on a small local HTML fixture](readme-assets/report.png)

<sub>Local demonstration fixture; no live website data.</sub>

## <img src="readme-assets/code.svg" width="24" height="24" alt=""> Explore the implementation

| File | Responsibility |
| --- | --- |
| `main.py` | CLI, shared session, workers, request policies, and crawl limits |
| `crawl.py` | URL normalization and Beautiful Soup extraction |
| `json_report.py` | Sorted, indented, atomic JSON output |
| `test_crawl.py` | Extraction compatibility tests |
| `test_async_crawler.py` | Local HTTP integration, scheduling, cancellation, CLI, and report tests |

The crawler processes HTML responses without rendering JavaScript. Visit identity uses the network location and path, ignoring query strings and trailing slashes. Outgoing links can appear in the report even when their destinations are outside the crawl scope. The frontier holds at most the configured number of scheduled URLs, and only the fixed workers fetch pages. HTML extraction parses each page once. Requests use a shared [aiohttp session](https://docs.aiohttp.org/en/stable/client_quickstart.html).

## <img src="readme-assets/learn.svg" width="24" height="24" alt=""> Verify the crawler

```bash
uv run python -m unittest -v
```

Tests use a local HTTP server and require no external websites. GitHub Actions runs them on every push and pull request.

This project explores async workers, queues, shared state, cancellation, request policies, HTML parsing, and structured output.

---

Built by **[Abdulrahman M. Yaqyn](https://yaqyn.dev)** through the [Boot.dev](https://www.boot.dev) curriculum.
