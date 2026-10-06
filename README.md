# PICTURE_to_ASCII

Turn any picture into ASCII art — right in your terminal, or in the browser.

```
...................:-=+****+=-:...................
.................=*#############=:................
...............=##################+...............
.............:*#####################:.............
............-########################=............
............=########################+............
.............*#######################.............
...............+##################+:..............
..................:-=+*####*+=-:..................
++++++++++++++++++++++++++++++++++++++++++++++++++
```

PICTURE_to_ASCII samples an image into a grid of character cells and picks a character for each cell based on its brightness. You control how it looks:

- **Size** — how many characters wide, character size and line spacing
- **Character set** — classic ASCII, a detailed 70-character ramp, Unicode blocks (`░▒▓█`), binary, dots, or your own
- **Character variance** — nudges cells to neighbouring characters for a rougher, hand-drawn texture
- **Tone** — brightness, contrast, gamma and invert
- **Color** — plain, a single color, the original image colors, or a two-color gradient (horizontal, vertical, diagonal, radial, or by brightness)

Output goes to the terminal (24-bit color), a `.txt` file, or a rendered `.png`.

There are three ways to use it — all with the same settings and conversion logic:

- the **`pic2ascii` command-line tool**
- the **`picture_to_ascii` Python library**
- a **web app** with live sliders

---

## Command-line tool

### Install

Requires Python 3.10+.

```sh
# as a command-line tool (isolated environment)
uv tool install git+https://github.com/Addaian/PICTURE_to_ASCII
# or: pipx install git+https://github.com/Addaian/PICTURE_to_ASCII

# as a library in your project / virtualenv (also installs the command)
pip install git+https://github.com/Addaian/PICTURE_to_ASCII
```

From a local clone: `pip install .` (or `pip install -e .` for development).

To run it without installing (needs [Pillow](https://pypi.org/project/pillow/)):

```sh
python3 -m picture_to_ascii photo.jpg
```

### Quick start

```sh
pic2ascii photo.jpg
```

That prints the image as ASCII art sized to fit your terminal. From there, add options:

```sh
# 80 characters wide, each character colored like the original pixel
pic2ascii photo.jpg -w 80 -m original

# Unicode block characters with some texture
pic2ascii photo.jpg -c blocks -v 0.4

# Pink → blue radial gradient
pic2ascii photo.jpg -g ff3c78 3cc8ff --gradient-dir radial

# Your own characters, more contrast, inverted for a light terminal
pic2ascii photo.jpg --chars " .oO@" --contrast 30 -i

# Save a high-resolution colored PNG
pic2ascii photo.jpg -w 160 -m original --font-size 14 -o art.png

# Save plain text
pic2ascii photo.jpg -w 100 -o art.txt

# Read from a pipe
curl -s https://example.com/cat.jpg | pic2ascii -
```

Colors are only printed when the output is a terminal, so `pic2ascii photo.jpg > art.txt` gives clean text.

### All options

Run `pic2ascii --help` for the full list.

| Group | Option | Default | Description |
|---|---|---|---|
| Output | `-o, --output FILE` | terminal | `.png` renders an image; any other extension writes plain text |
| Size | `-w, --cols N` | terminal width (or 100) | Characters per row |
| | `--aspect R` | 0.5 for text, measured from font for PNG | Character cell width ÷ height |
| | `--font-size PX` | 12 | Character size (PNG) |
| | `--line-height X` | 1.0 | Row spacing multiplier (PNG) |
| | `--font PATH` | Menlo / DejaVu Sans Mono | Monospace font file (PNG) |
| Characters | `-c, --charset NAME` | `standard` | `standard`, `detailed`, `blocks`, `binary`, `dots` |
| | `--chars STR` | | Custom characters, ordered sparse → dense |
| | `-v, --variance 0–1` | 0 | Character variance (same result every run) |
| | `-i, --invert` | off | Invert brightness — use on light backgrounds |
| Tone | `--brightness -100–100` | 0 | |
| | `--contrast -100–100` | 0 | |
| | `--gamma 0.1–5` | 1.0 | |
| Color | `-m, --color MODE` | `none` | `none`, `solid`, `original`, `gradient` |
| | `--fg HEX` | `#e8e8e8` | Text color for `solid` mode |
| | `-g, --gradient START END` | | Gradient colors (switches on gradient mode) |
| | `--gradient-dir DIR` | `horizontal` | `horizontal`, `vertical`, `diagonal`, `radial`, `brightness` |
| | `--bg HEX` | none (`#0d0d0f` for PNG) | Background color |
| | `--no-ansi` | off | Never print color codes |

### Tips

- **Character set order matters.** Characters go from *least ink* to *most ink*. On a dark background, bright areas get dense characters; use `-i` on a light background.
- **More columns = more detail.** Try `-w 200` with a small terminal font, or render a PNG.
- **Flat-looking result?** Raise `--contrast` or lower `--gamma`.

---

## Python library

Install with `pip install git+https://github.com/Addaian/PICTURE_to_ASCII`, then:

```python
from picture_to_ascii import image_to_ascii

art = image_to_ascii("photo.jpg", cols=80)

print(art)                 # plain ASCII text
print(art.to_ansi())       # with 24-bit terminal colors
art.save("art.txt")        # plain text file
art.save("art.png")        # rendered image
```

`image_to_ascii` accepts a file path or a `PIL.Image`, and takes the same settings as the CLI as keyword arguments:

```python
art = image_to_ascii(
    "photo.jpg",
    cols=120,
    charset="blocks",          # preset name, or your own string like " .oO@"
    variance=0.3,
    invert=False,
    brightness=0.1,            # -1 to 1
    contrast=0.2,              # -1 to 1
    gamma=1.0,
    char_aspect=0.5,           # character cell width ÷ height
    color_mode="gradient",     # "none", "solid", "original", "gradient"
    grad_start="#ff3c78",      # hex string or (r, g, b)
    grad_end=(60, 200, 255),
    grad_dir="radial",         # horizontal, vertical, diagonal, radial, brightness
)

img = art.to_image(font_size=14, line_height=1.0, bg="#0d0d0f")  # PIL.Image
img.show()
```

The result is an `AsciiArt` object:

| Attribute / method | Returns |
|---|---|
| `art.text` / `str(art)` | Plain text |
| `art.cols`, `art.rows` | Grid size |
| `art.grid[y][x]` | `Cell` with `.ch` (character), `.b` (brightness 0–1), `.rgb` (source color) |
| `art.to_ansi(bg=None)` | Text with ANSI color codes |
| `art.to_image(**options)` | `PIL.Image` — options: `font_size`, `line_height`, `bg`, `font_path`, `padding` |
| `art.save(path, **options)` | Writes `.png` (same options) or text |

Preset character sets are in `picture_to_ascii.CHARSETS`. For lower-level control, build a `Settings` object and call `convert(pil_image, settings)`.

---

## Web app

A browser version with live preview — no install needed.

```sh
python3 -m http.server -d web 8080
# open http://localhost:8080
```

(or just open `web/index.html` directly)

1. Drag an image onto the drop zone, click to upload, or paste from the clipboard
2. Adjust size, characters, variance, tone and colors with the sliders — the preview updates live
3. Copy the text, or download it as `.txt` or `.png`

---

## Project layout

```
picture_to_ascii/
  converter.py   image → character grid (tone, character set, variance, colors)
  render.py      terminal (ANSI), plain text and PNG output
  cli.py         pic2ascii command
  __init__.py    public API (image_to_ascii, AsciiArt, Settings, …)
web/
  index.html     browser UI
  style.css
  app.js
pyproject.toml
```

## License

MIT — see [LICENSE](LICENSE).
