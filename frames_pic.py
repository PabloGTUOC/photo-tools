import os
from PIL import Image, ImageDraw

# 🔧 Configuration
INPUT_FOLDER = "splits"
OUTPUT_FOLDER = "borders"

OUTPUT_LONG_SIDE = 3000   # max long edge for export
MIN_BORDER = 50            # minimum white border (all around)
BLACK_LINE = 9            # black stroke around image

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
    w, h = img.size

    # Step 1: choose fixed canvas size
    canvas_w, canvas_h = choose_canvas_size(w, h)

    # Step 2: compute max image size (inside borders)
    max_w = canvas_w - 2 * MIN_BORDER
    max_h = canvas_h - 2 * MIN_BORDER

    img.thumbnail((max_w, max_h), Image.LANCZOS)
    iw, ih = img.size

    # Step 3: create white canvas
    canvas = Image.new("RGB", (canvas_w, canvas_h), "white")

    # Step 4: compute centered position
    x = (canvas_w - iw) // 2
    y = (canvas_h - ih) // 2

    # Step 5: draw black stroke around photo
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([x - BLACK_LINE, y - BLACK_LINE,
                    x + iw + BLACK_LINE - 1, y + ih + BLACK_LINE - 1],
                   outline="black", width=BLACK_LINE)

    # Step 6: paste photo
    canvas.paste(img, (x, y))

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
