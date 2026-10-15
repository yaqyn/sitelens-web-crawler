"""Keyboard-first atlas workspace; crawl policies stay in main.AsyncCrawler."""
import asyncio
import time
from collections import deque

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical
from textual.theme import Theme
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Collapsible, Input, Label, RichLog, Select, Static, TabbedContent, TabPane

from pathlib import Path

from json_report import write_json_report


class NavigationInput(Input):
    """Single-line fields use vertical arrows for form navigation."""
    BINDINGS = [Binding("up", "app.focus_previous", show=False),
                Binding("down", "app.focus_next", show=False)]


class HelpScreen(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close help"), ("f1", "dismiss", "Close help")]

    def compose(self):
        with Vertical(id="help-dialog"):
            yield Static("SiteLens controls", classes="section")
            yield Static(
                "Tab / Shift+Tab: next / previous control\n"
                "Alt+Down / Alt+Up: next / previous control\n"
                "Up / Down: move between text fields\n"
                "Left / Right: edit text; arrows select open choices\n"
                "Enter / Space: select or activate\n\n"
                "F2: Plan crawl   F3: Field notes   F4: Appearance\n"
                "Ctrl+R: start   Ctrl+S: stop   Ctrl+Q: quit\n"
                "Escape: dismiss a choice, or stop a crawl\n\n"
                "Use terminal zoom for larger text. Use --plain for linear output.\n"
                "Field notes keep the latest 500 lines. No animation is used.",
                markup=False)
            yield Button("Close help", id="close-help", variant="primary")

    def on_button_pressed(self, event):
        event.stop()
        self.dismiss()


class SiteLensApp(App):
    TITLE = "SiteLens"
    ENABLE_COMMAND_PALETTE = False
    CSS_PATH = "terminal_ui.tcss"
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+r", "start", "Start crawl", priority=True),
        Binding("ctrl+s", "stop", "Stop crawl", priority=True),
        Binding("escape", "stop", "Stop crawl"),
        Binding("f1", "help", "Help", priority=True),
        Binding("f2", "view('plan')", "Plan", priority=True),
        Binding("f3", "view('notes')", "Notes", priority=True),
        Binding("f4", "view('appearance')", "Appearance", priority=True),
        Binding("alt+down", "focus_next", "Next control", priority=True),
        Binding("alt+up", "focus_previous", "Previous control", priority=True),
    ]

    def __init__(self, options):
        super().__init__()
        self.options = options
        self.crawler = None
        self.crawl_task = None
        self.started = 0
        self.finished = None
        self.ready = False
        self.pending_events = deque(maxlen=500)
        self.last_counts = None
        self.dropped_events = 0
        self.register_theme(Theme(
            name="atlas", primary="#71d7e6", secondary="#d6b879",
            accent="#d6b879", foreground="#f5e7c8", background="#061c2c",
            surface="#102e40", panel="#102e40", success="#9be2b0",
            warning="#f4cd83", error="#ffb5ad", dark=True))
        self.register_theme(Theme(
            name="parchment", primary="#07576a", secondary="#6a491b",
            accent="#6a491b", foreground="#172d3a", background="#f5e7c8",
            surface="#fff6df", panel="#e7d7b5", dark=False))
        self.register_theme(Theme(
            name="contrast", primary="#ffff00", secondary="#00ffff",
            accent="#ffff00", foreground="#ffffff", background="#000000",
            surface="#000000", panel="#000000", dark=True))
        self.theme = options.theme
        self.animation_level = "none"

    def compose(self) -> ComposeResult:
        yield Static("SiteLens  /  Website fieldwork", id="masthead")
        with Vertical(id="workspace"):
            yield Static("Explore. Extract. Report.", id="title")
            yield Static("Follow a website's links and collect its headings, images, and page text.", id="intro")
            with TabbedContent(initial="plan", id="tabs"):
                with TabPane("Plan crawl", id="plan"):
                    yield Static("1  Plan your crawl", classes="section")
                    yield Label("Website URL", classes="field-label")
                    yield NavigationInput(self.options.base_url or "", placeholder="https://example.com", id="url")
                    yield Label("Crawl preset", classes="field-label")
                    yield Select([("Custom / keep the limits below", "custom"),
                                  ("Balanced / 100 pages, 5 workers", "balanced"),
                                  ("Gentle / 20 pages, 2 workers, 1s delay", "gentle"),
                                  ("Single page / no link following", "single")],
                                 value="custom", allow_blank=False, id="preset")
                    with Grid(id="limits"):
                        for label, ident, value in [
                            ("Page limit", "pages", self.options.max_pages),
                            ("Concurrent workers", "workers", self.options.max_concurrency),
                            ("Request interval (seconds)", "delay", self.options.delay),
                            ("Link depth (blank = unlimited)", "depth", self.options.max_depth),
                        ]:
                            with Vertical(classes="limit-field"):
                                yield Label(label, classes="field-label")
                                yield NavigationInput("" if value is None else str(value), id=ident)
                    with Collapsible(title="Request policy and report paths", collapsed=True):
                        for label, ident, value in [
                            ("Request timeout (seconds)", "timeout", self.options.timeout),
                            ("Retries", "retries", self.options.retries),
                            ("Maximum response bytes", "bytes", self.options.max_bytes),
                            ("Page report path", "output", self.options.output),
                            ("Error report path (optional)", "errors", self.options.errors),
                        ]:
                            yield Label(label, classes="field-label")
                            yield NavigationInput("" if value is None else str(value), id=ident)
                        yield Checkbox("Respect robots.txt", value=not self.options.ignore_robots, id="robots")
                with TabPane("Field notes", id="notes"):
                    yield Static("2  Field notes", classes="section")
                    yield Static("Ready. Enter a website, choose limits, then start.", id="status", markup=False)
                    yield Static("0 collected | 0 failures | 0 queued", id="counts", markup=False)
                    yield RichLog(id="log", wrap=True, highlight=False, markup=False, max_lines=500)
                with TabPane("Appearance", id="appearance"):
                    yield Static("Appearance", classes="section")
                    yield Label("Color theme", classes="field-label")
                    yield Select([("Midnight atlas", "atlas"), ("Light parchment", "parchment"),
                                  ("High contrast", "contrast"), ("Terminal colors", "textual-ansi")],
                                 value=self.options.theme, allow_blank=False, id="theme-picker")
                    yield Label("Spacing", classes="field-label")
                    yield Select([("Comfortable", "comfortable"), ("Compact", "compact")],
                                 value="comfortable", allow_blank=False, id="density")
        with Vertical(id="bottom-dock"):
            with Vertical(id="bottom-bar"):
                with Horizontal(id="actions"):
                    yield Button("Start crawl", variant="primary", id="start")
                    yield Button("Stop crawl", id="stop", disabled=True)
                with Grid(id="keys"):
                    for label in ["Tab / S-Tab  Move", "Arrows  Navigate", "Enter  Select", "F1  Help",
                                  "F2/F3/F4  Views", "Ctrl+R  Start", "Ctrl+S  Stop", "Ctrl+Q  Quit"]:
                        yield Static(label, markup=False)

    def on_mount(self):
        self.base_screen = self.screen
        self.base_screen.query_one("#url", Input).focus()
        self.counts = self.base_screen.query_one("#counts", Static)
        self.event_log = self.base_screen.query_one("#log", RichLog)
        self.refresh_timer = self.set_interval(0.2, self.refresh_dashboard)
        self.ready = True
        self.call_after_refresh(self.base_screen.query_one("#plan").scroll_home, animate=False)

    def on_select_changed(self, event: Select.Changed):
        if event.select.id == "theme-picker":
            self.theme = str(event.value)
        elif event.select.id == "density":
            self.set_class(event.value == "compact", "compact")
        elif event.select.id == "preset" and self.ready and event.value != "custom":
            values = {"balanced": (100, 5, 0, ""), "gentle": (20, 2, 1, ""),
                      "single": (1, 1, 0, 0)}[str(event.value)]
            for ident, value in zip(("pages", "workers", "delay", "depth"), values):
                self.base_screen.query_one(f"#{ident}", Input).value = str(value)

    def on_resize(self, event):
        self.set_class(event.size.width < 76, "narrow")

    def action_help(self):
        if isinstance(self.screen, HelpScreen):
            self.pop_screen()
        else:
            self.push_screen(HelpScreen())

    def action_view(self, pane):
        if isinstance(self.screen, HelpScreen):
            return
        self.set_focus(None)
        self.base_screen.query_one("#tabs", TabbedContent).active = pane
        target = {"plan": "#url", "notes": "#log", "appearance": "#theme-picker"}[pane]
        self.call_after_refresh(self.base_screen.query_one(target).focus)

    def show_notes(self):
        self.action_view("notes")

    def value(self, ident):
        return self.base_screen.query_one(f"#{ident}", Input).value.strip()

    def number(self, ident, kind=int):
        field = self.base_screen.query_one(f"#{ident}", Input)
        try:
            return kind(field.value.strip())
        except ValueError:
            labels = {"workers": "Concurrent workers", "pages": "Page limit", "delay": "Request delay",
                      "depth": "Link depth", "timeout": "Request timeout", "retries": "Retries",
                      "bytes": "Maximum response bytes"}
            expected = "a whole number" if kind is int else "a number"
            raise ValueError(f"{labels[ident]} must be {expected}") from None

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "start":
            self.action_start()
        elif event.button.id == "stop":
            self.action_stop()

    def action_start(self):
        if self.crawl_task and not self.crawl_task.done():
            return
        from main import AsyncCrawler
        try:
            if not self.value("output"):
                raise ValueError("Enter a page report path")
            if self.value("errors") and Path(self.value("output")).resolve() == Path(self.value("errors")).resolve():
                raise ValueError("Page and error reports need different paths")
            self.crawler = AsyncCrawler(
                self.value("url"), self.number("workers"), self.number("pages"),
                delay=self.number("delay", float),
                max_depth=self.number("depth") if self.value("depth") else None,
                timeout=self.number("timeout", float), retries=self.number("retries"),
                max_bytes=self.number("bytes"),
                respect_robots=self.base_screen.query_one("#robots", Checkbox).value, quiet=True,
                on_event=self.crawl_event)
        except ValueError as error:
            self.base_screen.query_one("#status", Static).update(f"Check your settings: {error}")
            self.show_notes()
            return
        self.report_path, self.errors_path = self.value("output"), self.value("errors")
        self.pending_events.clear()
        self.dropped_events = 0
        self.last_counts = None
        self.event_log.clear()
        self.base_screen.query_one("#start", Button).disabled = True
        self.base_screen.query_one("#stop", Button).disabled = False
        self.started = time.monotonic()
        self.finished = None
        self.base_screen.query_one("#status", Static).update("Crawling. Checking robots.txt and following in-scope links.")
        self.show_notes()
        self.crawl_task = asyncio.create_task(self.run_crawl())
        self.crawl_task.add_done_callback(self.handle_early_cancel)

    def handle_early_cancel(self, task):
        if task.cancelled() and self.is_running:
            self.finished = time.monotonic()
            self.base_screen.query_one("#start", Button).disabled = False
            self.base_screen.query_one("#stop", Button).disabled = True
            self.base_screen.query_one("#status", Static).update(
                "Stopped before crawling. Reports were not written.")
            self.refresh_dashboard()

    def crawl_event(self, kind, url, detail=""):
        if len(self.pending_events) == self.pending_events.maxlen:
            self.dropped_events += 1
        # Treat remote content as literal text and keep each event bounded.
        line = f"{kind}: {url}" + (f" | {detail}" if detail else "")
        self.pending_events.append(" ".join(line.split())[:2000])

    def refresh_dashboard(self):
        if self.pending_events:
            lines = list(self.pending_events)
            self.pending_events.clear()
            if self.dropped_events:
                lines.insert(0, f"Skipped {self.dropped_events} older display events; reports are unaffected.")
                self.dropped_events = 0
            self.event_log.write("\n".join(lines), scroll_end=self.event_log.is_vertical_scroll_end)
        self.update_counts()

    def update_counts(self):
        if not self.crawler or not self.started:
            return
        snapshot = (len(self.crawler.page_data), len(self.crawler.errors),
                    self.crawler.queue.qsize(), len(self.crawler.seen),
                    int((self.finished or time.monotonic()) - self.started))
        if snapshot != self.last_counts:
            self.last_counts = snapshot
            pages, errors, queued, scheduled, elapsed = snapshot
            self.counts.update(f"{pages} collected | {errors} failures | {queued} queued | "
                               f"{scheduled} scheduled | {elapsed}s elapsed")

    async def run_crawl(self):
        try:
            async with self.crawler:
                pages = await self.crawler.crawl()
            write_json_report(pages, self.report_path)
            if self.errors_path:
                write_json_report({url: {"url": url, "error": error}
                                   for url, error in self.crawler.errors.items()}, self.errors_path)
            message = (f"Saved {len(pages)} pages to {self.report_path}; "
                       f"{len(self.crawler.errors)} failures.")
            if not pages:
                message += " No pages collected. Check field notes for robots or request failures."
            elif self.crawler.errors and not self.errors_path:
                message += " Set an error report path on your next crawl to export failures."
        except asyncio.CancelledError:
            message = "Stopped. Reports were not written. You can adjust settings and start again."
        except Exception as error:
            message = f"Crawl or report failed: {error}. Check the URL and report paths, then retry."
        finally:
            self.finished = time.monotonic()
            self.base_screen.query_one("#start", Button).disabled = False
            self.base_screen.query_one("#stop", Button).disabled = True
        self.base_screen.query_one("#status", Static).update(message)
        self.refresh_dashboard()

    def action_stop(self):
        if self.crawl_task and not self.crawl_task.done():
            self.crawl_task.cancel()

    async def action_quit(self):
        if self.crawl_task and not self.crawl_task.done():
            self.crawl_task.cancel()
            try:
                await self.crawl_task
            except asyncio.CancelledError:
                pass  # A task cancelled before its first step has no cleanup to run.
        self.refresh_timer.stop()
        self.exit()
