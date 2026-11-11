"""Videoda yuklanadigan namunaviy fayllar: dars ishlanmasi (PDF) va qisqa dars videosi (MP4)."""
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "samples"
OUT.mkdir(exist_ok=True)
FONT = "C:/Windows/Fonts/segoeui.ttf"
FONT_B = "C:/Windows/Fonts/segoeuib.ttf"


def pdf(name, title, lines):
    img = Image.new("RGB", (1240, 1754), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 1240, 150], fill=(65, 84, 241))
    d.text((80, 45), title, font=ImageFont.truetype(FONT_B, 46), fill="white")
    y = 220
    body = ImageFont.truetype(FONT, 30)
    for line in lines:
        d.text((80, y), line, font=body, fill=(30, 30, 40))
        y += 56
    img.save(OUT / name, "PDF", resolution=150)


pdf("Interfaol_dars_loyihasi.pdf", "Dars loyihasi: Interfaol metodlar", [
    "Fan: Tabiatshunoslik, 3-sinf",
    "Mavzu: «Suv va uning xossalari»",
    "Davomiyligi: 45 daqiqa",
    "",
    "1. Tashkiliy qism — 3 daqiqa",
    "2. «Aqliy hujum» — 7 daqiqa",
    "3. Juftlikda ishlash: tajriba — 15 daqiqa",
    "4. «Klaster» usuli — 10 daqiqa",
    "5. Refleksiya va baholash — 10 daqiqa",
])
pdf("dars_ishlanmasi_v1.pdf", "Dars ishlanmasi (1-versiya)", ["Savol-javob metodi", "3-sinf, «Tabiat»"])
pdf("dars_ishlanmasi_v2.pdf", "Dars ishlanmasi (2-versiya)", ["Ochiq savollar va juftlikda muhokama"])

ff = imageio_ffmpeg.get_ffmpeg_exe()
subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=duration=4:size=640x360:rate=25",
                "-pix_fmt", "yuv420p", "-c:v", "libx264", str(OUT / "Dars_videosi.mp4")], check=True)
print("ok", sorted(p.name for p in OUT.iterdir()), file=sys.stderr)
