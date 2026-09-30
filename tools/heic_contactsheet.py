from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
from pillow_heif import register_heif_opener


register_heif_opener()

source = Path("Sample")
output = source / "_review"
output.mkdir(exist_ok=True)
full_output = output / "full"
full_output.mkdir(exist_ok=True)

files = sorted(source.glob("*.HEIC"))
thumb_size = (360, 270)
cell_size = (380, 310)
columns = 4
rows = 4

for page_start in range(0, len(files), columns * rows):
    page_files = files[page_start : page_start + columns * rows]
    sheet = Image.new("RGB", (cell_size[0] * columns, cell_size[1] * rows), "white")
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(page_files):
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            full_path = full_output / f"{path.stem}.jpg"
            review_image = image.copy()
            review_image.thumbnail((2400, 2400))
            review_image.save(full_path, quality=90)
            image.thumbnail(thumb_size)
            x = (index % columns) * cell_size[0] + (cell_size[0] - image.width) // 2
            y = (index // columns) * cell_size[1] + 5
            sheet.paste(image, (x, y))
            draw.text(((index % columns) * cell_size[0] + 10, (index // columns) * cell_size[1] + 280), path.stem, fill="black")
    page_number = page_start // (columns * rows) + 1
    sheet.save(output / f"contact_{page_number}.jpg", quality=90)

print(f"Created {(len(files) + columns * rows - 1) // (columns * rows)} contact sheets for {len(files)} HEIC files in {output}")
