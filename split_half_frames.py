# split_half_frames.py

import os
import numpy as np
from PIL import Image, ImageOps

# Carpetas por defecto (las sobreescribe el GUI)
INPUT_FOLDER = "scans"
OUTPUT_FOLDER = "splits"

# ----------------- Parámetros de detección de bordes -----------------

THRESHOLD_DARK = 25        # píxel considerado “muy oscuro”
THRESHOLD_WHITE = 235      # píxel considerado “muy claro”
BORDER_TOL = 0.92          # % de píxeles extremos para considerar “todo borde”
MAX_CROP_PCT = 0.12        # no recortar más del 12% por cada lado al auto-crop
MARGIN = 0.20              # margen central ignorado para buscar el divisor
WINDOW = 20                # refinado del divisor

# Pentax 17: fotograma 17×24 mm → siempre vertical, lado corto arriba
PENTAX17_RATIO = 24.0 / 17.0  # alto / ancho ≈ 1.41


# --------------------------------------------------------------------
#   1) Auto-crop del marco blanco/negro del laboratorio (doble frame)
# --------------------------------------------------------------------

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


# --------------------------------------------------------------------
#   2) Buscar la columna de separación entre las dos medias fotos
# --------------------------------------------------------------------

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


# --------------------------------------------------------------------
#   3) Recorte fino de bandas negras respetando ratio Pentax 17
# --------------------------------------------------------------------

def _budget_from_ratio(h, w):
    """
    Calcula cuánto podemos recortar como máximo en alto y ancho para
    seguir cumpliendo aproximadamente el ratio Pentax 17 (24/17).
    """
    # Queremos h_final >= w * ratio  →  recorte_total_h <= h - w*ratio
    min_h = int(round(w * PENTAX17_RATIO))
    max_crop_h = max(0, h - min_h)

    # Y w_final >= h / ratio  →  recorte_total_w <= w - h/ratio
    min_w = int(round(h / PENTAX17_RATIO))
    max_crop_w = max(0, w - min_w)

    return max_crop_h, max_crop_w


def trim_dark_bands(img):
    """
    Quita bandas oscuras finas remanentes en los cuatro lados,
    pero SIN pasarse del ratio 24×17 de la Pentax 17.
    Prefiere dejar algo de borde negro antes que comer imagen.
    """
    g = np.array(img.convert("L"))
    h, w = g.shape

    # La Pentax 17 siempre es vertical; si por lo que sea viene apaisado, lo giramos.
    if w > h:
        img = img.rotate(90, expand=True)
        g = np.array(img.convert("L"))
        h, w = g.shape

    max_crop_h, max_crop_w = _budget_from_ratio(h, w)

    # --- recorte en vertical ---
    top = 0
    bottom = 0

    # desde arriba
    while top < h and (top + bottom) < max_crop_h:
        row = g[top, :]
        if row.mean() < THRESHOLD_DARK:
            top += 1
        else:
            break

    # desde abajo
    while bottom < h - top and (top + bottom) < max_crop_h:
        row = g[h - 1 - bottom, :]
        if row.mean() < THRESHOLD_DARK:
            bottom += 1
        else:
            break

    # --- recorte en horizontal ---
    left = 0
    right = 0

    # desde la izquierda
    while left < w and (left + right) < max_crop_w:
        col = g[:, left]
        if col.mean() < THRESHOLD_DARK:
            left += 1
        else:
            break

    # desde la derecha
    while right < w - left and (left + right) < max_crop_w:
        col = g[:, w - 1 - right]
        if col.mean() < THRESHOLD_DARK:
            right += 1
        else:
            break

    x0 = max(0, min(left, w - right - 1))
    x1 = min(w, max(w - right, x0 + 1))
    y0 = max(0, min(top, h - bottom - 1))
    y1 = min(h, max(h - bottom, y0 + 1))

    cropped = img.crop((x0, y0, x1, y1))

    # chequeo final: si el ratio ya está cerca, lo dejamos; si sigue MUY
    # por encima (recorte tímido), recortamos un pelín del bottom para acercarlo
    ch, cw = cropped.size[1], cropped.size[0]
    ratio = ch / cw
    if ratio > PENTAX17_RATIO * 1.10:  # más de un 10% más alto que el ratio teórico
        target_h = int(round(cw * PENTAX17_RATIO))
        if target_h < ch:
            extra = ch - target_h
            cropped = cropped.crop((0, extra, cw, ch))  # solo desde abajo

    return cropped


# --------------------------------------------------------------------
#   4) Split completo + trim
# --------------------------------------------------------------------

def split_half_frame(img_path, output_folder):
    """
    Divide un escaneo doble en dos medias fotos, elimina marco de laboratorio
    y ajusta bordes negros respetando el ratio Pentax 17.
    """
    base = os.path.splitext(os.path.basename(img_path))[0]

    # Carga con orientación correcta
    img = Image.open(img_path)
    img = ImageOps.exif_transpose(img).convert("RGB")

    # 1) Quitar marco blanco/negro grande
    img = autocrop_lab_border(img)

    # 2) Buscar divisor
    arr = np.array(img.convert("L"))
    split_col = find_split_column(arr)

    # 3) Cortar en dos y recortar bordes
    left_img  = img.crop((0, 0, split_col, img.height))
    right_img = img.crop((split_col, 0, img.width, img.height))
    left_img  = trim_dark_bands(left_img)
    right_img = trim_dark_bands(right_img)

    # 4) Guardar
    os.makedirs(output_folder, exist_ok=True)
    left_img.save(os.path.join(output_folder,  f"{base}_A.jpg"), quality=95, subsampling=0)
    right_img.save(os.path.join(output_folder, f"{base}_B.jpg"), quality=95, subsampling=0)
    print(f"✅ {base} → {base}_A.jpg + {base}_B.jpg")


# --------------------------------------------------------------------
#   5) Función de PREVIEW para el GUI
# --------------------------------------------------------------------

def preview_split(img_path):
    """
    Devuelve (img_entera_recortada, left, right) para usar en el GUI de preview.
    NO escribe nada a disco.
    """
    img = Image.open(img_path)
    img = ImageOps.exif_transpose(img).convert("RGB")

    img2 = autocrop_lab_border(img)
    arr = np.array(img2.convert("L"))
    split_col = find_split_column(arr)

    left_img  = img2.crop((0, 0, split_col, img2.height))
    right_img = img2.crop((split_col, 0, img2.width, img2.height))
    left_img  = trim_dark_bands(left_img)
    right_img = trim_dark_bands(right_img)

    return img2, left_img, right_img


# --------------------------------------------------------------------
#   6) Modo script directo
# --------------------------------------------------------------------

def main():
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    for f in os.listdir(INPUT_FOLDER):
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff")):
            split_half_frame(os.path.join(INPUT_FOLDER, f), OUTPUT_FOLDER)
    print(f"\n🎞️ Listo: {OUTPUT_FOLDER}")


if __name__ == "__main__":
    main()
