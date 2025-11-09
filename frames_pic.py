import os
from PIL import Image, ImageDraw, ImageOps, ImageStat

# ===== Config =====
OUTPUT_LONG_SIDE   = 3000       # long edge final
MIN_BORDER         = 50         # borde blanco mínimo
CORNER_RADIUS_PCT  = 0.02       # radio esquinas vs. lado menor de la foto
UPSCALE_SMALLER    = True
ANTIALIAS_SCALE    = 4          # supersampling para máscara redondeada

# Auto-trim de bordes oscuros del escaneo
AUTO_TRIM          = True
TRIM_THRESH        = 28         # 0..255 (más alto = más agresivo)
TRIM_MAX_PX        = 40         # recorte máximo por lado
TRIM_SAFETY_INSET  = 1          # px extra hacia dentro tras el recorte

def choose_canvas_size(w, h):
    # Portrait → 4:5 ; Landscape → 5:4  (width:height)
    if h >= w:
        return (OUTPUT_LONG_SIDE, int(OUTPUT_LONG_SIDE * 5 / 4))
    else:
        return (OUTPUT_LONG_SIDE, int(OUTPUT_LONG_SIDE * 4 / 5))

def _luma(px):  # quick grayscale weight
    r, g, b = px
    return 0.2126*r + 0.7152*g + 0.0722*b

def auto_trim_dark_edges(img: Image.Image) -> Image.Image:
    """
    Detecta “rebates” oscuros en los 4 lados y los recorta.
    Solo recorta si una franja inicial está por debajo de TRIM_THRESH.
    """
    if img.mode != "RGB":
        img = img.convert("RGB")
    w, h = img.size
    pixels = img.load()

    def edge_dark_run(side):
        limit = TRIM_MAX_PX
        acc = 0
        # tamaño de banda muestreada por paso (para ser robustos al grano)
        band = max(1, min(8, (w if side in ("top","bottom") else h)//200))

        for d in range(limit):
            if side == "left":
                x = d
                vals = [_luma(pixels[x, y]) for y in range(0, h, band)]
            elif side == "right":
                x = w-1-d
                vals = [_luma(pixels[x, y]) for y in range(0, h, band)]
            elif side == "top":
                y = d
                vals = [_luma(pixels[x, y]) for x in range(0, w, band)]
            else:  # bottom
                y = h-1-d
                vals = [_luma(pixels[x, y]) for x in range(0, w, band)]

            # si la franja es mayoritariamente oscura, seguimos
            if sum(v < TRIM_THRESH for v in vals) / len(vals) > 0.7:
                acc += 1
            else:
                break
        return acc

    left   = edge_dark_run("left")
    right  = edge_dark_run("right")
    top    = edge_dark_run("top")
    bottom = edge_dark_run("bottom")

    if max(left, right, top, bottom) == 0:
        return img  # nada que recortar

    # Inset de seguridad para evitar quedarnos justo en el borde
    left   = min(left   + TRIM_SAFETY_INSET, w-2)
    right  = min(right  + TRIM_SAFETY_INSET, w-2)
    top    = min(top    + TRIM_SAFETY_INSET, h-2)
    bottom = min(bottom + TRIM_SAFETY_INSET, h-2)

    box = (left, top, w-right, h-bottom)
    if box[2] - box[0] > 10 and box[3] - box[1] > 10:
        return img.crop(box)
    return img

def process_image(img_path, output_path):
    img = Image.open(img_path).convert("RGB")
    img = ImageOps.exif_transpose(img)

    # --- Recorte automático de bordes negros del escaneo ---
    if AUTO_TRIM:
        img = auto_trim_dark_edges(img)

    w0, h0 = img.size

    # 1) canvas fijo por orientación
    canvas_w, canvas_h = choose_canvas_size(w0, h0)

    # 2) caja interior
    max_w = canvas_w - 2 * MIN_BORDER
    max_h = canvas_h - 2 * MIN_BORDER

    # 3) reescalar para encajar
    scale = min(max_w / w0, max_h / h0)
    if scale < 1 or UPSCALE_SMALLER:
        new_w = max(1, int(round(w0 * scale)))
        new_h = max(1, int(round(h0 * scale)))
        img = img.resize((new_w, new_h), Image.LANCZOS)

    iw, ih = img.size

    # 4) canvas blanco
    canvas = Image.new("RGB", (canvas_w, canvas_h), "white")

    # 5) posición centrada
    x = (canvas_w - iw) // 2
    y = (canvas_h - ih) // 2

    # 6) máscara redondeada con antialias
    radius = max(1, int(min(iw, ih) * CORNER_RADIUS_PCT))
    aa_w, aa_h = iw * ANTIALIAS_SCALE, ih * ANTIALIAS_SCALE
    aa_radius = radius * ANTIALIAS_SCALE
    aa_mask = Image.new("L", (aa_w, aa_h), 0)
    ImageDraw.Draw(aa_mask).rounded_rectangle([0, 0, aa_w, aa_h], radius=aa_radius, fill=255)
    mask = aa_mask.resize((iw, ih), Image.LANCZOS)

    # 7) pegar
    canvas.paste(img, (x, y), mask)

    # 8) guardar
    canvas.save(output_path, quality=95, subsampling=0)
