from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

ROOT_DIR = Path(__file__).resolve().parent
CATALOG_FILE = ROOT_DIR / "data" / "official_buildings_catalog.json"
OUTPUT_DIR = ROOT_DIR / "data" / "building_icons"
MANIFEST_FILE = OUTPUT_DIR / "manifest.json"
FANDOM_API_URL = "https://goodgameempire.fandom.com/api.php"
SPECIAL_FIELDS = {
    "build_tokens",
    "upgrade_tokens",
    "plaster",
    "dragon_scale_tiles",
    "talers",
    "ducats",
    "rubies",
}
MANUAL_IMAGE_SOURCES = {
    "Military academy": Path(r"C:\Users\Dima\Desktop\Military_Academy1775646642.png"),
    "Военная академия": Path(r"C:\Users\Dima\Desktop\Military_Academy1775646642.png"),
}
FANDOM_PAGE_TITLE_ALIASES = {
    "Military academy": ["Military Academy"],
    "Encampment": ["Encampment"],
    "Toolsmith": ["Toolsmith"],
    "Toolsmith-Kingdoms": ["Toolsmith"],
    "Armory": ["Armory"],
    "Moat": ["Moat"],
    "Relic woodcutter": ["Relic Woodcutter"],
    "Relic quarry": ["Relic Quarry"],
    "Relictus": ["Relicus"],
    "Refinery": ["Refinery"],
    "Refinery-Kingdoms": ["Refinery"],
}
FANDOM_FILE_TITLE_ALIASES = {
    "Military Academy": ["File:Military Academy.png"],
    "Toolsmith": ["File:Toolsmith.png"],
    "Armory": ["File:Armory.png"],
    "Relicus": ["File:Relicus.png"],
    "Relic Woodcutter": ["File:Relic Woodcutter.png"],
    "Relic Quarry": ["File:Relic Quarry.png"],
    "Refinery": ["File:Refinery.png", "File:Refinery_level_5.png"],
}
CONTENT_TYPE_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
}


def slugify(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower())
    return text.strip("_") or "building"



def extension_from_content_type(content_type: str) -> str:
    normalized = str(content_type or "").split(";", 1)[0].strip().lower()
    return CONTENT_TYPE_EXTENSIONS.get(normalized, ".png")



def extension_from_url(url: str) -> str:
    suffix = Path(urlparse(str(url or "")).path).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
        return suffix
    return ".png"



def load_catalog() -> list[dict]:
    return json.loads(CATALOG_FILE.read_text(encoding="utf-8"))



def building_matches(item: dict) -> bool:
    fields = {str(field).strip() for field in (item.get("resource_fields") or []) if str(field).strip()}
    return bool(fields & SPECIAL_FIELDS)


def api_request(params: dict[str, str]) -> dict:
    url = FANDOM_API_URL + "?" + urlencode(params)
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def unique_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def fandom_search_titles(query: str) -> list[str]:
    if not str(query or "").strip():
        return []
    data = api_request(
        {
            "action": "query",
            "list": "search",
            "srsearch": str(query),
            "format": "json",
            "srlimit": "10",
        }
    )
    return [str(item.get("title") or "").strip() for item in data.get("query", {}).get("search", []) if str(item.get("title") or "").strip()]


def fandom_file_image_url(file_title: str) -> str:
    data = api_request(
        {
            "action": "query",
            "titles": file_title,
            "prop": "imageinfo",
            "iiprop": "url",
            "format": "json",
        }
    )
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        for info in page.get("imageinfo", []) or []:
            url = str(info.get("url") or "").strip()
            if url:
                return url
    return ""


def fandom_candidate_titles(name: str, display_name: str) -> list[str]:
    seed = [name, display_name]
    for key in [name, display_name]:
        seed.extend(FANDOM_PAGE_TITLE_ALIASES.get(str(key or "").strip(), []))
    for key in [name, display_name]:
        seed.extend(fandom_search_titles(key))
    return unique_strings(seed)


def fandom_page_image_url(title: str) -> str:
    if not str(title or "").strip():
        return ""
    data = api_request(
        {
            "action": "query",
            "titles": title,
            "prop": "pageimages",
            "format": "json",
            "pithumbsize": "800",
        }
    )
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        thumbnail = page.get("thumbnail") or {}
        source = str(thumbnail.get("source") or "").strip()
        if source:
            return source

    file_titles = list(FANDOM_FILE_TITLE_ALIASES.get(title, []))
    base_title = str(title).strip()
    if base_title:
        file_titles.extend(
            [
                f"File:{base_title}.png",
                f"File:{base_title}.jpg",
                f"File:{base_title}.jpeg",
                f"File:{base_title}.webp",
            ]
        )
    for file_title in unique_strings(file_titles):
        image_url = fandom_file_image_url(file_title)
        if image_url:
            return image_url
    return ""


def resolve_fandom_image_url(name: str, display_name: str) -> str:
    for title in fandom_candidate_titles(name, display_name):
        image_url = fandom_page_image_url(title)
        if image_url:
            return image_url
    return ""



def download_image(url: str) -> tuple[bytes, str]:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=30) as response:
        data = response.read()
        content_type = getattr(response.headers, "get_content_type", lambda: "")()
    return data, str(content_type or "")



def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    catalog = load_catalog()
    manifest: list[dict] = []

    for item in catalog:
        if not isinstance(item, dict) or not building_matches(item):
            continue
        name = str(item.get("name") or "").strip()
        display_name = str(item.get("display_name") or name).strip()
        slug = slugify(name or display_name)
        manual_source = MANUAL_IMAGE_SOURCES.get(name) or MANUAL_IMAGE_SOURCES.get(display_name)
        image_url = str(item.get("image_url") or "").strip()

        if manual_source and manual_source.exists():
            target = OUTPUT_DIR / f"{slug}{manual_source.suffix.lower() or '.png'}"
            shutil.copy2(manual_source, target)
            manifest.append(
                {
                    "name": name,
                    "display_name": display_name,
                    "status": "copied_manual",
                    "image_path": str(target),
                    "image_url": image_url,
                }
            )
            continue

        resolved_image_url = image_url or resolve_fandom_image_url(name, display_name)

        if resolved_image_url:
            try:
                data, content_type = download_image(resolved_image_url)
                ext = extension_from_content_type(content_type) if content_type else extension_from_url(resolved_image_url)
                target = OUTPUT_DIR / f"{slug}{ext}"
                target.write_bytes(data)
                manifest.append(
                    {
                        "name": name,
                        "display_name": display_name,
                        "status": "downloaded",
                        "image_path": str(target),
                        "image_url": resolved_image_url,
                    }
                )
                continue
            except Exception as exc:
                manifest.append(
                    {
                        "name": name,
                        "display_name": display_name,
                        "status": "download_failed",
                        "image_path": "",
                        "image_url": resolved_image_url,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                continue

        manifest.append(
            {
                "name": name,
                "display_name": display_name,
                "status": "missing_source",
                "image_path": "",
                "image_url": "",
            }
        )

    MANIFEST_FILE.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    downloaded = sum(1 for item in manifest if item.get("status") in {"downloaded", "copied_manual"})
    missing = sum(1 for item in manifest if item.get("status") == "missing_source")
    failed = sum(1 for item in manifest if item.get("status") == "download_failed")
    print(f"Processed: {len(manifest)}")
    print(f"Downloaded or copied: {downloaded}")
    print(f"Missing source: {missing}")
    print(f"Failed downloads: {failed}")
    print(f"Manifest: {MANIFEST_FILE}")


if __name__ == "__main__":
    main()
