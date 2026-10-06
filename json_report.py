"""Write deterministic reports atomically, preserving an existing file on failure."""
import json
import os
import tempfile
from pathlib import Path


def write_json_report(page_data, filename="report.json"):
    pages = sorted((page for page in page_data.values() if page is not None),
                   key=lambda page: page["url"])
    target = Path(filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent,
                                         prefix=f".{target.name}.", delete=False) as file:
            temporary = file.name
            json.dump(pages, file, indent=2, ensure_ascii=False)
            file.write("\n")
        os.replace(temporary, target)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
