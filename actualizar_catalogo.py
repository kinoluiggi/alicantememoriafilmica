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
import unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
FUENTES = os.path.join(AQUI, "fuentes.json")
SALIDA = os.path.join(AQUI, "catalog.json")
YTDLP_EXTRA = os.environ.get("YTDLP_EXTRA", "").split()

# ---------- detección de año ----------
RE_CIRCA = re.compile(r"\(\s*c\.?\s*(\d{4})\s*\)")
RE_PAREN = re.compile(r"\((1[5-9]\d{2}|20[0-2]\d)\s*\)")
RE_SUELTO = re.compile(r"(?<!\d)(1[5-9]\d{2}|20[0-2]\d)(?!\d)")

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

# ---------- fototeca local ----------
EXT_FOTO = {".jpg", ".jpeg", ".png", ".webp"}
RE_CARPETA_DECADA = re.compile(r"^(1[5-9]|20)\d0s?$")
RE_CARPETA_RANGO = re.compile(r"^(1[5-9]\d{2})\s*[-_]\s*(1[5-9]\d{2}|20\d{2})$")

def es_nombre_basura(nombre):
    """detecta nombres tipo descarga de Facebook: 186513774_..._n"""
    limpio = re.sub(r"[\d_\-n]", "", nombre.lower())
    return len(limpio) <= 2

def barrer_fotos():
    """Barre la carpeta fotos/ del repositorio. Año desde el nombre
    (1926_paseo.jpg, c1935_balneario.jpg) o, en su defecto, la década
    de la carpeta contenedora (marcada como circa)."""
    base = os.path.join(AQUI, "fotos")
    if not os.path.isdir(base):
        return []
    piezas = []
    for raiz, _dirs, archivos in os.walk(base):
        carpeta = os.path.basename(raiz)
        for a in sorted(archivos):
            nombre, ext = os.path.splitext(a)
            if ext.lower() not in EXT_FOTO:
                continue
            year, circa, period = None, False, None
            m = re.match(r"^c\.?_?(1[5-9]\d{2}|20\d{2})", nombre)
            if m:
                year, circa = int(m.group(1)), True
            else:
                m = RE_SUELTO.search(nombre)
                if m:
                    year = int(m.group(1))
            if not year:
                if RE_CARPETA_DECADA.match(carpeta):
                    year, circa = int(carpeta[:4]), True
                else:
                    mr = RE_CARPETA_RANGO.match(carpeta)
                    if mr:
                        period = f"{mr.group(1)}\u2013{mr.group(2)}"
                    else:
                        # carpeta temática: "Castillo... Años 1936-1937. Coleccion Loty"
                        my = RE_SUELTO.search(carpeta)
                        if my:
                            year, circa = int(my.group(1)), True
            if es_nombre_basura(nombre):
                titulo = ""
            else:
                titulo = RE_SUELTO.sub("", re.sub(r"^c\.?_?", "", nombre))
                titulo = titulo.replace("_", " ").replace("-", " ")
                titulo = re.sub(r"\s+", " ", titulo).strip(" ,.").strip()
                if titulo and titulo == titulo.lower():
                    titulo = titulo.capitalize()
            pieza = {
                "source": "foto",
                "file": os.path.relpath(os.path.join(raiz, a), AQUI).replace(os.sep, "/"),
                "title": titulo,
                "year": year,
                "circa": circa,
            }
            if period:
                pieza["period"] = period
            piezas.append(pieza)
    # fusionar metadatos curados (fotos_meta.json), si existen
    meta_path = os.path.join(AQUI, "fotos_meta.json")
    if os.path.exists(meta_path):
        with open(meta_path, encoding="utf-8") as f:
            meta = {m["file"]: m for m in json.load(f) if m.get("aprobado")}
        for p in piezas:
            m = meta.get(p["file"])
            if not m:
                continue
            for campo in ("title", "year", "circa", "period", "description", "master"):
                if m.get(campo) not in (None, ""):
                    p[campo] = m[campo]
    return piezas

EXT_MUSICA = {".mp3", ".ogg", ".m4a"}

def barrer_musica():
    """Barre la carpeta musica/ para la banda sonora de la proyección."""
    base = os.path.join(AQUI, "musica")
    if not os.path.isdir(base):
        return []
    pistas = []
    for a in sorted(os.listdir(base)):
        nombre, ext = os.path.splitext(a)
        if ext.lower() not in EXT_MUSICA:
            continue
        titulo = unicodedata.normalize("NFC", nombre)
        titulo = re.sub(r"^\d+\s+", "", titulo)          # número de pista
        titulo = re.sub(r"\(cover\)", "", titulo, flags=re.I)
        titulo = re.sub(r"\s+\d{2}$", "", titulo)         # número de toma
        titulo = titulo.replace("_ ", ": ").replace("_", " ")
        titulo = re.sub(r"\s+", " ", titulo).strip(" ,.-")
        pistas.append({"file": f"musica/{a}", "title": titulo})
    return pistas


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

    fotos = barrer_fotos()
    if fotos:
        print(f"→ fototeca local: {len(fotos)} fotos")
        piezas += fotos

    # Guardia: si todo falló, no tocar el catálogo existente
    if not piezas:
        print("!! Ninguna fuente devolvió piezas. Se conserva el catálogo anterior.", file=sys.stderr)
        sys.exit(1)

    # deduplicar por (source, id) o ruta/url.
    # Si un id aparece en el canal y también como entrada manual, la manual
    # tiene prioridad (permite fijar año/título a un video del canal propio).
    por_clave = {}
    orden = []
    for p in piezas:
        clave = (p.get("source"), p.get("id") or p.get("file") or p.get("url"))
        if clave not in por_clave:
            por_clave[clave] = p
            orden.append(clave)
        else:
            prev = por_clave[clave]
            # la entrada con año explícito (típicamente la manual) gana;
            # si ambas o ninguna, se conserva la primera
            if p.get("year") and not prev.get("year"):
                por_clave[clave] = p
            elif p.get("year") and prev.get("year") and len(p.get("title","")) > len(prev.get("title","")):
                por_clave[clave] = p
    unicos = [por_clave[c] for c in orden]

    # año
    sin_ano = []
    for p in unicos:
        if "year" not in p or p["year"] in (None, ""):
            y, circa = detectar_ano(p["title"])
            p["year"] = y
            p["circa"] = circa
        if not p["year"] and not p.get("period"):
            sin_ano.append(p["title"] or p.get("file", "?"))

    unicos.sort(key=lambda x: (x["year"] is None, x["year"] or 0, x["title"]))

    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(unicos, f, ensure_ascii=False, indent=1)

    musica = barrer_musica()
    if musica:
        print(f"→ banda sonora: {len(musica)} pistas")

    # re-embeber en las páginas que llevan el catálogo dentro
    for pagina in ("index.html", "fotos.html"):
        ruta = os.path.join(AQUI, pagina)
        if not os.path.exists(ruta):
            continue
        with open(ruta, encoding="utf-8") as f:
            html = f.read()
        nuevo = re.sub(
            r"/\*CATALOGO\*/.*?/\*FIN\*/",
            "/*CATALOGO*/" + json.dumps(unicos, ensure_ascii=False) + "/*FIN*/",
            html, flags=re.S,
        )
        if pagina == "fotos.html":
            nuevo = re.sub(
                r"/\*MUSICA\*/.*?/\*FIN_MUSICA\*/",
                "/*MUSICA*/" + json.dumps(musica, ensure_ascii=False) + "/*FIN_MUSICA*/",
                nuevo, flags=re.S,
            )
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(nuevo)
        print(f"✓ catálogo re-embebido en {pagina}")

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
