#!/usr/bin/env python3
"""
Renderiza el informe COMPLETO con las dos procedencias de texto y comprueba que
las dos encajan en la plantilla.

POR QUE EXISTE
--------------
Los textos del informe llegan del motor de reglas o del LLM, con formas
distintas, y cada desajuste dio un fallo que no se vio hasta produccion:

  * `diagnostico`: la plantilla itera, asi que un string se recorria letra a
    letra y pintaba un <p> por caracter.
  * `evitar`: la plantilla desempaqueta pares -> `too many values to unpack`.
  * `titular`: la plantilla espera un dict -> 500 con
    `string indices must be integers, not 'str'`.

Los tres eran la misma clase de error y se arreglaron de uno en uno, porque no
habia forma de probarlos: vivian en servidor.py, que no se importa sin
mediapipe. Ahora viven en vista_informe.py y esto los recorre enteros.

Se ejecuta sin mediapipe. Solo necesita jinja2:

    python3 prueba_informe.py
"""

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ.parent / "03-motor"))

import vista_informe                                          # noqa: E402
import calibres as mod_calibres                                # noqa: E402
import render_informe                                          # noqa: E402
from motor_recomendacion import analizar                       # noqa: E402

# Un pixel transparente: el render necesita una imagen, no la mira nadie.
PIXEL = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
         "AAAADUlEQVR42mP8z8AABAAB/wD/AAAAAElFTkSuQmCC")

MEDIDAS = {
    "ratios": {"indice_facial": 1.452, "bigonial_bizigomatica": 0.891,
               "bitemporal_bizigomatica": 0.871, "nariz_intercantal": 1.252,
               "nariz_bizigomatica": 0.294, "boca_nariz": 1.236,
               "intercantal_ojo": 1.135},
    "tercios_pct": {"superior": 31.5, "medio": 34.0, "inferior": 34.5},
    "quintos_pct": {"central": 24.0},
}
RESPUESTAS = {"nombre": "Ángel Aparicio", "transmitir": ["elegante"],
              "estilos": ["old_money"], "minutos": 10, "barba": "si",
              "cuello": "largo", "menos_favorita": "la nariz de perfil"}

# Salida del LLM con la forma real que devuelve el esquema de analisis_ia.py.
# Es una fixture a proposito: la prueba no debe gastar dinero en cada ejecucion.
IA = {
    "titular": "Base ovalada-cuadrada, cuidado con la altura",
    "diagnostico": ("El indice facial es 1.453, dentro del canon 1.3-1.55, asi que "
                    "no conviene alargarlo mas. La mandibula mide el 89.2% del "
                    "ancho de pomulos. El quinto central es 24.0% frente al canon "
                    "18.0-22.0%. En las fotos se ve pelo denso y liso."),
    "objetivo": ("Buscar un corte elegante con altura controlada. La barba corta "
                 "refuerza la mandibula, que ya esta al 89.2%."),
    "evitar": [
        {"que": "Copete alto peinado hacia atras.",
         "por_que": "Con un indice facial de 1.453 ya estas en la zona alta."},
        {"que": "Degradado alto a piel en las sienes.",
         "por_que": "La bitemporal/bizigomatica es 0.871."},
    ],
    "estilos": [
        {"nombre": "Executive contour a tijera con taper bajo", "encaje": 9,
         "por_que": "Respeta tu base con indice facial 1.453.",
         "como_pedirlo": "Arriba a tijera 6-7 cm delante, taper bajo.",
         "mantenimiento": "Cada 3-4 semanas, 6-8 minutos por la manana."},
        {"nombre": "Crop frances largo y texturizado", "encaje": 8,
         "por_que": "Baja el peso visual de la frente.",
         "como_pedirlo": "Arriba 4-5 cm con textura, degradado bajo.",
         "mantenimiento": "Cada 3 semanas, 3-5 minutos."},
    ],
    "mejor": 0,
    "prompt_imagen": "Edit only the hair and beard. Keep identity intact.",
}

fallos = []


def check(nombre, ok, detalle=""):
    print(("  OK    " if ok else "  FALLA") + f" · {nombre}"
          + (f"  [{detalle}]" if detalle else ""))
    if not ok:
        fallos.append(nombre)


def render(ia):
    """Monta los datos igual que servidor.py y renderiza. Si la forma de algun
    texto no encaja, esto revienta, que es justamente el objetivo."""
    clasificacion = {"morfotipo": {"forma": "ovalada", "porque": "prueba"}}
    r = analizar(MEDIDAS, clasificacion, RESPUESTAS)
    txt = vista_informe.textos(ia, r["textos"])
    datos = {
        "barberia": {"nombre": "BARBERÍA DEMO", "ciudad": "Tu Ciudad",
                     "barbero": "Tu Barbero"},
        "cliente": {"nombre": "Ángel A.", "expediente": "MST-TEST",
                    "fecha": "1 sep 2026"},
        "titular": txt["titular"], "diagnostico": txt["diagnostico"],
        "objetivo": txt["objetivo"], "evitar": txt["evitar"],
        "morfotipo": "ovalada", "n_proporciones": 16, "n_fuera": 3,
        "calibres": mod_calibres.construir(MEDIDAS), "receta": r["receta"],
        "estilos": (ia or {}).get("estilos"),
        "mejor_estilo": (ia or {}).get("mejor", 0),
        "por_ia": bool(ia),
        "hallazgo_principal": ({"titulo": r["textos"]["principal"].titulo}
                               if r["textos"]["principal"] else None),
        "plan": [{"fecha": "1 sep", "duracion": "45 min",
                  "titulo": "Corte base", "detalle": "Se fija la longitud."}],
        "simulacion": None,
    }
    geo = {"imagen": {"ancho": 100, "alto": 130, "datauri": PIXEL}, "capas": {}}
    return render_informe.construir(geo, datos)


def revisa(etiqueta, html):
    """Comprobaciones que valen para cualquier procedencia."""
    check(f"{etiqueta}: el informe se renderiza", len(html) > 10000,
          f"{len(html):,} bytes")

    # Un <p> por letra es la firma de haber iterado un string.
    letra = re.findall(r"<p>\s*\w\s*</p>", html)
    check(f"{etiqueta}: no hay parrafos de una sola letra", not letra,
          f"{len(letra)} encontrados")

    # Los decimales no pueden aparecer partidos al principio de un parrafo.
    check(f"{etiqueta}: ningun parrafo empieza por digito",
          not re.findall(r"<p>\d", html))

    for t in ("section", "article", "dl", "dd", "dt", "p", "div"):
        a = len(re.findall(r"<" + t + r"[\s>]", html))
        c = len(re.findall(r"</" + t + r">", html))
        if a != c:
            check(f"{etiqueta}: etiquetas <{t}> balanceadas", False, f"{a}/{c}")

    # La numeracion de secciones tiene que ser 01, 02, 03... sin saltos.
    nums = [int(x) for x in re.findall(r'class="num">(\d+)<', html)]
    check(f"{etiqueta}: secciones numeradas sin saltos",
          nums == list(range(1, len(nums) + 1)), str(nums))

    # Ningun hueco de plantilla sin rellenar.
    check(f"{etiqueta}: sin marcadores de plantilla sueltos",
          "{{" not in html and "{%" not in html)


def main():
    print("=== CON EL MOTOR DE REGLAS (sin LLM) ===")
    html_reglas = render(None)
    revisa("reglas", html_reglas)
    check("reglas: NO aparece la seccion de estilos",
          "Los cortes que te funcionan" not in html_reglas
          and "El corte que te funciona" not in html_reglas)

    print("\n=== CON EL LLM ===")
    html_ia = render(IA)
    revisa("LLM", html_ia)
    check("LLM: aparece la seccion de estilos",
          "Los cortes que te funcionan" in html_ia)
    for e in IA["estilos"]:
        check(f"LLM: esta el estilo «{e['nombre'][:34]}»", e["nombre"] in html_ia)
    check("LLM: el mejor lleva su sello", "El que mejor te queda" in html_ia)
    check("LLM: los encajes salen",
          re.findall('class="mono">' + r"(\d+)</span><small>/10", html_ia)
          == ["9", "8"])
    for e in IA["evitar"]:
        check(f"LLM: esta el error «{e['que'][:30]}»", e["que"] in html_ia)
    check("LLM: el titular no sale vacio",
          any(p in html_ia for p in IA["titular"].split()[:3]))

    print("\n=== FORMAS RARAS QUE NO DEBEN TUMBAR NADA ===")
    for etiqueta, roto in (
            ("titular vacio", {**IA, "titular": ""}),
            ("titular de una palabra", {**IA, "titular": "Ovalada"}),
            ("diagnostico vacio", {**IA, "diagnostico": ""}),
            ("evitar vacio", {**IA, "evitar": []}),
            ("evitar con pares incompletos",
             {**IA, "evitar": [{"que": "Solo esto"}, {"por_que": "y esto"}]}),
            ("estilos vacio", {**IA, "estilos": []}),
            ("mejor fuera de rango", {**IA, "mejor": 99}),
    ):
        try:
            render(roto)
            check(f"aguanta: {etiqueta}", True)
        except Exception as e:
            check(f"aguanta: {etiqueta}", False, f"{type(e).__name__}: {e}")

    print()
    if fallos:
        print(f"{len(fallos)} FALLOS: {fallos}")
        return 1
    print("TODO VERDE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
