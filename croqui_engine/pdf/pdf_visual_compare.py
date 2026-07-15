from __future__ import annotations

from pathlib import Path


def render_pdf_first_page(pdf_path: Path, png_path: Path, zoom: float = 1.0) -> Path:
    import fitz

    png_path.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(pdf_path) as doc:
        if not doc:
            raise ValueError(f"PDF sem paginas: {pdf_path}")
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        pix.save(png_path)
    return png_path


def compare_pdf_visual(target_pdf: Path, generated_pdf: Path, output_dir: Path) -> dict:
    from PIL import Image, ImageChops, ImageOps, ImageStat

    output_dir.mkdir(parents=True, exist_ok=True)
    target_png = render_pdf_first_page(target_pdf, output_dir / "target_page.png", zoom=2.0)
    generated_png = render_pdf_first_page(generated_pdf, output_dir / "generated_page.png", zoom=2.0)
    target = Image.open(target_png).convert("RGB")
    generated = Image.open(generated_png).convert("RGB").resize(target.size)
    diff = ImageChops.difference(target, generated)
    stat = ImageStat.Stat(diff)
    mean_diff = sum(stat.mean) / len(stat.mean)
    page_score = max(0.0, min(1.0, 1.0 - mean_diff / 255.0))
    heatmap = ImageOps.grayscale(diff).point(lambda value: min(255, value * 3))
    heatmap_rgb = ImageOps.colorize(heatmap, black="#ffffff", white="#d7332f")
    heatmap_path = output_dir / "visual_diff.png"
    heatmap_rgb.save(heatmap_path)

    target_drawing = _drawing_crop(target)
    generated_drawing = _drawing_crop(generated).resize(target_drawing.size)
    target_drawing_path = output_dir / "target_drawing.png"
    generated_drawing_path = output_dir / "generated_drawing.png"
    drawing_diff_path = output_dir / "drawing_diff.png"
    target_drawing.save(target_drawing_path)
    generated_drawing.save(generated_drawing_path)
    ImageOps.colorize(
        ImageOps.grayscale(ImageChops.difference(target_drawing, generated_drawing)).point(
            lambda value: min(255, value * 3)
        ),
        black="#ffffff",
        white="#d7332f",
    ).save(drawing_diff_path)
    foreground = _foreground_metrics(target_drawing, generated_drawing)
    strict_score = foreground["foreground_iou"]
    return {
        "visual_score": round(strict_score, 4),
        "page_visual_score": round(page_score, 4),
        "mean_pixel_diff": round(mean_diff, 4),
        **foreground,
        "target_png": str(target_png),
        "generated_png": str(generated_png),
        "visual_diff_path": str(heatmap_path),
        "target_drawing_png": str(target_drawing_path),
        "generated_drawing_png": str(generated_drawing_path),
        "drawing_diff_path": str(drawing_diff_path),
        "target_size": target.size,
        "generated_original_size": Image.open(generated_png).size,
    }


def _drawing_crop(image):
    width, height = image.size
    top = int(height * 0.12)
    bottom = _yellow_table_y(image) or int(height * 0.78)
    bottom = max(top + 10, min(bottom, int(height * 0.90)))
    left = int(width * 0.02)
    right = int(width * 0.98)
    return image.crop((left, top, right, bottom))


def _yellow_table_y(image) -> int | None:
    width, height = image.size
    pixels = image.load()
    start = int(height * 0.35)
    for y in range(start, height):
        hits = 0
        for x in range(0, width, 6):
            r, g, b = pixels[x, y]
            if r > 210 and g > 185 and b < 120:
                hits += 1
        if hits > width / 6 * 0.35:
            return y
    return None


def _foreground_metrics(target, generated) -> dict:
    target_mask = _foreground_mask(target)
    generated_mask = _foreground_mask(generated)
    intersection = 0
    union = 0
    target_count = 0
    generated_count = 0
    for t, g in zip(target_mask, generated_mask, strict=False):
        if t:
            target_count += 1
        if g:
            generated_count += 1
        if t or g:
            union += 1
        if t and g:
            intersection += 1
    precision = intersection / generated_count if generated_count else 0.0
    recall = intersection / target_count if target_count else 0.0
    iou = intersection / union if union else 1.0
    return {
        "foreground_iou": round(iou, 4),
        "foreground_precision": round(precision, 4),
        "foreground_recall": round(recall, 4),
        "target_foreground_px": target_count,
        "generated_foreground_px": generated_count,
    }


def _foreground_mask(image) -> list[bool]:
    from PIL import ImageOps

    gray = ImageOps.grayscale(image)
    return [value < 235 for value in gray.getdata()]
