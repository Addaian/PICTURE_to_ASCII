"""Core image → ASCII conversion. Mirrors the logic in web/app.js."""

from __future__ import annotations

import math
import numbers
import re
from dataclasses import dataclass, field, fields
from pathlib import Path

from PIL import Image, ImageOps

CHARSETS = {
    "standard": " .:-=+*#%@",
    "detailed": " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
    "blocks": " ░▒▓█",
    "binary": " 01",
    "dots": " ·•●",
}

GRADIENT_DIRS = ("horizontal", "vertical", "diagonal", "radial", "brightness")

COLOR_MODES = ("none", "solid", "original", "gradient")

RGB = tuple[int, int, int]

_HEX_RE = re.compile(r"#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})")


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

    def __post_init__(self) -> None:
        if isinstance(self.cols, bool) or not isinstance(self.cols, numbers.Integral) or self.cols < 1:
            raise ValueError(f"cols must be a positive integer, got {self.cols!r}")
        self.cols = int(self.cols)
        if not self.charset:
            raise ValueError("charset must not be empty")
        if not (math.isfinite(self.gamma) and self.gamma > 0):
            raise ValueError(f"gamma must be > 0, got {self.gamma!r}")
        if not (math.isfinite(self.char_aspect) and self.char_aspect > 0):
            raise ValueError(f"char_aspect must be > 0, got {self.char_aspect!r}")
        if self.color_mode not in COLOR_MODES:
            raise ValueError(f"color_mode must be one of {COLOR_MODES}, got {self.color_mode!r}")
        if self.grad_dir not in GRADIENT_DIRS:
            raise ValueError(f"grad_dir must be one of {GRADIENT_DIRS}, got {self.grad_dir!r}")
        self.fg = parse_color(self.fg)
        self.grad_start = parse_color(self.grad_start)
        self.grad_end = parse_color(self.grad_end)


@dataclass
class Cell:
    ch: str
    b: float
    rgb: RGB


@dataclass
class AsciiArt:
    cols: int
    rows: int
    settings: Settings = field(default_factory=Settings)
    grid: list[list[Cell]] = field(default_factory=list)

    @property
    def text(self) -> str:
        """Plain ASCII text, rows joined by newlines."""
        return "\n".join("".join(c.ch for c in row) for row in self.grid)

    def __str__(self) -> str:
        return self.text

    def to_ansi(self, bg: RGB | str | None = None) -> str:
        """Text with 24-bit ANSI color codes for printing to a terminal."""
        from .render import to_ansi

        return to_ansi(self, self.settings, parse_color(bg) if bg is not None else None)

    def to_image(self, **png_options) -> Image.Image:
        """Render to a PIL image. Options: font_size, line_height, bg, font_path, padding."""
        from .render import render_image

        if "bg" in png_options:
            png_options["bg"] = parse_color(png_options["bg"])
        return render_image(self, self.settings, **png_options)

    def save(self, path: str | Path, **png_options) -> None:
        """Save as PNG (if path ends in .png) or plain text."""
        path = Path(path)
        if path.suffix.lower() == ".png":
            self.to_image(**png_options).save(path)
        else:
            path.write_text(self.text + "\n", encoding="utf-8")


def parse_color(value: RGB | str) -> RGB:
    """Accept an (r, g, b) tuple or a hex string like '#ff8800' / 'f80'."""
    if isinstance(value, str):
        m = _HEX_RE.fullmatch(value)
        if not m:
            raise ValueError(f"invalid hex color: {value!r}")
        v = m.group(1)
        if len(v) == 3:
            v = "".join(c * 2 for c in v)
        n = int(v, 16)
        return ((n >> 16) & 255, (n >> 8) & 255, n & 255)
    rgb = tuple(int(c) for c in value)
    if len(rgb) != 3 or not all(0 <= c <= 255 for c in rgb):
        raise ValueError(f"RGB color must be three values 0-255, got {value!r}")
    return rgb  # type: ignore[return-value]


def round_half_up(v: float) -> int:
    """Match JavaScript's Math.round so the CLI and web app produce identical output."""
    return math.floor(v + 0.5)


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


def to_rgba(image: Image.Image) -> Image.Image:
    """Apply EXIF orientation and normalise any Pillow mode (incl. 16-bit / float) to 8-bit RGBA."""
    img = ImageOps.exif_transpose(image) or image
    if img.mode.startswith("I;16"):
        img = img.convert("I").point(lambda v: v / 257).convert("L")
    elif img.mode in ("I", "F"):
        lo, hi = img.convert("F").getextrema()
        if hi > lo:
            scale = 255 / (hi - lo)
            img = img.convert("F").point(lambda v: (v - lo) * scale).convert("L")
        else:  # flat image: no range to stretch, treat any positive value as white
            img = Image.new("L", img.size, 255 if lo > 0 else 0)
    return img.convert("RGBA")


def convert(image: Image.Image, s: Settings) -> AsciiArt:
    img = to_rgba(image)
    cols = s.cols
    rows = max(1, round_half_up(img.height / img.width * cols * s.char_aspect))
    px = img.resize((cols, rows), Image.Resampling.BOX).load()

    chars = s.charset if len(s.charset) >= 2 else " @"
    last = len(chars) - 1
    spread = s.variance * max(1.0, last * 0.5)

    art = AsciiArt(cols, rows, s)
    for y in range(rows):
        row = []
        for x in range(cols):
            r, g, bl, a = px[x, y]
            lum = (0.2126 * r + 0.7152 * g + 0.0722 * bl) / 255 * (a / 255)
            b = adjust_tone(lum, s)

            idx = b * last
            if spread > 0:
                idx += cell_noise(x, y) * spread
            idx = round_half_up(min(last, max(0, idx)))
            row.append(Cell(chars[idx], b, (r, g, bl)))
        art.grid.append(row)
    return art


def image_to_ascii(image: str | Path | Image.Image, **options) -> AsciiArt:
    """Convert an image (path or PIL Image) to ASCII art.

    Keyword options are the fields of :class:`Settings`. ``charset`` may be a
    preset name from :data:`CHARSETS` or a custom string; colors may be hex
    strings or RGB tuples.

    >>> art = image_to_ascii("photo.jpg", cols=80, charset="blocks", color_mode="original")
    >>> print(art.to_ansi())
    >>> art.save("art.png", font_size=14)
    """
    valid = {f.name for f in fields(Settings)}
    unknown = set(options) - valid
    if unknown:
        raise TypeError(f"unknown option(s): {', '.join(sorted(unknown))}")

    charset = options.get("charset")
    if charset in CHARSETS:
        options["charset"] = CHARSETS[charset]

    if not isinstance(image, Image.Image):
        with Image.open(image) as img:
            img.load()
            image = img.copy()
    return convert(image, Settings(**options))
