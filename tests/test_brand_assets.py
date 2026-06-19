"""Structural tests for the brand assets and the README logo header.

The logo is shown on both GitHub (light *and* dark themes) and PyPI (the README
is the PyPI long-description). These assert the asset files exist and are real
images, that the README's logo block swaps by colour scheme with a PyPI-safe
fallback, and that every asset URL the README names points at a file we actually
ship in assets/ — so a typo'd path can't render as a broken image on PyPI.
"""

import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
README = (ROOT / "README.md").read_text()

RAW_PREFIX = "https://raw.githubusercontent.com/Shreyas0786/ticketly/main/assets/"

# The assets the repo ships, with expected square icon dimensions where relevant.
EXPECTED_ASSETS = {
    "ticketly-logo-light.png": None,
    "ticketly-logo-dark.png": None,
    "ticketly-icon-512.png": (512, 512),
    "ticketly-icon-256.png": (256, 256),
    "ticketly-icon.svg": None,
    "ticketly-social.png": None,
}


def _png_size(path: Path):
    """Width/height from a PNG's IHDR, without an image library."""
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} is not a valid PNG"
    return struct.unpack(">II", data[16:24])


def test_assets_exist_and_are_real_images():
    for name, dims in EXPECTED_ASSETS.items():
        path = ASSETS / name
        assert path.is_file(), f"missing asset: assets/{name}"
        assert path.stat().st_size > 0, f"empty asset: assets/{name}"
        if name.endswith(".png"):
            assert _png_size(path)  # validates the PNG signature too
        if name.endswith(".svg"):
            assert "<svg" in path.read_text(), f"assets/{name} is not an SVG"
        if dims is not None:
            assert _png_size(path) == dims, f"assets/{name} expected {dims}"


def test_readme_asset_urls_resolve_to_shipped_files():
    # every assets/ URL the README names must map to a file we actually ship
    referenced = set(re.findall(re.escape(RAW_PREFIX) + r"([\w./-]+)", README))
    assert referenced, "README references no brand assets"
    for name in referenced:
        assert (ASSETS / name).is_file(), f"README points at missing assets/{name}"


def test_logo_swaps_by_colour_scheme():
    assert "<picture>" in README and "</picture>" in README
    assert "prefers-color-scheme: dark" in README
    assert "prefers-color-scheme: light" in README
    assert RAW_PREFIX + "ticketly-logo-dark.png" in README
    assert RAW_PREFIX + "ticketly-logo-light.png" in README


def test_fallback_img_is_pypi_safe():
    # PyPI renders on a white page and ignores <source>, so the <img> fallback
    # must be the light (dark-text) logo, not the dark (white-text) one.
    img = re.search(r"<img[^>]*\bsrc=\"([^\"]+)\"", README)
    assert img, "README logo has no <img> fallback"
    assert img.group(1) == RAW_PREFIX + "ticketly-logo-light.png"
    assert 'alt="Ticketly"' in README  # accessible name in place of the dropped H1
