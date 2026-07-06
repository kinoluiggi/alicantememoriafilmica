#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Actualizador de catálogo — Alicante Memoria Fílmica
Lee fuentes.json, barre canales/playlists de YouTube con yt-dlp,
suma entradas manuales (YouTube sueltos, Archive.org, enlaces),
detecta el año de filmación en los títulos y genera catalog.json.

Uso:  python3 actualizar_catalogo.py
Requiere: pip install yt-dlp
"""
import json
import os
import re
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
FUENTES = os.path.join(AQUI, "fuentes.json")
SALIDA = os.path.join(AQUI, "catalog.json")
YTDLP_EXTRA = os.environ.get("YTDLP_EXTRA", "").split()

# ---------- detección de año ----------
RE_CIRCA = re.compile(r"\(\s*c\.?\s*(\d{4})\s*\)")
RE_PAREN = re.compile(r"\((\d{4})\s*\)")
RE_SUELTO = re.compile(r"\b(18\d{2}|19\d{2}|20[0-2]\d)\b")

def detectar_ano(titulo):
    """Devuelve (año, circa) o (None, False)."""
    m = RE_CIRCA.search(titulo)
    if m:
        return int(m.group(1)), True
    m = RE_PAREN.search(titulo)
    if m:
        return int(m.group(1)), False
    m = RE_SUELTO.search(titulo)
    if m:
        return int(m.group(1)), False
    return None, False

# ---------- fuentes ----------
def barrer_youtube(url):
    """Lista plana de un canal o playlist. Devuelve [] si falla."""
    cmd = ["yt-dlp", "--flat-playlist", "--dump-single-json", url] + YTDLP_EXTRA
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if out.returncode != 0:
            print(f"  ! fallo yt-dlp en {url}: {out.stderr.strip()[:200]}", file=sys.stderr)
            return []
        data = json.loads(out.stdout)
        entradas = []
        for e in data.get("entries") or []:
            if not e or not e.get("id"):
                continue
            entradas.append({
                "id": e["id"],
                "title": (e.get("title") or "").strip(),
                "source": "youtube",
            })
        return entradas
    except Exception as ex:
        print(f"  ! excepción en {url}: {ex}", file=sys.stderr)
        return []

def normalizar_manual(entrada):
    """Entradas manuales de fuentes.json → formato del catálogo."""
    e = dict(entrada)
    e.setdefault("source", "link")
    e["title"] = (e.get("title") or "").strip()
    return e

def main():
    with open(FUENTES, encoding="utf-8") as f:
        fuentes = json.load(f)

    piezas = []

    for url in fuentes.get("youtube", []):
        print(f"→ barriendo {url}")
        piezas += barrer_youtube(url)

    for entrada in fuentes.get("manual", []):
        if entrada.get("activo", True):
            piezas.append(normalizar_manual(entrada))

    # Guardia: si todo falló, no tocar el catálogo existente
    if not piezas:
        print("!! Ninguna fuente devolvió piezas. Se conserva el catálogo anterior.", file=sys.stderr)
        sys.exit(1)

    # deduplicar por (source, id) o url
    vistos, unicos = set(), []
    for p in piezas:
        clave = (p.get("source"), p.get("id") or p.get("url"))
        if clave in vistos:
            continue
        vistos.add(clave)
        unicos.append(p)

    # año
    sin_ano = []
    for p in unicos:
        if "year" not in p or p["year"] in (None, ""):
            y, circa = detectar_ano(p["title"])
            p["year"] = y
            p["circa"] = circa
        if not p["year"]:
            sin_ano.append(p["title"])

    unicos.sort(key=lambda x: (x["year"] is None, x["year"] or 0, x["title"]))

    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(unicos, f, ensure_ascii=False, indent=1)

    # re-embeber en index.html si existe
    index = os.path.join(AQUI, "index.html")
    if os.path.exists(index):
        with open(index, encoding="utf-8") as f:
            html = f.read()
        nuevo = re.sub(
            r"/\*CATALOGO\*/.*?/\*FIN\*/",
            "/*CATALOGO*/" + json.dumps(unicos, ensure_ascii=False) + "/*FIN*/",
            html, flags=re.S,
        )
        with open(index, "w", encoding="utf-8") as f:
            f.write(nuevo)
        print("✓ catálogo re-embebido en index.html")

    con_ano = [p for p in unicos if p["year"]]
    print(f"✓ {len(unicos)} piezas ({len(con_ano)} datadas, {len(sin_ano)} sin datar)")
    if con_ano:
        print(f"  rango: {con_ano[0]['year']}–{con_ano[-1]['year']}")
    if sin_ano:
        print("  Sin año detectado (puedes fijarlo a mano en fuentes.json → manual):")
        for t in sin_ano:
            print(f"   · {t}")

if __name__ == "__main__":
    main()
