#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Preparador de copias web — Alicante Memoria Fílmica
Convierte tus másteres (carpetas por década) en copias web ligeras
listas para subir a la carpeta fotos/ del repositorio.

Uso:
    pip install Pillow
    python3 preparar_fotos.py /ruta/a/tus/masteres /ruta/de/salida/fotos

Estructura esperada de entrada (carpetas por década):
    masteres/1920/paseo explanada 1926.jpg
    masteres/1930/...

Salida:
    fotos/1920/1926_paseo_explanada.jpg   (≤1600px, JPEG q80)

El año se conserva si está en el nombre; si no, la foto hereda la
década de su carpeta (y se marca como "circa").
"""
import os
import re
import sys
import unicodedata

try:
    from PIL import Image, ImageOps
except ImportError:
    sys.exit("Falta Pillow:  pip install Pillow")

LADO_MAX = 1600
CALIDAD = 80
EXT_OK = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}

RE_ANO = re.compile(r"(?<!\d)(1[5-9]\d{2}|20[0-2]\d)(?!\d)")


def limpiar_nombre(nombre):
    """quita acentos y espacios para nombres seguros en URL"""
    n = unicodedata.normalize("NFKD", nombre)
    n = "".join(c for c in n if not unicodedata.combining(c))
    n = re.sub(r"[^\w\-]+", "_", n).strip("_").lower()
    return re.sub(r"_+", "_", n)


def main():
    if len(sys.argv) != 3:
        sys.exit("Uso: python3 preparar_fotos.py <carpeta_masteres> <carpeta_salida>")
    origen, destino = sys.argv[1], sys.argv[2]

    total, peso = 0, 0
    for raiz, _dirs, archivos in os.walk(origen):
        rel = os.path.relpath(raiz, origen)
        for a in sorted(archivos):
            base, ext = os.path.splitext(a)
            if ext.lower() not in EXT_OK:
                continue

            # año: del nombre del archivo, o nada (heredará la década de la carpeta)
            m = RE_ANO.search(base)
            ano = m.group(1) if m else None
            nombre = limpiar_nombre(RE_ANO.sub("", base) if ano else base)
            nuevo = (f"{ano}_{nombre}" if ano else nombre) + ".jpg"

            carpeta_out = os.path.join(destino, rel) if rel != "." else destino
            os.makedirs(carpeta_out, exist_ok=True)
            ruta_out = os.path.join(carpeta_out, nuevo)

            with Image.open(os.path.join(raiz, a)) as im:
                im = ImageOps.exif_transpose(im)
                if im.mode not in ("RGB", "L"):
                    im = im.convert("RGB")
                im.thumbnail((LADO_MAX, LADO_MAX), Image.LANCZOS)
                im.save(ruta_out, "JPEG", quality=CALIDAD, optimize=True, progressive=True)

            total += 1
            peso += os.path.getsize(ruta_out)
            print(f"  ✓ {rel}/{a}  →  {nuevo}")

    print(f"\n{total} fotos preparadas · {peso/1024/1024:.1f} MB en copias web")
    print("Sube la carpeta resultante como fotos/ al repositorio.")


if __name__ == "__main__":
    main()
