"""
Kiosk display metrics: scaled font/dimension helpers.
Reference dimensions and dev settings live in shared.config.
"""

from shared.config import (
    KIOSK_REFERENCE_HEIGHT,
    get_kiosk_dev_height,
    get_kiosk_dev_scale,
)


def scale_factor() -> float:
    """Scale for fonts/layout. Height ratio so proportions match TV."""
    if not get_kiosk_dev_scale():
        return 1.0
    return get_kiosk_dev_height() / KIOSK_REFERENCE_HEIGHT


def scaled(base_px: float) -> int:
    """Font size or dimension scaled for current mode. base_px = TV spec value."""
    return max(1, int(base_px * scale_factor()))
