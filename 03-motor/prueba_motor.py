#!/usr/bin/env python3
"""
Regresion del motor de recomendacion: SIETE morfotipos de manual entran y se
comprueba que salen recomendaciones DISTINTAS.

Existe por un bug concreto que estuvo vivo y no daba ningun sintoma: la rama
que detecta el rostro corto y ancho usaba `if d > 0`, y `_desvio` devuelve
NEGATIVO por debajo del canon, asi que era codigo muerto. Una cara redonda
generaba cero hallazgos y recibia exactamente la misma receta que una ovalada
perfecta. El informe salia igual de bonito, citando numeros correctos, y nadie
lo notaba salvo comparando dos informes de caras opuestas.

Se ejecuta sin mediapipe ni nada instalado:

    python3 prueba_motor.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from motor_recomendacion import CANON, analizar, detectar_hallazgos  # noqa: E402


def medidas(indice, bigonial, bitemporal, nariz=1.0, central=20.0,
            sup=33.0, inf=33.0):
    return {
        "ratios": {"indice_facial": indice, "bigonial_bizigomatica": bigonial,
                   "bitemporal_bizigomatica": bitemporal,
                   "nariz_intercantal": nariz},
        "tercios_pct": {"superior": sup, "medio": 100 - sup - inf, "inferior": inf},
        "quintos_pct": {"central": central},
    }


# Los siete morfotipos clasicos, con valores dentro de lo plausible.
MORFOTIPOS = {
    "redonda":    medidas(1.22, 0.86, 0.90),
    "cuadrada":   medidas(1.34, 0.97, 0.97),
    "alargada":   medidas(1.68, 0.78, 0.86),
    "ovalada":    medidas(1.42, 0.86, 0.88),
    "corazon":    medidas(1.45, 0.74, 0.99),
    "diamante":   medidas(1.50, 0.76, 0.79),
    "triangular": medidas(1.38, 0.96, 0.80),
}

RESPUESTAS = {"nombre": "Prueba", "transmitir": ["cercania"], "estilos": [],
              "minutos": 5, "barba": "si", "cuello": "medio",
              "menos_favorita": ""}

fallos = []


def check(nombre, ok, detalle=""):
    print(("  OK    " if ok else "  FALLA") + f" · {nombre}"
          + (f"  [{detalle}]" if detalle else ""))
    if not ok:
        fallos.append(nombre)


def main():
    print("=== EL ROSTRO CORTO Y ANCHO SE DETECTA ===")
    # Es la regresion del bug: por debajo del canon el desvio es negativo.
    bajo = CANON["indice_facial"][0] - 0.10
    hs = [h.clave for h in detectar_hallazgos(medidas(bajo, 0.86, 0.88), RESPUESTAS)]
    check(f"indice {bajo:.2f} (bajo el canon) genera 'cara_corta'",
          "cara_corta" in hs, ", ".join(hs) or "ninguno")
    alto = CANON["indice_facial"][1] + 0.10
    hs = [h.clave for h in detectar_hallazgos(medidas(alto, 0.86, 0.88), RESPUESTAS)]
    check(f"indice {alto:.2f} (sobre el canon) genera 'cara_alargada'",
          "cara_alargada" in hs, ", ".join(hs) or "ninguno")
    dentro = sum(CANON["indice_facial"]) / 2
    hs = [h.clave for h in detectar_hallazgos(medidas(dentro, 0.86, 0.88), RESPUESTAS)]
    check(f"indice {dentro:.2f} (en canon) no genera ninguno de los dos",
          not {"cara_corta", "cara_alargada"} & set(hs), ", ".join(hs) or "ninguno")

    print("\n=== CADA MORFOTIPO RECIBE SU PROPIA RECOMENDACION ===")
    salidas = {}
    for nombre, m in MORFOTIPOS.items():
        clasificacion = {"morfotipo": {"forma": nombre, "porque": "prueba"}}
        salidas[nombre] = analizar(m, clasificacion, RESPUESTAS)

    def unicos(extrae):
        return {json.dumps(extrae(s), sort_keys=True, ensure_ascii=False,
                           default=str) for s in salidas.values()}

    n = len(MORFOTIPOS)
    recetas = unicos(lambda s: s["receta"])
    check("las 7 recetas completas son distintas entre si",
          len(recetas) == n, f"{len(recetas)}/{n}")
    diag = unicos(lambda s: s["textos"]["diagnostico"])
    check("los 7 diagnosticos son distintos", len(diag) == n, f"{len(diag)}/{n}")

    # Toda afirmacion tiene que venir de un numero medido: ningun hallazgo
    # puede quedarse sin evidencia. Es la regla que sostiene el producto.
    sin_evidencia = [(nombre, h.clave) for nombre, s in salidas.items()
                     for h in s["hallazgos"] if not (h.evidencia or "").strip()]
    check("todo hallazgo lleva su evidencia numerica", not sin_evidencia,
          str(sin_evidencia[:3]))

    print("\n=== LO QUE TODAVIA NO DISCRIMINA ===")
    # No son fallos: son el trabajo pendiente, medido. Si estas cifras suben,
    # el motor ha ganado criterio de verdad.
    for campo in ("forma", "largo_cm", "laterales", "nuca", "barba",
                  "flequillo", "patillas", "raya"):
        d = len(unicos(lambda s, c=campo: s["receta"].get(c)))
        print(f"  receta.{campo:<11}: {d} valores distintos de {n} morfotipos"
              + ("   <-- no discrimina" if d <= 1 else ""))

    # Ningun campo de la receta puede venir vacio: un hueco en la ficha de
    # ejecucion es una instruccion que el barbero no recibe.
    obligatorios = ("forma", "largo_cm", "frontal_cm", "laterales", "nuca",
                    "flequillo", "patillas", "raya", "producto")
    huecos = [(n, c) for n, s_ in salidas.items() for c in obligatorios
              if not s_["receta"].get(c)]
    check("ningun campo de la receta viene vacio", not huecos, str(huecos[:3]))

    print()
    if fallos:
        print(f"{len(fallos)} FALLOS: {fallos}")
        return 1
    print("TODO VERDE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
