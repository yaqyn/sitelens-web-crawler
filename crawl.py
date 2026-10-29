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
    hostname = (parsed.hostname or "").lower()
    if ":" in hostname:
        hostname = f"[{hostname}]"
    default_port = (parsed.scheme.lower(), parsed.port) in {("http", 80), ("https", 443)}
    authority = hostname if parsed.port is None or default_port else f"{hostname}:{parsed.port}"
    query = f"?{parsed.query}" if parsed.query else ""
    return authority + parsed.path.rstrip("/") + query


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

    document_base = base_url
    base_tag = soup.find("base", href=True)
    if isinstance(base_tag, Tag):
        try:
            candidate = urljoin(base_url, base_tag.get("href"))
            if urlsplit(candidate).scheme in {"http", "https"}:
                document_base = candidate
        except (TypeError, ValueError):
            pass

    urls = []
    seen = set()

    for a_tag in soup.find_all("a"):
        if a_tag.has_attr("download"):
            continue
        relations = {str(value).lower() for value in (a_tag.get("rel") or [])}
        if "nofollow" in relations:
            continue
        href = a_tag.get("href")

        if href is not None:
            try:
                url = urldefrag(urljoin(document_base, href))[0]
                if urlsplit(url).scheme not in {"http", "https"}:
                    continue
                if url not in seen:
                    seen.add(url)
                    urls.append(url)
            except ValueError:
                continue

    return urls


def _srcset_urls(value):
    """Return candidate URLs using the HTML srcset token boundaries."""
    urls = []
    position = 0
    whitespace = " \t\n\f\r"

    while position < len(value):
        while position < len(value) and (value[position] in whitespace or value[position] == ","):
            position += 1
        if position >= len(value):
            break

        start = position
        while position < len(value) and value[position] not in whitespace:
            position += 1
        url = value[start:position]

        if url.endswith(","):
            url = url.rstrip(",")
        else:
            parentheses = 0
            while position < len(value):
                character = value[position]
                if character == "(":
                    parentheses += 1
                elif character == ")" and parentheses:
                    parentheses -= 1
                elif character == "," and not parentheses:
                    position += 1
                    break
                position += 1

        if url:
            urls.append(url)

    return urls


def get_images_from_html(html, base_url):
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")

    images = []
    seen = set()

    # A source element describes an image only when it belongs to a picture.
    # Audio and video source URLs must not leak into the image inventory.
    for img_tag in soup.select("img, picture source, video[poster]"):
        candidates = []
        if img_tag.name == "video":
            candidates.append(img_tag.get("poster"))
        else:
            for attribute in ("src", "data-src"):
                if img_tag.get(attribute) is not None:
                    candidates.append(img_tag.get(attribute))
            for attribute in ("srcset", "data-srcset"):
                if img_tag.get(attribute):
                    candidates.extend(_srcset_urls(img_tag.get(attribute)))
        for src in candidates:
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
