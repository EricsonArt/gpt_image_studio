"""Zapis i odczyt historii wygenerowanych obrazów.

Każda generacja ląduje w outputs/<timestamp>_<hash>/ jako image_N.png + image_N.json.
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Dict, List, Optional

import config


def _slugify(text: str, max_len: int = 30) -> str:
    safe = "".join(c if c.isalnum() else "_" for c in text.lower())[:max_len]
    return safe.strip("_") or "img"


def save_generation(
    images: List[bytes],
    metadata: Dict,
) -> Path:
    """Zapisuje wygenerowane obrazy + JSON metadane. Zwraca ścieżkę folderu."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    prompt_preview = _slugify(metadata.get("prompt", ""))
    hash_short = hashlib.md5(
        f"{timestamp}_{metadata.get('prompt','')}".encode()
    ).hexdigest()[:6]

    folder_name = f"{timestamp}_{prompt_preview}_{hash_short}"
    folder = config.OUTPUTS_DIR / folder_name
    folder.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    for i, img_bytes in enumerate(images, 1):
        img_path = folder / f"image_{i}.png"
        img_path.write_bytes(img_bytes)
        saved_paths.append(str(img_path.name))

        meta_path = folder / f"image_{i}.json"
        item_meta = {**metadata, "file": img_path.name, "index": i}
        meta_path.write_text(
            json.dumps(item_meta, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    return folder


def load_history(limit: int = 50) -> List[Dict]:
    """Zwraca listę wpisów: {folder, timestamp, items: [{path, metadata}]}.

    Sortowane od najnowszych.
    """
    if not config.OUTPUTS_DIR.exists():
        return []

    folders = sorted(
        [f for f in config.OUTPUTS_DIR.iterdir() if f.is_dir()],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )[:limit]

    history = []
    for folder in folders:
        items = []
        for png in sorted(folder.glob("image_*.png")):
            json_path = png.with_suffix(".json")
            metadata = {}
            if json_path.exists():
                try:
                    metadata = json.loads(json_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            items.append({"path": str(png), "metadata": metadata})

        if items:
            history.append({
                "folder": str(folder),
                "name": folder.name,
                "mtime": folder.stat().st_mtime,
                "items": items,
            })

    return history


def get_first_prompt(entry: Dict) -> str:
    if entry.get("items"):
        return entry["items"][0].get("metadata", {}).get("prompt", "")
    return ""
