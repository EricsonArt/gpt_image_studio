"""Konfiguracja GPT Image Studio.

Mapowania aspect ratio -> rozmiar w pikselach dla każdej rozdzielczości,
cennik i pomocnicze stałe.
"""

import os
from pathlib import Path
from typing import Dict, Tuple

from dotenv import load_dotenv

load_dotenv(encoding="utf-8")

ROOT_DIR = Path(__file__).parent
OUTPUTS_DIR = ROOT_DIR / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)

MODEL_ID = "gpt-image-2"

QUALITIES = ["low", "medium", "high"]
RESOLUTIONS = ["1K", "2K", "4K"]
ASPECT_RATIOS = ["1:1", "16:9", "9:16", "4:3", "3:4"]

# (aspect, resolution) -> (width, height)
# 4K = 2K + Real-ESRGAN x2 (więc native size = 2K)
SIZE_MAP: Dict[Tuple[str, str], Tuple[int, int]] = {
    ("1:1", "1K"): (1024, 1024),
    ("1:1", "2K"): (2048, 2048),
    ("1:1", "4K"): (2048, 2048),

    ("16:9", "1K"): (1280, 720),
    ("16:9", "2K"): (2560, 1440),
    ("16:9", "4K"): (2560, 1440),

    ("9:16", "1K"): (720, 1280),
    ("9:16", "2K"): (1440, 2560),
    ("9:16", "4K"): (1440, 2560),

    ("4:3", "1K"): (1024, 768),
    ("4:3", "2K"): (2048, 1536),
    ("4:3", "4K"): (2048, 1536),

    ("3:4", "1K"): (768, 1024),
    ("3:4", "2K"): (1536, 2048),
    ("3:4", "4K"): (1536, 2048),
}

# Cennik za 1 obraz w USD (przybliżony, na bazie OpenAI pricing dla gpt-image-2)
# Klucz: (quality, resolution_native) gdzie resolution_native to 1K lub 2K
PRICE_MAP: Dict[Tuple[str, str], float] = {
    ("low", "1K"): 0.011,
    ("medium", "1K"): 0.042,
    ("high", "1K"): 0.167,

    ("low", "2K"): 0.022,
    ("medium", "2K"): 0.084,
    ("high", "2K"): 0.250,
}

UPSCALE_PRICE = 0.002  # Replicate Real-ESRGAN per obraz

BATCH_MIN = 1
BATCH_MAX = 10
MAX_REFERENCE_IMAGES = 4


def get_secret(name: str, default: str = "") -> str:
    """Czyta sekret: session_state -> env var -> Streamlit secrets."""
    try:
        import streamlit as st
        if hasattr(st, "session_state") and st.session_state.get(name):
            return str(st.session_state[name])
    except Exception:
        pass

    val = os.getenv(name, "")
    if val and not val.startswith(("sk-...", "r8_...")):
        return val

    try:
        import streamlit as st
        if hasattr(st, "secrets") and name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return default


def native_resolution(resolution: str) -> str:
    """4K generujemy natywnie jako 2K, potem upscale."""
    return "2K" if resolution == "4K" else resolution


def needs_upscale(resolution: str) -> bool:
    return resolution == "4K"
