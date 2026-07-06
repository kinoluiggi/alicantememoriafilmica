#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Describidor de fotos — Alicante Memoria Fílmica
Manda al modelo de visión (Groq / Llama 4 Scout, el mismo de FilmoLens)
las fotos SIN título del catálogo y genera propuestas de identificación
en fotos_meta.json. Nada entra al sitio sin tu revisión: cada propuesta
nace con "aprobado": false y solo las aprobadas se fusionan al catálogo.

Uso:
    export GROQ_API_KEY="gsk_..."
    python3 describir_fotos.py            # solo fotos sin identificar
    python3 describir_fotos.py --todas    # todas las fotos
    python3 describir_fotos.py --worker https://tu-worker.workers.dev/lens

Flujo:
    1. correr este script  →  fotos_meta.json con propuestas
    2. revisar el JSON: corregir títulos/años y poner "aprobado": true
    3. correr actualizar_catalogo.py  →  las aprobadas entran al sitio
"""
import base64
import io
import json
import os
import re
import sys
import time
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
CATALOGO = os.path.join(AQUI, "catalog.json")
META = os.path.join(AQUI, "fotos_meta.json")

MODELO = "meta-llama/llama-4-scout-17b-16e-instruct"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
LADO_ENVIO = 1024  # px, suficiente para identificar y barato en tokens

PROMPT = """Eres archivista de un archivo fotográfico histórico de la provincia de Alicante (España).
Analiza esta imagen antigua (fotografía, postal o grabado) e identifícala.

Lugares frecuentes del acervo: la Explanada de España y su pavimento de ondas, el castillo de Santa Bárbara sobre el monte Benacantil, el puerto y sus muelles, la playa del Postiguet, el Mercado Central, el Teatro Principal, la Rambla, el barrio de Santa Cruz, el Raval Roig, el paseo de Canalejas, el ayuntamiento barroco, y municipios como Elche (palmeral), Alcoy, Orihuela, Villena, Denia o Tabarca.

Para datar, fíjate en: vestimenta, vehículos (tranvías, carros, coches), mobiliario urbano, edificios presentes o ausentes, técnica de la imagen (grabado, albúmina, postal fotomecánica, gelatina).

Responde SOLO con un objeto JSON, sin markdown ni texto adicional:
{
 "titulo": "título breve de catálogo, en español, sin año",
 "descripcion": "1-2 frases: qué se ve y qué permite identificarlo",
 "lugar": "lugar identificado o null si no es seguro",
 "ano_estimado": 1925,
 "decada_estimada": "1920s",
 "confianza": "alta|media|baja",
 "pistas_datacion": "en qué te basas para la fecha"
}
Si no reconoces el lugar con seguridad, dilo en la descripción y usa confianza baja. No inventes."""


def cargar_imagen_b64(ruta):
    try:
        from PIL import Image
        with Image.open(ruta) as im:
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            im.thumbnail((LADO_ENVIO, LADO_ENVIO))
            buf = io.BytesIO()
            im.convert("RGB").save(buf, "JPEG", quality=85)
            return base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        with open(ruta, "rb") as f:
            return base64.b64encode(f.read()).decode()


def consultar(b64, worker=None, api_key=None):
    cuerpo = {
        "model": MODELO,
        "temperature": 0.2,
        "max_tokens": 500,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        }],
    }
    url = worker or GROQ_URL
    req = urllib.request.Request(url, data=json.dumps(cuerpo).encode(),
                                 headers={"Content-Type": "application/json"})
    if not worker:
        req.add_header("Authorization", f"Bearer {api_key}")
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read())
    texto = data["choices"][0]["message"]["content"]
    texto = re.sub(r"```json|```", "", texto).strip()
    m = re.search(r"\{.*\}", texto, re.S)
    return json.loads(m.group(0)) if m else None


def main():
    todas = "--todas" in sys.argv
    worker = None
    if "--worker" in sys.argv:
        worker = sys.argv[sys.argv.index("--worker") + 1]
    api_key = os.environ.get("GROQ_API_KEY")
    if not worker and not api_key:
        sys.exit("Falta GROQ_API_KEY en el entorno, o usa --worker <url>")

    with open(CATALOGO, encoding="utf-8") as f:
        catalogo = json.load(f)

    meta = []
    if os.path.exists(META):
        with open(META, encoding="utf-8") as f:
            meta = json.load(f)
    ya = {m["file"] for m in meta}

    candidatas = [p for p in catalogo if p.get("source") == "foto"
                  and p["file"] not in ya
                  and (todas or not p.get("title"))]
    if not candidatas:
        print("Nada pendiente: todas las fotos tienen título o ya fueron propuestas.")
        return
    print(f"{len(candidatas)} fotos por identificar…\n")

    for i, p in enumerate(candidatas, 1):
        ruta = os.path.join(AQUI, p["file"])
        if not os.path.exists(ruta):
            print(f"  ! no existe {p['file']}, la salto")
            continue
        print(f"[{i}/{len(candidatas)}] {p['file']}")
        try:
            r = consultar(cargar_imagen_b64(ruta), worker, api_key)
        except Exception as ex:
            print(f"  ! error: {ex} — guardo lo que llevo y sigo")
            r = None
        if r:
            propuesta = {
                "file": p["file"],
                "aprobado": False,
                "title": (r.get("titulo") or "").strip(),
                "description": (r.get("descripcion") or "").strip(),
                "year": r.get("ano_estimado"),
                "circa": True,
                "_lugar": r.get("lugar"),
                "_confianza": r.get("confianza"),
                "_pistas": r.get("pistas_datacion"),
            }
            meta.append(propuesta)
            print(f"    → {propuesta['title']}  (c. {propuesta['year']}, "
                  f"confianza {propuesta['_confianza']})")
        # guardar en cada paso: si algo truena, no se pierde el avance
        with open(META, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=1)
        time.sleep(2.5)  # respeto al rate limit gratuito de Groq

    print(f"\n✓ propuestas en {META}")
    print("Revísalas, corrige lo necesario y cambia \"aprobado\": false → true")
    print("en las que quieras publicar. Luego corre actualizar_catalogo.py.")


if __name__ == "__main__":
    main()
