#!/usr/bin/env python3
"""
Exporta la geometria de las lineas de visagismo como JSON vectorial,
en lugar de quemarlas sobre un PNG.

Sirve para que el informe HTML pueda dibujarlas como SVG: animarlas
trazo a trazo, encenderlas y apagarlas por capas, y mantenerlas nitidas
a cualquier tamano.

Recorta ademas la foto a un encuadre centrado en el rostro y devuelve
las coordenadas ya referidas a ese recorte.

uso: exporta_geometria.py <frontal.png> <salida_dir>
"""

import base64
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from analiza_rostro import detectar, medir, clasificar, _json_safe  # noqa: E402

# Margen alrededor del rostro al recortar, en fracciones de la anchura facial.
MARGEN = {"arriba": 0.72, "abajo": 0.46, "lados": 0.42}


def recortar(img, P, m):
    """Encuadre centrado en el rostro. Devuelve la imagen y el desplazamiento."""
    h, w = img.shape[:2]
    ancho_facial = m["px"]["bizigomatica"]
    x0 = min(P["zigomatico_der"][0], P["temporal_der"][0]) - ancho_facial * MARGEN["lados"]
    x1 = max(P["zigomatico_izq"][0], P["temporal_izq"][0]) + ancho_facial * MARGEN["lados"]
    y0 = m["_y_trichion"] - ancho_facial * MARGEN["arriba"]
    y1 = P["menton"][1] + ancho_facial * MARGEN["abajo"]

    x0, y0 = max(0, int(x0)), max(0, int(y0))
    x1, y1 = min(w, int(x1)), min(h, int(y1))
    return img[y0:y1, x0:x1], (x0, y0)


def geometria(P, m, off):
    """Todas las lineas, agrupadas por capa, en coordenadas del recorte."""
    ox, oy = off

    def p(punto):
        return [round(float(punto[0] - ox), 1), round(float(punto[1] - oy), 1)]

    def xy(x, y):
        return [round(float(x - ox), 1), round(float(y - oy), 1)]

    x_izq = min(P["zigomatico_der"][0], P["temporal_der"][0])
    x_der = max(P["zigomatico_izq"][0], P["temporal_izq"][0])
    ancho = x_der - x_izq
    x_a, x_b = x_izq - ancho * 0.07, x_der + ancho * 0.07

    # --- Tercios: cuatro horizontales ---
    filas = [
        (m["_y_trichion"], "trichion", m["tercios_pct"]["superior"]),
        (P["glabela"][1], "glabela", m["tercios_pct"]["medio"]),
        (P["subnasale"][1], "subnasal", m["tercios_pct"]["inferior"]),
        (P["menton"][1], "menton", None),
    ]
    tercios = [
        {"tipo": "linea", "a": xy(x_a, y), "b": xy(x_b, y), "etiqueta": nom}
        for y, nom, _ in filas
    ]
    bandas = []
    for i in range(3):
        y_med = (filas[i][0] + filas[i + 1][0]) / 2
        bandas.append({
            "tipo": "valor", "pos": xy(x_a - ancho * 0.04, y_med),
            "texto": f"{filas[i][2]:.0f}%",
        })

    # --- Quintos: seis verticales + porcentaje de cada franja ---
    xs = sorted([
        P["zigomatico_der"][0], P["canto_ext_der"][0], P["canto_int_der"][0],
        P["canto_int_izq"][0], P["canto_ext_izq"][0], P["zigomatico_izq"][0],
    ])
    y_top, y_bot = P["temporal_der"][1], P["menton"][1]
    total = xs[-1] - xs[0]
    quintos = [
        {"tipo": "linea", "a": xy(x, y_top), "b": xy(x, y_bot)} for x in xs
    ]
    for i in range(5):
        pct = 100 * (xs[i + 1] - xs[i]) / total
        quintos.append({
            "tipo": "valor",
            "pos": xy((xs[i] + xs[i + 1]) / 2, y_top - (y_bot - y_top) * 0.045),
            "texto": f"{pct:.0f}%",
            "destacado": i == 2 and abs(pct - 20) > 2,
        })

    # --- Estructura: tres anchuras ---
    y_pomulo = (P["canto_ext_der"][1] + P["ala_nasal_der"][1]) / 2
    estructura = [
        {"tipo": "linea", "a": p(P["temporal_der"]), "b": p(P["temporal_izq"]),
         "etiqueta": "bitemporal", "valor": "87%"},
        {"tipo": "linea", "a": xy(P["zigomatico_der"][0], y_pomulo),
         "b": xy(P["zigomatico_izq"][0], y_pomulo),
         "etiqueta": "bizigomatica", "valor": "100%", "principal": True},
        {"tipo": "linea", "a": p(P["gonion_der"]), "b": p(P["gonion_izq"]),
         "etiqueta": "bigonial", "valor": "89%"},
    ]

    # --- Contorno mandibular ---
    contorno = [p(P[k]) for k in (
        "zigomatico_der", "gonion_der", "mandibula_med_der",
        "menton", "mandibula_med_izq", "gonion_izq", "zigomatico_izq")]

    # --- Eje de simetria ---
    cx = (P["zigomatico_der"][0] + P["zigomatico_izq"][0]) / 2
    eje = {"tipo": "linea", "a": xy(cx, m["_y_trichion"]), "b": xy(cx, P["menton"][1])}

    return {
        "eje": [eje],
        "estructura": estructura,
        "contorno": [{"tipo": "polilinea", "puntos": contorno}],
        "tercios": tercios + bandas,
        "quintos": quintos,
    }


def main():
    if len(sys.argv) < 3:
        raise SystemExit("uso: exporta_geometria.py <frontal.png> <salida_dir>")
    src, salida = Path(sys.argv[1]), Path(sys.argv[2])
    salida.mkdir(parents=True, exist_ok=True)

    img, P, _, _ = detectar(src)
    m = medir(P)
    c = clasificar(m)
    recorte, off = recortar(img, P, m)

    alto, ancho = recorte.shape[:2]
    jpg = salida / "rostro-encuadrado.jpg"
    cv2.imwrite(str(jpg), recorte, [cv2.IMWRITE_JPEG_QUALITY, 88])

    datos = {
        "imagen": {"ancho": ancho, "alto": alto,
                   "datauri": "data:image/jpeg;base64," +
                              base64.b64encode(jpg.read_bytes()).decode()},
        "capas": geometria(P, m, off),
        "clasificacion": c,
        "ratios": m["ratios"],
    }
    (salida / "geometria.json").write_text(
        json.dumps(datos, ensure_ascii=False, default=_json_safe), encoding="utf-8")

    print(f"recorte {ancho}x{alto} -> {jpg}")
    for capa, elems in datos["capas"].items():
        print(f"  {capa:12} {len(elems)} elementos")


if __name__ == "__main__":
    main()
