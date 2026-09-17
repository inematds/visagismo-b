#!/usr/bin/env python3
"""
Convierte las metricas medidas en las "reglas de calibre" del informe:
cada proporcion sobre una escala, con la franja de canon marcada y el
valor real encima.

Es la pieza que distingue el informe de una opinion: el lector no ve un
adjetivo, ve donde cae exactamente y cuanto se separa de lo normal.
"""

from motor_recomendacion import CANON


def _pos(valor, lo, hi):
    """Posicion en porcentaje dentro de la escala, recortada a los bordes."""
    return max(2.0, min(98.0, 100 * (valor - lo) / (hi - lo)))


def _calibre(nombre, sub, valor, texto_valor, escala, canon, pie_ok, pie_mal,
             unidad=""):
    lo, hi = escala
    c_lo, c_hi = canon
    dentro = c_lo <= valor <= c_hi
    return {
        "nombre": nombre,
        "sub": sub,
        "valor_txt": texto_valor,
        "estado": "ok" if dentro else "des",
        "canon_izq": _pos(c_lo, lo, hi),
        "canon_der": 100 - _pos(c_hi, lo, hi),
        "marca": _pos(valor, lo, hi),
        "esc_min": f"{lo:g}{unidad}".replace(".", ","),
        "esc_max": f"{hi:g}{unidad}".replace(".", ","),
        "pie": pie_ok if dentro else pie_mal,
        "dentro": dentro,
    }


def construir(m, destacado="quinto_central"):
    """Devuelve la lista de calibres del informe, el destacado el primero de su tipo."""
    r, t, q = m["ratios"], m["tercios_pct"], m["quintos_pct"]
    cal = []

    v = r["indice_facial"]
    cal.append(_calibre(
        "Índice facial", "Altura del rostro entre su anchura máxima",
        v, f"{v:.2f}".replace(".", ","), (1.10, 1.75), CANON["indice_facial"],
        "Canon 1,30–1,55 · <b class='ok'>dentro</b>",
        "Canon 1,30–1,55 · <b class='des'>fuera</b>"))

    v = r["bigonial_bizigomatica"]
    alto = v >= 0.87
    cal.append(_calibre(
        "Mandíbula frente a pómulos", "Cuánto se estrecha la cara hacia abajo",
        v, f"{v:.2f}".replace(".", ","), (0.65, 1.00), CANON["bigonial_bizigomatica"],
        "Canon 0,80–0,92 · <b class='ok'>" + ("en la parte alta" if alto else "dentro") + "</b>",
        "Canon 0,80–0,92 · <b class='des'>fuera</b>"))

    v = q["central"]
    dif = v - 20
    cal.append({**_calibre(
        "Quinto central", "Separación entre lagrimales sobre la anchura total",
        v, f"{v:.0f}%", (14.0, 26.0), CANON["quinto_central"],
        "Canon 20% · <b class='ok'>equilibrado</b>",
        f"Canon 20% · <b class='des'>{dif:+.0f} puntos</b>"),
        "contador": {"desde": 20, "hasta": round(v)}})

    v = r["nariz_intercantal"]
    cal.append(_calibre(
        "Nariz frente a lagrimales", "El canon clásico las quiere iguales",
        v, f"{v:.2f}".replace(".", ","), (0.80, 1.45), CANON["nariz_intercantal"],
        "Canon 1,00 · <b class='ok'>proporcionada</b>",
        f"Canon 1,00 · <b class='des'>{(v-1)*100:+.0f}%</b>"))

    desv = max(abs(x - 33.33) for x in t.values())
    cal.append(_calibre(
        "Reparto en tercios", "Frente / nariz / boca-mentón",
        33.33 + (desv if t["inferior"] > t["superior"] else -desv),
        "·".join(f"{t[k]:.0f}" for k in ("superior", "medio", "inferior")),
        (25.0, 42.0), CANON["tercio"],
        f"Desviación máx. {desv:.1f} pp · <b class='ok'>equilibrado</b>",
        f"Desviación máx. {desv:.1f} pp · <b class='des'>desigual</b>"))

    return cal
