"""Behavior checks for keyboard setup, presentation, and real local crawls."""
import asyncio
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from textual.widgets import Input, Select, Static, TabbedContent

from terminal_ui import HelpScreen, SiteLensApp
import test_async_crawler as local_fixture


def options(**overrides):
    values = dict(base_url=None, max_pages=37, max_concurrency=3, delay=0,
                  max_depth=None, timeout=30, retries=0, max_bytes=2_000_000,
                  output='report.json', errors=None, ignore_robots=False, theme='atlas')
    return Namespace(**(values | overrides))


class TestWorkspace(unittest.IsolatedAsyncioTestCase):
    async def test_keyboard_presets_and_validation(self):
        app = SiteLensApp(options())
        async with app.run_test(size=(80, 35)) as pilot:
            await pilot.pause()
            self.assertEqual(app.focused.id, 'url')
            self.assertEqual(app.value('pages'), '37')
            await pilot.press('tab', 'enter', 'down', 'down', 'enter')
            await pilot.pause()
            self.assertEqual(app.value('workers'), '2')
            self.assertEqual(app.value('delay'), '1')
            await pilot.press('ctrl+r')
            await pilot.pause()
            self.assertIsNone(app.crawler)
            self.assertIn('Check your settings', str(app.query_one('#status', Static).render()))
            self.assertEqual(app.query_one('#tabs', TabbedContent).active, 'notes')

    async def test_themes_and_narrow_layout(self):
        app = SiteLensApp(options())
        async with app.run_test(size=(40, 24)) as pilot:
            for theme in ['parchment', 'contrast', 'textual-ansi', 'atlas']:
                app.query_one('#theme-picker', Select).value = theme
                await pilot.pause()
                self.assertEqual(app.theme, theme)
            app.query_one('#density', Select).value = 'compact'
            await pilot.pause()
            self.assertTrue(app.has_class('compact'))
            self.assertLessEqual(app.query_one('#tabs').region.right, 40)
            await pilot.press('f1')
            self.assertIsInstance(app.screen, HelpScreen)
            await pilot.press('escape')
            self.assertNotIsInstance(app.screen, HelpScreen)

    async def test_centered_fixed_guide_and_shortcuts(self):
        app = SiteLensApp(options())
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            workspace = app.query_one('#workspace').region
            self.assertEqual(workspace.x, (120 - workspace.width) // 2)
            guide = app.query_one('#keys').region
            self.assertEqual(guide.x, workspace.x + 2)
            for key, pane in [('f3', 'notes'), ('f4', 'appearance'), ('f2', 'plan')]:
                await pilot.press(key)
                await pilot.pause()
                self.assertEqual(app.query_one('#tabs', TabbedContent).active, pane)
                self.assertEqual(app.query_one('#keys').region, guide)
            app.query_one('#url', Input).value = 'https://example.com/' + 'long/' * 200
            await pilot.press('down')
            self.assertEqual(app.focused.id, 'preset')
            await pilot.press('alt+up')
            self.assertEqual(app.focused.id, 'url')
            await pilot.press('alt+down')
            self.assertEqual(app.focused.id, 'preset')
            await pilot.press('alt+up')
            self.assertEqual(app.focused.id, 'url')
            self.assertEqual(app.query_one('#keys').region, guide)

    async def test_event_bursts_are_bounded_and_batched(self):
        from unittest.mock import patch
        app = SiteLensApp(options())
        async with app.run_test() as pilot:
            await pilot.pause()
            app.refresh_timer.pause()
            with patch.object(app.event_log, 'write') as write:
                for index in range(10_000):
                    app.crawl_event('Collected', f'https://example.com/{index}', '[bold]literal')
                self.assertEqual(len(app.pending_events), 500)
                write.assert_not_called()
                app.refresh_dashboard()
                write.assert_called_once()
                self.assertIn('Skipped 9500', write.call_args.args[0])
                self.assertIn('/9999', write.call_args.args[0])
                app.refresh_dashboard()
                write.assert_called_once()


class TestWorkspaceCrawls(unittest.IsolatedAsyncioTestCase):
    # Reuse the local HTTP fixture without inheriting/rerunning its test methods.
    asyncSetUp = local_fixture.TestAsyncCrawler.asyncSetUp
    handle = local_fixture.TestAsyncCrawler.handle

    async def test_immediate_stop_restores_controls(self):
        from textual.widgets import Button
        app = SiteLensApp(options(base_url=self.base))
        async with app.run_test() as pilot:
            await pilot.pause()
            app.action_start()
            app.action_stop()
            await asyncio.sleep(0)
            await pilot.pause()
            self.assertTrue(app.crawl_task.cancelled())
            self.assertFalse(app.query_one('#start', Button).disabled)
            self.assertTrue(app.query_one('#stop', Button).disabled)
            self.assertEqual(self.hits, [])

    async def test_crawl_and_cancel_preserve_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'pages.json'
            app = SiteLensApp(options(base_url=self.base, output=str(output), max_depth=0))
            async with app.run_test(size=(100, 40)) as pilot:
                await pilot.pause()
                await pilot.press('ctrl+r')
                app.action_help()
                await pilot.pause()
                await asyncio.wait_for(app.crawl_task, 5)
                self.assertIsInstance(app.screen, HelpScreen)
                await pilot.press('escape')
                self.assertTrue(output.exists())
                self.assertEqual(len(app.crawler.page_data), 1)
                original = output.read_bytes()
                app.query_one('#url', Input).value = self.base + '/slow'
                app.action_start()
                await asyncio.sleep(0.03)
                app.action_stop()
                await app.crawl_task
                self.assertTrue(app.crawler.session.closed)
                self.assertFalse(app.crawler.all_tasks)
                self.assertEqual(output.read_bytes(), original)
                self.assertIn('Stopped.', str(app.query_one('#status', Static).render()))
