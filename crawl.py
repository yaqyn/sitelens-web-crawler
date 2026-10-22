from urllib.parse import urldefrag, urlsplit, urljoin
from typing import TypedDict
from bs4 import BeautifulSoup, Tag


class PageData(TypedDict):
    url: str
    heading: str
    first_paragraph: str
    outgoing_links: list[str]
    image_urls: list[str]


def normalize_url(url):
    parsed = urlsplit(url)
    query = f"?{parsed.query}" if parsed.query else ""
    return parsed.netloc.lower() + parsed.path.rstrip("/") + query


def get_heading_from_html(html: str | BeautifulSoup) -> str:
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")

    h_tag = soup.find("h1")

    if not isinstance(h_tag, Tag):
        h_tag = soup.find("h2")

    return " ".join(h_tag.stripped_strings) if isinstance(h_tag, Tag) else ""


def get_first_paragraph_from_html(html: str | BeautifulSoup) -> str:
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")

    main = soup.find("main")

    if isinstance(main, Tag):
        p_tag = main.find("p")
    else:
        p_tag = soup.find("p")

    return " ".join(p_tag.stripped_strings) if isinstance(p_tag, Tag) else ""


def get_urls_from_html(html, base_url):
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")

    urls = []
    seen = set()

    for a_tag in soup.find_all("a"):
        href = a_tag.get("href")

        if href is not None:
            try:
                url = urldefrag(urljoin(base_url, href))[0]
                if urlsplit(url).scheme not in {"http", "https"}:
                    continue
                if url not in seen:
                    seen.add(url)
                    urls.append(url)
            except ValueError:
                continue

    return urls


def get_images_from_html(html, base_url):
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")

    images = []
    seen = set()

    for img_tag in soup.find_all("img"):
        src = img_tag.get("src")

        if src is not None:
            try:
                url = urldefrag(urljoin(base_url, src))[0]
                if urlsplit(url).scheme not in {"http", "https"}:
                    continue
                if url not in seen:
                    seen.add(url)
                    images.append(url)
            except ValueError:
                continue

    return images


def extract_page_data(html: str, page_url: str) -> PageData:
    soup = BeautifulSoup(html, "html.parser")
    return {
        "url": page_url,
        "heading": get_heading_from_html(soup),
        "first_paragraph": get_first_paragraph_from_html(soup),
        "outgoing_links": get_urls_from_html(soup, page_url),
        "image_urls": get_images_from_html(soup, page_url),
    }
