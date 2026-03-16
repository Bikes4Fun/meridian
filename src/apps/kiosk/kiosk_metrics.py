"""
Kiosk display metrics: font/dimension helpers.
TV spec values used directly; no scaling.
"""


def scaled(base_px: float) -> int:
    """Font size or dimension. base_px = TV spec value."""
    return max(1, int(base_px))
