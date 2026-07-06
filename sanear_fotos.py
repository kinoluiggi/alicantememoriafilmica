#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Saneador de fotos — Alicante Memoria Fílmica
Corre esto DESPUÉS de copiar fotos nuevas a fotos/<decada>/ y ANTES del push.
Renombra los archivos a nombres seguros para la web y vuelca la información
de los nombres originales (título, año, créditos) a fotos_meta.json.
Las fotos ya saneadas se dejan en paz; puedes correrlo cuantas veces quieras.

Uso:  python3 sanear_fotos.py
"""
import os, re, json, unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
META = os.path.join(AQUI, "fotos_meta.json")

RE_ANO = re.compile(r"(?<!\d)(1[5-9]\d{2}|20[0-2]\d)(?!\d)")
RE_RANGO = re.compile(r"(1[5-9]\d{2})\s*[-\u2013]\s*\d{2,4}")
RE_CIRCA = re.compile(r"hacia|c\.\s*\d|finales|principios|siglo|años", re.I)
RE_SEGURO = re.compile(r"^(fb_[\d_]+|\d{4}_[a-z0-9_]*|[a-z0-9_]+)(_\d+)?\.jpg$")
BOILER = re.compile(r"gigapixel|high\s*fidelity|v\d(\-\d+x)?|\b2x\b|de\s+tamaño\s+grande|\bcopia\b|\bimg\b|\bdsc\b|\bn\b", re.I)

def limpiar(t):
    t = re.sub(r"\d{7,}", " ", t)
    t = BOILER.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip(" ,._-\u2013")

def slug(t, maxw=7):
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    palabras = re.sub(r"[^\w\s]", " ", t).split()[:maxw]
    return "_".join(p.lower() for p in palabras)[:64]

def main():
    meta = []
    if os.path.exists(META):
        with open(META, encoding="utf-8") as f:
            meta = json.load(f)
    ya = {m["file"] for m in meta}
    usados = set()
    for raiz, _d, archivos in os.walk(os.path.join(AQUI, "fotos")):
        for a in archivos:
            usados.add(os.path.join(raiz, a))

    nuevos = renombrados = 0
    for raiz, _d, archivos in os.walk(os.path.join(AQUI, "fotos")):
        for a in sorted(archivos):
            base, ext = os.path.splitext(a)
            if ext.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
                continue
            rel = os.path.relpath(os.path.join(raiz, a), AQUI).replace(os.sep, "/")
            if RE_SEGURO.match(a):
                continue  # ya saneada en una corrida anterior

            original = unicodedata.normalize("NFC", base)
            original = re.sub(r"\s+", " ", original.replace("_", " ")).strip(" ,._")

            m = RE_RANGO.search(original) or RE_ANO.search(original)
            ano = int(m.group(1)) if m else None
            circa = bool(m and (RE_RANGO.search(original) or RE_CIRCA.search(original)))

            cuerpo = limpiar(RE_ANO.sub(" ", original))
            cuerpo = re.sub(r"\(\s*Año\s*\)", "", cuerpo, flags=re.I)
            cuerpo = re.sub(r"(hacia\s+el\s+año|hacia)\s*[\.,]?\s*$", "", cuerpo, flags=re.I)
            cuerpo = re.sub(r"\s+", " ", cuerpo).strip(" ,.()-\u2013")

            if len(re.sub(r"[\W\d]", "", cuerpo)) <= 3:
                titulo, desc = "", ""
                nuevo = (f"{ano}_foto" if ano else "fb_" + (re.findall(r"\d+", base) or ["x"])[0][:9]) + ".jpg"
            else:
                partes = re.split(r"\.\s+", cuerpo, maxsplit=1)
                titulo = partes[0].strip(" ,.")
                desc = partes[1].strip(" ,.") if len(partes) > 1 else ""
                nuevo = ((str(ano) + "_") if ano else "") + slug(titulo) + ".jpg"

            n, cand = 1, nuevo
            while os.path.join(raiz, cand) in usados and cand != a:
                n += 1
                cand = nuevo.replace(".jpg", f"_{n}.jpg")
            nuevo = cand
            usados.add(os.path.join(raiz, nuevo))
            if a != nuevo:
                os.rename(os.path.join(raiz, a), os.path.join(raiz, nuevo))
                renombrados += 1
            if titulo:
                rel_nuevo = os.path.relpath(os.path.join(raiz, nuevo), AQUI).replace(os.sep, "/")
                if rel_nuevo not in ya:
                    e = {"file": rel_nuevo, "aprobado": True,
                         "title": titulo, "year": ano, "circa": circa}
                    if desc:
                        e["description"] = desc
                    meta.append(e)
                    ya.add(rel_nuevo)
                    nuevos += 1

    with open(META, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(f"✓ {renombrados} archivos renombrados, {nuevos} fichas nuevas en fotos_meta.json")
    print("Ahora: commit + push, y corre el workflow en Actions (o python3 actualizar_catalogo.py local).")

if __name__ == "__main__":
    main()
