#!/usr/bin/env python3
"""
Analisis de visagismo con un LLM multimodal: le entran LAS FOTOS y LAS MEDIDAS,
y devuelve el analisis, entre uno y tres estilos recomendados, y el prompt de
imagen del que mejor le queda.

POR QUE FOTO **Y** MEDIDAS
--------------------------
Podria mandarse solo la foto. No se hace, y es la decision de diseno mas
importante de este fichero: el motor ya ha medido 16 proporciones con una
precision que ningun ojo alcanza (el quinto central al 24 % frente al 20 % del
canon, los tercios, el contorno mandibular). Si esos numeros no viajan con la
foto, el modelo los estima a ojo y el informe pierde lo unico que no se puede
copiar.

Van los dos: la foto aporta lo que un numero no ve (donde nace el pelo, la
densidad, si es liso u ondulado, como cae hoy, como crece la barba) y las
medidas aportan lo que la vista no mide. Y se le exige citar los numeros, para
que cada afirmacion del informe sea comprobable.

PROVEEDOR
---------
OpenAI (`OPENAI_API_KEY`). Se eligio por ser la clave mas comun de tener; tenia. Se llama por HTTP con urllib en vez de instalar un SDK, igual que hace el
resto del proyecto: la imagen del contenedor ya pesa 780 MB.

Cambiar a Claude seria sustituir solo `_llamar()`: el prompt, el esquema de
salida y todo lo demas son comunes.

SI FALLA, NO PASA NADA
----------------------
Sin clave, o si la llamada falla, `analizar()` devuelve None y el informe sale
con el motor de reglas de motor_recomendacion.py, que funciona por su cuenta.
Igual que la simulacion de imagen: se degrada, no se rompe.
"""

import base64
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from motor_recomendacion import CANON  # noqa: E402

MODELO_POR_DEFECTO = "gpt-5.5"   # verificado el 1-sep contra la cuenta:
ENDPOINT = "https://api.openai.com/v1/chat/completions"


def modelo():
    """Se lee en cada llamada, no al importar: servidor.py importa este modulo
    ANTES de cargar el .env.local, asi que leerlo arriba ignoraria MODELO_IA en
    local. Es el mismo fallo que ya hubo en historial.py."""
    return os.environ.get("MODELO_IA", "").strip() or MODELO_POR_DEFECTO


def activo():
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())


# ---------------------------------------------------------------------------
# Esquema de salida. Es lo que mantiene el informe ESTRUCTURADO en vez de un
# parrafo suelto: cada campo tiene su sitio en la plantilla.
#
# Sin minItems/maxItems ni minimum/maximum a proposito: el modo estricto de
# OpenAI no los admite. Los limites se aplican en Python al recibir.
# ---------------------------------------------------------------------------
ESQUEMA = {
    "type": "object",
    "properties": {
        "titular": {
            "type": "string",
            "description": "Frase corta con gancho que resume el hallazgo principal "
                           "de este rostro. Maximo 9 palabras.",
        },
        "diagnostico": {
            "type": "string",
            "description": "Que caracteriza a este rostro, en 3 a 5 frases. Cada "
                           "afirmacion sobre proporciones cita el numero medido "
                           "que la sostiene.",
        },
        "objetivo": {
            "type": "string",
            "description": "Que se busca conseguir con el corte, en 2 o 3 frases.",
        },
        # Estructurado como pares, no como texto: la plantilla del informe los
        # pinta uno por uno con su cruz roja. Un parrafo suelto no encajaria.
        "evitar": {
            "type": "array",
            "description": "Entre dos y cuatro cosas que NO le funcionan a este rostro.",
            "items": {
                "type": "object",
                "properties": {
                    "que": {"type": "string",
                            "description": "Que evitar, en una frase corta que "
                                           "termina en punto. Ej: 'Rapar la nuca alta.'"},
                    "por_que": {"type": "string",
                                "description": "Por que no le funciona A ESTE rostro, "
                                               "citando la medida concreta."},
                },
                "required": ["que", "por_que"],
                "additionalProperties": False,
            },
        },
        "estilos": {
            "type": "array",
            "description": "Entre uno y tres cortes, ordenados de mejor a peor encaje.",
            "items": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string",
                               "description": "Nombre del corte tal y como se pide "
                                              "en una barberia espanola."},
                    "por_que": {"type": "string",
                                "description": "Por que le funciona A ESTE rostro, "
                                               "citando la medida concreta."},
                    "como_pedirlo": {"type": "string",
                                     "description": "Instruccion para el barbero: largos "
                                                    "en cm, numero de maquina, degradado, "
                                                    "flequillo, patillas."},
                    "mantenimiento": {"type": "string",
                                      "description": "Cada cuanto hay que repasarlo y "
                                                     "cuanto tiempo pide por la manana."},
                    "encaje": {"type": "integer",
                               "description": "Lo bien que le encaja, de 1 a 10."},
                },
                "required": ["nombre", "por_que", "como_pedirlo",
                             "mantenimiento", "encaje"],
                "additionalProperties": False,
            },
        },
        "mejor": {
            "type": "integer",
            "description": "Indice (empezando en 0) del estilo de la lista que mejor "
                           "le queda. Normalmente 0.",
        },
        "prompt_imagen": {
            "type": "string",
            "description": "Prompt EN INGLES para un generador de imagen que edita la "
                           "foto del cliente y le pone el corte elegido. Describe solo "
                           "pelo y barba. Exige explicitamente conservar los rasgos, la "
                           "identidad, la forma de la cara y la mirada intactos.",
        },
    },
    "required": ["titular", "diagnostico", "objetivo", "evitar", "estilos",
                 "mejor", "prompt_imagen"],
    "additionalProperties": False,
}


SISTEMA = """\
Eres el barbero de referencia de una barberia espanola, con formacion en \
antropometria facial. Llevas veinte anos haciendo asesoria de imagen y has visto \
miles de caras. Escribes como hablas: directo, concreto, sin florituras.

COMO TRABAJAS

Mides antes de opinar. Cuando dices que un rostro es alargado, dices cuanto; \
cuando dices que la mandibula manda, dices el porcentaje. Recibes las medidas \
reales del rostro ya tomadas sobre la foto: usalas, citalas y apoyate en ellas. \
No estimes a ojo lo que ya viene medido.

Las fotos te sirven para lo que un numero no capta: donde nace el pelo, cuanta \
densidad tiene, si es liso u ondulado, como cae ahora, si hay retroceso en las \
sienes, como crece la barba. Eso tambien manda en la recomendacion.

REGLAS QUE NO ROMPES

1. Ninguna afirmacion sobre proporciones sin el numero que la respalda.
2. Nada de halagos vacios. Si algo no le favorece, se dice, con tacto y con el \
   motivo. Ha pagado por criterio, no por que le den la razon.
3. Nada de misticismo ni de proporcion aurea: es un mito desmentido. Trabajas \
   con antropometria y con oficio.
4. Nunca hables de personalidad, origen, etnia, edad, salud ni atractivo. Solo \
   geometria del rostro, pelo y barba.
5. Espanol de Espana, tuteando. Vocabulario de barberia real: degradado, \
   desfilado, entresacar, perfilado, numero de maquina, milimetros, centimetros.
6. Respeta lo que ha declarado en el formulario. Si dice que tiene dos minutos \
   por la manana, no le propongas nada que pida secador. Si dice que su barba \
   crece mal, no le propongas volumen donde no hay pelo.
7. Los estilos que propongas tienen que ser distintos entre si de verdad, no la \
   misma idea con tres nombres.
8. El prompt de imagen va en ingles, describe solo pelo y barba, y exige \
   conservar la identidad de la persona intacta.
"""


def _b64(ruta, ancho=900, calidad=82):
    """Reduce y codifica. Reducir importa: una foto de movil sin tocar gasta
    muchos tokens sin aportar ni un detalle util mas."""
    try:
        import cv2
        img = cv2.imread(str(ruta))
        if img is None:
            return None
        h, w = img.shape[:2]
        if w > ancho:
            img = cv2.resize(img, (ancho, int(h * ancho / w)),
                             interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, calidad])
        if not ok:
            return None
        return base64.standard_b64encode(buf.tobytes()).decode("ascii")
    except Exception:
        try:
            return base64.standard_b64encode(Path(ruta).read_bytes()).decode("ascii")
        except OSError:
            return None


def _tabla_medidas(medidas, clasificacion):
    """Las medidas en texto, cada una con su canon y si se sale. Que el modelo
    lea «0,96 (canon 0,80-0,92) POR ENCIMA» y no tenga que deducirlo."""
    filas = []
    for clave, valor in (medidas.get("ratios") or {}).items():
        if not isinstance(valor, (int, float)):
            continue
        rango = CANON.get(clave)
        if rango:
            lo, hi = rango
            estado = ("dentro del canon" if lo <= valor <= hi else
                      "POR ENCIMA del canon" if valor > hi else "POR DEBAJO del canon")
            filas.append(f"  - {clave}: {valor:.3f}  (canon {lo}-{hi})  -> {estado}")
        else:
            filas.append(f"  - {clave}: {valor:.3f}")

    t = medidas.get("tercios_pct") or {}
    if t:
        filas.append(
            f"  - tercios verticales: superior {t.get('superior', 0):.1f}%, "
            f"medio {t.get('medio', 0):.1f}%, inferior {t.get('inferior', 0):.1f}% "
            f"(el reparto equilibrado es 33% cada uno)")
    q = medidas.get("quintos_pct") or {}
    if q.get("central"):
        lo, hi = CANON["quinto_central"]
        filas.append(f"  - quinto central: {q['central']:.1f}% (canon {lo}-{hi}%)")

    forma = ((clasificacion or {}).get("morfotipo") or {}).get("forma")
    if forma:
        filas.append(f"  - morfotipo que calcula el motor por reglas: {forma}")
    return "\n".join(filas)


def _formulario(respuestas):
    r = respuestas or {}
    def txt(v):
        return ", ".join(v) if isinstance(v, list) else str(v)
    lineas = [
        f"  - quiere transmitir: {txt(r.get('transmitir')) or 'no lo dice'}",
        f"  - estilos que le gustan: {txt(r.get('estilos')) or 'no lo dice'}",
        f"  - minutos que dedica por la manana: {r.get('minutos', 'no lo dice')}",
        f"  - barba: {r.get('barba', 'no lo dice')}",
        f"  - cuello: {r.get('cuello', 'no lo dice')}",
    ]
    if (r.get("menos_favorita") or "").strip():
        lineas.append(f"  - lo que menos le gusta de su cara: "
                      f"{r['menos_favorita'].strip()}")
    return "\n".join(lineas)


def _llamar(mensajes, tiempo_limite=180):
    """La unica parte atada al proveedor. Cambiar de LLM es cambiar esto."""
    cuerpo = {
        "model": modelo(),
        "messages": mensajes,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "informe_visagismo", "strict": True,
                            "schema": ESQUEMA},
        },
    }
    pet = Request(ENDPOINT, method="POST",
                  data=json.dumps(cuerpo, ensure_ascii=False).encode("utf-8"))
    pet.add_header("Authorization", f"Bearer {os.environ['OPENAI_API_KEY'].strip()}")
    pet.add_header("Content-Type", "application/json")
    with urlopen(pet, timeout=tiempo_limite) as r:
        return json.load(r)


def analizar(frontal, perfil, medidas, clasificacion, respuestas,
             receta_reglas=None):
    """Devuelve el analisis del modelo, o None si no se puede.

    NUNCA lanza: el informe tiene que salir aunque esto falle.
    """
    if not activo():
        return None

    img_f = _b64(frontal)
    if not img_f:
        print("  analisis IA: no se pudo leer la foto frontal", flush=True)
        return None

    contenido = [{"type": "image_url",
                  "image_url": {"url": f"data:image/jpeg;base64,{img_f}"}}]
    img_p = _b64(perfil) if perfil else None
    if img_p:
        contenido.append({"type": "image_url",
                          "image_url": {"url": f"data:image/jpeg;base64,{img_p}"}})

    ref = ""
    if receta_reglas:
        ref = ("\nLo que propone el motor de reglas de la casa, como referencia. "
               "Puedes apartarte de esto si las fotos te dicen otra cosa, pero "
               "entonces explica por que en el diagnostico:\n"
               f"  - forma: {receta_reglas.get('forma')}\n"
               f"  - largo arriba: {receta_reglas.get('largo_cm')} cm\n"
               f"  - flequillo: {(receta_reglas.get('flequillo') or [''])[0]}\n"
               f"  - laterales: {(receta_reglas.get('laterales') or [''])[0]}\n")

    contenido.append({"type": "text", "text": f"""\
{'Tienes dos fotos: la primera de frente y la segunda de perfil.' if img_p
 else 'Tienes una foto de frente.'}

MEDIDAS REALES DE ESTE ROSTRO, ya tomadas sobre la foto con 468 puntos
faciales. Estas son las que tienes que citar:

{_tabla_medidas(medidas, clasificacion)}

LO QUE HA CONTESTADO EL CLIENTE EN EL FORMULARIO:

{_formulario(respuestas)}
{ref}
Haz el analisis de visagismo de este rostro y propon entre uno y tres cortes que
le funcionen de verdad, ordenados de mejor a peor encaje. Para el mejor, escribe
tambien el prompt en ingles con el que un generador de imagen le pondra ese corte
sobre su propia foto, conservando su identidad intacta."""})

    mensajes = [{"role": "system", "content": SISTEMA},
                {"role": "user", "content": contenido}]

    arranque = time.time()
    try:
        bruto = _llamar(mensajes)
    except HTTPError as e:
        detalle = ""
        try:
            detalle = e.read().decode()[:300]
        except Exception:
            pass
        print(f"  analisis IA: HTTP {e.code} {detalle}", flush=True)
        return None
    except (URLError, OSError, ValueError) as e:
        print(f"  analisis IA: fallo -> {type(e).__name__}: {e}", flush=True)
        return None

    try:
        eleccion = bruto["choices"][0]
        if eleccion.get("finish_reason") == "length":
            print("  analisis IA: respuesta cortada por longitud", flush=True)
            return None
        datos = json.loads(eleccion["message"]["content"])
    except (KeyError, IndexError, TypeError, ValueError) as e:
        print(f"  analisis IA: respuesta ilegible -> {type(e).__name__}: {e}",
              flush=True)
        return None

    # --- Limites que el modo estricto no puede expresar, aplicados aqui -----
    estilos = [e for e in (datos.get("estilos") or []) if e.get("nombre")]
    if not estilos:
        print("  analisis IA: no ha propuesto ningun estilo", flush=True)
        return None
    estilos = estilos[:3]
    for e in estilos:
        try:
            e["encaje"] = max(1, min(int(e.get("encaje", 5)), 10))
        except (TypeError, ValueError):
            e["encaje"] = 5
    datos["estilos"] = estilos

    # `evitar` llega como pares; se descartan los incompletos y se acota a cuatro.
    datos["evitar"] = [e for e in (datos.get("evitar") or [])
                       if (e.get("que") or "").strip()
                       and (e.get("por_que") or "").strip()][:4]
    try:
        datos["mejor"] = max(0, min(int(datos.get("mejor", 0)), len(estilos) - 1))
    except (TypeError, ValueError):
        datos["mejor"] = 0

    uso = bruto.get("usage") or {}
    datos["_meta"] = {
        "modelo": modelo(),
        "tokens_entrada": uso.get("prompt_tokens"),
        "tokens_salida": uso.get("completion_tokens"),
        "segundos": round(time.time() - arranque, 1),
        "con_perfil": bool(img_p),
    }
    print(f"  analisis IA: {len(estilos)} estilos · {modelo()} · "
          f"{uso.get('prompt_tokens')} tokens entrada, "
          f"{uso.get('completion_tokens')} salida · "
          f"{datos['_meta']['segundos']} s", flush=True)
    return datos


if __name__ == "__main__":
    import sys
    print(f"modelo : {modelo()}")
    print(f"clave  : {'definida' if activo() else 'SIN DEFINIR (se usan las reglas)'}")
    if len(sys.argv) > 1:
        # Prueba rapida:  python3 analisis_ia.py foto-frontal.jpg [perfil.jpg]
        m = {"ratios": {"indice_facial": 1.42, "bigonial_bizigomatica": 0.89,
                        "bitemporal_bizigomatica": 0.88, "nariz_intercantal": 1.18},
             "tercios_pct": {"superior": 32.0, "medio": 34.0, "inferior": 34.0},
             "quintos_pct": {"central": 24.0}}
        r = analizar(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None, m,
                     {"morfotipo": {"forma": "ovalada"}},
                     {"minutos": 5, "barba": "si", "cuello": "medio",
                      "transmitir": ["cercania"], "estilos": []})
        print(json.dumps(r, ensure_ascii=False, indent=2) if r else "sin resultado")
