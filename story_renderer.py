"""Render Acolad V2.5 story templates: landscape / portrait / text-only.

No source label is ever drawn. Source links remain in manifest.json for checking.
All coordinates are expressed on the original 941x1672 graphic and scaled to
1080x1920, so template resolution may vary without changing layout rules.
"""
import os
import subprocess
from pathlib import Path
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, features

CANVAS = (1080, 1920)
REFERENCE = (941, 1672)
TEMPLATE_DIR = Path("assets/templates")
OUTPUT_DIR = Path("stories_output")

# Distinct, wide body-text regions for each format; no source overlay.
# Coordinates intentionally inset from decorations and the Instagram footer.
ZONES = {
    "landscape": {
        "photo": (184, 301, 757, 724),
        "title": (96, 712, 840, 806),
        "body": (91, 903, 846, 1377),
    },
    "portrait": {
        "photo": (237, 208, 705, 883),
        "title": (95, 913, 842, 1008),
        "body": (98, 1060, 837, 1411),
    },
    "text_only": {
        "title": (95, 324, 838, 424),
        "body": (106, 598, 830, 1350),
    },
}


def to_rect(bounds):
    sx, sy = CANVAS[0] / REFERENCE[0], CANVAS[1] / REFERENCE[1]
    return tuple(round(z * (sx if i % 2 == 0 else sy)) for i, z in enumerate(bounds))


@lru_cache(maxsize=2)
def font_path(bold=False):
    """Prefer a working IRANSans, otherwise fetch the official OFL Vazirmatn.

    The uploaded files supplied for this project contain only 0x00 bytes and are
    not fonts. We never modify them, and never pretend they were loaded.
    Downloaded third-party fonts live only in the runner's temporary directory
    (outside stories_output and outside any uploaded artifact).
    """
    from tempfile import gettempdir
    from urllib.request import Request, urlopen

    if not features.check("raqm"):
        raise RuntimeError("Pillow requires libraqm for correct Persian/RTL layout")

    folder = Path(__file__).resolve().parent / "assets" / "fonts"
    explicit = os.getenv("STORY_FONT_BOLD" if bold else "STORY_FONT", "").strip()
    names = (["IRANSans-Bold.ttf", "IRANSans_Bold.ttf",
              "IRANSans-Black.ttf", "IRANSans_Black.ttf"] if bold else
             ["IRANSans-Regular.ttf", "IRANSans.ttf",
              "IRANSans-Medium.ttf", "IRANSans_Medium.ttf"])

    def valid_font(path):
        try:
            if path.stat().st_size < 10000 or path.stat().st_size > 3500000:
                raise ValueError("unexpected font file size")
            with path.open("rb") as fh:
                sig = fh.read(4)
            if sig not in (b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf"):
                raise ValueError("not a TrueType/OpenType font")
            ft = ImageFont.truetype(str(path), 28, layout_engine=ImageFont.Layout.RAQM)
            ft.getbbox("آکولاد / News 2026", direction="rtl")
            return ft
        except (OSError, ValueError) as exc:
            print(f"FONT INVALID: {path.name} ({exc})", flush=True)
            return None

    for candidate in ([Path(explicit)] if explicit else []) + [folder / n for n in names]:
        if candidate.is_file():
            ft = valid_font(candidate)
            if ft is not None:
                print(f"FONT ACTIVE: {candidate.name} | {ft.getname()[0]}", flush=True)
                return str(candidate)

    # Open-source Persian font. Repo release/tag and filenames are pinned.
    weight = "Bold" if bold else "Regular"
    filename = f"Vazirmatn-{weight}.ttf"
    cache = Path(gettempdir()) / "acolad_story_font_cache"
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / filename
    if destination.is_file():
        ft = valid_font(destination)
        if ft is not None:
            print(f"FONT ACTIVE: {filename} (Vazirmatn fallback)", flush=True)
            return str(destination)

    url = ("https://raw.githubusercontent.com/rastikerdar/vazirmatn/"
           "v33.003/fonts/ttf/" + filename)
    print(f"FONT FALLBACK: local IRANSans files are invalid or missing; "
          f"retrieving open-source {filename}", flush=True)
    try:
        req = Request(url, headers={"User-Agent": "AcoladStoryGenerator/2.5"})
        with urlopen(req, timeout=30) as response:
            content = response.read(3500001)
        if not 10000 <= len(content) <= 3500000 or content[:4] not in (
            b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf"
        ):
            raise ValueError("Downloaded data is not a valid font file")
        temp = destination.with_suffix(".partial")
        temp.write_bytes(content)
        temp.replace(destination)
        ft = valid_font(destination)
        if ft is None:
            raise ValueError("Downloaded font was rejected by Pillow")
        print(f"FONT ACTIVE: {filename} | {ft.getname()[0]}", flush=True)
        return str(destination)
    except Exception as exc:
        # Keep PREVIEW working even if raw.githubusercontent.com is blocked.
        print(f"FONT DOWNLOAD WARNING: {type(exc).__name__}: {exc}", flush=True)
        for candidate in (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
                          if bold else Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                          Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf")):
            if candidate.is_file():
                ft = valid_font(candidate)
                if ft is not None:
                    print(f"FONT ACTIVE: {candidate.name} (emergency system fallback)", flush=True)
                    return str(candidate)
        raise RuntimeError("No readable font available; check GitHub network access") from exc


def _text_width(draw, text, font):
    return draw.textlength(text, font=font, direction="rtl")


def _wrap(draw, text, font, width):
    """Wrap by whole words; preserve natural paragraphs and Persian shaping."""
    lines = []
    for paragraph in str(text).split("\n"):
        words = paragraph.split()
        if not words:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if current and _text_width(draw, candidate, font) > width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
    return lines


def draw_fitted_text(canvas, text, bounds, *, headline=False):
    """Center Persian text line by line and vertically in the free content box.

    No justification, no stretched glyph spacing, no truncation. If content
    genuinely does not fit, return False so caller can use text-only template.
    """
    x1, y1, x2, y2 = to_rect(bounds)
    # Wider copy and modest padding: keep a visible safe margin from the
    # decorative purple frame without losing a third of the content region.
    pad_x = 10 if headline else 13
    pad_top = 5 if headline else 12
    pad_bottom = 5 if headline else 13
    max_w = x2 - x1 - pad_x * 2
    max_h = y2 - y1 - pad_top - pad_bottom
    draw = ImageDraw.Draw(canvas)
    text = str(text or "").replace("\r", "\n").strip()
    text = "\n".join(" ".join(line.split()) for line in text.split("\n"))
    if not text:
        return False
    sizes = (range(48, 27, -1) if headline else range(42, 26, -1))
    max_lines = 2 if headline else 22
    chosen = None
    for size in sizes:
        font = ImageFont.truetype(font_path(bold=headline), size,
                                  layout_engine=ImageFont.Layout.RAQM)
        lines = _wrap(draw, text, font, max_w)
        leading = round(size * (1.29 if headline else 1.43))
        needed_h = len(lines) * leading
        if (len(lines) <= max_lines and needed_h <= max_h and
            all(not line or _text_width(draw, line, font) <= max_w + 2
                for line in lines)):
            chosen = font, lines, leading, needed_h
            break
    if chosen is None:
        return False
    font, lines, leading, needed_h = chosen
    y = y1 + pad_top + max(0, (max_h - needed_h) // 2)
    center_x = (x1 + x2) / 2
    for line in lines:
        if line:
            # Center by actual glyph bounding box, independent of mixed
            # right-to-left and left-to-right segments in each line.
            ink = draw.textbbox((0, 0), line, font=font, anchor="lt", direction="rtl")
            ink_w = ink[2] - ink[0]
            ink_h = ink[3] - ink[1]
            # anchor lt makes ink bounds relative to the anchor; use that
            # displacement to position visible ink exactly in the safe region.
            draw.text((round(center_x - (ink[0] + ink[2]) / 2),
                       round(y + (leading - ink_h) / 2 - ink[1])),
                      line, font=font, fill="#141416", anchor="lt", direction="rtl")
        y += leading
    return True


def insert_photo(canvas, original_image, bounds):
    """Display entire source picture; use a tinted blurred extension as side padding."""
    x1, y1, x2, y2 = to_rect(bounds)
    width, height = x2 - x1, y2 - y1
    img = ImageOps.exif_transpose(original_image).convert("RGB")
    blurred = ImageOps.fit(img, (width, height), method=Image.Resampling.LANCZOS)
    blurred = blurred.filter(ImageFilter.GaussianBlur(radius=38))
    blurred = Image.blend(blurred, Image.new("RGB", (width, height), "#EEE7FA"), 0.32)
    inset = 9
    main = ImageOps.contain(img, (width - 2 * inset, height - 2 * inset),
                            method=Image.Resampling.LANCZOS)
    blurred.paste(main, ((width - main.width) // 2, (height - main.height) // 2))
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, width-1, height-1), 22, fill=255)
    canvas.paste(blurred, (x1, y1), mask)


def template_name(topic, mode):
    if topic not in ("tech", "ai", "marketing", "social"):
        raise ValueError("Unknown topic: " + str(topic))
    if mode == "text_only":
        return f"{topic}_text_only.png"
    if mode in ("landscape", "portrait"):
        return f"{topic}_photo_{mode}.png"
    raise ValueError("Unknown mode: " + str(mode))


def new_canvas(topic, mode):
    f = TEMPLATE_DIR / template_name(topic, mode)
    if not f.is_file():
        raise FileNotFoundError(f"Missing uploaded story template: {f}")
    return Image.open(f).convert("RGB").resize(CANVAS, Image.Resampling.LANCZOS)


def _cyan(rgb):
    r, g, b = rgb[:3]
    return r < 175 and g > 140 and b > 196 and (b - r) > 45


def _detect_headline_bar(template):
    """Infer the cyan headline strip from the *actual* uploaded template.

    Earlier generated templates do not use identical vertical coordinates;
    we therefore detect the colored title band instead of hard-coding one.
    """
    im = template.resize(REFERENCE, Image.Resampling.NEAREST).convert("RGB")
    x = REFERENCE[0] // 2
    marked = []
    for y in range(260, 1190):
        if _cyan(im.getpixel((x, y))):
            marked.append(y)
    runs = []
    for y in marked:
        if not runs or y > runs[-1][-1] + 1:
            runs.append([y])
        else:
            runs[-1].append(y)
    choices = []
    for run in runs:
        if len(run) < 42:
            continue
        mid = (run[0] + run[-1]) // 2
        left, right = x, x
        while left > 0 and _cyan(im.getpixel((left-1, mid))):
            left -= 1
        while right < REFERENCE[0]-1 and _cyan(im.getpixel((right+1, mid))):
            right += 1
        if right - left >= 360:
            choices.append((right-left, len(run), left, run[0], right, run[-1]))
    if not choices:
        raise RuntimeError("Could not locate cyan title bar in template")
    _, _, left, top, right, bottom = max(choices)
    return left, top, right, bottom


def _layout_for_template(topic, mode, template):
    left, top, right, bottom = _detect_headline_bar(template)
    # Derive safe text bounds from the actual visible cyan strip.
    title = (max(95, left+25), top+4, min(845, right-23), bottom-3)
    body_top = bottom + (44 if mode == "text_only" else 38)
    body_end = 1380 if mode == "text_only" else 1395
    # Text must be INSET from the visible frame. Previous bounds extended
    # beyond the left border and cramped the rightmost Persian line.
    body = ((126, body_top + 5, 811, body_end - 4) if mode == "text_only"
            else (105, body_top + 5, 829, body_end - 4))
    if mode == "text_only":
        return {"title": title, "body": body}
    # Tall photo area appears in templates with lower headline strip.
    if top >= 860:
        photo = (219, 219, 720, min(top-56, 864))
    else:
        photo = (189, 298, 753, min(top-54, 735))
    if photo[3] <= photo[1]+110:
        photo = ZONES[mode]["photo"]
    return {"title": title, "body": body, "photo": photo}


def _draw_mode(story, mode):
    canvas = new_canvas(story.topic, mode)
    zone = _layout_for_template(story.topic, mode, canvas)
    if mode != "text_only":
        if story.image is None:
            raise ValueError("Photo mode requires an image")
        insert_photo(canvas, story.image, zone["photo"])
    short = mode != "text_only"
    body = story.summary_photo_fa if short else story.summary_fa
    if not draw_fitted_text(canvas, story.title_fa, zone["title"], headline=True):
        return None, "headline too long for layout"
    if not draw_fitted_text(canvas, body, zone["body"]):
        return None, "body too long for layout"
    return canvas, ""


def render_story(story, index):
    # Every article has an explicit text-only escape route so weak images don't
    # cost valuable news coverage. Landscape/portrait choice uses aspect ratio.
    preferred = "text_only"
    if story.image is not None:
        preferred = "landscape" if story.image.width / story.image.height >= 1.1 else "portrait"
    options = [preferred] if preferred == "text_only" else [preferred, "text_only"]
    failures = []
    for mode in options:
        canvas, reason = _draw_mode(story, mode)
        if canvas is None:
            failures.append(f"{mode}: {reason}")
            continue
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        filename = OUTPUT_DIR / f"{index:02d}_{story.topic}_{mode}.png"
        canvas.save(filename, "PNG", optimize=True)
        if mode != preferred:
            print(f"FALLBACK: {story.topic}: photo layout could not fit copy")
        print(f"RENDER OK: {filename}")
        return filename, mode
    raise RuntimeError(f"Unable to fit {story.topic} copy in story template: " + "; ".join(failures))


def render_intro():
    p = TEMPLATE_DIR / "intro_story.png"
    if not p.is_file():
        raise FileNotFoundError(f"Missing {p}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / "01_intro.png"
    Image.open(p).convert("RGB").resize(CANVAS, Image.Resampling.LANCZOS).save(out)
    print(f"RENDER OK: {out}")
    return out
