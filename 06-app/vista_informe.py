#!/usr/bin/env python3
"""
Adapta los textos al formato EXACTO que espera la plantilla del informe.

POR QUE EXISTE ESTE FICHERO
---------------------------
Los textos pueden venir de dos sitios con formas distintas:

    campo        motor de reglas          LLM
    ---------    ----------------------   -------------------------
    titular      dict linea1/enfasis/..   string
    diagnostico  lista de parrafos        string
    objetivo     lista de parrafos        string
    evitar       lista de (que, por_que)  lista de {que, por_que}

La plantilla espera SIEMPRE la forma del motor de reglas. Cada desajuste dio un
error distinto y ninguno se vio hasta produccion: un string iterado letra a
letra, un `too many values to unpack`, y un 500 con
`string indices must be integers`.

Estaban dentro de servidor.py, que no se puede importar sin mediapipe, asi que
no habia forma de probarlos. Aqui no dependen de nada: `prueba_informe.py` los
recorre con las dos procedencias y comprueba que las dos salidas encajan.

Sin dependencias a proposito. Solo `re`.
"""

import re


def parrafos(texto, por_parrafo=2):
    """Normaliza a lista de parrafos. Acepta lista (se deja) o texto (se parte).

    Sin esto, la plantilla —que hace `{% for p in diagnostico %}`— recorreria
    un string CARACTER A CARACTER y pintaria un <p> por letra.
    """
    if not texto:
        return []
    if isinstance(texto, (list, tuple)):
        return [t for t in texto if t]

    texto = str(texto).strip()
    sueltos = [b.strip() for b in texto.split("\n\n") if b.strip()]
    if len(sueltos) > 1:
        return sueltos

    # Se parte SOLO en puntuacion + espacio + mayuscula. Partir por cualquier
    # punto rompia los decimales: "indice facial 1.453" salia como "1." y "453".
    frases = [f.strip() for f in
              re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÜÑ¿¡])", texto) if f.strip()]
    if len(frases) <= por_parrafo:
        return [texto]
    return [" ".join(frases[i:i + por_parrafo])
            for i in range(0, len(frases), por_parrafo)]


def titular(t):
    """Devuelve el titular partido en linea1 / antes / enfasis / despues.

    El motor de reglas da un dict con linea1, linea2 y el fragmento a resaltar.
    El LLM da una frase suelta: se parte por la mitad de las palabras y la
    segunda mitad va como enfasis, que es lo que la plantilla resalta.
    """
    if not t:
        return {"linea1": "", "antes": "", "enfasis": "", "despues": ""}

    if isinstance(t, dict):
        linea2, enfasis = t.get("linea2", ""), t.get("enfasis", "")
        if enfasis and enfasis in linea2:
            i = linea2.index(enfasis)
            return {"linea1": t.get("linea1", ""), "antes": linea2[:i],
                    "enfasis": enfasis, "despues": linea2[i + len(enfasis):]}
        return {"linea1": t.get("linea1", ""), "antes": linea2,
                "enfasis": "", "despues": ""}

    # Texto suelto: se reparte en dos lineas por palabras, no por caracteres,
    # para no cortar ninguna.
    palabras = str(t).strip().rstrip(".").split()
    if not palabras:
        return {"linea1": "", "antes": "", "enfasis": "", "despues": ""}
    if len(palabras) <= 3:
        return {"linea1": "", "antes": "", "enfasis": " ".join(palabras),
                "despues": ""}
    corte = (len(palabras) + 1) // 2
    return {"linea1": " ".join(palabras[:corte]), "antes": "",
            "enfasis": " ".join(palabras[corte:]), "despues": ""}


def evitar(lista):
    """Normaliza a lista de pares (que, por_que), que es lo que la plantilla
    desempaqueta con `{% for titulo, razon in evitar %}`.

    El motor de reglas ya da tuplas; el LLM da diccionarios.
    """
    fuera = []
    for e in (lista or []):
        if isinstance(e, dict):
            que, por_que = (e.get("que") or "").strip(), (e.get("por_que") or "").strip()
        elif isinstance(e, (list, tuple)) and len(e) >= 2:
            que, por_que = str(e[0]).strip(), str(e[1]).strip()
        else:
            continue
        if que and por_que:
            fuera.append((que, por_que))
    return fuera


def textos(ia, reglas):
    """Los cuatro bloques de texto del informe, vengan de donde vengan.

    `ia` es lo que devolvio el LLM (o None) y `reglas` es `analizar()["textos"]`.
    Campo a campo gana el LLM si lo trae, y si no las reglas: asi un LLM que
    devuelve medio informe no deja huecos.
    """
    ia = ia or {}
    reglas = reglas or {}
    return {
        "titular": titular(ia.get("titular") or reglas.get("titular")),
        "diagnostico": parrafos(ia.get("diagnostico") or reglas.get("diagnostico")),
        "objetivo": parrafos(ia.get("objetivo") or reglas.get("objetivo")),
        "evitar": evitar(ia.get("evitar") or reglas.get("evitar")),
    }
