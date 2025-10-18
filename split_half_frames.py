import os
import numpy as np
from PIL import Image

# 🔧 Configuration: change these folder names if needed
INPUT_FOLDER = "scans"
OUTPUT_FOLDER = "splits"

# Trimming parameters
THRESHOLD = 10   # darkness threshold for trimming (0=black, 255=white)
MARGIN = 0.2     # ignore this fraction at each side when searching for divider
WINDOW = 20      # refinement window size around the divider


def find_split_column(arr, margin=MARGIN, window=WINDOW):
    """
    Find the vertical column with the darkest average (likely the divider).
    """
    profile = arr.mean(axis=0)  # average brightness per column
    w = arr.shape[1]

    start = int(w * margin)
    end = int(w * (1 - margin))
    profile_central = profile[start:end]

    min_idx = np.argmin(profile_central) + start

    # refine around the minimum
    left = max(start, min_idx - window)
    right = min(end, min_idx + window)
    refined = left + np.argmin(profile[left:right])

    return refined


def trim_black_edges(img, threshold=THRESHOLD):
    """
    Trim vertical black borders from a split image.
    """
    gray = img.convert("L")
    arr = np.array(gray)
    profile = arr.mean(axis=0)

    left = 0
    while left < len(profile) and profile[left] < threshold:
        left += 1

    right = len(profile) - 1
    while right > 0 and profile[right] < threshold:
        right -= 1

    if right > left:
        img = img.crop((left, 0, right, img.height))
    return img


def split_half_frame(img_path, output_folder):
    """Split one lab scan into two half-frame images and trim black edges."""
    img_gray = Image.open(img_path).convert("L")
    arr = np.array(img_gray)

    split_col = find_split_column(arr)

    img_color = Image.open(img_path).convert("RGB")
    left_img = img_color.crop((0, 0, split_col, img_color.height))
    right_img = img_color.crop((split_col, 0, img_color.width, img_color.height))

    # trim leftover dark bands
    left_img = trim_black_edges(left_img)
    right_img = trim_black_edges(right_img)

    # save
    basename = os.path.splitext(os.path.basename(img_path))[0]
    left_img.save(os.path.join(output_folder, f"{basename}_A.jpg"), quality=95, subsampling=0)
    right_img.save(os.path.join(output_folder, f"{basename}_B.jpg"), quality=95, subsampling=0)

    print(f"✅ {basename} → {basename}_A.jpg + {basename}_B.jpg")


def main():
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    for file in os.listdir(INPUT_FOLDER):
        if file.lower().endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff")):
            split_half_frame(os.path.join(INPUT_FOLDER, file), OUTPUT_FOLDER)

    print(f"\n🎞️ All done! Split images saved in: {OUTPUT_FOLDER}")


if __name__ == "__main__":
    main()