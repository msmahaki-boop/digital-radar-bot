"""Render Acolad news story PNGs from already-uploaded template backgrounds."""
import os
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

CANVAS = (1080, 1920)
TEMPLATE_DIR = Path("assets/templates")
OUTPUT_DIR = Path("stories_output")

# Layout rectangle coordinates refer to the original 941x1672 image geometry.
# All are scaled to output dimensions; safe inset keeps decorative open corners visible.
LAYOUT = {
    "tech": {"template": "tech_story.png", "photo": (185, 301, 744, 824),
             "title": (160, 939, 796, 1023), "summary": (105, 1049, 824, 1165),
             "source": (480, 1198, 708, 1265)},
    "ai": {"template": "ai_story.png", "photo": (201, 310, 735, 828),
           "title": (100, 972, 846, 1070), "summary": (215, 1124, 830, 1276),
           "source": (470, 1304, 738, 1380)},
    "marketing": {"template": "marketing_story.png", "photo": (215, 314, 719, 921),
                  "title": (115, 1035, 826, 1130), "summary": (96, 1160, 835, 1285),
                  "source": (268, 1316, 752, 1388)},
    "social": {"template": "social_story.png", "photo": (243, 280, 688, 846),
               "title": (103, 932, 828, 1024), "summary": (120, 1056, 811, 1226),
               "source": (304, 1258, 649, 1350)},
}


def find_font(bold=False):
    """Use a freely available Persian-capable system font; no font upload required."""
    env = os.getenv("STORY_FONT", "").strip()
    candidates = ([env] if env else []) + [
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    try:
        result = subprocess.check_output(
            ["fc-match", "-f", "%{file}", "Noto Sans Arabic:style=Bold" if bold else "Noto Sans Arabic"],
            text=True, timeout=3)
        if os.path.isfile(result):
            return result
    except (OSError, subprocess.SubprocessError):
        pass
    raise RuntimeError("No Persian-capable font found. Install fonts-noto-core.")


def rect(box):
    return (round(box[0] * CANVAS[0] / 941), round(box[1] * CANVAS[1] / 1672),
            round(box[2] * CANVAS[0] / 941), round(box[3] * CANVAS[1] / 1672))


def text_length(draw, text, font):
    try:
        return draw.textlength(text, font=font, direction="rtl")
    except (ValueError, KeyError):
        return draw.textlength(text, font=font)


def wrap_rtl(draw, text, font, max_width, max_lines):
    words = str(text).split()
    lines = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if current and text_length(draw, candidate, font) > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while lines[-1] and text_length(draw, lines[-1] + "…", font) > max_width:
            lines[-1] = lines[-1][:-1]
        lines[-1] = lines[-1].rstrip(" ،.؛") + "…"
    return lines


def draw_fit_text(img, text, bounds, *, title=False, color="#141416"):
    box = rect(bounds)
    x1, y1, x2, y2 = box
    draw = ImageDraw.Draw(img)
    width = x2 - x1 - 14
    height = y2 - y1 - 10
    text = " ".join(str(text or "").split())
    if not text:
        return
    font_path = find_font(bold=title)
    max_lines = 2 if title else 3
    start_size = 53 if title else 37
    minimum = 31 if title else 24
    for size in range(start_size, minimum - 1, -1):
        font = ImageFont.truetype(font_path, size)
        lines = wrap_rtl(draw, text, font, width, max_lines)
        line_height = int(size * 1.53)
        if len(lines) * line_height <= height and all(text_length(draw, s, font) <= width for s in lines):
            break
    else:
        font = ImageFont.truetype(font_path, minimum)
        lines = wrap_rtl(draw, text, font, width, max_lines)
        line_height = int(minimum * 1.48)
    top = y1 + max(2, (height - len(lines) * line_height) // 2) + 4
    for line in lines:
        # RAQM correctly joins Persian characters and handles mixed Latin/Persian.
        draw.text((x2 - 12, top), line, font=font, fill=color,
                  anchor="ra", direction="rtl")
        top += line_height


def place_photo(canvas, image, bounds):
    box = rect(bounds)
    w, h = box[2] - box[0], box[3] - box[1]
    inset = round(CANVAS[0] * 0.005)
    bw, bh = w - 2 * inset, h - 2 * inset
    # Fill remaining space with a blurred image; show the entire original on top.
    blurred = ImageOps.fit(image, (bw, bh), method=Image.Resampling.LANCZOS)
    blurred = blurred.filter(ImageFilter.GaussianBlur(radius=36))
    blurred = Image.blend(blurred, Image.new("RGB", (bw, bh), "#F2F0FA"), 0.42)
    fitted = ImageOps.contain(image, (bw - 20, bh - 20), Image.Resampling.LANCZOS)
    ix = (bw - fitted.width) // 2
    iy = (bh - fitted.height) // 2
    blurred.paste(fitted, (ix, iy))
    radius = round(26 * CANVAS[0] / 941)
    mask = Image.new("L", (bw, bh), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, bw - 1, bh - 1),
                                            radius=radius, fill=255)
    canvas.paste(blurred, (box[0] + inset, box[1] + inset), mask)


def fill_image_free_area(canvas, topic, bounds):
    x1, y1, x2, y2 = rect(bounds)
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    draw = ImageDraw.Draw(canvas)
    radius = min(x2-x1, y2-y1) // 3
    # A brand-native vector treatment rather than a fake or unrelated news photo.
    draw.ellipse((cx-radius, cy-radius, cx+radius, cy+radius),
                 fill="#E5E0FA", outline="#7B2CBF", width=3)
    # Curly braces are the brand symbol; use Latin-capable font to avoid empty glyph boxes.
    braces = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 100)
    caption = ImageFont.truetype(find_font(bold=True), 43)
    draw.text((cx, cy - 45), "{  }", font=braces, fill="#7B2CBF",
              anchor="mm", direction="ltr")
    label = {"tech": "تکنولوژی", "ai": "هوش مصنوعی",
             "marketing": "بازاریابی دیجیتال", "social": "سوشال مدیا و محتوا"}[topic]
    draw.text((cx, cy + 64), label, font=caption,
              fill="#141416", anchor="mm", direction="rtl")


def source_text(canvas, text, bounds):
    x1, y1, x2, y2 = rect(bounds)
    draw = ImageDraw.Draw(canvas)
    # The Arabic-only display font may not contain Latin glyphs (TechCrunch etc.).
    # DejaVu Sans supports both scripts; size is reduced to fit the source label.
    font_file = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    is_latin = all(ord(ch) < 128 for ch in text)
    direction = "ltr" if is_latin else "rtl"
    max_w = x2-x1-12
    for size in range(27, 17, -1):
        font = ImageFont.truetype(font_file, size)
        if draw.textlength(text, font=font, direction=direction) <= max_w:
            break
    if draw.textlength(text, font=font, direction=direction) > max_w:
        while len(text) > 4 and draw.textlength(text + "…", font=font,
                                                 direction=direction) > max_w:
            text = text[:-1]
        text = text.rstrip() + "…"
    draw.text((x2-6, (y1+y2)//2 + 16), text, font=font, fill="#33215E",
              anchor="rm", direction=direction)


def render_story(story, index):
    if story.topic not in LAYOUT:
        raise ValueError("Unknown topic: " + story.topic)
    layout = LAYOUT[story.topic]
    path = TEMPLATE_DIR / layout["template"]
    if not path.exists():
        raise FileNotFoundError(f"Missing template {path}")
    canvas = Image.open(path).convert("RGB").resize(CANVAS, Image.Resampling.LANCZOS)
    if story.image is not None:
        place_photo(canvas, story.image, layout["photo"])
        mode = "photo"
    else:
        fill_image_free_area(canvas, story.topic, layout["photo"])
        mode = "text-only"
    draw_fit_text(canvas, story.title_fa, layout["title"], title=True)
    draw_fit_text(canvas, story.summary_fa, layout["summary"])
    source_text(canvas, story.source, layout["source"])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = OUTPUT_DIR / f"{index:02d}_{story.topic}_{mode}.png"
    canvas.save(filename, "PNG", optimize=True)
    print(f"RENDER OK: {filename}")
    return filename, mode


def render_intro():
    intro = TEMPLATE_DIR / "intro_story.png"
    if not intro.exists():
        raise FileNotFoundError(f"Missing {intro}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / "01_intro.png"
    Image.open(intro).convert("RGB").resize(CANVAS, Image.Resampling.LANCZOS).save(out)
    print("RENDER OK:", out)
    return out
