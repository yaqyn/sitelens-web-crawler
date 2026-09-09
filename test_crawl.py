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
