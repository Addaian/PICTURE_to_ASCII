"""Output targets: ANSI terminal text, plain text, and PNG."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .converter import RGB, AsciiArt, Settings, cell_color

MONO_FONTS = [
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/SFNSMono.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
    "C:/Windows/Fonts/consola.ttf",
]


def to_ansi(art: AsciiArt, s: Settings, bg: RGB | None = None) -> str:
    """Text with 24-bit ANSI color codes (only emits a code when the color changes)."""
    if s.color_mode == "none" and bg is None:
        return art.text

    bg_code = f"\x1b[48;2;{bg[0]};{bg[1]};{bg[2]}m" if bg else ""
    lines = []
    for y in range(art.rows):
        parts = [bg_code]
        prev = None
        for x in range(art.cols):
            color = cell_color(art, x, y, s)
            if color is not None and color != prev:
                parts.append(f"\x1b[38;2;{color[0]};{color[1]};{color[2]}m")
                prev = color
            parts.append(art.grid[y][x].ch)
        parts.append("\x1b[0m")
        lines.append("".join(parts))
    return "\n".join(lines)


def load_font(size: int, path: str | None = None) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in [path, *MONO_FONTS]:
        if candidate and Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default(size=size)


def to_png(
    art: AsciiArt,
    s: Settings,
    path: str | Path,
    font_size: int = 12,
    line_height: float = 1.0,
    bg: RGB = (13, 13, 15),
    font_path: str | None = None,
    padding: int = 16,
) -> None:
    font = load_font(font_size, font_path)
    cell_w = font.getlength("M")
    cell_h = font_size * line_height
    width = int(art.cols * cell_w + padding * 2)
    height = int(art.rows * cell_h + padding * 2)

    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)
    default = s.fg if s.color_mode == "none" else None

    for y in range(art.rows):
        cy = padding + y * cell_h + cell_h / 2
        for x in range(art.cols):
            ch = art.grid[y][x].ch
            if ch == " ":
                continue
            color = cell_color(art, x, y, s) or default
            draw.text((padding + x * cell_w, cy), ch, font=font, fill=color, anchor="lm")

    img.save(path)
