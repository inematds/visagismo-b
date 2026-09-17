#!/usr/bin/env python3
"""
Motor de medicion facial para analisis de visagismo.

Entrada : foto frontal (obligatoria) + foto de perfil (opcional)
Salida  : JSON con medidas normalizadas + PNG con el overlay de lineas

No decide el corte de pelo. Solo MIDE y CLASIFICA con reglas explicitas,
para que el texto del informe se apoye en numeros y no en adjetivos.
Cada metrica lleva su nivel de confianza: el informe solo debe afirmar
lo que aqui viene marcado como fiable.
"""

import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np
import mediapipe as mp

# ---------------------------------------------------------------------------
# Indices de MediaPipe FaceMesh (468 pts) usados como puntos antropometricos.
# Nombre anatomico -> indice. Documentado porque no son evidentes.
# ---------------------------------------------------------------------------
PT = {
    "frente_alta": 10,        # limite superior del mesh (~trichion, ver nota)
    "glabela": 9,             # entrecejo
    "nasion": 168,            # raiz nasal
    "pronasale": 1,           # punta de la nariz
    "subnasale": 2,           # base de la nariz
    "stomion": 13,            # linea de los labios
    "menton": 152,            # punto mas bajo del menton
    "temporal_der": 54,       # anchura frontal
    "temporal_izq": 284,
    "zigomatico_der": 234,    # anchura bizigomatica (pomulos)
    "zigomatico_izq": 454,
    "gonion_der": 58,         # angulo mandibular real (bajo el lobulo)
    "gonion_izq": 288,
    "mandibula_med_der": 172,  # contorno mandibular intermedio
    "mandibula_med_izq": 397,
    "canto_ext_der": 33,      # ojos
    "canto_int_der": 133,
    "canto_int_izq": 362,
    "canto_ext_izq": 263,
    "ala_nasal_der": 48,      # anchura de la nariz
    "ala_nasal_izq": 278,
    "comisura_der": 61,       # anchura de la boca
    "comisura_izq": 291,
}

# El mesh de MediaPipe NO llega al nacimiento del pelo real. El punto 10 cae
# en la frente alta, no en el trichion. Corregimos con un factor empirico
# para estimar el tercio superior; queda marcado como confianza "media".
FACTOR_TRICHION = 1.16


MODELO = Path(__file__).parent / "modelos" / "face_landmarker.task"


def _json_safe(o):
    """numpy no es serializable por defecto; el JSON debe salir limpio."""
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(f"No serializable: {type(o)}")


def _xy(lm, idx, w, h):
    p = lm[idx]
    return np.array([p.x * w, p.y * h])


def _dist(a, b):
    return float(np.linalg.norm(a - b))


def _angulo(a, vertice, b):
    """Angulo en grados en `vertice`, formado por los segmentos a-vertice-b."""
    v1, v2 = a - vertice, b - vertice
    cos = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
    return float(math.degrees(math.acos(np.clip(cos, -1.0, 1.0))))


def detectar(path):
    img = cv2.imread(str(path))
    if img is None:
        raise SystemExit(f"No se pudo abrir la imagen: {path}")
    h, w = img.shape[:2]
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Dos APIs de MediaPipe conviven en el ecosistema: la legacy `solutions`
    # (0.10.x, estable en macOS ARM) y la nueva `tasks` (1.x, que en Mac
    # revienta con el delegado Metal). Probamos legacy y caemos a tasks.
    lm = None
    if hasattr(mp, "solutions"):
        with mp.solutions.face_mesh.FaceMesh(
            static_image_mode=True, max_num_faces=2, refine_landmarks=True,
            min_detection_confidence=0.5,
        ) as fm:
            res = fm.process(rgb)
        if res.multi_face_landmarks and len(res.multi_face_landmarks) != 1:
            raise SystemExit("A foto deve conter exatamente um rosto")
        if res.multi_face_landmarks:
            lm = res.multi_face_landmarks[0].landmark
    else:
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision
        opciones = vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(MODELO)),
            num_faces=2,
        )
        with vision.FaceLandmarker.create_from_options(opciones) as det:
            res = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
        if res.face_landmarks and len(res.face_landmarks) != 1:
            raise SystemExit("A foto deve conter exatamente um rosto")
        if res.face_landmarks:
            lm = res.face_landmarks[0]

    if lm is None:
        raise SystemExit(f"No se detecto ningun rostro en {path}")
    P = {k: _xy(lm, i, w, h) for k, i in PT.items()}
    return img, P, lm, (w, h)


def medir(P):
    """Devuelve el bloque de metricas crudas, todas en pixeles o ratios."""
    bitemporal = _dist(P["temporal_der"], P["temporal_izq"])
    bizigomatica = _dist(P["zigomatico_der"], P["zigomatico_izq"])
    bigonial = _dist(P["gonion_der"], P["gonion_izq"])

    # Altura facial: de la frente estimada al menton.
    y_frente = P["frente_alta"][1]
    y_menton = P["menton"][1]
    alto_visible = y_menton - y_frente
    y_trichion = y_menton - alto_visible * FACTOR_TRICHION
    altura_facial = y_menton - y_trichion

    # Tercios verticales clasicos: trichion-glabela / glabela-subnasal / subnasal-menton
    t1 = P["glabela"][1] - y_trichion
    t2 = P["subnasale"][1] - P["glabela"][1]
    t3 = y_menton - P["subnasale"][1]
    total = t1 + t2 + t3

    # Quintos horizontales: la cara "ideal" mide 5 anchuras de ojo.
    ancho_ojo_der = _dist(P["canto_ext_der"], P["canto_int_der"])
    ancho_ojo_izq = _dist(P["canto_int_izq"], P["canto_ext_izq"])
    ancho_ojo = (ancho_ojo_der + ancho_ojo_izq) / 2
    intercantal = _dist(P["canto_int_der"], P["canto_int_izq"])
    ancho_nariz = _dist(P["ala_nasal_der"], P["ala_nasal_izq"])
    ancho_boca = _dist(P["comisura_der"], P["comisura_izq"])

    # Angulo gonial aproximado desde frontal (el fiable es de perfil).
    ang_gonial = _angulo(P["zigomatico_der"], P["gonion_der"], P["menton"])

    # Quintos horizontales, como porcentaje de la anchura total del rostro.
    xs = sorted([
        P["zigomatico_der"][0], P["canto_ext_der"][0], P["canto_int_der"][0],
        P["canto_int_izq"][0], P["canto_ext_izq"][0], P["zigomatico_izq"][0],
    ])
    total_x = xs[-1] - xs[0]
    pct = [100 * (xs[i + 1] - xs[i]) / total_x for i in range(5)]
    quintos = {
        "lateral_der": pct[0], "ojo_der": pct[1], "central": pct[2],
        "ojo_izq": pct[3], "lateral_izq": pct[4],
    }

    return {
        "px": {
            "bitemporal": bitemporal,
            "bizigomatica": bizigomatica,
            "bigonial": bigonial,
            "altura_facial": altura_facial,
            "ancho_ojo": ancho_ojo,
            "intercantal": intercantal,
            "ancho_nariz": ancho_nariz,
            "ancho_boca": ancho_boca,
        },
        "ratios": {
            "indice_facial": altura_facial / bizigomatica,
            "bigonial_bizigomatica": bigonial / bizigomatica,
            "bitemporal_bizigomatica": bitemporal / bizigomatica,
            "nariz_intercantal": ancho_nariz / intercantal,
            "nariz_bizigomatica": ancho_nariz / bizigomatica,
            "boca_nariz": ancho_boca / ancho_nariz,
            "intercantal_ojo": intercantal / ancho_ojo,
        },
        "tercios_pct": {
            "superior": 100 * t1 / total,
            "medio": 100 * t2 / total,
            "inferior": 100 * t3 / total,
        },
        "quintos_pct": quintos,
        "angulos": {"gonial_frontal_aprox": ang_gonial},
        "_y_trichion": float(y_trichion),
    }


def clasificar(m):
    """Reglas EXPLICITAS. Cada veredicto dice por que y con que numero."""
    r, t = m["ratios"], m["tercios_pct"]
    out = {}

    # --- Morfotipo facial ---
    ifac = r["indice_facial"]
    bg = r["bigonial_bizigomatica"]
    bt = r["bitemporal_bizigomatica"]

    if ifac >= 1.55:
        largo = "alargado"
    elif ifac <= 1.30:
        largo = "corto"
    else:
        largo = "proporcionado"

    if bg >= 0.92 and bt >= 0.90 and ifac <= 1.45:
        forma = "cuadrado"
    elif bg >= 0.92 and ifac > 1.45:
        forma = "rectangular"
    elif bg < 0.80 and bt < 0.88:
        forma = "ovalado"
    elif bt < 0.82 and bg >= 0.85:
        forma = "triangular de base ancha"
    elif bg < 0.82 and bt >= 0.92:
        forma = "de corazón"
    else:
        forma = "ovalado-cuadrado"

    out["morfotipo"] = {
        "forma": forma,
        "proporcion": largo,
        "porque": (
            f"tu índice facial es {ifac:.2f}".replace(".", ",")
            + f", la mandíbula mide el {bg*100:.0f}% del ancho de los pómulos "
              f"y la frente el {bt*100:.0f}%"
        ),
        "confianza": "alta",
    }

    # --- Equilibrio de tercios ---
    desvios = {k: v - 33.33 for k, v in t.items()}
    dominante = max(desvios, key=lambda k: desvios[k])
    out["tercios"] = {
        "reparto": {k: round(v, 1) for k, v in t.items()},
        "dominante": dominante,
        "desviacion_max_pp": round(max(abs(v) for v in desvios.values()), 1),
        "equilibrado": max(abs(v) for v in desvios.values()) < 3.0,
        "confianza": "media",  # depende del trichion estimado
        "nota": "El tercio superior se estima: el nacimiento del pelo no es detectable por vision.",
    }

    # --- Nariz: protagonismo relativo ---
    nz = r["nariz_bizigomatica"]
    out["nariz"] = {
        "ancho_rel_pomulos_pct": round(nz * 100, 1),
        "vs_intercantal": round(r["nariz_intercantal"], 2),
        "veredicto": (
            "estrecha" if nz < 0.24 else "proporcionada" if nz <= 0.28 else "ancha"
        ),
        "regla_clasica": "El ancho de la nariz deberia igualar la distancia entre lagrimales (ratio 1.0)",
        "confianza": "alta",
    }

    # --- Mandibula ---
    out["mandibula"] = {
        "ratio_bigonial": round(bg, 2),
        "angulo_gonial_frontal": round(m["angulos"]["gonial_frontal_aprox"], 1),
        "veredicto": (
            "marcada y ancha" if bg >= 0.92
            else "definida" if bg >= 0.84
            else "estrecha / afilada"
        ),
        "confianza": "media",
        "nota": "El angulo gonial real solo se mide con fiabilidad en la foto de perfil.",
    }

    return out


# ---------------------------------------------------------------------------
# Overlay: las lineas que se dibujan sobre la foto.
# ---------------------------------------------------------------------------
COL = {
    "tercios": (255, 214, 92),    # BGR - ambar
    "quintos": (196, 154, 255),   # lila
    "estructura": (120, 255, 190),  # verde menta
    "eje": (255, 255, 255),
    "acento": (110, 130, 255),    # coral
}


def dibujar(img, P, m, out_path, mostrar=("tercios", "quintos", "estructura")):
    h, w = img.shape[:2]
    lienzo = img.copy()
    capa = np.zeros_like(img)
    grosor = max(1, int(round(w / 500)))
    fuente = cv2.FONT_HERSHEY_DUPLEX
    escala = w / 900

    def linea(p1, p2, color, gr=None, guion=False):
        p1 = tuple(np.int32(p1)); p2 = tuple(np.int32(p2))
        gr = gr or grosor
        if not guion:
            cv2.line(capa, p1, p2, color, gr, cv2.LINE_AA)
            return
        d = int(np.hypot(p2[0]-p1[0], p2[1]-p1[1]))
        for i in range(0, d, 14):
            a = i / max(d, 1); b = min((i + 7) / max(d, 1), 1.0)
            pa = (int(p1[0]+(p2[0]-p1[0])*a), int(p1[1]+(p2[1]-p1[1])*a))
            pb = (int(p1[0]+(p2[0]-p1[0])*b), int(p1[1]+(p2[1]-p1[1])*b))
            cv2.line(capa, pa, pb, color, gr, cv2.LINE_AA)

    def etiqueta(texto, pos, color):
        (tw, th), _ = cv2.getTextSize(texto, fuente, escala*0.5, 1)
        x, y = int(pos[0]), int(pos[1])
        cv2.rectangle(capa, (x-4, y-th-6), (x+tw+4, y+4), (20, 18, 16), -1)
        cv2.putText(capa, texto, (x, y), fuente, escala*0.5, color, 1, cv2.LINE_AA)

    x_izq = float(min(P["zigomatico_der"][0], P["temporal_der"][0])) - w*0.03
    x_der = float(max(P["zigomatico_izq"][0], P["temporal_izq"][0])) + w*0.03

    if "tercios" in mostrar:
        ys = [m["_y_trichion"], P["glabela"][1], P["subnasale"][1], P["menton"][1]]
        nombres = ["trichion (est.)", "glabela", "subnasal", "menton"]
        for y, nom in zip(ys, nombres):
            linea((x_izq, y), (x_der, y), COL["tercios"])
            etiqueta(nom, (x_der + w*0.01, y + 4), COL["tercios"])
        for i, clave in enumerate(["superior", "medio", "inferior"]):
            ymid = (ys[i] + ys[i+1]) / 2
            etiqueta(f"{m['tercios_pct'][clave]:.1f}%", (x_izq - w*0.11, ymid), COL["tercios"])

    if "quintos" in mostrar:
        # Regla clasica: la cara "ideal" mide cinco anchuras de ojo.
        xs = sorted([
            P["zigomatico_der"][0], P["canto_ext_der"][0], P["canto_int_der"][0],
            P["canto_int_izq"][0], P["canto_ext_izq"][0], P["zigomatico_izq"][0],
        ])
        y0 = P["temporal_der"][1]
        y1 = P["menton"][1]
        ancho_total = xs[-1] - xs[0]
        for x in xs:
            linea((x, y0), (x, y1), COL["quintos"], 1, guion=True)
        y_pct = P["canto_ext_der"][1] - h * 0.055
        for i in range(5):
            pct = 100 * (xs[i+1] - xs[i]) / ancho_total
            etiqueta(f"{pct:.0f}%", ((xs[i]+xs[i+1])/2 - w*0.018, y_pct),
                     COL["quintos"])

    if "estructura" in mostrar:
        # La anchura bizigomatica se mide en el punto mas lateral del mesh,
        # pero se representa a la altura del arco zigomatico (bajo los ojos).
        y_pomulo = (P["canto_ext_der"][1] + P["ala_nasal_der"][1]) / 2
        zd = np.array([P["zigomatico_der"][0], y_pomulo])
        zi = np.array([P["zigomatico_izq"][0], y_pomulo])
        for pa, pb, nom, col in [
            (P["temporal_der"], P["temporal_izq"], "bitemporal", COL["estructura"]),
            (zd, zi, "bizigomatica", COL["acento"]),
            (P["gonion_der"], P["gonion_izq"], "bigonial", COL["estructura"]),
        ]:
            linea(pa, pb, col, grosor + 1)
            etiqueta(nom, (pb[0] + w*0.012, pb[1]), col)
        # Eje de simetria
        cx = (P["zigomatico_der"][0] + P["zigomatico_izq"][0]) / 2
        linea((cx, m["_y_trichion"]), (cx, P["menton"][1]), COL["eje"], 1, guion=True)
        # Contorno mandibular
        for a, b in [("zigomatico_der", "gonion_der"),
                     ("gonion_der", "mandibula_med_der"),
                     ("mandibula_med_der", "menton"),
                     ("menton", "mandibula_med_izq"),
                     ("mandibula_med_izq", "gonion_izq"),
                     ("gonion_izq", "zigomatico_izq")]:
            linea(P[a], P[b], COL["acento"], grosor)

    cv2.addWeighted(capa, 0.92, lienzo, 1.0, 0, lienzo)
    cv2.imwrite(str(out_path), lienzo)
    return out_path


def main():
    if len(sys.argv) < 2:
        raise SystemExit("uso: analiza_rostro.py <frontal.png> [salida_dir]")
    frontal = Path(sys.argv[1])
    salida = Path(sys.argv[2]) if len(sys.argv) > 2 else frontal.parent

    img, P, _, _ = detectar(frontal)
    m = medir(P)
    c = clasificar(m)

    salida.mkdir(parents=True, exist_ok=True)
    png_full = dibujar(img, P, m, salida / "overlay-completo.png")
    dibujar(img, P, m, salida / "overlay-tercios.png", mostrar=("tercios",))
    dibujar(img, P, m, salida / "overlay-estructura.png", mostrar=("estructura",))

    informe = {"fuente": str(frontal), "medidas": m, "clasificacion": c}
    (salida / "medidas.json").write_text(
        json.dumps(informe, indent=2, ensure_ascii=False, default=_json_safe),
        encoding="utf-8",
    )

    print(json.dumps(c, indent=2, ensure_ascii=False, default=_json_safe))
    print(f"\noverlay -> {png_full}")


if __name__ == "__main__":
    main()
