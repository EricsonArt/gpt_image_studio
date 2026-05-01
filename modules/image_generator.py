"""Wrapper na OpenAI gpt-image-2."""

import base64
import io
import requests as _requests
from typing import List, Optional

from openai import OpenAI

import config

# quality → sufiks promptu (gpt-image-2 nie obsługuje param quality)
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
    out = []
    for item in result.data:
        if getattr(item, "b64_json", None):
            out.append(base64.b64decode(item.b64_json))
        elif getattr(item, "url", None):
            resp = _requests.get(item.url, timeout=60)
            resp.raise_for_status()
            out.append(resp.content)
    return out


def _enrich_prompt(prompt: str, quality: str, negative_prompt: str = "") -> str:
    full = prompt.strip()
    suffix = _QUALITY_SUFFIX.get(quality, "")
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
    size = config.get_size(aspect_ratio, resolution)

    try:
        if reference_images:
            named = [_named_buf(img, f"ref_{i}.png") for i, img in enumerate(reference_images)]
            result = client.images.edit(
                model=config.MODEL_ID, prompt=full_prompt, image=named, size=size, n=n,
            )
        else:
            result = client.images.generate(
                model=config.MODEL_ID, prompt=full_prompt, size=size, n=n,
            )
    except Exception as e:
        err_str = str(e)
        if "must be verified" in err_str or "403" in err_str:
            raise RuntimeError(
                "Twoja organizacja OpenAI nie jest jeszcze zweryfikowana.\n\n"
                "Weryfikacja jest wymagana do gpt-image-2.\n"
                "Przejdz na: platform.openai.com/settings/organization/general\n"
                "i kliknij Start przy 'Individual'. Potem poczekaj ~15 minut."
            ) from None
        raise

    images = _extract_images(result)
    if not images:
        raise RuntimeError("API zwrocilo pusta odpowiedz.")
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
    """Edytuje/inpaintuje obraz."""
    if not prompt.strip():
        raise ValueError("Prompt nie moze byc pusty.")

    client = _client()
    full_prompt = _enrich_prompt(prompt, quality)
    size = config.get_size(aspect_ratio, resolution)

    kwargs = dict(
        model=config.MODEL_ID,
        prompt=full_prompt,
        image=_named_buf(image_bytes),
        size=size,
        n=n,
    )
    if mask_bytes:
        kwargs["mask"] = _named_buf(mask_bytes, "mask.png")

    try:
        result = client.images.edit(**kwargs)
    except Exception as e:
        if "must be verified" in str(e) or "403" in str(e):
            raise RuntimeError(
                "Organizacja wymaga weryfikacji. Kliknij Start/Individual na "
                "platform.openai.com/settings/organization/general"
            ) from None
        raise

    images = _extract_images(result)
    if not images:
        raise RuntimeError("API zwrocilo pusta odpowiedz.")
    return images
