import os
import numpy as np
from PIL import Image, ImageOps

# Carpetas
INPUT_FOLDER = "scans"
OUTPUT_FOLDER = "splits"

# Parámetros de detección
THRESHOLD_DARK = 25        # píxel considerado “muy oscuro”
THRESHOLD_WHITE = 235      # píxel considerado “muy claro”
BORDER_TOL = 0.92          # % de píxeles extremos para considerar “todo borde”
MAX_CROP_PCT = 0.12        # no recortar más del 12% por cada lado al auto-crop
MARGIN = 0.20              # margen central ignorado para buscar el divisor
WINDOW = 20                # refinado del divisor

# Proporción nativa Pentax 17: 17x24 (lado corto / lado largo)
TARGET_RATIO = 17.0 / 24.0
RATIO_TOL = 0.10  # 10% de tolerancia antes de tocar nada

def autocrop_lab_border(img):
    """
    Elimina marcos grandes casi blancos o casi negros alrededor del escaneo
    (funciona con laboratorios que añaden borde blanco y con fotograma negro).
    """
    g = np.array(img.convert("L"))
    h, w = g.shape

    max_x = int(w * MAX_CROP_PCT)
    max_y = int(h * MAX_CROP_PCT)

    def scan_from_left():
        x = 0
        while x < max_x:
            col = g[:, x]
            if (col >= THRESHOLD_WHITE).mean() > BORDER_TOL or (col <= THRESHOLD_DARK).mean() > BORDER_TOL:
                x += 1
            else:
                break
        return x

    def scan_from_right():
        x = w - 1
        limit = w - max_x
        while x > limit:
            col = g[:, x]
            if (col >= THRESHOLD_WHITE).mean() > BORDER_TOL or (col <= THRESHOLD_DARK).mean() > BORDER_TOL:
                x -= 1
            else:
                break
        return w - 1 - x

    def scan_from_top():
        y = 0
        while y < max_y:
            row = g[y, :]
            if (row >= THRESHOLD_WHITE).mean() > BORDER_TOL or (row <= THRESHOLD_DARK).mean() > BORDER_TOL:
                y += 1
            else:
                break
        return y

    def scan_from_bottom():
        y = h - 1
        limit = h - max_y
        while y > limit:
            row = g[y, :]
            if (row >= THRESHOLD_WHITE).mean() > BORDER_TOL or (row <= THRESHOLD_DARK).mean() > BORDER_TOL:
                y -= 1
            else:
                break
        return h - 1 - y

    left   = scan_from_left()
    right  = scan_from_right()
    top    = scan_from_top()
    bottom = scan_from_bottom()

    # Evita invertir coordenadas si algo salió raro
    x0 = min(max(0, left), w - 2)
    x1 = max(x0 + 1, w - right)
    y0 = min(max(0, top), h - 2)
    y1 = max(y0 + 1, h - bottom)

    return img.crop((x0, y0, x1, y1))


def find_split_column(arr, margin=MARGIN, window=WINDOW):
    """Busca la columna más oscura (divisor) en la zona central."""
    profile = arr.mean(axis=0)
    w = arr.shape[1]
    start = int(w * margin)
    end = int(w * (1 - margin))
    start = max(0, min(start, w - 1))
    end   = max(start + 1, min(end, w))

    idx = np.argmin(profile[start:end]) + start
    l = max(start, idx - window)
    r = min(end, idx + window)
    return l + np.argmin(profile[l:r])


def trim_dark_bands(img):
    """
    Quita bandas oscuras finas remanentes en los cuatro lados
    y usa la proporción 17x24 para evitar cortar demasiado imagen
    en fotos muy oscuras.
    """
    g = np.array(img.convert("L"))
    h, w = g.shape

    # --- recorte inicial por bandas oscuras ---
    top = 0
    while top < h and g[top, :].mean() < THRESHOLD_DARK:
        top += 1

    bottom = h - 1
    while bottom > 0 and g[bottom, :].mean() < THRESHOLD_DARK:
        bottom -= 1

    left = 0
    while left < w and g[:, left].mean() < THRESHOLD_DARK:
        left += 1

    right = w - 1
    while right > 0 and g[:, right].mean() < THRESHOLD_DARK:
        right -= 1

    # Aseguramos que hay algo de área
    if bottom <= top:
        top = 0
        bottom = h - 1
    if right <= left:
        left = 0
        right = w - 1

    # --- cálculo de proporción resultante ---
    crop_w = right - left + 1
    crop_h = bottom - top + 1

    short = min(crop_w, crop_h)
    long = max(crop_w, crop_h)
    ratio = short / float(long)

    # Si la imagen se ha quedado "demasiado cuadrada"
    # (ratio > TARGET_RATIO * (1 + tolerancia)),
    # asumimos que hemos recortado demasiado en el lado largo
    # y extendemos ese lado hacia el borde opuesto.
    if ratio > TARGET_RATIO * (1.0 + RATIO_TOL):
        # lado largo vertical
        if crop_h >= crop_w:
            # lado corto = ancho; lado largo = alto
            desired_long = int(round(short / TARGET_RATIO))
            desired_long = min(desired_long, h - top)  # no salirnos de la imagen
            desired_bottom = top + desired_long - 1
            bottom = min(h - 1, max(bottom, desired_bottom))
        else:
            # lado largo horizontal
            desired_long = int(round(short / TARGET_RATIO))
            desired_long = min(desired_long, w - left)
            desired_right = left + desired_long - 1
            right = min(w - 1, max(right, desired_right))

        # recomputamos dimensiones tras el ajuste
        crop_w = right - left + 1
        crop_h = bottom - top + 1

    # Coordenadas finales asegurando coherencia
    x0 = max(0, min(left, right - 1))
    x1 = min(w, max(right + 1, x0 + 1))
    y0 = max(0, min(top, bottom - 1))
    y1 = min(h, max(bottom + 1, y0 + 1))

    return img.crop((x0, y0, x1, y1))


def split_half_frame(img_path, output_folder):
    # Carga con orientación correcta
    base = os.path.splitext(os.path.basename(img_path))[0]
    img = Image.open(img_path)
    img = ImageOps.exif_transpose(img).convert("RGB")

    # 1) Quitar marco (blanco o negro) del laboratorio
    img = autocrop_lab_border(img)

    # 2) Buscar divisor
    arr = np.array(img.convert("L"))
    split_col = find_split_column(arr)

    # 3) Cortar y afinar bordes oscuros residuales
    left_img  = img.crop((0, 0, split_col, img.height))
    right_img = img.crop((split_col, 0, img.width, img.height))
    left_img  = trim_dark_bands(left_img)
    right_img = trim_dark_bands(right_img)

    # 4) Guardar
    os.makedirs(output_folder, exist_ok=True)
    left_img.save(os.path.join(output_folder,  f"{base}_A.jpg"), quality=95, subsampling=0)
    right_img.save(os.path.join(output_folder, f"{base}_B.jpg"), quality=95, subsampling=0)
    print(f"✅ {base} → {base}_A.jpg + {base}_B.jpg")


def main():
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    for f in os.listdir(INPUT_FOLDER):
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff")):
            split_half_frame(os.path.join(INPUT_FOLDER, f), OUTPUT_FOLDER)
    print(f"\n🎞️ Listo: {OUTPUT_FOLDER}")


if __name__ == "__main__":
    main()
