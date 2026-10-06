"""Core image → ASCII conversion. Mirrors the logic in web/app.js."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from PIL import Image

CHARSETS = {
    "standard": " .:-=+*#%@",
    "detailed": " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
    "blocks": " ░▒▓█",
    "binary": " 01",
    "dots": " ·•●",
}

GRADIENT_DIRS = ("horizontal", "vertical", "diagonal", "radial", "brightness")

RGB = tuple[int, int, int]


@dataclass
class Settings:
    cols: int = 100
    charset: str = CHARSETS["standard"]
    variance: float = 0.0
    invert: bool = False
    brightness: float = 0.0  # -1 .. 1
    contrast: float = 0.0  # -1 .. 1
    gamma: float = 1.0
    char_aspect: float = 0.5  # cell width / cell height
    color_mode: str = "none"  # none | solid | original | gradient
    fg: RGB = (232, 232, 232)
    grad_start: RGB = (255, 60, 120)
    grad_end: RGB = (60, 200, 255)
    grad_dir: str = "horizontal"


@dataclass
class Cell:
    ch: str
    b: float
    rgb: RGB


@dataclass
class AsciiArt:
    cols: int
    rows: int
    grid: list[list[Cell]] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join("".join(c.ch for c in row) for row in self.grid)


def clamp01(v: float) -> float:
    return min(1.0, max(0.0, v))


def cell_noise(x: int, y: int) -> float:
    """Deterministic per-cell noise in [-1, 1] (same hash as the web version)."""
    h = (x * 374761393 + y * 668265263) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    h ^= h >> 16
    return (h / 4294967295) * 2 - 1


def adjust_tone(b: float, s: Settings) -> float:
    k = 1 + s.contrast * 3 if s.contrast >= 0 else 1 + s.contrast
    b = (b - 0.5) * k + 0.5 + s.brightness
    b = clamp01(b) ** (1 / s.gamma)
    return 1 - b if s.invert else b


def gradient_t(x: int, y: int, cols: int, rows: int, b: float, direction: str) -> float:
    u = x / (cols - 1) if cols > 1 else 0.0
    v = y / (rows - 1) if rows > 1 else 0.0
    if direction == "vertical":
        return v
    if direction == "diagonal":
        return (u + v) / 2
    if direction == "radial":
        return clamp01(math.hypot(u - 0.5, v - 0.5) / math.sqrt(0.5))
    if direction == "brightness":
        return b
    return u


def cell_color(art: AsciiArt, x: int, y: int, s: Settings) -> RGB | None:
    cell = art.grid[y][x]
    if s.color_mode == "solid":
        return s.fg
    if s.color_mode == "original":
        return cell.rgb
    if s.color_mode == "gradient":
        t = gradient_t(x, y, art.cols, art.rows, cell.b, s.grad_dir)
        a, b = s.grad_start, s.grad_end
        return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))  # type: ignore[return-value]
    return None


def convert(image: Image.Image, s: Settings) -> AsciiArt:
    img = image.convert("RGBA")
    cols = max(1, s.cols)
    rows = max(1, round(img.height / img.width * cols * s.char_aspect))
    px = img.resize((cols, rows), Image.Resampling.BOX).load()

    chars = s.charset if len(s.charset) >= 2 else " @"
    last = len(chars) - 1
    spread = s.variance * max(1.0, last * 0.5)

    art = AsciiArt(cols, rows)
    for y in range(rows):
        row = []
        for x in range(cols):
            r, g, bl, a = px[x, y]
            lum = (0.2126 * r + 0.7152 * g + 0.0722 * bl) / 255 * (a / 255)
            b = adjust_tone(lum, s)

            idx = b * last
            if spread > 0:
                idx += cell_noise(x, y) * spread
            idx = round(min(last, max(0, idx)))
            row.append(Cell(chars[idx], b, (r, g, bl)))
        art.grid.append(row)
    return art
