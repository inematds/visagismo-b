#!/usr/bin/env python3
"""
El salto de MEDIDA a RECOMENDACION. Es el corazon del producto.

Funciona en tres pasos, deliberadamente separados:

  1. HALLAZGOS   Cada metrica se compara con su canon. Lo que se desvia
                 genera un hallazgo con su severidad y sus directivas.
  2. RECETA      Las directivas se consolidan en decisiones concretas de
                 corte y barba, resolviendo los conflictos por prioridad.
  3. REDACCION   Se escriben los textos, SIEMPRE citando el numero que
                 justifica cada afirmacion.

La regla que sostiene todo: **ninguna frase del informe puede afirmar
nada que no venga de un hallazgo medido o de una respuesta del cliente**.
Es lo que evita que el texto suene a IA rellenando huecos.
"""

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Canon. Cada rango es (minimo, maximo) de normalidad.
# ---------------------------------------------------------------------------
CANON = {
    "indice_facial": (1.30, 1.55),
    "bigonial_bizigomatica": (0.80, 0.92),
    "bitemporal_bizigomatica": (0.82, 0.95),
    "nariz_intercantal": (0.90, 1.10),
    "nariz_bizigomatica": (0.22, 0.28),
    "intercantal_ojo": (0.90, 1.10),
    "quinto_central": (18.0, 22.0),
    "tercio": (30.5, 36.0),
}


@dataclass
class Hallazgo:
    clave: str
    titulo: str
    severidad: float          # 0-1; ordena que manda en el informe
    evidencia: str            # el numero que lo justifica. Nunca vacio.
    directivas: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# 1. HALLAZGOS
# ---------------------------------------------------------------------------
def _desvio(valor, rango):
    """Cuanto se sale del canon, normalizado por la amplitud del rango."""
    lo, hi = rango
    if valor < lo:
        return (valor - lo) / (hi - lo)
    if valor > hi:
        return (valor - hi) / (hi - lo)
    return 0.0


def detectar_hallazgos(m, resp):
    r = m["ratios"]
    t = m["tercios_pct"]
    q = m.get("quintos_pct", {})
    h = []

    # --- Centro del rostro dominante: el hallazgo mas frecuente y mas util ---
    qc = q.get("central")
    d_nariz = _desvio(r["nariz_intercantal"], CANON["nariz_intercantal"])
    d_qc = _desvio(qc, CANON["quinto_central"]) if qc else 0.0
    if d_qc > 0.3 or d_nariz > 0.3:
        ev = []
        if qc:
            ev.append(f"quinto central {qc:.0f}% frente al 20% del canon")
        if d_nariz > 0:
            ev.append(f"nariz un {(r['nariz_intercantal']-1)*100:.0f}% más ancha "
                      f"que la distancia entre lagrimales")
        h.append(Hallazgo(
            "centro_dominante", "El centro del rostro concentra la atención",
            min(1.0, max(d_qc, d_nariz)), " · ".join(ev),
            ["INTERES_ARRIBA", "TEXTURA_FRONTAL", "NO_FRENTE_DESPEJADA",
             "NO_ESTRECHAR_LATERALES"]))

    # --- Proporcion general del rostro ---
    d = _desvio(r["indice_facial"], CANON["indice_facial"])
    # OJO con el signo: _desvio devuelve NEGATIVO por debajo del canon. Con
    # "if d > 0" la rama de cara_corta era codigo muerto y una cara redonda
    # (indice 1,22) no generaba ningun hallazgo: se trataba igual que una
    # ovalada perfecta. _desvio solo vale 0 dentro del canon, asi que la
    # condicion correcta es "distinto de 0".
    if d != 0:
        if r["indice_facial"] > CANON["indice_facial"][1]:
            h.append(Hallazgo(
                "cara_alargada", "Rostro alargado", min(1.0, d),
                f"índice facial {r['indice_facial']:.2f} sobre un canon de 1,30–1,55",
                ["NO_ALTURA_ARRIBA", "ANCHO_LATERALES", "NO_NUCA_ALTA",
                 "FLEQUILLO", "PATILLA_LARGA"]))
        else:
            h.append(Hallazgo(
                "cara_corta", "Rostro corto y ancho", min(1.0, abs(d)),
                f"índice facial {r['indice_facial']:.2f} bajo el canon de 1,30–1,55",
                ["ALTURA_ARRIBA", "ESTRECHAR_LATERALES", "NO_FLEQUILLO",
                 "ANGULAR", "PATILLA_CORTA"]))

    # --- Mandibula ---
    bg = r["bigonial_bizigomatica"]
    d = _desvio(bg, CANON["bigonial_bizigomatica"])
    if bg > CANON["bigonial_bizigomatica"][1]:
        h.append(Hallazgo(
            "mandibula_ancha", "Mandíbula marcada", min(1.0, d),
            f"mandíbula al {bg*100:.0f}% del ancho de pómulos (canon hasta 92%)",
            ["NO_BARBA_ANCHA", "TEXTURA_ARRIBA", "NO_CORTE_PLANO",
             "SUAVIZAR", "PATILLA_CORTA"]))
    elif bg < CANON["bigonial_bizigomatica"][0]:
        h.append(Hallazgo(
            "mandibula_estrecha", "Mandíbula poco marcada", min(1.0, abs(d)),
            f"mandíbula al {bg*100:.0f}% del ancho de pómulos (canon desde 80%)",
            ["BARBA_ESTRUCTURA", "NO_VOLUMEN_LATERAL_BAJO", "PATILLA_LARGA"]))
    elif bg >= 0.87:
        h.append(Hallazgo(
            "mandibula_definida", "Mandíbula definida", 0.25,
            f"mandíbula al {bg*100:.0f}% del ancho de pómulos, en la franja alta",
            ["NO_BARBA_ANCHA"]))

    # --- Frente ---
    bt = r["bitemporal_bizigomatica"]
    if bt > CANON["bitemporal_bizigomatica"][1]:
        h.append(Hallazgo(
            "frente_ancha", "Frente ancha",
            min(1.0, _desvio(bt, CANON["bitemporal_bizigomatica"])),
            f"frente al {bt*100:.0f}% del ancho de pómulos (canon hasta 95%)",
            ["CUBRIR_SIENES", "NO_VOLUMEN_LATERAL_ALTO", "FLEQUILLO"]))
    elif bt < CANON["bitemporal_bizigomatica"][0]:
        h.append(Hallazgo(
            "frente_estrecha", "Frente estrecha",
            min(1.0, abs(_desvio(bt, CANON["bitemporal_bizigomatica"]))),
            f"frente al {bt*100:.0f}% del ancho de pómulos (canon desde 82%)",
            ["VOLUMEN_LATERAL_ALTO", "NO_CUBRIR_SIENES", "NO_FLEQUILLO"]))

    # --- Pomulos dominantes: el rostro en diamante ---
    # Frente Y mandibula por debajo del canon significa que los pomulos son el
    # punto mas ancho. Leidas por separado, cada metrica solo dice "estrecha";
    # juntas piden lo contrario: volumen arriba y abajo, nada en los pomulos.
    if (bt < CANON["bitemporal_bizigomatica"][0]
            and bg < CANON["bigonial_bizigomatica"][0]):
        h.append(Hallazgo(
            "pomulos_dominantes", "Los pómulos son el punto más ancho",
            min(1.0, (abs(_desvio(bt, CANON["bitemporal_bizigomatica"]))
                      + abs(_desvio(bg, CANON["bigonial_bizigomatica"]))) / 2),
            f"frente al {bt*100:.0f}% y mandíbula al {bg*100:.0f}% del ancho de "
            f"pómulos: ambas por debajo del canon",
            ["NO_VOLUMEN_POMULOS", "ALTURA_ARRIBA", "BARBA_ESTRUCTURA",
             "VOLUMEN_LATERAL_ALTO"]))

    # --- Tercios ---
    for nombre, etiqueta in (("superior", "frente"), ("inferior", "mentón")):
        v = t[nombre]
        d = _desvio(v, CANON["tercio"])
        if abs(d) > 0.35:
            grande = v > CANON["tercio"][1]
            h.append(Hallazgo(
                f"tercio_{nombre}_{'grande' if grande else 'pequeno'}",
                f"Tercio {nombre} {'largo' if grande else 'corto'}",
                min(1.0, abs(d)),
                f"el tercio {nombre} ocupa el {v:.0f}% del rostro "
                f"(el reparto equilibrado es 33%)",
                (["NO_ALTURA_ARRIBA", "CUBRIR_FRENTE", "FLEQUILLO"] if grande and nombre == "superior"
                 else ["ALTURA_ARRIBA"] if nombre == "superior"
                 else ["BARBA_CORTA"] if grande else ["BARBA_ESTRUCTURA"])))

    # --- Lo que aporta el cliente y la vision no puede medir ---
    if resp.get("cuello") == "largo":
        h.append(Hallazgo(
            "cuello_largo", "Cuello largo y estrecho", 0.55,
            "declarado por el cliente en el cuestionario",
            ["NUCA_LARGA", "NO_NUCA_ALTA", "BARBA_INTEGRA_CUELLO"]))
    elif resp.get("cuello") == "corto":
        h.append(Hallazgo(
            "cuello_corto", "Cuello corto y ancho", 0.45,
            "declarado por el cliente en el cuestionario",
            ["NUCA_ALTA", "NO_BARBA_LARGA"]))

    if resp.get("barba") == "poca":
        h.append(Hallazgo(
            "barba_irregular", "La barba crece de forma desigual", 0.5,
            "declarado por el cliente en el cuestionario",
            ["BARBA_MUY_CORTA"]))

    h.sort(key=lambda x: x.severidad, reverse=True)
    return h


# ---------------------------------------------------------------------------
# 2. RECETA
# ---------------------------------------------------------------------------
def construir_receta(hallazgos, resp):
    d = {dd for hh in hallazgos for dd in hh.directivas}
    minutos = resp.get("minutos", 5)
    estilos = set(resp.get("estilos", []))
    pulido = bool(estilos & {"old_money", "clasico", "ejecutivo"})

    # --- Longitud arriba ---
    # El orden importa: manda la directiva del hallazgo mas grave, y las
    # combinaciones van ANTES que los casos simples para que no las tapen.
    if "NO_VOLUMEN_POMULOS" in d:
        # Diamante: se construye arriba y se deja el ancho medio en paz.
        largo_cm, frontal_cm = (6, 8), (7, 9)
        forma = "volumen en la zona alta con laterales pegados a la altura del pómulo"
    elif "FLEQUILLO" in d and "NO_FLEQUILLO" not in d and "NO_ALTURA_ARRIBA" in d:
        # Rostro alargado o tercio superior largo: se acorta por delante, no
        # se levanta por arriba, que alargaria mas.
        largo_cm, frontal_cm = (5, 7), (8, 10)
        forma = "media longitud con caída frontal marcada, sin volumen en la raíz"
    elif "INTERES_ARRIBA" in d or "TEXTURA_ARRIBA" in d:
        largo_cm, frontal_cm = (5, 7), (7, 8)
        forma = "media longitud texturizada con caída frontal"
    elif "ALTURA_ARRIBA" in d and "NO_ALTURA_ARRIBA" not in d:
        largo_cm, frontal_cm = (6, 8), (8, 9)
        forma = "volumen alto con raíz levantada"
    else:
        largo_cm, frontal_cm = (4, 5), (5, 6)
        forma = "longitud corta-media, pulida"

    # Sin tiempo por la manana no se sostiene un peinado que exige secador.
    aviso_tiempo = None
    if minutos <= 2 and largo_cm[1] >= 7:
        largo_cm, frontal_cm = (4, 5), (5, 6)
        forma = "media longitud, versión corta y de caída natural"
        aviso_tiempo = ("Se ha acortado la propuesta porque declaraste menos de "
                        "2 minutos por la mañana: la versión larga necesita secador "
                        "para funcionar.")

    # --- Laterales ---
    if "NO_VOLUMEN_POMULOS" in d:
        laterales = ("degradado que se cierra justo a la altura del pómulo y se "
                     "abre otra vez hacia la sien",
                     "nº 1 (3 mm) en el pómulo, nº 2 (6 mm) arriba",
                     "es el único punto donde no debe haber volumen")
    elif "VOLUMEN_LATERAL_ALTO" in d and "NO_VOLUMEN_LATERAL_ALTO" not in d:
        laterales = ("degradado bajo dejando cuerpo por encima de la oreja y en la sien",
                     "nº 2 (6 mm)", "el ancho se gana arriba, no abajo")
    elif "NO_ESTRECHAR_LATERALES" in d or "ANCHO_LATERALES" in d:
        laterales = ("degradado bajo, arrancando a la altura del pabellón de la oreja",
                     "nº 2 (6 mm)", "no bajar de ahí ni hacer fade alto")
    elif "ESTRECHAR_LATERALES" in d:
        laterales = ("degradado medio, limpio", "nº 1 (3 mm)",
                     "sin llegar a piel, para no endurecer el conjunto")
    else:
        laterales = ("degradado bajo clásico", "nº 1,5 (4,5 mm)", "transición suave")

    # --- Nuca ---
    if "NUCA_LARGA" in d or "NO_NUCA_ALTA" in d:
        nuca = ("terminación limpia pero natural, conservando longitud y continuidad",
                "no subir el rapado")
    elif "NUCA_ALTA" in d:
        nuca = ("nuca recogida y despejada", "libera el cuello y alarga la silueta")
    else:
        nuca = ("terminación limpia estándar", "sin subir en exceso")

    # --- Barba ---
    tiene = resp.get("barba", "si")
    if tiene == "no":
        barba = None
    elif "BARBA_MUY_CORTA" in d:
        barba = ("1–3 mm", "uniforme, que disimula las zonas de menor densidad",
                 "sin intentar volumen donde no crece")
    elif "BARBA_ESTRUCTURA" in d and "NO_BARBA_ANCHA" not in d:
        barba = ("6–9 mm", "algo más de cuerpo en el mentón para dar estructura",
                 "línea de mejilla marcada y recta")
    elif "NO_BARBA_ANCHA" in d:
        barba = ("3–5 mm", "uniforme, laterales contenidos, algo más de presencia en el mentón",
                 "línea de mejilla limpia respetando su altura natural; nunca ancha ni cuadrada")
    else:
        barba = ("4–6 mm", "uniforme y bien perfilada",
                 "líneas de mejilla y cuello definidas")

    cuello_barba = ("dos dedos por encima de la nuez" if barba else None)

    # --- Flequillo. Es la decision con mas peso visual y no estaba tomada ---
    # Un rostro alargado o una frente ancha piden romper la vertical por
    # delante; un rostro corto y ancho pide justo lo contrario, porque el
    # flequillo le come el unico tercio que le sobra.
    if "NO_FLEQUILLO" in d:
        flequillo = ("sin flequillo", "el frontal se peina hacia arriba y atrás",
                     "cubrir la frente acortaría más el rostro")
    elif "FLEQUILLO" in d:
        if "CUBRIR_SIENES" in d:
            flequillo = ("caída frontal larga y desfilada, abierta hacia un lado",
                         "cubre el nacimiento y las sienes sin línea recta",
                         "nunca flequillo recto de borde marcado: subraya el ancho")
        else:
            flequillo = ("caída frontal desfilada sobre la frente",
                         "resta altura al tercio superior",
                         "desfilado, no recto, para que no corte la cara en dos")
    else:
        flequillo = ("frontal libre, sin flequillo definido",
                     "puede llevarse caído o hacia atrás según el día",
                     "la proporción no obliga a ninguna de las dos")

    # --- Patillas: prolongan o cortan la mandibula ---
    if "PATILLA_CORTA" in d and "PATILLA_LARGA" not in d:
        patillas = ("cortas, terminadas a media oreja",
                    "no prolongar la línea de la mandíbula hacia abajo")
    elif "PATILLA_LARGA" in d:
        patillas = ("algo más largas, hasta el lóbulo",
                    "prolongan la mandíbula y le dan continuidad")
    else:
        patillas = ("a la altura del centro de la oreja", "terminación recta y limpia")

    # --- Raya: la asimetria suaviza los rostros angulosos ---
    if "SUAVIZAR" in d:
        raya = ("desplazada del centro, marcada con el peine",
                "la asimetría rompe la simetría angulosa del conjunto")
    elif "ANGULAR" in d:
        raya = ("sin raya, peinado hacia arriba",
                "las líneas verticales estiran un rostro ancho")
    else:
        raya = ("natural, siguiendo la caída propia del pelo", "sin marcarla")

    # --- Producto, segun tiempo y acabado buscado ---
    if pulido:
        producto = ("cera de acabado mate y fijación media",
                    "aplicar sobre pelo casi seco y peinar con la mano")
    else:
        producto = ("pasta mate de fijación media",
                    "sobre pelo húmedo, secar con los dedos empujando hacia delante")

    return {
        "forma": forma, "largo_cm": largo_cm, "frontal_cm": frontal_cm,
        "laterales": laterales, "nuca": nuca, "barba": barba,
        "cuello_barba": cuello_barba, "producto": producto,
        "flequillo": flequillo, "patillas": patillas, "raya": raya,
        "minutos": minutos, "aviso_tiempo": aviso_tiempo,
        "directivas": sorted(d),
    }


# ---------------------------------------------------------------------------
# 3. REDACCION
# ---------------------------------------------------------------------------
TRANSMITIR = {
    "masculino": "masculinidad", "elegante": "elegancia",
    "profesional": "credibilidad profesional", "dominante": "presencia",
    "juvenil": "frescura", "relajado": "naturalidad",
    "moderno": "actualidad", "clasico": "sobriedad",
    "sofisticado": "sofisticación", "natural": "naturalidad",
}


def _lista(items):
    items = list(items)
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " y " + items[-1]


def redactar(m, hallazgos, receta, resp, clasificacion):
    forma = clasificacion["morfotipo"]["forma"]
    principal = hallazgos[0] if hallazgos else None
    metas = [TRANSMITIR.get(x, x) for x in resp.get("transmitir", [])][:3]

    # --- Titular: nace del hallazgo principal, no es una frase de plantilla ---
    titulares = {
        "centro_dominante": ("No necesitas otra cara.", "repartirla", "Necesitas {} mejor."),
        "cara_alargada": ("Tu cara no es larga.", "ancho", "Le falta {} donde toca."),
        "cara_corta": ("No necesitas más cara.", "altura", "Necesitas {} arriba."),
        "mandibula_ancha": ("Tu mandíbula es un activo.", "compita", "Solo necesita que algo {}."),
        "mandibula_estrecha": ("La mandíbula se dibuja.", "construye", "No se hereda: se {}."),
        "frente_estrecha": ("Tu frente pide aire.", "abrirla", "Todo consiste en {}."),
        "frente_ancha": ("Tienes frente de sobra.", "enmarcarla", "Solo hay que {}."),
        "cuello_largo": ("El corte no acaba en la nuca.", "continúa", "{} en el cuello."),
    }
    clave = principal.clave if principal else "centro_dominante"
    t = titulares.get(clave, titulares["centro_dominante"])
    titular = {"linea1": t[0], "enfasis": t[1], "linea2": t[2].format(t[1])}

    # --- Diagnostico ---
    dentro = [hh for hh in hallazgos if hh.severidad < 0.3]
    fuera = [hh for hh in hallazgos if hh.severidad >= 0.3]
    diag = [
        f"Tu rostro es <strong>{forma}</strong>: "
        f"{clasificacion['morfotipo']['porque']}."
    ]
    if fuera:
        diag.append(
            "<strong>Lo que se sale del canon es esto:</strong> "
            + _lista([f"{hh.titulo.lower()} ({hh.evidencia})" for hh in fuera[:2]])
            + ". Es de ahí de donde sale toda la propuesta."
        )
    else:
        diag.append(
            "No hay ninguna proporción claramente fuera del canon. Eso es una buena "
            "noticia y significa que el trabajo va de afinar, no de compensar."
        )

    # --- Objetivo ---
    obj = []
    if metas:
        obj.append(f"Buscas transmitir {_lista(metas)}.")
    if principal:
        obj.append(f"La palanca principal es {principal.titulo.lower()}: {principal.evidencia}.")
    disgusta = (resp.get("menos_favorita") or "").strip()
    if disgusta:
        obj.append(
            f"Dijiste que lo que menos te gusta es «{disgusta}». No vamos a intentar "
            f"esconderlo: vamos a crear otros puntos de interés para que la mirada "
            f"se reparta."
        )

    # --- Que evitar: se deduce de las directivas, no es una lista fija ---
    evitar = []
    d = set(receta["directivas"])
    if "NO_FRENTE_DESPEJADA" in d:
        evitar.append(("Pelo hacia atrás con la frente despejada.",
                       "Parece la opción masculina y es la que peor te funciona: "
                       "deja el centro del rostro sin nada que le compita."))
    if "NO_ESTRECHAR_LATERALES" in d:
        evitar.append(("Fade alto o laterales rapados a piel.",
                       "Estrechar los lados devuelve todo el protagonismo al centro."))
    if "NO_CORTE_PLANO" in d:
        evitar.append(("Corte plano y geométrico arriba.",
                       "Refuerza una horizontalidad que tu estructura ya aporta de sobra."))
    if "NO_BARBA_ANCHA" in d:
        evitar.append(("Fabricar mandíbula con una barba grande.",
                       "Ganarías volumen y perderías limpieza. Tu ratio ya está alto."))
    if "NO_NUCA_ALTA" in d:
        evitar.append(("Rapar la nuca alta.",
                       "Con un cuello largo, alarga todavía más y rompe la continuidad."))
    if "NO_ALTURA_ARRIBA" in d:
        evitar.append(("Volumen alto o tupé.",
                       "Añade altura a un rostro que ya la tiene de sobra."))
    if not evitar:
        evitar.append(("Cambiar de corte cada visita.",
                       "Tu estructura no pide compensaciones; pide constancia."))

    return {"titular": titular, "diagnostico": diag, "objetivo": obj,
            "evitar": evitar[:3], "principal": principal}


def analizar(medidas, clasificacion, respuestas):
    """Punto de entrada unico: medidas + respuestas -> todo lo que el informe necesita."""
    hallazgos = detectar_hallazgos(medidas, respuestas)
    receta = construir_receta(hallazgos, respuestas)
    textos = redactar(medidas, hallazgos, receta, respuestas, clasificacion)
    return {"hallazgos": hallazgos, "receta": receta, "textos": textos}
