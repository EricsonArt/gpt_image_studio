"""Szacowanie kosztu generacji przed kliknięciem Generate."""

import config


def estimate_cost(quality: str, resolution: str, n: int) -> float:
    native_res = config.native_resolution(resolution)
    per_image = config.PRICE_MAP.get((quality, native_res), 0.0)
    total = per_image * n
    if config.needs_upscale(resolution):
        total += config.UPSCALE_PRICE * n
    return total


def format_cost(cost: float) -> str:
    if cost < 0.01:
        return f"<$0.01"
    return f"${cost:.2f}"
