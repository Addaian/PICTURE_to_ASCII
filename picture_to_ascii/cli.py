"""Command-line interface: pic2ascii IMAGE [options]"""

from __future__ import annotations

import argparse
import math
import os
import shutil
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image

from .converter import CHARSETS, GRADIENT_DIRS, RGB, Settings, convert, parse_color
from .render import load_font, to_ansi, to_png


def hex_color(value: str) -> RGB:
    try:
        return parse_color(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid hex color: {value!r}") from None


def ranged(lo: float, hi: float, cast=float, lo_exclusive: bool = False):
    def parse(value: str):
        try:
            f = cast(value)
        except ValueError:
            raise argparse.ArgumentTypeError(f"invalid number: {value!r}") from None
        too_low = f <= lo if lo_exclusive else f < lo
        if not math.isfinite(f) or too_low or f > hi:
            bound = f"> {lo}" if lo_exclusive else f">= {lo}"
            raise argparse.ArgumentTypeError(f"must be {bound} and <= {hi}")
        return f

    return parse


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pic2ascii",
        description="Convert an image to ASCII art.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("image", help="image file path, or '-' to read from stdin")
    p.add_argument("-o", "--output", help="write to a file: .png renders an image, anything else is plain text")

    size = p.add_argument_group("size")
    size.add_argument(
        "-w", "--cols", type=ranged(1, 10_000, int), help="characters per row (default: terminal width, or 100)"
    )
    size.add_argument(
        "--aspect",
        type=ranged(0, 100, lo_exclusive=True),
        help="character cell width/height ratio (default: 0.5 for text, measured from the font for PNG)",
    )
    size.add_argument("--font-size", type=ranged(1, 1000, int), default=12, help="character size in px (PNG output)")
    size.add_argument(
        "--line-height", type=ranged(0, 10, lo_exclusive=True), default=1.0, help="row spacing multiplier (PNG output)"
    )
    size.add_argument("--font", help="path to a monospace .ttf/.ttc font (PNG output)")

    chars = p.add_argument_group("characters")
    chars.add_argument("-c", "--charset", choices=CHARSETS, default="standard", help="character set preset")
    chars.add_argument("--chars", help="custom character set, ordered sparse -> dense (overrides --charset)")
    chars.add_argument("-v", "--variance", type=ranged(0, 1), default=0.0, help="random character variance, 0-1")
    chars.add_argument("-i", "--invert", action="store_true", help="invert brightness (for light backgrounds)")

    tone = p.add_argument_group("tone")
    tone.add_argument("--brightness", type=ranged(-100, 100), default=0, help="-100 to 100")
    tone.add_argument("--contrast", type=ranged(-100, 100), default=0, help="-100 to 100")
    tone.add_argument("--gamma", type=ranged(0.1, 5), default=1.0, help="0.1 to 5")

    color = p.add_argument_group("color")
    color.add_argument(
        "-m",
        "--color",
        choices=["none", "solid", "original", "gradient"],
        default="none",
        help="color mode",
    )
    color.add_argument("--fg", type=hex_color, default="#e8e8e8", help="text color for solid mode")
    color.add_argument(
        "-g",
        "--gradient",
        nargs=2,
        type=hex_color,
        metavar=("START", "END"),
        help="gradient colors (implies --color gradient)",
    )
    color.add_argument("--gradient-dir", choices=GRADIENT_DIRS, default="horizontal")
    color.add_argument("--bg", type=hex_color, help="background color (terminal and PNG; PNG default #0d0d0f)")
    color.add_argument("--no-ansi", action="store_true", help="never emit color codes to stdout")
    return p


def load_image(src: str) -> Image.Image:
    if src == "-":
        return Image.open(BytesIO(sys.stdin.buffer.read()))
    return Image.open(src)


def fail(msg: str) -> int:
    print(f"pic2ascii: {msg}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        image = load_image(args.image)
        image.load()
    except (OSError, ValueError, Image.DecompressionBombError) as e:
        return fail(f"cannot read image: {e}")

    if args.cols is None:
        args.cols = shutil.get_terminal_size((100, 24)).columns if sys.stdout.isatty() and not args.output else 100

    is_png = bool(args.output) and Path(args.output).suffix.lower() == ".png"
    if is_png:
        try:
            font = load_font(args.font_size, args.font)
        except OSError as e:
            return fail(f"cannot load font: {e}")
        if args.aspect is None:
            args.aspect = font.getlength("M") / (args.font_size * args.line_height)
    elif args.aspect is None:
        args.aspect = 0.5

    color_mode = "gradient" if args.gradient else args.color
    grad = args.gradient or [(255, 60, 120), (60, 200, 255)]

    try:
        s = Settings(
            cols=args.cols,
            charset=args.chars if args.chars else CHARSETS[args.charset],
            variance=args.variance,
            invert=args.invert,
            brightness=args.brightness / 100,
            contrast=args.contrast / 100,
            gamma=args.gamma,
            char_aspect=args.aspect,
            color_mode=color_mode,
            fg=args.fg,
            grad_start=grad[0],
            grad_end=grad[1],
            grad_dir=args.gradient_dir,
        )
    except ValueError as e:
        return fail(str(e))
    art = convert(image, s)

    if args.output:
        out = Path(args.output)
        try:
            if is_png:
                to_png(
                    art,
                    s,
                    out,
                    font_size=args.font_size,
                    line_height=args.line_height,
                    bg=args.bg or (13, 13, 15),
                    font_path=args.font,
                )
            else:
                out.write_text(art.text + "\n", encoding="utf-8")
        except OSError as e:
            return fail(f"cannot write {out}: {e}")
        print(f"wrote {out} ({art.cols}x{art.rows})", file=sys.stderr)
        return 0

    use_ansi = sys.stdout.isatty() and not args.no_ansi
    try:
        print(to_ansi(art, s, args.bg) if use_ansi else art.text)
        sys.stdout.flush()
    except BrokenPipeError:
        # Output was piped into something that exited early (e.g. `| head`).
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 141
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
