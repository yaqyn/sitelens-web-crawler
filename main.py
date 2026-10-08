"""Bounded asynchronous crawling with explicit request and scope policies."""
import argparse
import asyncio
import math
import sys
from urllib.parse import urlsplit, urljoin, urldefrag
from urllib.robotparser import RobotFileParser

import aiohttp
import requests

from crawl import extract_page_data, normalize_url
from json_report import write_json_report

USER_AGENT = "SiteLens/2.0"


def get_html(url):
    """Compatibility helper; the CLI uses the async session exclusively."""
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    if not response.headers.get("Content-Type", "").lower().startswith("text/html"):
        raise ValueError("expected text/html content")
    return response.text


def validate_url(url):
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL must be an absolute http:// or https:// address")
    if parsed.username or parsed.password:
        raise ValueError("URLs with embedded credentials are not supported")
    parsed.port  # Validate malformed ports before making a request.
    return url


class AsyncCrawler:
    def __init__(self, base_url, max_concurrency=5, max_pages=100, *,
                 timeout=30, retries=2, delay=0, max_depth=None,
                 respect_robots=True, max_bytes=2_000_000, quiet=False):
        validate_url(base_url)
        if max_concurrency < 1 or max_pages < 1 or max_bytes < 1:
            raise ValueError("Concurrency, page limit, and byte limit must be positive")
        if not math.isfinite(timeout) or not math.isfinite(delay) or timeout <= 0 or retries < 0 or delay < 0:
            raise ValueError("Timeout must be positive; retries and delay must be nonnegative")
        if max_depth is not None and max_depth < 0:
            raise ValueError("Depth must be nonnegative")
        self.base_url = urldefrag(base_url)[0]
        self.base_domain = urlsplit(base_url).netloc.lower()
        self.max_concurrency, self.max_pages = max_concurrency, max_pages
        self.timeout, self.retries, self.delay = timeout, retries, delay
        self.max_depth, self.max_bytes = max_depth, max_bytes
        self.respect_robots, self.quiet = respect_robots, quiet
        self.page_data, self.errors = {}, {}
        self.seen = set()
        self.queue = asyncio.Queue()
        self.all_tasks = set()
        self.session = None
        self.robots = None
        self.rate_lock = asyncio.Lock()
        self.next_request = 0

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout),
            headers={"User-Agent": USER_AGENT},
            connector=aiohttp.TCPConnector(limit=self.max_concurrency))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        for task in self.all_tasks:
            task.cancel()
        await asyncio.gather(*self.all_tasks, return_exceptions=True)
        await self.session.close()

    def in_scope(self, url):
        parsed = urlsplit(url)
        return (parsed.scheme in {"http", "https"} and
                parsed.netloc.lower() == self.base_domain and
                parsed.username is None and parsed.password is None)

    async def pace(self):
        async with self.rate_lock:
            loop = asyncio.get_running_loop()
            await asyncio.sleep(max(0, self.next_request - loop.time()))
            self.next_request = loop.time() + self.delay

    async def read_body(self, response):
        body = bytearray()
        async for chunk in response.content.iter_chunked(65536):
            body.extend(chunk)
            if len(body) > self.max_bytes:
                raise ValueError(f"Response exceeds {self.max_bytes} bytes")
        return body.decode(response.charset or "utf-8", errors="replace")

    async def load_robots(self):
        if not self.respect_robots:
            return
        parsed = urlsplit(self.base_url)
        url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        self.robots = RobotFileParser(url)
        try:
            await self.pace()
            async with self.session.get(url, allow_redirects=False) as response:
                if response.status == 404:
                    self.robots.allow_all = True
                elif response.status >= 400 or 300 <= response.status < 400:
                    self.robots.disallow_all = True
                    self.errors[url] = f"robots.txt returned HTTP {response.status}; crawl blocked"
                else:
                    self.robots.parse((await self.read_body(response)).splitlines())
                    self.delay = max(self.delay, self.robots.crawl_delay(USER_AGENT) or 0)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, LookupError) as error:
            self.robots.disallow_all = True
            self.errors[url] = f"Cannot read robots.txt; crawl blocked: {error}"

    async def get_html(self, url):
        for attempt in range(self.retries + 1):
            try:
                current = url
                for _ in range(11):
                    if not self.in_scope(current):
                        raise ValueError("Redirect leaves the crawl domain")
                    if self.robots and not self.robots.can_fetch(USER_AGENT, current):
                        raise ValueError("Blocked by robots.txt")
                    await self.pace()
                    async with self.session.get(current, allow_redirects=False) as response:
                        if response.status in {301, 302, 303, 307, 308}:
                            location = response.headers.get("Location")
                            if not location:
                                raise ValueError("Redirect has no Location header")
                            current = urldefrag(urljoin(current, location))[0]
                            continue
                        response.raise_for_status()
                        if not response.headers.get("Content-Type", "").lower().startswith("text/html"):
                            raise ValueError("expected text/html content")
                        return await self.read_body(response), current
                raise ValueError("Too many redirects")
            except aiohttp.ClientResponseError as error:
                if error.status not in {429, 500, 502, 503, 504} or attempt == self.retries:
                    raise
            except (aiohttp.ClientConnectionError, asyncio.TimeoutError):
                if attempt == self.retries:
                    raise
            await asyncio.sleep(min(2 ** attempt, 8))

    def enqueue(self, url, depth):
        url = urldefrag(url)[0]
        if not self.in_scope(url) or (self.max_depth is not None and depth > self.max_depth):
            return
        if self.robots and not self.robots.can_fetch(USER_AGENT, url):
            return
        normalized = normalize_url(url)
        if normalized in self.seen or len(self.seen) >= self.max_pages:
            return
        self.seen.add(normalized)
        self.queue.put_nowait((url, depth, normalized))

    async def worker(self):
        while True:
            url, depth, normalized = await self.queue.get()
            try:
                if not self.quiet:
                    print(f"crawling: {url}")
                html, final_url = await self.get_html(url)
                data = extract_page_data(html, final_url)
                self.page_data[normalized] = data
                for link in data["outgoing_links"]:
                    self.enqueue(link, depth + 1)
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, LookupError) as error:
                self.errors[url] = str(error) or type(error).__name__
                if not self.quiet:
                    print(f"failed: {url}: {self.errors[url]}", file=sys.stderr)
            finally:
                self.queue.task_done()

    async def crawl(self):
        if self.session is None:
            raise RuntimeError("Use 'async with AsyncCrawler(...)' before crawling")
        await self.load_robots()
        self.enqueue(self.base_url, 0)
        self.all_tasks = {asyncio.create_task(self.worker()) for _ in range(self.max_concurrency)}
        try:
            await self.queue.join()
        finally:
            for task in self.all_tasks:
                task.cancel()
            await asyncio.gather(*self.all_tasks, return_exceptions=True)
            self.all_tasks.clear()
        return self.page_data


async def crawl_site_async(base_url):
    async with AsyncCrawler(base_url) as crawler:
        return await crawler.crawl()


def positive_int(value):
    result = int(value)
    if result < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return result


async def main(argv=None):
    parser = argparse.ArgumentParser(description="Explore a website and export structured page data")
    parser.add_argument("base_url")
    parser.add_argument("max_concurrency", nargs="?", type=positive_int, default=5)
    parser.add_argument("max_pages", nargs="?", type=positive_int, default=100)
    parser.add_argument("--output", default="report.json")
    parser.add_argument("--errors", help="Optional JSON error report")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--delay", type=float, default=0)
    parser.add_argument("--max-depth", type=int)
    parser.add_argument("--max-bytes", type=positive_int, default=2_000_000)
    parser.add_argument("--ignore-robots", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    try:
        crawler = AsyncCrawler(args.base_url, args.max_concurrency, args.max_pages,
                               timeout=args.timeout, retries=args.retries, delay=args.delay,
                               max_depth=args.max_depth, max_bytes=args.max_bytes,
                               respect_robots=not args.ignore_robots, quiet=args.quiet)
    except ValueError as error:
        parser.error(str(error))
    try:
        async with crawler:
            pages = await crawler.crawl()
        write_json_report(pages, args.output)
        if args.errors:
            write_json_report({url: {"url": url, "error": error}
                               for url, error in crawler.errors.items()}, args.errors)
        print(f"Saved {len(pages)} pages to {args.output}; {len(crawler.errors)} failures")
        return 0 if pages else 1
    except (OSError, aiohttp.ClientError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130)
