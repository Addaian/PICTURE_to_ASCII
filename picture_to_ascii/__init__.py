"""Picture to ASCII — convert images to ASCII art.

    >>> from picture_to_ascii import image_to_ascii
    >>> art = image_to_ascii("photo.jpg", cols=80, color_mode="original")
    >>> print(art)              # plain text
    >>> print(art.to_ansi())    # 24-bit color for terminals
    >>> art.save("art.png")     # or "art.txt"
"""

from .converter import CHARSETS, GRADIENT_DIRS, AsciiArt, Cell, Settings, convert, image_to_ascii, parse_color
from .render import render_image, to_ansi, to_png

__all__ = [
    "CHARSETS",
    "GRADIENT_DIRS",
    "AsciiArt",
    "Cell",
    "Settings",
    "convert",
    "image_to_ascii",
    "parse_color",
    "render_image",
    "to_ansi",
    "to_png",
]
__version__ = "0.1.0"
