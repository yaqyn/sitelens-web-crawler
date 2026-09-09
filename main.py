import asyncio
import sys
from urllib.parse import urlsplit

import aiohttp
import requests

from crawl import extract_page_data, normalize_url
from json_report import write_json_report


def get_html(url):
    response = requests.get(url, headers={"User-Agent": "BootCrawler/1.0"})
    response.raise_for_status()
    if not response.headers.get("Content-Type", "").lower().startswith("text/html"):
        raise ValueError("expected text/html content")
    return response.text


class AsyncCrawler:
    def __init__(self, base_url, max_concurrency=5, max_pages=100):
        self.base_url = base_url
        self.base_domain = urlsplit(base_url).netloc
        self.page_data = {}
        self.lock = asyncio.Lock()
        self.max_concurrency = max_concurrency
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.max_pages = max_pages
        self.should_stop = False
        self.all_tasks = set()
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()

    async def add_page_visit(self, normalized_url):
        async with self.lock:
            if self.should_stop:
                return False
            if normalized_url in self.page_data:
                return False
            if len(self.page_data) >= self.max_pages:
                self.should_stop = True
                print("Reached maximum number of pages to crawl.")
                current_task = asyncio.current_task()
                for task in self.all_tasks:
                    if task is not current_task:
                        task.cancel()
                return False
            self.page_data[normalized_url] = None
            return True

    async def get_html(self, url):
        async with self.session.get(url, headers={"User-Agent": "BootCrawler/1.0"}) as response:
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "")
            if not content_type.lower().startswith("text/html"):
                raise ValueError(f"expected text/html content, got {content_type or 'unknown'}")
            return await response.text()

    async def crawl_page(self, current_url=None):
        if self.should_stop:
            return
        if current_url is None:
            current_url = self.base_url
        if urlsplit(current_url).netloc != self.base_domain:
            return

        normalized_url = normalize_url(current_url)
        if not await self.add_page_visit(normalized_url):
            return

        print(f"crawling: {current_url}")
        try:
            async with self.semaphore:
                html = await self.get_html(current_url)
        except asyncio.CancelledError:
            async with self.lock:
                self.page_data.pop(normalized_url, None)
            raise
        except (aiohttp.ClientError, ValueError) as error:
            print(f"failed to crawl {current_url}: {error}")
            async with self.lock:
                self.page_data.pop(normalized_url, None)
            return

        data = extract_page_data(html, current_url)
        async with self.lock:
            self.page_data[normalized_url] = data

        tasks = []
        for url in data["outgoing_links"]:
            task = asyncio.create_task(self.crawl_page(url))
            self.all_tasks.add(task)
            task.add_done_callback(self.all_tasks.discard)
            tasks.append(task)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def crawl(self):
        await self.crawl_page(self.base_url)
        return self.page_data


async def crawl_site_async(base_url):
    async with AsyncCrawler(base_url) as crawler:
        return await crawler.crawl()


async def main():
    if len(sys.argv) < 2:
        print("no website provided")
        sys.exit(1)

    if len(sys.argv) > 4:
        print("too many arguments provided")
        sys.exit(1)

    base_url = sys.argv[1]
    max_concurrency = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    max_pages = int(sys.argv[3]) if len(sys.argv) > 3 else 100
    print(f"starting crawl of: {base_url}")
    print(get_html(base_url))
    async with AsyncCrawler(base_url, max_concurrency, max_pages) as crawler:
        page_data = await crawler.crawl()
    print(f"found {len(page_data)} pages")
    write_json_report(page_data)


if __name__ == "__main__":
    asyncio.run(main())
