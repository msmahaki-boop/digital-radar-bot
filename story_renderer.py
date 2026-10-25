"""Acolad Minimal Story Generator V2.6.

Preview-only: no posting. Eight photo/text templates share one open photo zone.
Original aspect ratios are preserved; no blurred/photo frames or cropping.
The rendered emphasis terms are grounded phrases returned by the editor.
"""
import re
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps, features
import os

CANVAS = (1080, 1920)
REFERENCE = (941, 1672)
TEMPLATE_DIR = Path("assets/templates")
OUTPUT_DIR = Path("stories_output")
TOPICS = ("tech", "ai", "marketing", "social", "iran_economy", "small_business_growth", "iran_platforms")
NEW_ZONE_DATA = __import__('json').loads((TEMPLATE_DIR / 'acolad_new_template_manifest.json').read_text(encoding='utf-8'))['topics']


def scale_box(box):
    sx, sy = CANVAS[0] / REFERENCE[0], CANVAS[1] / REFERENCE[1]
    return tuple(round(v * (sx if i % 2 == 0 else sy)) for i, v in enumerate(box))

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



@lru_cache(maxsize=60)
def get_font(size, bold=False):
    return ImageFont.truetype(font_path(bold), size, layout_engine=ImageFont.Layout.RAQM)


def _measure(draw, text, font):
    return draw.textlength(str(text), font=font, direction="rtl")


def _wrap(draw, text, font, width):
    """Wrap logical Persian text without destroying paragraphs or bidi shaping."""
    lines = []
    for para in str(text).split("\n"):
        words = para.split()
        if not words:
            if lines and lines[-1]:
                lines.append("")
            continue
        cur = ""
        for word in words:
            test = (cur + " " + word).strip()
            if cur and _measure(draw, test, font) > width:
                lines.append(cur)
                cur = word
            else:
                cur = test
        if cur:
            lines.append(cur)
    return lines


def _styled_runs(line, phrases):
    """Select non-overlapping, literal editorial phrases; never highlight invented text."""
    runs = []
    matches = []
    for term in sorted({x.strip() for x in phrases if x and x.strip()}, key=len, reverse=True):
        for m in re.finditer(re.escape(term), line, flags=re.IGNORECASE):
            # Restrict emphasis to distinct words/phrases, not partial Persian words.
            i, j = m.span()
            if (i and line[i-1].isalnum()) or (j < len(line) and line[j].isalnum()):
                continue
            if not any(i < e and j > s for s, e in matches):
                matches.append((i, j))
    matches.sort()
    cur = 0
    for i, j in matches:
        if i > cur:
            runs.append((line[cur:i], False))
        runs.append((line[i:j], True))
        cur = j
    if cur < len(line):
        runs.append((line[cur:], False))
    return runs or [(line, False)]


def draw_story_text(canvas, text, bounds, *, headline=False, phrases=()):
    """Adaptive centered Persian text with optional subtle bold/color/marker accents."""
    x1, y1, x2, y2 = scale_box(bounds)
    safe_x = 16 if headline else 20
    safe_y = 5 if headline else 13
    max_w, max_h = (x2-x1-2*safe_x), (y2-y1-2*safe_y)
    text = str(text or "").replace("\r", "\n").strip()
    if not text:
        return False
    # Remove stray markdown markup: emphasis is carried separately in manifest fields.
    text = re.sub(r"(\*\*|==)(.*?)(\*\*|==)", lambda m: m.group(2), text)
    text = "\n".join(" ".join(row.split()) for row in text.split("\n"))
    d = ImageDraw.Draw(canvas)
    sizes = range(49, 28, -1) if headline else range(42, 24, -1)
    chosen = None
    for size in sizes:
        normal = get_font(size, bold=headline)
        lines = _wrap(d, text, normal, max_w * 0.96)
        step = round(size * (1.32 if headline else 1.49))
        # Paragraph breaks are half a line, not huge empty gaps.
        effective = sum(step * (0.58 if not ln else 1) for ln in lines)
        if (len(lines) <= (2 if headline else 26) and effective <= max_h and
                all((not ln or _measure(d, ln, normal) <= max_w) for ln in lines)):
            chosen = size, lines, step, effective
            break
    if chosen is None:
        return False
    size, lines, step, effective = chosen
    normal, strong = get_font(size, bold=headline), get_font(size, bold=True)
    # Vertical centering without excessive top padding.
    y = y1 + safe_y + max(0, (max_h - effective) / 2)
    cx = (x1 + x2) / 2
    for ln in lines:
        if not ln:
            y += step * 0.58
            continue
        runs = [(ln, False)] if headline else _styled_runs(ln, phrases)
        advance = sum(_measure(d, value, strong if highlight else normal)
                      for value, highlight in runs)
        cursor = cx + advance/2
        for value, highlight in runs:
            font = strong if highlight else normal
            width = _measure(d, value, font)
            left = cursor - width
            color = "#5730A8" if highlight else "#141416"
            if highlight:
                # Half-height pastel marker; deliberately understated.
                mark_y = y + step * 0.49
                d.rounded_rectangle((round(left-2), round(mark_y), round(cursor+2),
                                     round(mark_y+size*0.48)), radius=7,
                                    fill="#E4DDFC")
            box = d.textbbox((0,0), value, font=font, anchor="lt", direction="rtl")
            ink_h = box[3]-box[1]
            d.text((round(left-box[0]), round(y+(step-ink_h)/2-box[1])),
                   value, font=font, fill=color, direction="rtl", anchor="lt")
            cursor = left
        y += step
    return True


def template_name(topic, mode):
    if topic not in TOPICS:
        raise ValueError(f"Unknown category: {topic}")
    if mode not in ("text_only", "photo"):
        raise ValueError(f"Unknown mode: {mode}")
    return f"{topic}_{'text' if mode == 'text_only' else 'photo'}.png"


def load_template(topic, mode):
    path = TEMPLATE_DIR / template_name(topic, mode)
    if not path.is_file():
        raise FileNotFoundError(f"V2.6 template missing: {path}. Upload the minimalist template with this exact name")
    return Image.open(path).convert("RGB").resize(CANVAS, Image.Resampling.LANCZOS)


def _cyan(pixel):
    r,g,b = pixel[:3]
    return r<175 and g>140 and b>196 and b-r>45


def _headline_zone(template):
    """Find the actual cyan rounded bar; 8 generated templates have different Y positions."""
    ref=template.resize(REFERENCE, Image.Resampling.NEAREST).convert("RGB")
    x=REFERENCE[0]//2
    intervals=[]; start=None
    for y in range(260, 1150):
        found=_cyan(ref.getpixel((x,y)))
        if found and start is None:
            start=y
        elif not found and start is not None:
            if y-start>44:
                intervals.append((start,y-1))
            start=None
    if start is not None:
        intervals.append((start,1149))
    candidates=[]
    for top,bottom in intervals:
        mid=(top+bottom)//2
        l=x; r=x
        while l>0 and _cyan(ref.getpixel((l-1,mid))):l-=1
        while r<REFERENCE[0]-1 and _cyan(ref.getpixel((r+1,mid))):r+=1
        if r-l>350:
            candidates.append((r-l,l,top,r,bottom))
    if not candidates:
        raise RuntimeError('No cyan headline bar found. Confirm the new minimalist image was uploaded.')
    _,l,t,r,b=max(candidates)
    return (l+17, t+6, r-17, b-6)


def _category_start(template, title_bottom):
    """Detect tiny purple category chip below the text panel to protect the footer."""
    im=template.resize(REFERENCE, Image.Resampling.NEAREST).convert("RGB")
    for y in range(max(title_bottom+125, 1240), 1480, 2):
        count=0
        for x in range(310,631,4):
            r,g,b=im.getpixel((x,y))
            if r<170 and g<130 and b>115 and b>r+20:
                count+=1
        if count>=5:
            return y
    return 1340 if title_bottom<650 else 1400


def _zones(template, mode):
    l,top,r,bottom=_headline_zone(template)
    chip=_category_start(template,bottom)
    zones={
        'title':(l,top,r,bottom),
        'body':(82, bottom+44, 859, min(chip-46, 1390))
    }
    if mode=='photo':
        # Intentionally open, *unframed* space above the title for any image ratio.
        zones['photo']=(98, 155, 843, top-33)
    return zones


def insert_unframed_photo(canvas, image, bounds):
    """Contain the full image in the available open area, with no frame/crop/blur."""
    x1,y1,x2,y2=scale_box(bounds)
    max_w,max_h=x2-x1,y2-y1
    if max_h<150:
        raise RuntimeError('Photo slot too short; check template geometry')
    img=ImageOps.exif_transpose(image).convert('RGB')
    img=ImageOps.contain(img, (max_w,max_h), method=Image.Resampling.LANCZOS)
    # Very wide images appear naturally shorter, portraits naturally narrower.
    px=x1+(max_w-img.width)//2
    py=y1+(max_h-img.height)//2
    canvas.paste(img,(px,py))
    print(f"PHOTO FIT: original {image.width}x{image.height} -> {img.width}x{img.height}; crop=none, frame=none")


def _draw_variant(story, mode):
    canvas=load_template(story.topic, mode)
    if story.topic in NEW_ZONE_DATA:
        item = NEW_ZONE_DATA[story.topic]['modes']['text' if mode=='text_only' else 'photo']['geometry_1080x1920']
        # Existing text renderer accepts boxes in 941x1672 reference geometry.
        zones = {key: tuple(round(v*(REFERENCE[i%2]/CANVAS[i%2])) for i,v in enumerate(box))
                 for key,box in item.items() if key in ('title','body','photo') and box is not None}
    else:
        zones=_zones(canvas,mode)
    if mode=='photo':
        if story.image is None:
            raise RuntimeError('No image provided')
        insert_unframed_photo(canvas,story.image,zones['photo'])
    text=story.summary_photo_fa if mode=='photo' else story.summary_fa
    emphasis=getattr(story, 'emphasis_terms', ()) or ()
    if not draw_story_text(canvas,story.title_fa,zones['title'],headline=True):
        return None, 'headline too long'
    if not draw_story_text(canvas,text,zones['body'],phrases=emphasis):
        return None, 'body does not fit'
    return canvas, ''


def render_story(story,index):
    preferred='photo' if story.image is not None else 'text_only'
    attempts=[preferred] if preferred=='text_only' else ['photo','text_only']
    errors=[]
    for mode in attempts:
        try:
            canvas,reason=_draw_variant(story,mode)
        except Exception as exc:
            errors.append(f'{mode}: {type(exc).__name__}: {exc}')
            continue
        if canvas is None:
            errors.append(f'{mode}: {reason}')
            continue
        OUTPUT_DIR.mkdir(parents=True,exist_ok=True)
        path=OUTPUT_DIR/f'{index:02d}_{story.topic}_{mode}.png'
        canvas.save(path,'PNG',optimize=True)
        print(f'RENDER OK: {path} | V2.6 | {mode}')
        if mode!=preferred:
            print(f'LAYOUT FALLBACK: {story.topic}: full story shown in text-only template')
        return path,mode
    raise RuntimeError('All layouts failed for '+story.topic+': '+'; '.join(errors))


def render_intro():
    path=TEMPLATE_DIR/'intro_story.png'
    if not path.is_file():
        raise FileNotFoundError(f'Missing unchanged intro template: {path}')
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out=OUTPUT_DIR/'01_intro.png'
    Image.open(path).convert('RGB').resize(CANVAS,Image.Resampling.LANCZOS).save(out)
    print('RENDER OK:',out)
    return out
