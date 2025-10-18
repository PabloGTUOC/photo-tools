import os
from PIL import Image, ImageSequence

TIFF_INPUT  = "scans"
JPEG_OUTPUT = "jpeg_output_light"

MAX_LONG_EDGE   = 2048       # pixels
JPEG_QUALITY    = 90         # visually lossless, 1–3 MB typical
JPEG_SUBSAMPLING = 2         # 4:2:0 (standard)
JPEG_PROGRESSIVE = True
JPEG_OPTIMIZE    = True
FLATTEN_BG       = (255, 255, 255)

def flatten_if_alpha(img):
    if img.mode in ("RGBA", "LA") or ("transparency" in img.info):
        bg = Image.new("RGB", img.size, FLATTEN_BG)
        alpha = img.getchannel("A") if "A" in img.getbands() else None
        bg.paste(img.convert("RGB"), mask=alpha)
        return bg
    return img.convert("RGB")

def resize_to_long_edge(img, max_long):
    w, h = img.size
    if max(w, h) > max_long:
        if w >= h:
            new_w = max_long
            new_h = int(h * max_long / w)
        else:
            new_h = max_long
            new_w = int(w * max_long / h)
        return img.resize((new_w, new_h), Image.LANCZOS)
    return img

def convert_tiff(src_path, out_dir):
    with Image.open(src_path) as im:
        base = os.path.splitext(os.path.basename(src_path))[0]
        for i, frame in enumerate(ImageSequence.Iterator(im), start=1):
            img = flatten_if_alpha(frame.copy())
            img = resize_to_long_edge(img, MAX_LONG_EDGE)
            out_name = f"{base}_p{i:03d}.jpg" if im.n_frames > 1 else f"{base}.jpg"
            out_path = os.path.join(out_dir, out_name)
            img.save(
                out_path,
                quality=JPEG_QUALITY,
                subsampling=JPEG_SUBSAMPLING,
                progressive=JPEG_PROGRESSIVE,
                optimize=JPEG_OPTIMIZE,
            )
            print(f"✅ {src_path} → {out_path} ({img.size[0]}x{img.size[1]})")

def main():
    os.makedirs(JPEG_OUTPUT, exist_ok=True)
    for f in os.listdir(TIFF_INPUT):
        if f.lower().endswith((".tif", ".tiff")):
            convert_tiff(os.path.join(TIFF_INPUT, f), JPEG_OUTPUT)
    print(f"\n🎉 All done! Lighter JPEGs saved in: {JPEG_OUTPUT}")

if __name__ == "__main__":
    main()
