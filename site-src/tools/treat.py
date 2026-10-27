"""Turn a public-domain artwork into a halftone/duotone book cover image."""
import io, sys, math, hashlib, time
import numpy as np, requests
from PIL import Image, ImageFile, ImageFilter, ImageOps

ImageFile.LOAD_TRUNCATED_IMAGES = True

W, H = 720, 960
UA = {"AIC-User-Agent": "s1directory (sharan@cura.inc)", "User-Agent": "s1directory/1.0"}


def fetch(image_id):
    for attempt in range(3):
        for size in ("1686,", "843,"):
            r = requests.get(f"https://www.artic.edu/iiif/2/{image_id}/full/{size}/0/default.jpg", headers=UA, timeout=60)
            if r.ok and len(r.content) > 5000:
                return Image.open(io.BytesIO(r.content)).convert("RGB")
        time.sleep(2 + attempt * 3)
    r.raise_for_status()
    raise IOError(f"empty image {image_id}")


def hex_rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32) / 255


def cover_crop(img, focus=None):
    fx, fy = focus or (0.5, 0.42)
    iw, ih = img.size
    target = W / H
    if iw / ih > target:
        nw = int(ih * target)
        x = int((iw - nw) * fx)
        img = img.crop((x, 0, x + nw, ih))
    else:
        nh = int(iw / target)
        y = int((ih - nh) * fy)
        img = img.crop((0, y, iw, y + nh))
    return img.resize((W, H), Image.LANCZOS)


def treat(img, ink, paper, accent, seed=0, focus=None):
    img = cover_crop(img, focus)
    g = ImageOps.autocontrast(img.convert("L"), cutoff=1.5)
    g = g.filter(ImageFilter.UnsharpMask(radius=2, percent=80, threshold=2))
    L = np.asarray(g, dtype=np.float32) / 255
    L = np.clip((L - 0.5) * 1.15 + 0.52, 0, 1)

    # 45-degree amplitude-modulated dot screen
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    cell = 5.0
    a = math.radians(45)
    u = (xx * math.cos(a) + yy * math.sin(a)) * 2 * math.pi / cell
    v = (-xx * math.sin(a) + yy * math.cos(a)) * 2 * math.pi / cell
    screen = 0.5 + 0.25 * (np.cos(u) + np.cos(v))
    soft = 1 / (1 + np.exp(-(L - screen) * 14))  # soft-edged dots
    tone = 0.45 * L + 0.55 * soft

    rng = np.random.default_rng(seed)
    tone += rng.normal(0, 0.045, tone.shape).astype(np.float32)
    tone = np.clip(tone, 0, 1)[..., None]

    ink, paper, accent = hex_rgb(ink), hex_rgb(paper), hex_rgb(accent)
    # tritone: ink -> accent -> paper, accent kept subtle in the mids
    mid = ink * 0.45 + accent * 0.55
    lo = np.clip(tone * 2, 0, 1)
    hi = np.clip(tone * 2 - 1, 0, 1)
    rgb = np.where(tone < 0.5, ink + (mid - ink) * lo, mid + (paper - mid) * hi)

    # misregistration: shift a faint accent layer like a riso second drum
    shadow = np.roll(1 - tone, (2, 3), axis=(0, 1))
    rgb = rgb * (1 - 0.08 * shadow) + accent * 0.08 * shadow

    # vignette
    r = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H / 2) / H) ** 2)[..., None]
    rgb *= 1 - 0.35 * np.clip(r - 0.25, 0, 1)
    return Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))


def make(image_id, ink, paper, accent, out, cache_dir=None, focus=None):
    src = None
    if cache_dir:
        p = f"{cache_dir}/{image_id}.jpg"
        try:
            src = Image.open(p).convert("RGB")
        except FileNotFoundError:
            src = fetch(image_id)
            src.save(p, quality=92)
    else:
        src = fetch(image_id)
    seed = int(hashlib.md5(image_id.encode()).hexdigest()[:8], 16)
    treat(src, ink, paper, accent, seed, focus).save(out, quality=74, optimize=True, progressive=True)


if __name__ == "__main__":
    make(*sys.argv[1:6])
