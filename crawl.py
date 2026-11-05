from urllib.parse import urldefrag, urlsplit, urljoin
from typing import TypedDict
from bs4 import BeautifulSoup, Tag


class PageData(TypedDict):
    url: str
    title: str
    description: str
    canonical_url: str
    language: str
    robots: list[str]
    alternate_languages: list[dict[str, str]]
    heading: str
    heading_counts: dict[str, int]
    form_summary: dict[str, int]
    image_summary: dict[str, int]
    landmark_summary: dict[str, int]
    link_accessibility_summary: dict[str, int]
    metadata_summary: dict[str, bool]
    first_paragraph: str
    word_count: int
    outgoing_links: list[str]
    link_counts: dict[str, int]
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


def get_heading_counts_from_html(html: str | BeautifulSoup) -> dict[str, int]:
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")
    return {f"h{level}": len(soup.find_all(f"h{level}")) for level in range(1, 7)}


def get_form_summary_from_html(html: str | BeautifulSoup) -> dict[str, int]:
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")
    forms = soup.find_all("form")
    return {
        "forms": len(forms),
        "controls": sum(len(form.select("input, select, textarea, button")) for form in forms),
    }


def get_image_summary_from_html(html: str | BeautifulSoup) -> dict[str, int]:
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")
    images = soup.find_all("img")
    return {
        "images": len(images),
        "with_alt": sum(isinstance(image.get("alt"), str) for image in images),
        "empty_alt": sum(image.get("alt") == "" for image in images),
    }


def get_landmark_summary_from_html(html: str | BeautifulSoup) -> dict[str, int]:
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")
    return {name: len(soup.find_all(name)) for name in ("main", "nav", "header", "footer", "aside")}


def get_link_accessibility_summary_from_html(html: str | BeautifulSoup) -> dict[str, int]:
    """Count anchors with a text, aria, or image-alt accessible name."""
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", href=True)
    named = 0
    for link in links:
        aria = link.get("aria-label")
        text_name = " ".join(link.stripped_strings)
        image_name = any(
            isinstance(image.get("alt"), str) and image.get("alt").strip()
            for image in link.find_all("img")
        )
        if text_name or isinstance(aria, str) and aria.strip() or image_name:
            named += 1
    return {"links": len(links), "named": named, "unnamed": len(links) - named}


def get_metadata_summary_from_html(html: str | BeautifulSoup) -> dict[str, bool]:
    """Report document metadata declared by actual meta elements."""
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")
    has_charset = any(
        isinstance(meta.get("charset"), str) and bool(meta.get("charset").strip())
        for meta in soup.find_all("meta")
    )
    has_viewport = any(
        isinstance(meta.get("name"), str)
        and meta.get("name").strip().casefold() == "viewport"
        and isinstance(meta.get("content"), str)
        and bool(meta.get("content").strip())
        for meta in soup.find_all("meta")
    )
    return {"charset": has_charset, "viewport": has_viewport}


def get_title_from_html(html: str | BeautifulSoup) -> str:
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")
    title = soup.find("title")
    return " ".join(title.stripped_strings) if isinstance(title, Tag) else ""


def get_description_from_html(html: str | BeautifulSoup) -> str:
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")
    meta = soup.find("meta", attrs={"name": lambda value: isinstance(value, str) and value.casefold() == "description"})
    if not isinstance(meta, Tag) or not isinstance(meta.get("content"), str):
        return ""
    return " ".join(meta["content"].split())


def get_canonical_url_from_html(html: str | BeautifulSoup, page_url: str) -> str:
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")
    link = soup.find("link", rel=lambda value: isinstance(value, (str, list)) and "canonical" in ([value.casefold()] if isinstance(value, str) else [str(item).casefold() for item in value]))
    if not isinstance(link, Tag) or not isinstance(link.get("href"), str):
        return ""
    try:
        candidate = urldefrag(urljoin(page_url, link["href"]))[0]
        return candidate if urlsplit(candidate).scheme in {"http", "https"} else ""
    except ValueError:
        return ""


def get_language_from_html(html: str | BeautifulSoup) -> str:
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")
    root = soup.find("html")
    if not isinstance(root, Tag) or not isinstance(root.get("lang"), str):
        return ""
    return root["lang"].strip().lower()[:35]


def get_robots_from_html(html: str | BeautifulSoup) -> list[str]:
    """Return normalized directives from the document's robots meta tags."""
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")
    directives = []
    seen = set()
    for meta in soup.find_all("meta", attrs={"name": lambda value: isinstance(value, str) and value.casefold() == "robots"}):
        content = meta.get("content")
        if not isinstance(content, str):
            continue
        for value in content.split(","):
            directive = value.strip().lower()
            if directive and directive not in seen:
                seen.add(directive)
                directives.append(directive)
    return directives


def get_first_paragraph_from_html(html: str | BeautifulSoup) -> str:
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")

    main = soup.find("main")

    if isinstance(main, Tag):
        p_tag = main.find("p")
    else:
        p_tag = soup.find("p")

    return " ".join(p_tag.stripped_strings) if isinstance(p_tag, Tag) else ""


def get_word_count_from_html(html: str | BeautifulSoup) -> int:
    """Count visible content words, excluding non-reader document elements."""
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")
    for hidden in soup.select("script, style, template, noscript"):
        hidden.decompose()
    content = soup.find("main") or soup.find("body") or soup
    return len(" ".join(content.stripped_strings).split())


def _document_base_url(soup: BeautifulSoup, base_url: str) -> str:
    base_tag = soup.find("base", href=True)
    if isinstance(base_tag, Tag):
        try:
            candidate = urljoin(base_url, base_tag.get("href"))
            if urlsplit(candidate).scheme in {"http", "https"}:
                return candidate
        except (TypeError, ValueError):
            pass
    return base_url


def get_alternate_languages_from_html(html: str | BeautifulSoup, page_url: str) -> list[dict[str, str]]:
    """Return web alternates declared by link[rel=alternate][hreflang]."""
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")
    document_base = _document_base_url(soup, page_url)
    alternates = []
    seen = set()
    for link in soup.find_all("link"):
        relations = {str(value).casefold() for value in (link.get("rel") or [])}
        language = link.get("hreflang")
        href = link.get("href")
        if "alternate" not in relations or not isinstance(language, str) or not isinstance(href, str):
            continue
        try:
            url = urldefrag(urljoin(document_base, href))[0]
        except ValueError:
            continue
        language = language.strip().lower()
        key = (language, url)
        if language and urlsplit(url).scheme in {"http", "https"} and key not in seen:
            seen.add(key)
            alternates.append({"language": language[:35], "url": url})
    return alternates


def get_urls_from_html(html, base_url):
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")

    document_base = _document_base_url(soup, base_url)

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


def count_link_destinations(urls: list[str], page_url: str) -> dict[str, int]:
    """Summarize same-host and external web destinations."""
    page_host = (urlsplit(page_url).hostname or "").casefold()
    internal = sum((urlsplit(url).hostname or "").casefold() == page_host for url in urls)
    return {"internal": internal, "external": len(urls) - internal}


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
    document_base = _document_base_url(soup, base_url)

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
                url = urldefrag(urljoin(document_base, src))[0]
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
    outgoing_links = get_urls_from_html(soup, page_url)
    return {
        "url": page_url,
        "title": get_title_from_html(soup),
        "description": get_description_from_html(soup),
        "canonical_url": get_canonical_url_from_html(soup, page_url),
        "language": get_language_from_html(soup),
        "robots": get_robots_from_html(soup),
        "alternate_languages": get_alternate_languages_from_html(soup, page_url),
        "heading": get_heading_from_html(soup),
        "heading_counts": get_heading_counts_from_html(soup),
        "form_summary": get_form_summary_from_html(soup),
        "image_summary": get_image_summary_from_html(soup),
        "landmark_summary": get_landmark_summary_from_html(soup),
        "link_accessibility_summary": get_link_accessibility_summary_from_html(soup),
        "metadata_summary": get_metadata_summary_from_html(soup),
        "first_paragraph": get_first_paragraph_from_html(soup),
        "word_count": get_word_count_from_html(soup),
        "outgoing_links": outgoing_links,
        "link_counts": count_link_destinations(outgoing_links, page_url),
        "image_urls": get_images_from_html(soup, page_url),
    }
