import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from aiohttp import web

from main import AsyncCrawler, main
from json_report import write_json_report


class TestAsyncCrawler(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.hits = []
        self.active = self.peak = self.flaky_attempts = 0
        self.robots_status = 200
        app = web.Application()
        app.router.add_get('/{path:.*}', self.handle)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        self.addAsyncCleanup(self.runner.cleanup)
        site = web.TCPSite(self.runner, '127.0.0.1', 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        self.base = f'http://127.0.0.1:{port}'

    async def handle(self, request):
        path = request.path
        self.hits.append(path)
        if path == '/robots.txt':
            return web.Response(text='User-agent: *\nDisallow: /private\n', status=self.robots_status)
        if path == '/redirect':
            raise web.HTTPFound('http://localhost:1/outside')
        if path == '/to-private':
            raise web.HTTPFound('/private')
        if path == '/binary':
            return web.Response(body=b'abc', content_type='application/octet-stream')
        if path == '/large':
            return web.Response(text='x' * 2000, content_type='text/html')
        if path == '/flaky':
            self.flaky_attempts += 1
            if self.flaky_attempts == 1:
                return web.Response(status=503)
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            await asyncio.sleep(0.1 if path == '/slow' else 0.01)
            if path == '/':
                links = ['/a', '/a#fragment', '/b', '/private', '/binary', '/redirect']
            elif path == '/wide':
                links = [f'/page{i}' for i in range(100)]
            else:
                links = ['/deep'] if path == '/a' else []
            html = '<h1>Page</h1><p>Text</p>' + ''.join(f'<a href="{link}">Link</a>' for link in links)
            return web.Response(text=html, content_type='text/html')
        finally:
            self.active -= 1

    async def crawl(self, path='/', **options):
        async with AsyncCrawler(self.base + path, quiet=True, **options) as crawler:
            await crawler.crawl()
        return crawler

    async def test_scope_robots_and_failures(self):
        crawler = await self.crawl(retries=0)
        self.assertEqual(len(crawler.page_data), 4)
        self.assertEqual(len(crawler.errors), 2)
        self.assertNotIn('/private', self.hits)
        self.assertEqual(self.hits.count('/a'), 1)
        self.assertTrue(all(value is not None for value in crawler.page_data.values()))
        self.assertFalse(crawler.all_tasks)
        self.assertTrue(crawler.session.closed)

    async def test_page_cap_finishes_accepted_work(self):
        crawler = await self.crawl('/wide', max_pages=5, max_concurrency=2)
        self.assertEqual(len(crawler.page_data), 5)
        self.assertEqual(len(crawler.seen), 5)
        self.assertLessEqual(self.peak, 2)

    async def test_depth_limit(self):
        crawler = await self.crawl(max_depth=0)
        self.assertEqual(len(crawler.page_data), 1)
        self.assertEqual(self.hits, ['/robots.txt', '/'])

    async def test_retry(self):
        crawler = await self.crawl('/flaky', retries=1)
        self.assertEqual(self.flaky_attempts, 2)
        self.assertEqual(len(crawler.page_data), 1)

    async def test_timeout(self):
        crawler = await self.crawl('/slow', timeout=0.03, retries=0)
        self.assertEqual(len(crawler.errors), 1)
        self.assertEqual(crawler.page_data, {})

    async def test_size_limit(self):
        crawler = await self.crawl('/large', max_bytes=100)
        self.assertIn('exceeds', next(iter(crawler.errors.values())))

    async def test_robots_unavailable_blocks_crawl(self):
        self.robots_status = 503
        crawler = await self.crawl()
        self.assertEqual(crawler.page_data, {})
        self.assertEqual(self.hits, ['/robots.txt'])

    async def test_missing_robots_allows_crawl(self):
        self.robots_status = 404
        crawler = await self.crawl(max_depth=0)
        self.assertEqual(len(crawler.page_data), 1)

    async def test_redirect_rechecks_robots(self):
        crawler = await self.crawl('/to-private')
        self.assertEqual(len(crawler.errors), 1)
        self.assertNotIn('/private', self.hits)

    async def test_cli_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'nested/report.json'
            errors = Path(directory) / 'errors.json'
            status = await main([self.base, '2', '10', '--quiet', '--output', str(output),
                                 '--errors', str(errors), '--max-depth', '0'])
            self.assertEqual(status, 0)
            self.assertEqual(len(json.loads(output.read_text())), 1)
            self.assertEqual(json.loads(errors.read_text()), [])

    async def test_launcher_end_to_end_from_another_directory(self):
        launcher = Path(__file__).resolve().parent / 'launch'
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'pages.json'
            process = await asyncio.create_subprocess_exec(
                str(launcher), self.base, '2', '5', '--max-depth', '0', '--quiet',
                '--output', str(output), cwd=directory,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await asyncio.wait_for(process.communicate(), 30)
            self.assertEqual(process.returncode, 0, stderr.decode())
            self.assertIn('Saved 1 pages', stdout.decode())
            self.assertEqual(len(json.loads(output.read_text())), 1)

    async def test_cancellation_cleans_workers(self):
        async with AsyncCrawler(self.base + '/slow', quiet=True) as crawler:
            task = asyncio.create_task(crawler.crawl())
            await asyncio.sleep(0.03)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertFalse(crawler.all_tasks)


class TestValidationAndReport(unittest.TestCase):
    def test_invalid_options(self):
        for options in [{'max_pages': 0}, {'max_concurrency': 0}, {'timeout': 0},
                        {'delay': -1}, {'max_depth': -1}, {'retries': -1}, {'timeout': float('nan')}]:
            with self.subTest(options=options), self.assertRaises(ValueError):
                AsyncCrawler('https://example.com', **options)
        for url in ['file:///tmp/a', 'example.com', 'https://a:bad', 'https://user:pass@example.com']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                AsyncCrawler(url)

    def test_report_sorting_and_atomic_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'report.json'
            write_json_report({'b': {'url': 'b'}, 'a': {'url': 'a'}, 'pending': None}, output)
            self.assertEqual([p['url'] for p in json.loads(output.read_text())], ['a', 'b'])
            original = output.read_text()
            with self.assertRaises(TypeError):
                write_json_report({'bad': {'url': 'bad', 'data': object()}}, output)
            self.assertEqual(output.read_text(), original)
            self.assertEqual(list(Path(directory).iterdir()), [output])
