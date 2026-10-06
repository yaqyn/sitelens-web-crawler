from urllib.parse import urlsplit, urljoin
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
    return parsed.netloc.lower() + parsed.path.rstrip("/")


def get_heading_from_html(html: str | BeautifulSoup) -> str:
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")

    h_tag = soup.find("h1")

    if not isinstance(h_tag, Tag):
        h_tag = soup.find("h2")

    return h_tag.get_text(strip=True) if isinstance(h_tag, Tag) else ""


def get_first_paragraph_from_html(html: str | BeautifulSoup) -> str:
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")

    main = soup.find("main")

    if isinstance(main, Tag):
        p_tag = main.find("p")
    else:
        p_tag = soup.find("p")

    return p_tag.get_text(strip=True) if isinstance(p_tag, Tag) else ""


def get_urls_from_html(html, base_url):
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")

    urls = []

    for a_tag in soup.find_all("a"):
        href = a_tag.get("href")

        if href is not None:
            urls.append(urljoin(base_url, href))

    return urls


def get_images_from_html(html, base_url):
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")

    images = []

    for img_tag in soup.find_all("img"):
        src = img_tag.get("src")

        if src is not None:
            images.append(urljoin(base_url, src))

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
