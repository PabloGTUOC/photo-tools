import os
from PIL import Image, ImageDraw, ImageOps

# 🔧 Configuration
INPUT_FOLDER = "scans"
OUTPUT_FOLDER = "borders"

OUTPUT_LONG_SIDE = 3000   # max long edge for export
MIN_BORDER = 50            # minimum white border (all around)
CORNER_RADIUS_PCT = 0.02   # rounded corner radius as % of smaller image side
UPSCALE_SMALLER = True    # if True, small images will scale up to meet the target box

def choose_canvas_size(w, h):
    """
    Portraits → 4:5 (width:height).
    Landscapes → 5:4 (width:height).
    """
    if h >= w:  # portrait
        return (OUTPUT_LONG_SIDE, int(OUTPUT_LONG_SIDE * 5 / 4))  # 4:5 portrait
    else:       # landscape
        return (OUTPUT_LONG_SIDE, int(OUTPUT_LONG_SIDE * 4 / 5))  # 5:4 landscape
def process_image(img_path, output_path):
    img = Image.open(img_path).convert("RGB")
    img = ImageOps.exif_transpose(img)
    w, h = img.size

    # Step 1: choose fixed canvas size
    canvas_w, canvas_h = choose_canvas_size(w, h)

    # Step 2: compute max image size (inside borders)
    max_w = canvas_w - 2 * MIN_BORDER
    max_h = canvas_h - 2 * MIN_BORDER

    # Compute scale to fit within the box
    w0, h0 = img.size
    scale = min(max_w / w0, max_h / h0)

    # Resize: always downscale; upscale only if UPSCALE_SMALLER is True
    if scale < 1 or UPSCALE_SMALLER:
        new_w = max(1, int(round(w0 * scale)))
        new_h = max(1, int(round(h0 * scale)))
        img = img.resize((new_w, new_h), Image.LANCZOS)

    iw, ih = img.size

    # Step 3: create white canvas
    canvas = Image.new("RGB", (canvas_w, canvas_h), "white")

    # Step 4: compute centered position
    x = (canvas_w - iw) // 2
    y = (canvas_h - ih) // 2

    # Step 5: create a rounded-corner mask and paste the image with it
    radius = max(1, int(min(iw, ih) * CORNER_RADIUS_PCT))
    mask = Image.new("L", (iw, ih), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([0, 0, iw, ih], radius=radius, fill=255)

    # Step 6: paste image with rounded corners onto the white canvas
    canvas.paste(img, (x, y), mask)

    # Save
    canvas.save(output_path, quality=95, subsampling=0)


def main():
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    for file in os.listdir(INPUT_FOLDER):
        if file.lower().endswith((".jpg", ".jpeg", ".png")):
            in_path = os.path.join(INPUT_FOLDER, file)
            name, ext = os.path.splitext(file)
            out_path = os.path.join(OUTPUT_FOLDER, f"{name}_blog{ext}")
            process_image(in_path, out_path)

    print(f"\n✅ All done! Portraits = 4:5, Landscapes = 5:4 saved in: {OUTPUT_FOLDER}")


if __name__ == "__main__":
    main()
