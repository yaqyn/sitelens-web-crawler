import unittest
from crawl import (
    normalize_url,
    get_heading_from_html,
    get_first_paragraph_from_html,
    get_urls_from_html,
    get_images_from_html,
    extract_page_data,
)


class TestCrawl(unittest.TestCase):
    def test_malformed_urls_do_not_discard_valid_page_data(self):
        result = extract_page_data(
            '<h1>Useful page</h1><a href="http://[">bad</a><a href="/valid">good</a>'
            '<img src="https://["><img src="/image.png">', "https://example.com")
        self.assertEqual(result["heading"], "Useful page")
        self.assertEqual(result["outgoing_links"], ["https://example.com/valid"])
        self.assertEqual(result["image_urls"], ["https://example.com/image.png"])


    def test_inline_elements_preserve_word_boundaries(self):
        html = "<h1>Hello <em>world</em> today</h1><p>Read <a href='/'>this guide</a> now.</p>"
        self.assertEqual(get_heading_from_html(html), "Hello world today")
        self.assertEqual(get_first_paragraph_from_html(html), "Read this guide now.")

    # normalize_url tests

    def test_normalize_url_https(self):
        input_url = "https://www.boot.dev/blog/path"
        actual = normalize_url(input_url)
        expected = "www.boot.dev/blog/path"
        self.assertEqual(actual, expected)

    def test_normalize_url_https_trailing_slash(self):
        input_url = "https://www.boot.dev/blog/path/"
        actual = normalize_url(input_url)
        expected = "www.boot.dev/blog/path"
        self.assertEqual(actual, expected)

    def test_normalize_url_http_trailing_slash(self):
        input_url = "http://www.boot.dev/blog/path/"
        actual = normalize_url(input_url)
        expected = "www.boot.dev/blog/path"
        self.assertEqual(actual, expected)

    def test_normalize_url_http(self):
        input_url = "http://www.boot.dev/blog/path"
        actual = normalize_url(input_url)
        expected = "www.boot.dev/blog/path"
        self.assertEqual(actual, expected)

    def test_normalize_url_preserves_distinct_query_pages(self):
        self.assertNotEqual(
            normalize_url("https://example.com/search?page=1"),
            normalize_url("https://example.com/search?page=2"),
        )

    # get_heading_from_html tests

    def test_get_heading_from_html_h1(self):
        input_body = "<html><body><h1>Test Title</h1></body></html>"
        actual = get_heading_from_html(input_body)
        expected = "Test Title"
        self.assertEqual(actual, expected)

    def test_get_heading_from_html_h2_fallback(self):
        input_body = "<html><body><h2>Test Subtitle</h2></body></html>"
        actual = get_heading_from_html(input_body)
        expected = "Test Subtitle"
        self.assertEqual(actual, expected)

    def test_get_heading_from_html_empty(self):
        input_body = "<html><body><p>No heading here.</p></body></html>"
        actual = get_heading_from_html(input_body)
        expected = ""
        self.assertEqual(actual, expected)

    # get_first_paragraph_from_html tests

    def test_get_first_paragraph_from_html_basic(self):
        input_body = "<html><body><p>First paragraph.</p></body></html>"
        actual = get_first_paragraph_from_html(input_body)
        expected = "First paragraph."
        self.assertEqual(actual, expected)

    def test_get_first_paragraph_from_html_main_priority(self):
        input_body = """<html><body>
            <p>Outside paragraph.</p>
            <main>
                <p>Main paragraph.</p>
            </main>
        </body></html>"""
        actual = get_first_paragraph_from_html(input_body)
        expected = "Main paragraph."
        self.assertEqual(actual, expected)

    def test_get_first_paragraph_from_html_empty(self):
        input_body = "<html><body><h1>No paragraph here.</h1></body></html>"
        actual = get_first_paragraph_from_html(input_body)
        expected = ""
        self.assertEqual(actual, expected)

    # get_urls_from_html tests

    def test_get_urls_from_html_absolute(self):
        input_url = "https://crawler-test.com"
        input_body = '<html><body><a href="https://crawler-test.com"><span>Boot.dev</span></a></body></html>'
        actual = get_urls_from_html(input_body, input_url)
        expected = ["https://crawler-test.com"]
        self.assertEqual(actual, expected)

    def test_get_urls_from_html_relative(self):
        input_url = "https://crawler-test.com"
        input_body = '<html><body><a href="/about">About</a></body></html>'
        actual = get_urls_from_html(input_body, input_url)
        expected = ["https://crawler-test.com/about"]
        self.assertEqual(actual, expected)

    def test_links_honor_document_base_url(self):
        html = '<base href="https://example.com/docs/"><a href="guide">Guide</a>'
        self.assertEqual(
            get_urls_from_html(html, "https://example.com/index.html"),
            ["https://example.com/docs/guide"],
        )

    def test_get_urls_from_html_all_links(self):
        input_url = "https://crawler-test.com"
        input_body = """<html><body>
            <a href="/about">About</a>
            <a href="/contact">Contact</a>
            <a href="https://example.com">Example</a>
        </body></html>"""
        actual = get_urls_from_html(input_body, input_url)
        expected = [
            "https://crawler-test.com/about",
            "https://crawler-test.com/contact",
            "https://example.com",
        ]
        self.assertEqual(actual, expected)

    def test_duplicate_resources_are_reported_once(self):
        html = '<a href="/same">one</a><a href="/same">two</a><img src="/same.png"><img src="/same.png">'
        self.assertEqual(get_urls_from_html(html, "https://example.com"), ["https://example.com/same"])
        self.assertEqual(get_images_from_html(html, "https://example.com"), ["https://example.com/same.png"])

    def test_link_fragments_do_not_create_duplicate_pages(self):
        html = '<a href="/guide#start">start</a><a href="/guide#details">details</a>'
        self.assertEqual(get_urls_from_html(html, "https://example.com"), ["https://example.com/guide"])

    def test_non_web_links_are_not_reported_as_crawl_targets(self):
        html = '<a href="mailto:hi@example.com">mail</a><a href="javascript:void(0)">script</a><a href="/guide">guide</a>'
        self.assertEqual(get_urls_from_html(html, "https://example.com"), ["https://example.com/guide"])

    # get_images_from_html tests

    def test_get_images_from_html_relative(self):
        input_url = "https://crawler-test.com"
        input_body = '<html><body><img src="/logo.png" alt="Logo"></body></html>'
        actual = get_images_from_html(input_body, input_url)
        expected = ["https://crawler-test.com/logo.png"]
        self.assertEqual(actual, expected)

    def test_get_images_from_html_absolute(self):
        input_url = "https://crawler-test.com"
        input_body = '<html><body><img src="https://example.com/image.png"></body></html>'
        actual = get_images_from_html(input_body, input_url)
        expected = ["https://example.com/image.png"]
        self.assertEqual(actual, expected)

    def test_get_images_from_html_includes_responsive_sources(self):
        html = '<img src="/fallback.png" srcset="/small.png 1x, /large.png 2x">'
        self.assertEqual(
            get_images_from_html(html, "https://crawler-test.com"),
            [
                "https://crawler-test.com/fallback.png",
                "https://crawler-test.com/small.png",
                "https://crawler-test.com/large.png",
            ],
        )

    def test_get_images_from_html_includes_picture_sources(self):
        html = '<picture><source srcset="/wide.webp 2x"><img src="/fallback.png"></picture>'
        self.assertEqual(
            get_images_from_html(html, "https://crawler-test.com"),
            ["https://crawler-test.com/wide.webp", "https://crawler-test.com/fallback.png"],
        )

    def test_get_images_from_html_excludes_media_sources(self):
        html = (
            '<audio><source src="/sound.mp3"></audio>'
            '<video><source src="/movie.webm"><img src="/poster.png"></video>'
        )
        self.assertEqual(
            get_images_from_html(html, "https://crawler-test.com"),
            ["https://crawler-test.com/poster.png"],
        )

    def test_get_images_from_html_includes_video_posters(self):
        html = (
            '<video poster="/preview.jpg" src="/movie.mp4" data-src="/lazy-movie.mp4">'
            '<source src="/movie.webm"></video>'
        )
        self.assertEqual(
            get_images_from_html(html, "https://crawler-test.com"),
            ["https://crawler-test.com/preview.jpg"],
        )

    def test_get_images_from_html_includes_lazy_loaded_sources(self):
        html = '<img data-src="/lazy.png" data-srcset="/lazy-small.png 1x, /lazy-large.png 2x">'
        self.assertEqual(
            get_images_from_html(html, "https://crawler-test.com"),
            [
                "https://crawler-test.com/lazy.png",
                "https://crawler-test.com/lazy-small.png",
                "https://crawler-test.com/lazy-large.png",
            ],
        )

    def test_srcset_commas_inside_urls_do_not_create_fake_candidates(self):
        html = (
            '<img srcset="data:image/png;base64,AAAA 1x, '
            '/large.png 2x, /map,detail.png 3x">'
        )
        self.assertEqual(
            get_images_from_html(html, "https://crawler-test.com"),
            [
                "https://crawler-test.com/large.png",
                "https://crawler-test.com/map,detail.png",
            ],
        )

    def test_non_web_images_are_ignored_and_fragments_are_deduplicated(self):
        html = (
            '<img src="data:image/png;base64,abc">'
            '<img src="javascript:alert(1)">'
            '<img src="/cover.png#one"><img src="/cover.png#two">'
        )
        self.assertEqual(
            get_images_from_html(html, "https://crawler-test.com"),
            ["https://crawler-test.com/cover.png"],
        )

    def test_get_images_from_html_missing_src(self):
        input_url = "https://crawler-test.com"
        input_body = """<html><body>
            <img alt="Logo">
            <img src="/valid.png">
            <img>
        </body></html>"""
        actual = get_images_from_html(input_body, input_url)
        expected = ["https://crawler-test.com/valid.png"]
        self.assertEqual(actual, expected)

    # extract_page_data tests

    def test_extract_page_data_basic(self):
        input_url = "https://crawler-test.com"
        input_body = """<html><body>
            <h1>Test Title</h1>
            <p>This is the first paragraph.</p>
            <a href="/link1">Link 1</a>
            <img src="/image1.jpg" alt="Image 1">
        </body></html>"""
        actual = extract_page_data(input_body, input_url)
        expected = {
            "url": "https://crawler-test.com",
            "heading": "Test Title",
            "first_paragraph": "This is the first paragraph.",
            "outgoing_links": ["https://crawler-test.com/link1"],
            "image_urls": ["https://crawler-test.com/image1.jpg"],
        }
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
