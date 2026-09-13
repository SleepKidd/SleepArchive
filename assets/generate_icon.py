from pathlib import Path

from PIL import Image, ImageDraw


def main() -> None:
    size = 1024
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((48, 48, 976, 976), radius=235, fill=(108, 92, 231, 255))
    draw.rounded_rectangle((230, 300, 794, 460), radius=55, fill=(255, 255, 255, 230))
    draw.rounded_rectangle((180, 430, 844, 800), radius=80, fill=(255, 255, 255, 255))
    draw.rounded_rectangle((380, 530, 644, 615), radius=42, fill=(108, 92, 231, 255))
    draw.ellipse((520, 120, 835, 435), fill=(39, 32, 79, 255))
    draw.ellipse((455, 70, 748, 363), fill=(108, 92, 231, 255))
    output = Path(__file__).with_name("SleepArchive.ico")
    image.save(output, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    main()

