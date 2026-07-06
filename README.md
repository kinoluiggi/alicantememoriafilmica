# Alicante, Memoria Fílmica

**Línea de tiempo de la memoria audiovisual de la provincia de Alicante, 1905–1966.**

🎞️ **Sitio:** https://kinoluiggi.github.io/alicantememoriafilmica/
📺 **Canal:** https://www.youtube.com/@alicantememoriafilmica

Noticiarios, documentales, rodajes de paso y actualidades filmadas en la provincia de Alicante, reunidas y ordenadas **por año de filmación** — no de publicación. De la visita de Alfonso XIII al puerto en 1905 a las cámaras extranjeras de los años sesenta, pasando por la Guerra Civil, las Hogueras de San Juan, la huerta, la fábrica y la costa.

Proyecto de recuperación de la memoria fílmica alicantina iniciado en 2020, hermano de [Naranjas de Hiroshima](https://www.naranjasdehiroshima.com).

## Cómo funciona

El sitio es una sola página estática (`index.html`) con el catálogo embebido. No requiere servidor ni API keys.

- **`fuentes.json`** — centro de control del catálogo. En `"youtube"` van canales o playlists completas; en `"manual"` se agregan piezas sueltas: videos de YouTube de otros canales, ítems de Archive.org (`"source": "archive"`) o enlaces externos sin embed (`"source": "link"`).
- **`actualizar_catalogo.py`** — barre todas las fuentes con [yt-dlp](https://github.com/yt-dlp/yt-dlp), detecta el año de filmación en los títulos (soporta `(1928)`, `(c. 1935)` y años sueltos), deduplica, genera `catalog.json` y lo re-embebe en `index.html`.
- **`.github/workflows/actualizar.yml`** — cron semanal (lunes) que corre el script y publica los cambios solo si hay piezas nuevas.

### Actualizar a mano

```bash
pip install yt-dlp
python3 actualizar_catalogo.py
```

Las piezas cuyo título no incluya un año detectable se listan al final de la ejecución y caen en la sección **Sin datar** del sitio; su año puede fijarse a mano en `fuentes.json → manual`.

## Convención de títulos

Para que una pieza nueva se date sola, basta con incluir el año entre paréntesis al final del título del video:

```
Alicante. Hogueras de San Juan (1950)
Inauguración del balneario de Aguas de Busot. Alicante (c. 1935)
```

## Derechos

Las piezas se reproducen desde sus fuentes originales mediante embeds; los derechos pertenecen a sus titulares. Los materiales se reúnen aquí con fines de documentación, investigación y divulgación de la memoria audiovisual alicantina.
