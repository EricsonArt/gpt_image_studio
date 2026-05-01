"""Upscaling 2K -> 4K przez Real-ESRGAN na Replicate.

Fallback: Pillow Lanczos jeśli Replicate niedostępne.
"""

import io
from typing import Optional

import requests
from PIL import Image

import config


REPLICATE_MODEL = "nightmareai/real-esrgan"


def _replicate_available() -> bool:
    return bool(config.get_secret("REPLICATE_API_TOKEN"))


def _upscale_replicate(image_bytes: bytes, scale: int = 2) -> bytes:
    import replicate

    token = config.get_secret("REPLICATE_API_TOKEN")
    client = replicate.Client(api_token=token)

    # Real-ESRGAN przyjmuje data URI lub publiczny URL
    import base64
    data_uri = "data:image/png;base64," + base64.b64encode(image_bytes).decode()

    output_url = client.run(
        REPLICATE_MODEL,
        input={
            "image": data_uri,
            "scale": scale,
            "face_enhance": False,
        },
    )

    if isinstance(output_url, list):
        output_url = output_url[0]
    if hasattr(output_url, "read"):
        return output_url.read()

    resp = requests.get(str(output_url), timeout=120)
    resp.raise_for_status()
    return resp.content


def _upscale_lanczos(image_bytes: bytes, scale: int = 2) -> bytes:
    img = Image.open(io.BytesIO(image_bytes))
    new_size = (img.width * scale, img.height * scale)
    upscaled = img.resize(new_size, Image.LANCZOS)
    buf = io.BytesIO()
    upscaled.save(buf, format="PNG")
    return buf.getvalue()


def upscale_to_4k(image_bytes: bytes, allow_fallback: bool = True) -> bytes:
    """Upscale obrazu 2K do 4K. Próbuje Real-ESRGAN, fallback Lanczos."""
    if _replicate_available():
        try:
            return _upscale_replicate(image_bytes, scale=2)
        except Exception as e:
            if not allow_fallback:
                raise
            print(f"[upscaler] Replicate failed, fallback Lanczos")
    return _upscale_lanczos(image_bytes, scale=2)


def has_replicate() -> bool:
    return _replicate_available()
