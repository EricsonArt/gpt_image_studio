"""Wrapper na OpenAI gpt-image-2 (generations + edits)."""

import base64
import io
import requests as _requests
from typing import List, Optional

from openai import OpenAI

import config

# Parametry nieobsługiwane przez gpt-image-2 w generate/edit
_UNSUPPORTED = {"quality", "response_format"}

# Mapowanie quality -> sufiks promptu (gpt-image-2 nie ma param quality)
_QUALITY_SUFFIX = {
    "low":    "",
    "medium": "high quality",
    "high":   "ultra high quality, intricate details, 8k, masterpiece",
}


def _client() -> OpenAI:
    api_key = config.get_secret("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Brak OPENAI_API_KEY — wpisz klucz w sidebarze.")
    return OpenAI(api_key=api_key)


def _named_buf(data: bytes, name: str = "image.png") -> io.BytesIO:
    buf = io.BytesIO(data)
    buf.name = name
    return buf


def _extract_images(result) -> List[bytes]:
    """Obsługuje b64_json i url w odpowiedzi."""
    out = []
    for item in result.data:
        if getattr(item, "b64_json", None):
            out.append(base64.b64decode(item.b64_json))
        elif getattr(item, "url", None):
            resp = _requests.get(item.url, timeout=60)
            resp.raise_for_status()
            out.append(resp.content)
    return out


def _build_size(aspect: str, resolution: str) -> str:
    native = config.native_resolution(resolution)
    w, h = config.SIZE_MAP[(aspect, native)]
    return f"{w}x{h}"


def _enrich_prompt(prompt: str, quality: str, negative_prompt: str = "") -> str:
    suffix = _QUALITY_SUFFIX.get(quality, "")
    full = prompt.strip()
    if suffix:
        full = f"{full}, {suffix}"
    if negative_prompt.strip():
        full += f". Avoid: {negative_prompt.strip()}"
    return full


def generate_images(
    prompt: str,
    quality: str,
    aspect_ratio: str,
    resolution: str,
    n: int,
    reference_images: Optional[List[bytes]] = None,
    negative_prompt: str = "",
) -> List[bytes]:
    """Generuje n obrazów. Zwraca listę bajtów PNG."""
    if not prompt.strip():
        raise ValueError("Prompt nie może być pusty.")

    client = _client()
    full_prompt = _enrich_prompt(prompt, quality, negative_prompt)
    size = _build_size(aspect_ratio, resolution)

    if reference_images:
        named = [_named_buf(img, f"ref_{i}.png") for i, img in enumerate(reference_images)]
        result = client.images.edit(
            model=config.MODEL_ID,
            prompt=full_prompt,
            image=named,
            size=size,
            n=n,
        )
    else:
        result = client.images.generate(
            model=config.MODEL_ID,
            prompt=full_prompt,
            size=size,
            n=n,
        )

    images = _extract_images(result)
    if not images:
        raise RuntimeError("API zwróciło pustą odpowiedź — sprawdź klucz API i prompt.")
    return images


def edit_image(
    image_bytes: bytes,
    prompt: str,
    quality: str,
    aspect_ratio: str,
    resolution: str,
    mask_bytes: Optional[bytes] = None,
    n: int = 1,
) -> List[bytes]:
    """Edytuje/inpaintuje obraz. Zwraca listę bajtów PNG."""
    if not prompt.strip():
        raise ValueError("Prompt nie może być pusty.")

    client = _client()
    full_prompt = _enrich_prompt(prompt, quality)
    size = _build_size(aspect_ratio, resolution)

    kwargs = dict(
        model=config.MODEL_ID,
        prompt=full_prompt,
        image=_named_buf(image_bytes, "image.png"),
        size=size,
        n=n,
    )
    if mask_bytes:
        kwargs["mask"] = _named_buf(mask_bytes, "mask.png")

    result = client.images.edit(**kwargs)
    images = _extract_images(result)
    if not images:
        raise RuntimeError("API zwróciło pustą odpowiedź.")
    return images
