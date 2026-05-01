"""Zapis i odczyt historii wygenerowanych obrazów."""

import hashlib
import json
import time
import unicodedata
from pathlib import Path
from typing import Dict, List

import config


def _slugify(text: str, max_len: int = 30) -> str:
    """ASCII-safe slug — polskie litery zamieniamy na ekwiwalenty łacińskie."""
    # Normalizacja NFKD + odrzucenie znaków diakrytycznych → czyste ASCII
    normalized = unicodedata.normalize("NFKD", text)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    safe = "".join(c if c.isalnum() else "_" for c in ascii_only.lower())[:max_len]
    return safe.strip("_") or "img"


def save_generation(images: List[bytes], metadata: Dict) -> Path:
    """Zapisuje obrazy + JSON metadane. Zwraca ścieżkę folderu."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    prompt = metadata.get("prompt", "")
    prompt_preview = _slugify(prompt)
    hash_short = hashlib.md5(
        f"{timestamp}_{prompt}".encode("utf-8")
    ).hexdigest()[:6]

    folder = config.OUTPUTS_DIR / f"{timestamp}_{prompt_preview}_{hash_short}"
    folder.mkdir(parents=True, exist_ok=True)

    for i, img_bytes in enumerate(images, 1):
        img_path = folder / f"image_{i}.png"
        img_path.write_bytes(img_bytes)

        meta_path = folder / f"image_{i}.json"
        item_meta = {**metadata, "file": img_path.name, "index": i}
        meta_path.write_text(
            json.dumps(item_meta, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    return folder


def load_history(limit: int = 50) -> List[Dict]:
    """Zwraca listę generacji od najnowszych."""
    if not config.OUTPUTS_DIR.exists():
        return []

    folders = sorted(
        [f for f in config.OUTPUTS_DIR.iterdir() if f.is_dir()],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )[:limit]

    result = []
    for folder in folders:
        items = []
        for png in sorted(folder.glob("image_*.png")):
            metadata = {}
            json_path = png.with_suffix(".json")
            if json_path.exists():
                try:
                    metadata = json.loads(json_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            items.append({"path": str(png), "metadata": metadata})

        if items:
            result.append({
                "folder": str(folder),
                "name": folder.name,
                "mtime": folder.stat().st_mtime,
                "items": items,
            })

    return result


def get_first_prompt(entry: Dict) -> str:
    if entry.get("items"):
        return entry["items"][0].get("metadata", {}).get("prompt", "")
    return ""
