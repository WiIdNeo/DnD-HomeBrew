#!/usr/bin/env python3
"""
kartenraster.py - erzeugt eine Karte mit Kachelraster, Rand und Kilometerskala.

Voraussetzung:  pip install pillow

Beispiele
---------
Leere Weltkarte, 48 x 24 Kacheln, 833 km pro Kachel:
    python kartenraster.py --tiles-x 48 --tiles-y 24 --km 833 -o welt.png

Regionalkarte (8x8 Kacheln, 104 km pro Kachel), 60 Pixel pro Kachel:
    python kartenraster.py --tiles-x 8 --tiles-y 8 --km 104 --tile-px 60 -o region.png

Raster auf bestehendes Bild legen (Kacheln werden quadratisch, wenn --tiles-y fehlt):
    python kartenraster.py --input meine_karte.png --tiles-x 48 --km 833 -o welt_raster.png

Rand: oben/links/rechts 100 px, unten 0 px (anpassbar):
    python kartenraster.py --tiles-x 20 --tiles-y 12 --km 26 --border-bottom 100
"""

import argparse
import math
import sys

from PIL import Image, ImageColor, ImageDraw, ImageFont


def load_font(size):
    """Sucht eine brauchbare TrueType-Schrift, sonst Pillow-Standard."""
    for name in ("DejaVuSans.ttf", "arial.ttf", "Arial.ttf", "Helvetica.ttc"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # sehr alte Pillow-Version
        return ImageFont.load_default()


def draw_grid(size, tiles_x, tiles_y, line_color, line_width, major_every, major_width):
    """Zeichnet das Raster auf eine transparente Ebene der Kartengröße."""
    w, h = size
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    tile_w = w / tiles_x
    tile_h = h / tiles_y

    for i in range(tiles_x + 1):
        x = min(round(i * tile_w), w - 1)
        major = major_every and i % major_every == 0
        d.line([(x, 0), (x, h)], fill=line_color, width=major_width if major else line_width)
    for j in range(tiles_y + 1):
        y = min(round(j * tile_h), h - 1)
        major = major_every and j % major_every == 0
        d.line([(0, y), (w, y)], fill=line_color, width=major_width if major else line_width)
    return layer


def draw_scale(draw, x, y, tile_w, tiles_x, tiles_y, km):
    """Zeichnet Maßstabsbalken und Beschriftung (oben links im Rand)."""
    font = load_font(16)
    small = load_font(13)

    # Balkenlänge in Kacheln: kleinste "runde" Zahl, die mindestens ~150 px lang ist
    n = tiles_x
    for candidate in (1, 2, 5, 10, 20, 50, 100, 200, 500):
        if candidate <= tiles_x and candidate * tile_w >= 150:
            n = candidate
            break

    bar_h = 8
    bar_y = y + 24
    for i in range(n):
        x0 = round(x + i * tile_w)
        x1 = round(x + (i + 1) * tile_w)
        fill = "black" if i % 2 == 0 else "white"
        draw.rectangle([x0, bar_y, x1, bar_y + bar_h], fill=fill, outline="black")

    draw.text((x, y), f"{n} Tile{'s' if n != 1 else ''} = {fmt_km(n * km)} km", fill="black", font=font)
    draw.text(
        (x, bar_y + bar_h + 6),
        f"1 Tile = {fmt_km(km)} km   |   Map: {fmt_km(tiles_x * km)} x {fmt_km(tiles_y * km)} km "
        f"({tiles_x} x {tiles_y} Tiles)",
        fill="black",
        font=small,
    )


def fmt_km(value):
    """Formatiert Kilometerangaben ohne unnötige Nachkommastellen."""
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value)):,}".replace(",", ".")
    return f"{value:.1f}".replace(".", ",")


def parse_args():
    p = argparse.ArgumentParser(description="Kartenraster mit Rand und Kilometerskala erzeugen.")
    p.add_argument("--tiles-x", type=int, required=True, help="Anzahl Kacheln horizontal")
    p.add_argument("--tiles-y", type=int, help="Anzahl Kacheln vertikal (bei --input optional)")
    p.add_argument("--km", type=float, required=True, help="Kilometer pro Kachel")
    p.add_argument("--input", "-i", help="Bestehendes Bild, auf das das Raster gelegt wird")
    p.add_argument("--output", "-o", default="karte.png", help="Ausgabedatei (Standard: karte.png)")
    p.add_argument("--tile-px", type=int, default=40, help="Pixel pro Kachel ohne --input (Standard: 40)")

    p.add_argument("--border-top", type=int, default=100, help="Rand oben in Pixel (Standard: 100)")
    p.add_argument("--border-left", type=int, default=100, help="Rand links in Pixel (Standard: 100)")
    p.add_argument("--border-right", type=int, default=100, help="Rand rechts in Pixel (Standard: 100)")
    p.add_argument("--border-bottom", type=int, default=0, help="Rand unten in Pixel (Standard: 0)")

    p.add_argument("--line-color", default="#5a78a064",
                   help="Linienfarbe, Hex mit optionalem Alpha, z.B. #00000050 (Standard: #5a78a064)")
    p.add_argument("--line-width", type=int, default=1, help="Linienstärke (Standard: 1)")
    p.add_argument("--major-every", type=int, default=0,
                   help="Jede n-te Linie dicker zeichnen (0 = aus)")
    p.add_argument("--major-width", type=int, default=2, help="Stärke der dicken Linien (Standard: 2)")
    p.add_argument("--no-labels", action="store_true", help="Keine Kachelnummern am Rand")
    p.add_argument("--no-scale", action="store_true", help="Keine Skala im Rand")
    return p.parse_args()


def main():
    a = parse_args()
    if a.tiles_x < 1 or (a.tiles_y is not None and a.tiles_y < 1):
        sys.exit("Kachelzahlen müssen mindestens 1 sein.")

    # --- Kartenfläche vorbereiten ---------------------------------------
    if a.input:
        base = Image.open(a.input).convert("RGBA")
        w, h = base.size
        tile_w = w / a.tiles_x
        if a.tiles_y is None:
            tiles_y = max(1, round(h / tile_w))
            print(f"tiles-y nicht angegeben, verwende {tiles_y} (quadratische Kacheln).")
        else:
            tiles_y = a.tiles_y
        tile_h = h / tiles_y
        if abs(tile_w - tile_h) / tile_w > 0.05:
            print(f"Warnung: Kacheln sind nicht quadratisch ({tile_w:.1f} x {tile_h:.1f} px). "
                  f"Passende tiles-y wäre ca. {h / tile_w:.1f}.")
    else:
        if a.tiles_y is None:
            sys.exit("Ohne --input muss --tiles-y angegeben werden.")
        tiles_y = a.tiles_y
        w, h = a.tiles_x * a.tile_px, tiles_y * a.tile_px
        base = Image.new("RGBA", (w, h), "white")
        tile_w = a.tile_px

    line_color = ImageColor.getcolor(a.line_color, "RGBA")
    grid = draw_grid((w, h), a.tiles_x, tiles_y, line_color,
                     a.line_width, a.major_every, a.major_width)
    map_img = Image.alpha_composite(base, grid)

    # --- Leinwand mit Rand ----------------------------------------------
    bt, bl, br, bb = a.border_top, a.border_left, a.border_right, a.border_bottom
    canvas = Image.new("RGBA", (bl + w + br, bt + h + bb), "white")
    canvas.paste(map_img, (bl, bt))
    d = ImageDraw.Draw(canvas)
    d.rectangle([bl, bt, bl + w - 1, bt + h - 1], outline="black", width=2)

    # --- Kachelnummern ----------------------------------------------------
    if not a.no_labels:
        font = load_font(12)
        tile_h = h / tiles_y
        if bt >= 20:
            step = max(1, math.ceil(30 / tile_w))
            for i in range(0, a.tiles_x, step):
                d.text((bl + (i + 0.5) * tile_w, bt - 4), str(i + 1), fill="black", font=font, anchor="ms")
        if bl >= 30:
            step = max(1, math.ceil(18 / tile_h))
            for j in range(0, tiles_y, step):
                d.text((bl - 6, bt + (j + 0.5) * tile_h), str(j + 1), fill="black", font=font, anchor="rm")

    # --- Skala --------------------------------------------------------------
    if not a.no_scale:
        if bt >= 80:
            draw_scale(d, bl, 10, tile_w, a.tiles_x, tiles_y, a.km)
        else:
            print("Hinweis: Oberer Rand < 80 px, Skala wird nicht gezeichnet.")

    canvas.convert("RGB").save(a.output)
    print(f"Gespeichert: {a.output}  ({canvas.width} x {canvas.height} px, "
          f"{a.tiles_x} x {tiles_y} Kacheln, {fmt_km(a.km)} km/Kachel)")


if __name__ == "__main__":
    main()