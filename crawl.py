from urllib.parse import urlsplit

def normalize_url(url):
    parsed = urlsplit(url)
    return parsed.netloc + parsed.path.rstrip("/")
