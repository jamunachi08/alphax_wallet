"""
alphax_wallet.alphax_wallet.palette_utils
=========================================

Derive a full theme palette from a small number of seed colours (typically
extracted from a logo image client-side using Canvas).

The math:
  - Convert hex → HSL (the most perceptually-uniform space for colour math)
  - Lighten = increase L, decrease S slightly
  - Darken = decrease L, decrease S slightly
  - Soft tint = boost L close to 1, drop S significantly
  - Pick complementary / analogous accents on the colour wheel

This is the same approach Material Design and Tailwind use to generate
shade scales from a brand colour.
"""

from __future__ import annotations

import colorsys
from typing import Tuple


# ----------------------------------------------------------------------------
# Hex ↔ HSL conversions
# ----------------------------------------------------------------------------

def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """'#7A2F87' → (122, 47, 135)"""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise ValueError(f"Invalid hex: {hex_color}")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """(122, 47, 135) → '#7A2F87'"""
    return "#{:02X}{:02X}{:02X}".format(
        max(0, min(255, int(r))),
        max(0, min(255, int(g))),
        max(0, min(255, int(b))),
    )


def hex_to_hsl(hex_color: str) -> Tuple[float, float, float]:
    """Return HSL in 0..1 range."""
    r, g, b = hex_to_rgb(hex_color)
    h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    return (h, s, l)


def hsl_to_hex(h: float, s: float, l: float) -> str:
    s = max(0.0, min(1.0, s))
    l = max(0.0, min(1.0, l))
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return rgb_to_hex(r * 255, g * 255, b * 255)


# ----------------------------------------------------------------------------
# Shade operations
# ----------------------------------------------------------------------------

def lighten(hex_color: str, amount: float = 0.15) -> str:
    """Increase lightness by `amount` (0..1)."""
    h, s, l = hex_to_hsl(hex_color)
    return hsl_to_hex(h, s, l + amount)


def darken(hex_color: str, amount: float = 0.15) -> str:
    """Decrease lightness by `amount`."""
    h, s, l = hex_to_hsl(hex_color)
    return hsl_to_hex(h, s, l - amount)


def soft_tint(hex_color: str) -> str:
    """Very light, low-saturation version — good for background tints."""
    h, s, l = hex_to_hsl(hex_color)
    return hsl_to_hex(h, max(s * 0.3, 0.15), 0.95)


def to_dark_surface(hex_color: str, level: int = 0) -> str:
    """
    Generate a dark surface colour anchored to the primary hue.
    level: 0 = deepest (base), 1 = mid, 2 = elevated.
    """
    h, s, l = hex_to_hsl(hex_color)
    # Lock saturation to a moody mid-range, lock lightness very low
    new_s = max(min(s, 0.7), 0.5)
    new_l = 0.06 + (level * 0.05)  # 0.06, 0.11, 0.16
    return hsl_to_hex(h, new_s, new_l)


def complementary(hex_color: str) -> str:
    """The colour 180° opposite on the wheel."""
    h, s, l = hex_to_hsl(hex_color)
    return hsl_to_hex((h + 0.5) % 1.0, s, l)


def analogous(hex_color: str, shift: float = 0.083) -> str:
    """30° (default) along the wheel — used for accent colours."""
    h, s, l = hex_to_hsl(hex_color)
    return hsl_to_hex((h + shift) % 1.0, s, l)


def warm_accent(primary: str) -> str:
    """
    Pick a warm gold/amber accent. We do this by anchoring to a fixed
    'warm hue' (around 40° on the wheel = gold) but borrowing the primary's
    saturation so the gold harmonises with the brand.
    """
    h, s, l = hex_to_hsl(primary)
    # 40° hue = gold; clamp lightness mid-range, keep saturation rich
    return hsl_to_hex(40 / 360, max(s, 0.55), 0.57)


def pink_accent(primary: str) -> str:
    """
    Rose/pink accent for 'live' indicators. Anchored to 340° (pink) with
    primary's saturation profile.
    """
    h, s, l = hex_to_hsl(primary)
    return hsl_to_hex(340 / 360, max(s * 0.7, 0.4), 0.66)


# ----------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------

def derive_palette(seeds: dict) -> dict:
    """
    Take a small dict of seed colours and derive the full palette.

    Inputs (any subset; the most useful is just `primary`):
        {
            "primary": "#7A2F87",
            "accent": "#D9A54A",      # optional
            "pink": "#D97A9E",        # optional
            "dark_base": "#18061F",   # optional
        }

    Returns the full palette dict ready to be saved on Wallet Theme.
    """
    primary = seeds.get("primary") or "#7A2F87"

    accent = seeds.get("accent") or warm_accent(primary)
    pink = seeds.get("pink") or pink_accent(primary)
    dark_base = seeds.get("dark_base") or to_dark_surface(primary, 0)

    palette = {
        "primary": primary,
        "primary_dark": darken(primary, 0.12),
        "primary_light": lighten(primary, 0.12),
        "primary_soft": soft_tint(primary),

        "accent": accent,
        "accent_light": lighten(accent, 0.12),

        "pink": pink,
        "pink_dark": darken(pink, 0.08),

        "dark_base": dark_base,
        "dark_mid": to_dark_surface(primary, 1),
        "dark_elev": to_dark_surface(primary, 2),

        "text_on_dark": "#F5EDEF",
        "text_on_dark_muted": "#E6D6BE",
        "text_on_dark_faint": lighten(primary, 0.30),
    }
    return palette


def palette_to_css_variables(theme: dict) -> str:
    """Render a palette dict as a `:root { --ax-X: Y; }` CSS block."""
    rules = []
    mapping = {
        "primary": "--ax-primary",
        "primary_dark": "--ax-primary-dark",
        "primary_light": "--ax-primary-light",
        "primary_soft": "--ax-primary-soft",
        "accent": "--ax-accent",
        "accent_light": "--ax-accent-light",
        "pink": "--ax-pink",
        "pink_dark": "--ax-pink-dark",
        "dark_base": "--ax-dark-base",
        "dark_mid": "--ax-dark-mid",
        "dark_elev": "--ax-dark-elev",
        "text_on_dark": "--ax-text-on-dark",
        "text_on_dark_muted": "--ax-text-on-dark-muted",
        "text_on_dark_faint": "--ax-text-on-dark-faint",
    }
    for field, var in mapping.items():
        val = theme.get(field)
        if val:
            rules.append(f"  {var}: {val};")
            # Also write the legacy --alphax-* names so old CSS keeps working
            legacy = var.replace("--ax-", "--alphax-")
            rules.append(f"  {legacy}: {val};")
    return ":root {\n" + "\n".join(rules) + "\n}\n"
