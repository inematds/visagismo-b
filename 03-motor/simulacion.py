#!/usr/bin/env python3
"""
Simulacion del "despues": la cara del cliente con el corte propuesto.

Dos reglas que no se negocian:

  1. El prompt se construye desde la RECETA medida, no a mano. Si el informe
     dice 5-7 cm y degradado bajo, la imagen pide 5-7 cm y degradado bajo.
  2. La imagen generada pasa por el VERIFICADOR: se remide la cara sintetica
     y se compara con la real. Si el modelo ha "embellecido" el rasgo que el
     informe diagnostica, se descarta. Sin esto el informe se contradice solo.

Proveedor: fal.ai (clave en FAL_KEY). Procesa fuera de la UE: para produccion
hay que resolver la transferencia internacional antes de encenderlo con
clientes reales. Ver blueprint §9.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

MODELO = "fal-ai/nano-banana-pro/edit"

# Elegido el 31-ago comparando contra fal-ai/nano-banana/edit sobre la misma
# foto y el mismo prompt, midiendo el resultado con el propio verificador:
#
#   nano-banana-pro   desviacion media 1,14 %   max 3,67 %   ~0,15 $/img
#   nano-banana       desviacion media 1,67 %   max 5,11 %   ~0,04 $/img
#
# Y ademas obedecio mejor el brief: la version barata seguia poniendo flequillo
# sobre las cejas. Se paga la diferencia porque esta es la imagen que vende.
#
# AVISO: n=1 (una sola cara). Antes de fijarlo como decision de producto hay que
# repetir la comparacion con 20-30 rostros variados.

BASE_IDENTIDAD = (
    "Edit ONLY the hair and the beard of this man. Preserve his facial identity "
    "with absolute fidelity: identical face shape, identical eyes and eyebrows, "
    "identical nose shape and size, identical mouth, identical skin texture and "
    "pores, identical expression, identical lighting, identical background, "
    "identical clothing and camera angle. Do NOT slim the face, do NOT reshape "
    "or narrow the nose, do NOT beautify or smooth the skin. "
)


# La receta se escribe en espanol para el informe; el generador entiende
# mejor el ingles. Se traduce aqui en vez de duplicar la receta.
FORMA_EN = {
    "media longitud texturizada con caída frontal":
        "medium-length textured crop with a forward-falling front",
    "volumen alto con raíz levantada":
        "high-volume style with lifted roots",
    "longitud corta-media, pulida":
        "short-to-medium polished cut",
    "media longitud, versión corta y de caída natural":
        "medium-length cut in its shorter version, falling naturally",
}

BARBA_EN = {
    "uniforme, que disimula las zonas de menor densidad":
        "even, blending the patchier areas",
    "algo más de cuerpo en el mentón para dar estructura":
        "with a little more body at the chin to build structure",
    "uniforme, laterales contenidos, algo más de presencia en el mentón":
        "even, with contained sides and slightly more presence at the chin",
    "uniforme y bien perfilada": "even and cleanly outlined",
}

LINEAS_EN = {
    "sin intentar volumen donde no crece": "without forcing volume where it does not grow",
    "línea de mejilla marcada y recta": "with a defined straight cheek line",
    "línea de mejilla limpia respetando su altura natural; nunca ancha ni cuadrada":
        "clean cheek line at its natural height, never wide or square",
    "líneas de mejilla y cuello definidas": "with defined cheek and neck lines",
}


def _cm(par):
    return f"{par[0]}-{par[1]} cm"


def construir_prompt(receta, vista="frontal"):
    """Traduce la receta medida a instrucciones para el generador."""
    partes = [BASE_IDENTIDAD]

    pelo = (
        f"HAIR: give him a {FORMA_EN.get(receta['forma'], receta['forma'])}, "
        f"approximately {_cm(receta['largo_cm'])} "
        f"on top, with visible volume and movement. The front section is "
        f"{_cm(receta['frontal_cm'])} long and falls slightly forward and to one "
        f"side in irregular separated strands. The forehead stays visible: "
        f"the front strands must NEVER cover the eyebrows and this is NOT a "
        f"fringe or curtain haircut. Keep the hairline visible. "
    )
    if "NO_FRENTE_DESPEJADA" in receta["directivas"]:
        pelo += "Never a straight fringe, never slicked back, never rigid. "
    if "NO_ESTRECHAR_LATERALES" in receta["directivas"]:
        pelo += ("Sides keep their density with a soft low taper, never a high "
                 "skin fade and never shaved to the skin. ")
    else:
        pelo += "Sides with a clean, controlled taper. "
    if "NO_NUCA_ALTA" in receta["directivas"]:
        pelo += "The nape stays natural with some length, not shaved high. "
    partes.append(pelo)

    if receta.get("barba"):
        largo, cuerpo, lineas = receta["barba"]
        partes.append(
            f"BEARD: short, evenly trimmed beard at roughly {largo}, "
            f"{BARBA_EN.get(cuerpo, cuerpo)}, {LINEAS_EN.get(lineas, lineas)}. "
        )
    else:
        partes.append("BEARD: keep him clean shaven, exactly as in the photo. ")

    if vista == "perfil":
        partes.append(
            "This is a SIDE PROFILE photograph. Keep the exact same head angle "
            "and the same side of the face visible. The nose profile, the chin "
            "projection and the ear must remain identical. "
        )

    partes.append(
        "Photorealistic result, natural light, same framing as the original photograph."
    )
    return "".join(partes)


def envolver_prompt(prompt_ia, vista="frontal"):
    """Envuelve el prompt del LLM con lo que no es negociable.

    El modelo de imagen embellece si se le deja, y el informe se contradice si
    la imagen arregla lo que el texto dice compensar. Por eso la instruccion de
    conservar la identidad va delante SIEMPRE, escrita por nosotros, y la
    coletilla de perfil la ponemos nosotros y no el LLM.
    """
    partes = [BASE_IDENTIDAD, prompt_ia.strip(), " "]
    if vista == "perfil":
        partes.append(
            "This is a SIDE PROFILE photograph. Keep the exact same head angle "
            "and the same side of the face visible. The nose profile, the chin "
            "projection and the ear must remain identical. ")
    partes.append(
        "Photorealistic result, natural light, same framing as the original photograph.")
    return "".join(partes)


ANCHO_ENVIO = 900     # suficiente para que el modelo trabaje bien
CALIDAD_ENVIO = 90


class SinSaldo(RuntimeError):
    """La cuenta del generador se ha quedado sin saldo."""


def _data_uri(ruta):
    """La foto viaja embebida en la peticion, no subida a su almacenamiento.

    Es deliberado: asi la imagen del cliente no queda alojada en un servidor
    de terceros fuera de la UE esperando a caducar. Solo se procesa y se
    descarta con la peticion.
    """
    import base64
    import cv2

    img = cv2.imread(str(ruta))
    if img is None:
        raise RuntimeError(f"No se pudo leer {ruta}")
    if img.shape[1] > ANCHO_ENVIO:
        alto = int(img.shape[0] * ANCHO_ENVIO / img.shape[1])
        img = cv2.resize(img, (ANCHO_ENVIO, alto), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, CALIDAD_ENVIO])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


def generar(ruta_foto, receta, vista="frontal", prompt_ia=None):
    """Genera la variante y devuelve la URL del resultado.

    `prompt_ia` es el prompt que ha escrito el LLM para el estilo que ha
    elegido. Si viene, sustituye a la descripcion derivada de la receta, pero
    NO sustituye a BASE_IDENTIDAD ni a la coletilla de perfil: esas se anaden
    siempre por encima, porque son las que sostienen al verificador de
    identidad y no pueden depender de lo que redacte un modelo.
    """
    import fal_client

    if not os.environ.get("FAL_KEY"):
        raise RuntimeError("Falta FAL_KEY en el entorno.")

    url_entrada = _data_uri(ruta_foto)

    try:
        resultado = _pedir(fal_client, url_entrada, receta, vista, prompt_ia)
    except Exception as e:
        if "Exhausted balance" in str(e) or "User is locked" in str(e):
            raise SinSaldo(
                "La cuenta de fal.ai se ha quedado sin saldo. El informe se "
                "genera igual, pero sin simulación."
            ) from e
        raise
    imagenes = resultado.get("images") or []
    if not imagenes:
        raise RuntimeError(f"El generador no devolvio ninguna imagen: {resultado}")
    return imagenes[0]["url"]


def _pedir(fal_client, url_entrada, receta, vista, prompt_ia=None):
    return fal_client.subscribe(
        MODELO,
        arguments={
            "prompt": (envolver_prompt(prompt_ia, vista) if prompt_ia
                       else construir_prompt(receta, vista)),
            "image_urls": [url_entrada],
            "num_images": 1,
            "output_format": "jpeg",
        },
        with_logs=False,
    )


def verificar(ruta_original, ruta_generada, umbral_medio=3.0, umbral_max=6.0):
    """Remide la cara generada y la compara con la real.

    Devuelve (aprobada, informe). Si el modelo ha retocado la geometria por
    encima del umbral, la simulacion NO debe publicarse: contradiria al texto.
    """
    from analiza_rostro import detectar, medir

    claves = ["indice_facial", "bigonial_bizigomatica", "bitemporal_bizigomatica",
              "nariz_intercantal", "nariz_bizigomatica", "boca_nariz"]
    try:
        _, P1, _, _ = detectar(ruta_original)
        _, P2, _, _ = detectar(ruta_generada)
    except SystemExit as e:
        return False, {"error": f"no se pudo medir una de las dos caras: {e}"}

    r1, r2 = medir(P1)["ratios"], medir(P2)["ratios"]
    desvios = {k: abs(100 * (r2[k] - r1[k]) / r1[k]) for k in claves}
    medio = sum(desvios.values()) / len(desvios)
    maximo = max(desvios.values())
    peor = max(desvios, key=desvios.get)

    aprobada = medio <= umbral_medio and maximo <= umbral_max
    return aprobada, {
        "desviacion_media_pct": round(medio, 2),
        "desviacion_maxima_pct": round(maximo, 2),
        "metrica_peor": peor,
        "detalle": {k: round(v, 2) for k, v in desvios.items()},
        "umbrales": {"medio": umbral_medio, "maximo": umbral_max},
    }
