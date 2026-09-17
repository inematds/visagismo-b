#!/usr/bin/env python3
"""
Medicion del PERFIL. Es la mitad del rostro que el frontal no puede ver.

Aqui viven las metricas que de frente son imposibles o poco fiables:
el angulo gonial real, la proyeccion de la nariz, el angulo nasolabial,
la convexidad facial y la posicion de los labios respecto a la linea E.

Son justo las que deciden si a alguien le favorece el pelo hacia atras,
cuanta nuca dejar, o si la barba tiene que construir menton.

╔══════════════════════════════════════════════════════════════════════╗
║  ESTADO: EXPERIMENTAL. NO USAR SUS NUMEROS EN EL INFORME.            ║
╚══════════════════════════════════════════════════════════════════════╝

Probado el 2026-08-31 con dos vias, las dos insuficientes:

VIA A — medir sobre la foto de perfil.
    MediaPipe detecta (478 landmarks) pero AJUSTA MAL la malla: los puntos
    que de frente son laterales colapsan hacia el centro visible. Verificado
    dibujandolos: `pronasale` cae en el puente de la nariz en vez de la punta,
    `menton` y `pogonion` dentro de la barba, `gonion` en mitad de la mejilla
    y `tragus` sin tocar la oreja. Los angulos que salen de ahi son basura
    (daba "nariz poco proyectada" en un perfil de nariz prominente).

VIA B — derivar el perfil de la coordenada Z del FRONTAL.
    El ORDEN de profundidades si es anatomicamente correcto y esta verificado:
        punta nariz < glabela < frente < nasion < subnasal < labios
                    < pogonion < menton < gonion < tragus
    Pero la ESCALA de Z esta comprimida: la profundidad facial sale 0,69 veces
    la anchura bizigomatica cuando la referencia antropometrica es ~0,93.
    Con la cara aplastada, todos los angulos salen mas planos de lo real.

    Se probo un factor de calibracion. Se descarto: mover ese factor mueve
    todos los angulos a la vez, y sin una medida real de referencia (un calibre
    sobre una cara) es ajustar un parametro libre hasta que los numeros queden
    bonitos. Eso no es medir.

QUE SI SE PUEDE USAR HOY:
  * El ORDEN de profundidades, para afirmaciones relativas y comparativas
    ("el menton queda por detras del labio inferior"), nunca en grados.
  * La foto de perfil como ENTRADA de la simulacion y como material visual.

PARA CERRARLO HACE FALTA una de estas tres:
  1. Calibrar con medidas reales de calibre sobre 10-15 caras.
  2. Un modelo de reconstruccion 3D con escala metrica (3DDFA, DECA, FaceScape).
  3. Una referencia de escala en la propia foto (una tarjeta junto a la cara).
"""

import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from analiza_rostro import detectar, _dist, _angulo, _json_safe  # noqa: E402

# Puntos del contorno visible en una vista lateral.
PT_PERFIL = {
    "frente_alta": 10,
    "glabela": 9,
    "nasion": 168,
    "pronasale": 1,        # punta de la nariz
    "subnasale": 2,        # base de la nariz
    "labio_sup": 0,        # borde superior del labio
    "stomion": 13,
    "labio_inf": 17,
    "pogonion": 199,       # punto mas anterior del menton
    "menton": 152,         # punto mas bajo
    "gonion_der": 58,
    "gonion_izq": 288,
    "tragus_der": 234,     # referencia auricular
    "tragus_izq": 454,
}

# Rangos de normalidad, tomados de la antropometria facial clasica.
CANON_PERFIL = {
    "nasofrontal": (115.0, 135.0),
    "nasolabial": (90.0, 110.0),
    "convexidad": (165.0, 175.0),
    "gonial": (118.0, 132.0),
    "proyeccion_nasal": (0.50, 0.62),
}


def _xy(lm, idx, w, h):
    p = lm[idx]
    return np.array([p.x * w, p.y * h])


def detectar_perfil(ruta):
    """Como el frontal, pero quedandose con los puntos utiles de lado."""
    img, _, lm, (w, h) = detectar(ruta)
    P = {k: _xy(lm, i, w, h) for k, i in PT_PERFIL.items()}

    # Hacia donde mira: el lado con la nariz por delante del menton.
    mira_derecha = P["pronasale"][0] > P["menton"][0]
    P["gonion"] = P["gonion_izq"] if mira_derecha else P["gonion_der"]
    P["tragus"] = P["tragus_izq"] if mira_derecha else P["tragus_der"]
    return img, P, mira_derecha


def medir_perfil(P):
    """Los cinco angulos y ratios que solo se ven de lado."""
    nasofrontal = _angulo(P["glabela"], P["nasion"], P["pronasale"])
    nasolabial = _angulo(P["pronasale"], P["subnasale"], P["labio_sup"])
    convexidad = _angulo(P["glabela"], P["subnasale"], P["pogonion"])
    gonial = _angulo(P["tragus"], P["gonion"], P["menton"])

    # Proyeccion nasal (ratio de Goode): cuanto sobresale la punta respecto
    # a la longitud del dorso. Se mide en horizontal desde la raiz nasal.
    dorso = _dist(P["nasion"], P["pronasale"])
    salida = abs(P["pronasale"][0] - P["subnasale"][0])
    proyeccion = salida / dorso if dorso else 0.0

    # Linea E de Ricketts: recta de la punta de la nariz al punto mas
    # anterior del menton. Los labios deben quedar ligeramente por detras.
    a, b = P["pronasale"], P["pogonion"]
    def distancia_a_E(p):
        """Positivo = por delante de la linea (labio adelantado)."""
        v = b - a
        n = np.array([v[1], -v[0]])
        n = n / (np.linalg.norm(n) or 1)
        d = float(np.dot(p - a, n))
        # El signo depende de hacia donde mira; se normaliza con el menton.
        return d

    escala = _dist(P["nasion"], P["menton"]) or 1.0
    e_sup = 100 * distancia_a_E(P["labio_sup"]) / escala
    e_inf = 100 * distancia_a_E(P["labio_inf"]) / escala

    return {
        "angulos": {
            "nasofrontal": nasofrontal,
            "nasolabial": nasolabial,
            "convexidad": convexidad,
            "gonial": gonial,
        },
        "ratios": {"proyeccion_nasal": proyeccion},
        "linea_e": {"labio_superior_pct": e_sup, "labio_inferior_pct": e_inf},
        "confianza": "media",
    }


def clasificar_perfil(mp):
    """Veredictos con su numero al lado. Nunca un adjetivo suelto."""
    a = mp["angulos"]
    out = {}

    v = a["convexidad"]
    lo, hi = CANON_PERFIL["convexidad"]
    out["convexidad"] = {
        "valor": round(v, 1), "canon": f"{lo:.0f}–{hi:.0f}°",
        "veredicto": ("perfil recto" if lo <= v <= hi else
                      "perfil convexo" if v < lo else "perfil cóncavo"),
        "porque": f"ángulo glabela–subnasal–mentón de {v:.0f}°",
    }

    v = a["nasolabial"]
    lo, hi = CANON_PERFIL["nasolabial"]
    out["nasolabial"] = {
        "valor": round(v, 1), "canon": f"{lo:.0f}–{hi:.0f}°",
        "veredicto": ("dentro del canon" if lo <= v <= hi else
                      "punta nasal descendida" if v < lo else "punta nasal elevada"),
        "porque": f"ángulo nasolabial de {v:.0f}°",
    }

    v = a["gonial"]
    lo, hi = CANON_PERFIL["gonial"]
    out["gonial"] = {
        "valor": round(v, 1), "canon": f"{lo:.0f}–{hi:.0f}°",
        "veredicto": ("mandíbula bien angulada" if lo <= v <= hi else
                      "mandíbula muy marcada" if v < lo else "mandíbula poco angulada"),
        "porque": f"ángulo gonial de {v:.0f}° medido de perfil",
    }

    v = a["nasofrontal"]
    lo, hi = CANON_PERFIL["nasofrontal"]
    out["nasofrontal"] = {
        "valor": round(v, 1), "canon": f"{lo:.0f}–{hi:.0f}°",
        "veredicto": ("transición frente-nariz suave" if lo <= v <= hi else
                      "raíz nasal marcada" if v < lo else "raíz nasal plana"),
        "porque": f"ángulo nasofrontal de {v:.0f}°",
    }

    v = mp["ratios"]["proyeccion_nasal"]
    lo, hi = CANON_PERFIL["proyeccion_nasal"]
    out["proyeccion_nasal"] = {
        "valor": round(v, 2), "canon": f"{lo:.2f}–{hi:.2f}",
        "veredicto": ("proyección proporcionada" if lo <= v <= hi else
                      "nariz poco proyectada" if v < lo else "nariz muy proyectada"),
        "porque": f"la punta sobresale {v:.2f} veces la longitud del dorso",
    }
    return out


# ---------------------------------------------------------------------------
# Geometria para el SVG del informe
# ---------------------------------------------------------------------------
MARGEN_P = {"arriba": 0.55, "abajo": 0.40, "lados": 0.30}


def recortar_perfil(img, P):
    h, w = img.shape[:2]
    alto = abs(P["menton"][1] - P["frente_alta"][1]) or 1
    xs = [P[k][0] for k in ("pronasale", "gonion", "menton", "glabela", "tragus")]
    x0 = min(xs) - alto * MARGEN_P["lados"]
    x1 = max(xs) + alto * MARGEN_P["lados"]
    y0 = P["frente_alta"][1] - alto * MARGEN_P["arriba"]
    y1 = P["menton"][1] + alto * MARGEN_P["abajo"]
    x0, y0 = max(0, int(x0)), max(0, int(y0))
    x1, y1 = min(w, int(x1)), min(h, int(y1))
    return img[y0:y1, x0:x1], (x0, y0)


def geometria_perfil(P, mp, off):
    ox, oy = off

    def p(k):
        return [round(float(P[k][0] - ox), 1), round(float(P[k][1] - oy), 1)]

    a = mp["angulos"]
    return {
        "linea_e": [
            {"tipo": "linea", "a": p("pronasale"), "b": p("pogonion"),
             "etiqueta": "línea E"},
        ],
        "angulos": [
            {"tipo": "polilinea", "puntos": [p("glabela"), p("nasion"), p("pronasale")],
             "etiqueta": f"nasofrontal {a['nasofrontal']:.0f}°", "vertice": p("nasion")},
            {"tipo": "polilinea", "puntos": [p("pronasale"), p("subnasale"), p("labio_sup")],
             "etiqueta": f"nasolabial {a['nasolabial']:.0f}°", "vertice": p("subnasale")},
            {"tipo": "polilinea", "puntos": [p("tragus"), p("gonion"), p("menton")],
             "etiqueta": f"gonial {a['gonial']:.0f}°", "vertice": p("gonion")},
        ],
        "convexidad": [
            {"tipo": "polilinea", "puntos": [p("glabela"), p("subnasale"), p("pogonion")],
             "etiqueta": f"convexidad {a['convexidad']:.0f}°", "vertice": p("subnasale")},
        ],
    }


def main():
    if len(sys.argv) < 2:
        raise SystemExit("uso: analiza_perfil.py <perfil.png> [salida_dir]")
    src = Path(sys.argv[1])
    salida = Path(sys.argv[2]) if len(sys.argv) > 2 else src.parent
    salida.mkdir(parents=True, exist_ok=True)

    img, P, mira_derecha = detectar_perfil(src)
    mp = medir_perfil(P)
    cp = clasificar_perfil(mp)
    recorte, off = recortar_perfil(img, P)
    cv2.imwrite(str(salida / "perfil-encuadrado.jpg"), recorte,
                [cv2.IMWRITE_JPEG_QUALITY, 88])

    (salida / "perfil.json").write_text(json.dumps(
        {"mira_derecha": mira_derecha, "medidas": mp, "clasificacion": cp,
         "capas": geometria_perfil(P, mp, off)},
        indent=2, ensure_ascii=False, default=_json_safe), encoding="utf-8")

    print(f"mira a la {'derecha' if mira_derecha else 'izquierda'} · "
          f"recorte {recorte.shape[1]}x{recorte.shape[0]}")
    for k, v in cp.items():
        print(f"  {k:18} {v['valor']:>7} (canon {v['canon']:>12})  {v['veredicto']}")


if __name__ == "__main__":
    main()
