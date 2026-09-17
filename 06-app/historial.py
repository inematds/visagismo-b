#!/usr/bin/env python3
"""
Historial de informes generados: una fila por generacion en Supabase, mas el
HTML del informe en Storage.

POR QUE EXISTE
--------------
El disco del contenedor de Vercel es efimero y por instancia: un informe
generado en una instancia no existe para las demas, y cuando el contenedor
escala a cero se va todo. Sin esto no hay forma de evaluar despues lo que el
motor ha ido produciendo.

QUE SE GUARDA Y QUE NO
----------------------
Se guardan DOS cosas distintas a proposito, porque tienen naturaleza distinta:

  1. La ficha de datos (medidas, morfotipo, receta, respuestas, coste, tiempo).
     Es texto, NO contiene la cara, y es lo que sirve para evaluar el motor.
     Se guarda siempre y sin plazo.

  2. El informe HTML, que lleva las fotos incrustadas como data URI.
     ESO SON FOTOS DE CARAS. Se guarda con fecha de caducidad (DIAS_HISTORIAL,
     90 por defecto) y se borra solo.

**El nombre del cliente no se guarda.** Para evaluar el motor no aporta nada y
es dato personal: se elimina de las respuestas antes de escribir la fila.

Las fotos originales NO se guardan salvo que se pida expresamente con
GUARDAR_FOTOS=si. Guardarlas permitiria volver a medir los casos viejos con el
motor nuevo (un banco de pruebas), pero es acumular un archivo de caras.

REGLA QUE NO SE ROMPE
---------------------
Nada de aqui puede tumbar la entrega de un informe. Si Supabase esta caido, el
cliente recibe su informe igual y el log lo dice. Ninguna funcion de este
modulo lanza excepciones hacia fuera.
"""

import json
import os
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# PRIVILEGIO MINIMO. La clave que viaja dentro del contenedor es la PUBLICA
# (anon), y las politicas de RLS solo le permiten INSERT en visagismo_informes
# y subir a su bucket: no puede leer ni los propios informes, ni ninguna otra
# tabla del ecosistema, ni descargar del bucket, ni borrar.
#
# La clave de SERVICIO nunca debe llegar a produccion: salta RLS y daria acceso
# a toda la base de datos (Skool, ads, miembros...) desde una demo publica.
# Aqui solo se usa si esta presente en local, y unicamente para purgar().
#
# Se admiten los nombres SKOOL_SUPABASE_* porque son los que ya viven en el
# .env.local del escritorio: asi no hace falta duplicar la misma clave.
TABLA = "visagismo_informes"
BUCKET = "visagismo-informes"

# ~0,15 $ por imagen generada (nano-banana-pro), ver simulacion.py
COSTE_IMAGEN = 0.15


def _env(*nombres, defecto=""):
    for n in nombres:
        v = os.environ.get(n)
        if v:
            return v.strip()
    return defecto


# La configuracion se lee EN CADA LLAMADA, no al importar el modulo.
# En Vercel da igual (las variables ya estan en el entorno del proceso), pero
# en local salen de .env.local, que servidor.py carga DESPUES de importar esto:
# leerlas al importar dejaba el historial apagado en silencio.
def URL():
    return _env("SUPABASE_URL", "SKOOL_SUPABASE_URL").rstrip("/")


def CLAVE():
    """La clave PUBLICA: es la que viaja a produccion y solo puede insertar."""
    return _env("SUPABASE_ANON_KEY", "SKOOL_SUPABASE_ANON_KEY")


def CLAVE_ADMIN():
    """La de servicio. Solo existe en local; nunca debe llegar a produccion."""
    return _env("SUPABASE_SERVICE_KEY", "SKOOL_SUPABASE_SERVICE_KEY")


def DIAS_HISTORIAL():
    """Dias que se conserva el HTML (lleva las fotos dentro). 0 = no guardarlo,
    solo la ficha de datos, que es la que no lleva cara."""
    try:
        return int(os.environ.get("DIAS_HISTORIAL") or 90)
    except ValueError:
        return 90


def GUARDAR_FOTOS():
    """Archivar tambien las fotos originales. Desactivado a proposito."""
    return _env("GUARDAR_FOTOS").lower() in ("1", "si", "sí", "true", "yes")


def activo():
    return bool(URL() and CLAVE())


def _peticion(metodo, ruta, cuerpo=None, tipo="application/json", cabeceras=None,
              clave=None):
    """Peticion cruda con urllib: el proyecto ya la usa y asi no entra ninguna
    dependencia nueva en una imagen que ya pesa 780 MB."""
    k = clave or CLAVE()
    pet = Request(f"{URL()}{ruta}", method=metodo)
    pet.add_header("apikey", k)
    pet.add_header("Authorization", f"Bearer {k}")
    pet.add_header("Content-Type", tipo)
    for k, v in (cabeceras or {}).items():
        pet.add_header(k, v)
    datos = cuerpo
    if isinstance(cuerpo, (dict, list)):
        datos = json.dumps(cuerpo, ensure_ascii=False, default=str).encode()
    with urlopen(pet, data=datos, timeout=30) as r:
        return r.status, r.read()


def _subir(ruta_destino, contenido, tipo):
    """Sin x-upsert a proposito: el upsert hace que Storage exija tambien
    permiso de UPDATE, y la clave de produccion solo tiene INSERT. No hace
    falta, porque cada ruta lleva el id de sesion y nunca colisiona."""
    estado, _ = _peticion("POST", f"/storage/v1/object/{BUCKET}/{ruta_destino}",
                          cuerpo=contenido, tipo=tipo)
    return estado in (200, 201)


def _verificacion(carpeta):
    """Lo que dijo el verificador de identidad, si llego a ejecutarse.

    carpeta puede ser None: los fallos (sin cara, formato invalido) se
    registran sin carpeta de sesion, y son justamente las filas mas valiosas
    para evaluar el motor.
    """
    if not carpeta:
        return {}
    f = Path(carpeta) / "verificacion.json"
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def guardar(sesion, carpeta, *, resultado, expediente="", datos=None,
            medidas=None, clasificacion=None, respuestas=None, html=None,
            segundos=None, tuvo_perfil=False, fotos=None, nota="", ia=None):
    """Escribe una fila del historial. Devuelve True si se guardo.

    Se llama TAMBIEN cuando algo falla (no se encontro cara, formato invalido):
    para evaluar el motor, los fallos son el dato mas valioso y hoy no dejaban
    ningun rastro.
    """
    if not activo():
        return False

    try:
        ver = _verificacion(carpeta)
        sim = (datos or {}).get("simulacion")
        n_imagenes = 0
        if sim:
            n_imagenes = 2 if sim.get("despues_perfil") else 1

        # El nombre fuera: dato personal que no aporta nada para evaluar.
        resp = dict(respuestas or {})
        resp.pop("nombre", None)

        fila = {
            "sesion": sesion,
            "expediente": expediente,
            "resultado": resultado,
            "morfotipo": (datos or {}).get("morfotipo"),
            "n_proporciones": (datos or {}).get("n_proporciones"),
            "n_fuera": (datos or {}).get("n_fuera"),
            "titular": " ".join((datos or {}).get("titular") or []) or None,
            "ratios": medidas,
            "clasificacion": clasificacion,
            "receta": (datos or {}).get("receta"),
            "respuestas": resp or None,
            "modelo_imagen": "fal-ai/nano-banana-pro/edit" if sim else None,
            "simulacion_ok": bool(sim),
            "desviacion": ver.get("desviacion_media_pct"),
            "tuvo_perfil": tuvo_perfil,
            "segundos": round(segundos, 1) if segundos else None,
            "coste_estimado": round(n_imagenes * COSTE_IMAGEN, 2) or None,
            "nota": nota or None,
        }

        # Del analisis con LLM se guarda el gasto y los estilos propuestos: es
        # como se vera si el modelo acaba repitiendo siempre los mismos cortes.
        if ia:
            meta = ia.get("_meta") or {}
            fila["analisis_ia"] = True
            fila["modelo_ia"] = meta.get("modelo")
            fila["tokens_ia"] = {"entrada": meta.get("tokens_entrada"),
                                 "salida": meta.get("tokens_salida"),
                                 "segundos": meta.get("segundos")}
            fila["estilos_ia"] = [{"nombre": e.get("nombre"), "encaje": e.get("encaje")}
                                  for e in (ia.get("estilos") or [])]
        elif resultado == "entregado":
            fila["analisis_ia"] = False

        # El HTML, con plazo. Si DIAS_HISTORIAL es 0 no se guarda: queda la
        # ficha de datos, que es lo que no lleva cara.
        dias = DIAS_HISTORIAL()
        if html and dias > 0:
            destino = f"{date.today().isoformat()}/{sesion}.html"
            if _subir(destino, html.encode("utf-8"), "text/html; charset=utf-8"):
                fila["informe_ruta"] = destino
                fila["informe_caduca"] = (
                    date.today() + timedelta(days=dias)).isoformat()

        if GUARDAR_FOTOS() and fotos:
            guardadas = {}
            for etiqueta, ruta in fotos.items():
                if not ruta or not Path(ruta).exists():
                    continue
                d = f"{date.today().isoformat()}/{sesion}-{etiqueta}{Path(ruta).suffix}"
                if _subir(d, Path(ruta).read_bytes(), "image/jpeg"):
                    guardadas[etiqueta] = d
            if guardadas:
                fila["fotos_ruta"] = guardadas

        _peticion("POST", f"/rest/v1/{TABLA}", cuerpo=fila,
                  cabeceras={"Prefer": "return=minimal"})
        print(f"[{sesion}] historial guardado ({resultado})", flush=True)
        return True

    except (HTTPError, URLError, OSError, ValueError, TypeError) as e:
        detalle = ""
        if isinstance(e, HTTPError):
            try:
                detalle = e.read().decode()[:300]
            except Exception:
                pass
        print(f"[{sesion}] historial NO guardado: {type(e).__name__}: {e} {detalle}",
              flush=True)
        return False


def purgar():
    """Borra del Storage los informes pasados de plazo y deja la ficha.

    NO la ejecuta el servidor: la clave de produccion no tiene permiso para
    leer ni borrar, y eso es deliberado. Se lanza desde el Mac, donde si esta
    la clave de servicio:

        ./venv/bin/python historial.py --purgar

    La fila se conserva (no lleva cara); lo que desaparece es el HTML con las
    fotos dentro.
    """
    admin = CLAVE_ADMIN()
    if not URL() or not admin:
        print("historial: purga omitida (hace falta la clave de servicio, "
              "que solo existe en local)", flush=True)
        return 0
    try:
        _, cuerpo = _peticion(
            "GET",
            f"/rest/v1/{TABLA}?select=id,informe_ruta"
            f"&informe_caduca=lt.{date.today().isoformat()}"
            f"&informe_ruta=not.is.null&limit=200", clave=admin)
        pendientes = json.loads(cuerpo)
        if not pendientes:
            return 0
        rutas = [p["informe_ruta"] for p in pendientes]
        _peticion("DELETE", f"/storage/v1/object/{BUCKET}",
                  cuerpo={"prefixes": rutas}, clave=admin)
        for p in pendientes:
            _peticion("PATCH", f"/rest/v1/{TABLA}?id=eq.{p['id']}",
                      cuerpo={"informe_ruta": None, "fotos_ruta": None,
                              "nota": "HTML borrado por plazo"},
                      cabeceras={"Prefer": "return=minimal"},
                      clave=admin)
        print(f"historial: {len(rutas)} informes borrados por plazo "
              f"(>{DIAS_HISTORIAL()} dias)", flush=True)
        return len(rutas)
    except (HTTPError, URLError, OSError, ValueError) as e:
        print(f"historial: purga fallida: {type(e).__name__}: {e}", flush=True)
        return 0


def resumen():
    """Imprime el estado del historial. Necesita la clave de servicio (local)."""
    admin = CLAVE_ADMIN()
    if not URL() or not admin:
        print("hace falta la clave de servicio (solo esta en local)")
        return
    def pide(vista):
        try:
            _, c = _peticion("GET", f"/rest/v1/{vista}?select=*", clave=admin)
            return json.loads(c)
        except (HTTPError, URLError, OSError, ValueError) as e:
            print(f"  error leyendo {vista}: {e}")
            return []

    f = (pide("visagismo_fiabilidad") or [{}])[0]
    print("\nFIABILIDAD DEL MOTOR")
    print(f"  intentos          : {f.get('intentos', 0)}")
    print(f"  informes ok       : {f.get('ok', 0)}")
    print(f"  sin cara          : {f.get('sin_cara', 0)}"
          f"  ({f.get('pct_sin_cara') or 0} %)")
    print(f"  errores internos  : {f.get('errores', 0)}")
    print(f"  ok sin simulacion : {f.get('sin_simulacion', 0)}")

    ia = pide("visagismo_uso_ia")
    if ia and ia[0].get("informes"):
        x = ia[0]
        print("\nANALISIS CON LLM")
        print(f"  informes con LLM  : {x.get('con_ia', 0)} de {x.get('informes', 0)}")
        print(f"  modelo            : {x.get('modelo') or '-'}")
        print(f"  tokens de media   : {x.get('tokens_medios') or 0} por informe")
        print(f"  segundos de media : {x.get('segundos_medios') or 0}")

    m = pide("visagismo_morfotipos")
    if m:
        print("\nMORFOTIPOS DETECTADOS")
        for x in m:
            print(f"  {x['morfotipo']:<14} {x['veces']:>4}  ({x['pct']} %)"
                  f"   fuera de canon: {x['media_fuera_de_canon']}")

    d = pide("visagismo_por_dia")
    if d:
        print("\nPOR DIA")
        print(f"  {'dia':<12}{'ok':>4}{'fallos':>8}{'seg':>7}{'coste':>8}{'desv%':>7}")
        for x in d[:14]:
            print(f"  {x['dia']:<12}{x['entregados']:>4}{x['fallos']:>8}"
                  f"{x['seg_medio'] or 0:>7}{x['coste_dia'] or 0:>8}"
                  f"{x['desviacion_media'] or 0:>7}")
    print()


if __name__ == "__main__":
    import sys
    if "--purgar" in sys.argv:
        purgar()
        raise SystemExit(0)
    if "--resumen" in sys.argv:
        resumen()
        raise SystemExit(0)
    # Comprobacion rapida: ./venv/bin/python historial.py
    print(f"URL      : {URL() or '(sin definir)'}")
    print(f"clave    : {'definida (publica)' if CLAVE() else 'SIN DEFINIR'}")
    print(f"admin    : {'definida (solo local)' if CLAVE_ADMIN() else 'no'}")
    print(f"activo   : {activo()}")
    print(f"plazo    : {DIAS_HISTORIAL()} dias" if DIAS_HISTORIAL() else "plazo    : no guardar HTML")
    print(f"fotos    : {'SI' if GUARDAR_FOTOS() else 'no'}")
    if activo():
        try:
            _, c = _peticion("GET", f"/rest/v1/{TABLA}?select=count", clave=CLAVE_ADMIN() or CLAVE())
            print(f"filas    : {json.loads(c)}")
        except Exception as e:
            print(f"filas    : error -> {e}")
