#!/usr/bin/env python3
"""
Demo comercial completa del analisis de visagismo, de punta a punta:

    landing  ->  pago (simulado)  ->  cuestionario + fotos  ->  informe real

No es el flujo definitivo del producto (ese pasara por WhatsApp y por la
revision del barbero antes de entregar). Esta version existe para ENSENARLO:
el cliente potencial sube sus fotos, contesta, y recibe su informe de verdad,
medido sobre su cara, en menos de un minuto.

Lo unico simulado es el cobro. Todo lo demas es el motor real.

    ./venv/bin/uvicorn servidor:app --reload --port 8000
"""

import base64
import hashlib
import hmac
import json
import traceback
import os
import re
import shutil
import sys
import uuid
import time
from datetime import date, timedelta
from urllib.request import urlopen
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

def _cargar_env():
    """Carga TODOS los .env.local del arbol, del mas cercano al mas lejano.

    Acumula en vez de parar en el primero a proposito: `vercel link` deja un
    .env.local propio en la raiz del proyecto que no contiene FAL_KEY, y
    pararse ahi dejaba el generador de imagen sin clave en local.
    `setdefault` hace que gane el mas cercano y que las variables ya
    definidas en el entorno (las de produccion) tengan prioridad sobre todo.
    """
    aqui = Path(__file__).resolve()
    encontrados = []
    for carpeta in [aqui.parent, *aqui.parents]:
        env = carpeta / ".env.local"
        if not env.exists():
            continue
        for linea in env.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))
        encontrados.append(env)
    return encontrados[0] if encontrados else None


RAIZ = Path(__file__).resolve().parent
MOTOR = RAIZ.parent / "03-motor"
ESTATICO = RAIZ / "estatico"
SESIONES = RAIZ / "sesiones"
sys.path.insert(0, str(MOTOR))

from analiza_rostro import detectar, medir, clasificar          # noqa: E402
from exporta_geometria import recortar, geometria               # noqa: E402
from motor_recomendacion import analizar                        # noqa: E402
import calibres as mod_calibres                                 # noqa: E402
import render_informe                                           # noqa: E402
import simulacion                                               # noqa: E402

import analisis_ia                                             # noqa: E402
import historial                                                # noqa: E402
import vista_informe                                          # noqa: E402

import cv2                                                      # noqa: E402

_env = _cargar_env()
# Se dice en el arranque porque un historial apagado no da ningun sintoma: los
# informes se entregan igual y no se guarda nada. Esta linea es la unica forma
# de verlo sin generar un informe.
_hist = "DESACTIVADO"
if historial.activo():
    _hist = (f"activo (plazo {historial.DIAS_HISTORIAL()} d"
             f"{', con fotos' if historial.GUARDAR_FOTOS() else ''})")
print(f"entorno: {'cargado de ' + str(_env) if _env else 'sin .env.local'} · "
      f"generador de imagen: {'activo' if os.environ.get('FAL_KEY') else 'DESACTIVADO'} · "
      f"historial: {_hist} · "
      f"analisis IA: {analisis_ia.modelo() if analisis_ia.activo() else 'DESACTIVADO'}")

app = FastAPI(title="Visagismo · demo")


@app.middleware("http")
async def compuerta(request: Request, siguiente):
    """La clave se comprueba aqui, una sola vez, para TODAS las rutas. Ponerla
    ruta por ruta es lo que hace que un dia se anada una nueva y se olvide."""
    if request.url.path in LIBRES or _tiene_acceso(request):
        return await siguiente(request)
    # Ojo: aqui hay que DEVOLVER la respuesta, no lanzar HTTPException. Los
    # manejadores de error de FastAPI cuelgan del router, que va por dentro de
    # este middleware: una excepcion lanzada aqui sube por encima y sale como
    # un 500 sin capturar. Un POST sin clave (p. ej. /generar) recibe la misma
    # pantalla, que es lo util si la cookie caduco con el formulario abierto.
    return HTMLResponse(_pagina_clave(), status_code=401, headers=SIN_INDEXAR)


# Sin esto, cualquier fallo llega al cliente como un JSON crudo
# ({"detail": "..."}), que en una demo comercial queda fatal.
@app.exception_handler(StarletteHTTPException)
@app.exception_handler(HTTPException)
async def error_bonito(request: Request, exc: HTTPException):
    return HTMLResponse(_pagina_error(exc.status_code, exc.detail),
                        status_code=exc.status_code, headers=SIN_INDEXAR)


@app.exception_handler(Exception)
async def error_inesperado(request: Request, exc: Exception):
    traceback.print_exc()
    # Un 500 tambien va al historial. El primero que hubo no dejo ningun rastro
    # ahi: solo se supo por los logs de Vercel, y los logs caducan. Con esto,
    # `historial.py --resumen` los cuenta como lo que son, fallos del sistema.
    try:
        historial.guardar(f"err{uuid.uuid4().hex[:9]}", None, resultado="error-interno",
                          nota=f"{type(exc).__name__}: {exc} · {request.url.path}"[:400])
    except Exception:
        pass
    return HTMLResponse(_pagina_error(
        500, "Algo ha fallado por nuestra parte. Vuelve a intentarlo en un momento."),
        status_code=500, headers=SIN_INDEXAR)


TITULARES = {
    400: "No hemos podido con esa foto",
    413: "Esas fotos pesan demasiado",
    422: "No hemos podido con esa foto",
    404: "Aquí no hay nada",
    429: "Hemos llegado al límite de hoy",
    500: "Se nos ha ido la mano",
}


def _pagina_error(codigo, mensaje):
    volver = "/formulario" if codigo in (400, 413, 422) else "/"
    etiqueta = "Volver a intentarlo" if volver == "/formulario" else "Volver al inicio"
    titular = TITULARES.get(codigo, "Algo no ha ido bien")
    return f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Barbería Demo</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,700&family=Archivo:wght@400;600;700&display=swap">
<style>
  body{{margin:0;min-height:100vh;background:#F4F1EC;color:#14181F;
    font-family:Archivo,system-ui,sans-serif;display:flex;align-items:center;
    justify-content:center;padding:28px}}
  .caja{{max-width:440px;text-align:center}}
  .poste{{width:14px;height:56px;margin:0 auto 26px;border-radius:7px;
    background:repeating-linear-gradient(155deg,#C2102E 0 7px,#fff 7px 14px,
      #16386B 14px 21px,#fff 21px 28px);background-size:100% 28px;
    box-shadow:inset 0 0 0 1px rgba(20,24,31,.2);animation:g 2.6s linear infinite}}
  @keyframes g{{to{{background-position:0 -28px}}}}
  h1{{font-family:"Bricolage Grotesque",Archivo,sans-serif;font-size:26px;
    margin:0 0 12px;letter-spacing:-.01em}}
  p{{margin:0 0 26px;font-size:16px;line-height:1.6;color:#4A5361}}
  a{{display:inline-block;background:#C2102E;color:#fff;text-decoration:none;
    padding:15px 28px;border-radius:999px;font-weight:700;font-size:15px}}
  small{{display:block;margin-top:22px;font-size:11px;color:#7C8697;letter-spacing:.1em}}
</style>
<div class="caja">
  <div class="poste"></div>
  <h1>{titular}</h1>
  <p>{mensaje}</p>
  <a href="{volver}">{etiqueta}</a>
  <small>BARBERÍA DEMO · ERROR {codigo}</small>
</div>"""

def _pagina_clave(fallo=False):
    aviso = ('<p class="mal">Esa clave no es. Vuelve a probar.</p>' if fallo
             else '<p>Esta demo no es publica todavia. Pon la clave para entrar.</p>')
    return f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Barbería Demo</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,700&family=Archivo:wght@400;600;700&display=swap">
<style>
  body{{margin:0;min-height:100vh;background:#F4F1EC;color:#14181F;
    font-family:Archivo,system-ui,sans-serif;display:flex;align-items:center;
    justify-content:center;padding:28px}}
  .caja{{max-width:400px;width:100%;text-align:center}}
  .poste{{width:14px;height:56px;margin:0 auto 26px;border-radius:7px;
    background:repeating-linear-gradient(155deg,#C2102E 0 7px,#fff 7px 14px,
      #16386B 14px 21px,#fff 21px 28px);background-size:100% 28px;
    box-shadow:inset 0 0 0 1px rgba(20,24,31,.2);animation:g 2.6s linear infinite}}
  @keyframes g{{to{{background-position:0 -28px}}}}
  h1{{font-family:"Bricolage Grotesque",Archivo,sans-serif;font-size:26px;
    margin:0 0 12px;letter-spacing:-.01em}}
  p{{margin:0 0 24px;font-size:16px;line-height:1.6;color:#4A5361}}
  p.mal{{color:#C2102E;font-weight:600}}
  form{{display:flex;flex-direction:column;gap:12px}}
  input{{font-family:inherit;font-size:22px;text-align:center;letter-spacing:.5em;
    padding:16px 14px;border:2px solid #D5CFC1;border-radius:12px;
    background:#fff;color:#14181F;width:100%;box-sizing:border-box}}
  input:focus{{outline:none;border-color:#16386B}}
  button{{font-family:inherit;background:#C2102E;color:#fff;border:0;cursor:pointer;
    padding:16px 28px;border-radius:999px;font-weight:700;font-size:15px}}
  small{{display:block;margin-top:22px;font-size:11px;color:#7C8697;letter-spacing:.1em}}
</style>
<div class="caja">
  <div class="poste"></div>
  <h1>Acceso reservado</h1>
  {aviso}
  <form method="post" action="/clave">
    <input name="clave" type="password" inputmode="numeric" autocomplete="off"
           autofocus required aria-label="Clave de acceso">
    <button type="submit">Entrar</button>
  </form>
  <small>BARBERÍA DEMO · DEMO PRIVADA</small>
</div>"""


BARBERIA = {"nombre": "BARBERÍA DEMO", "ciudad": "Tu Ciudad", "barbero": "Tu Barbero"}
MESES = ["ene", "feb", "mar", "abr", "may", "jun",
         "jul", "ago", "sep", "oct", "nov", "dic"]

# Formatos de imagen que aceptamos en el formulario.
EXT_OK = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
MAX_BYTES = 12 * 1024 * 1024

# --- Proteccion de una demo publica -----------------------------------------
# Tope de informes al dia. Viene desactivado; el
# mecanismo se conserva porque cada informe con las dos vistas cuesta ~0,30 EUR
# en el generador de imagen. Para encenderlo basta con definir LIMITE_DIARIO.
LIMITE_DIARIO = int(os.environ.get("LIMITE_DIARIO", "0"))  # 0 = sin tope

# Son fotos de caras: en una demo no hay ninguna razon para conservarlas.
# Se borran solas al cabo de unas horas.
HORAS_RETENCION = int(os.environ.get("HORAS_RETENCION", "24"))

# Si se define, la demo entera queda detras de una clave: sin ella no se ve
# la landing y, sobre todo, NO se puede llamar a /generar (cada informe cuesta
# ~0,30 EUR en el generador de imagen). Se entra una vez y queda una cookie.
CLAVE = os.environ.get("CLAVE_DEMO", "").strip()

# Rutas que siguen abiertas con la clave puesta: la propia pantalla de entrada
# y el robots.txt (que justamente pide que nadie indexe esto).
LIBRES = {"/clave", "/robots.txt"}

COOKIE = "vb_acceso"


def _token():
    """Firma derivada de la propia clave: no hace falta un secreto aparte, y al
    cambiar la clave caducan solas todas las cookies emitidas con la anterior."""
    return hmac.new(CLAVE.encode(), b"visagismo-demo-v1", hashlib.sha256).hexdigest()[:32]


def _tiene_acceso(request: Request) -> bool:
    if not CLAVE:                      # sin CLAVE_DEMO definida, demo abierta
        return True
    galleta = request.cookies.get(COOKIE, "")
    return bool(galleta) and hmac.compare_digest(galleta, _token())


def _generados_hoy():
    hoy = date.today().isoformat()
    return sum(1 for d in SESIONES.iterdir()
               if d.is_dir()
               and date.fromtimestamp(d.stat().st_mtime).isoformat() == hoy)


def _limpiar_caducadas():
    """Borra las sesiones pasadas de plazo. Se ejecuta en cada generacion:
    sin cron, sin nada que se pueda olvidar de encender."""
    limite = time.time() - HORAS_RETENCION * 3600
    borradas = 0
    for d in list(SESIONES.iterdir()):
        try:
            if d.is_dir() and d.stat().st_mtime < limite:
                shutil.rmtree(d, ignore_errors=True)
                borradas += 1
        except OSError:
            pass
    if borradas:
        print(f"retencion: {borradas} sesiones borradas (>{HORAS_RETENCION} h)", flush=True)


SIN_INDEXAR = {"X-Robots-Tag": "noindex, nofollow, noarchive"}

ETIQUETA_CAT = {"pelo": "El cabello", "barba": "La barba",
                "historia": "Historia del oficio", "visagismo": "Visagismo"}

try:
    CURIOSIDADES = json.loads((RAIZ / "curiosidades.json").read_text(encoding="utf-8"))
except Exception:
    CURIOSIDADES = []


def pagina(nombre):
    return HTMLResponse((ESTATICO / nombre).read_text(encoding="utf-8"),
                        headers=SIN_INDEXAR)


@app.get("/robots.txt")
def robots():
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("User-agent: *\nDisallow: /\n")


# ---------------------------------------------------------------------------
# Puerta de entrada
# ---------------------------------------------------------------------------
@app.get("/clave", response_class=HTMLResponse)
def pedir_clave(request: Request):
    if _tiene_acceso(request):
        return RedirectResponse("/", status_code=303)
    return HTMLResponse(_pagina_clave(), headers=SIN_INDEXAR)


@app.post("/clave")
def comprobar_clave(clave: str = Form(""), request: Request = None):
    if not CLAVE:
        return RedirectResponse("/", status_code=303)
    if not hmac.compare_digest(clave.strip(), CLAVE):
        # Un segundo de espera por intento: con una clave corta es lo que
        # convierte un barrido de todas las combinaciones en algo lento.
        time.sleep(1)
        return HTMLResponse(_pagina_clave(fallo=True), status_code=401,
                            headers=SIN_INDEXAR)
    respuesta = RedirectResponse("/", status_code=303)
    respuesta.set_cookie(
        COOKIE, _token(), max_age=30 * 24 * 3600, httponly=True,
        samesite="lax", secure=(request is not None and request.url.scheme == "https"))
    return respuesta


# ---------------------------------------------------------------------------
FALTA_VISOR = """
<div style="padding:34px 26px;text-align:center;font:14px/1.6 system-ui,sans-serif;
            color:#5b5347;background:repeating-linear-gradient(45deg,
            rgba(0,0,0,.02) 0 12px, transparent 12px 24px);border-radius:8px">
  <div style="font-weight:700;color:#2b2620;margin-bottom:8px">
    Aqui va tu retícula de ejemplo
  </div>
  <div style="max-width:44ch;margin:0 auto 14px">
    El kit no trae ninguna cara: esta es la pieza que vende y tiene que ser tuya.
    Genera la tuya con una foto frontal, de frente y con buena luz.
  </div>
  <code style="display:inline-block;background:#2b2620;color:#f4f1ec;padding:9px 13px;
               border-radius:6px;font-size:12.5px;text-align:left">
    python3 03-motor/genera_visor_ejemplo.py TU-FOTO.jpg \\<br>
    &nbsp;&nbsp;&nbsp;&nbsp;06-app/estatico/_visor-ejemplo.html
  </code>
</div>
"""


# Rutas del embudo
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def landing():
    """La landing lleva incrustado un visor real: la misma reticula que recibe
    el cliente, sobre un rostro de ejemplo. Se inyecta aqui en vez de dejarlo
    escrito en el fichero para no duplicar 200 KB de imagen en el repositorio."""
    html = (ESTATICO / "landing.html").read_text(encoding="utf-8")
    visor = ESTATICO / "_visor-ejemplo.html"
    if visor.exists():
        relleno = visor.read_text(encoding="utf-8")
    else:
        # El kit no trae ninguna cara de ejemplo a proposito: la de la landing
        # es la pieza de venta y tiene que ser tuya, no la de otro.
        relleno = FALTA_VISOR
    return HTMLResponse(html.replace("<!-- VISOR_EJEMPLO -->", relleno),
                        headers=SIN_INDEXAR)


@app.get("/pago", response_class=HTMLResponse)
def pago():
    return pagina("checkout.html")


@app.get("/formulario", response_class=HTMLResponse)
def formulario():
    """El formulario lleva las curiosidades incrustadas: durante la espera se
    muestran en el propio navegador, sin pedirle nada al servidor."""
    html = (ESTATICO / "formulario.html").read_text(encoding="utf-8")
    datos = json.dumps(
        [{"t": c["texto"], "c": ETIQUETA_CAT.get(c["categoria"], "")}
         for c in CURIOSIDADES], ensure_ascii=False)
    return HTMLResponse(html.replace("/*CURIOSIDADES*/[]", datos), headers=SIN_INDEXAR)


@app.get("/informe/{sesion}", response_class=HTMLResponse)
def ver_informe(sesion: str):
    destino = SESIONES / sesion / "informe.html"
    if not destino.exists():
        raise HTTPException(404, "Ese informe no existe o ya ha caducado.")
    return HTMLResponse(destino.read_text(encoding="utf-8"), headers=SIN_INDEXAR)


# ---------------------------------------------------------------------------
# Generacion
# ---------------------------------------------------------------------------
def _normalizar(ruta):
    """Deja la imagen en un formato que OpenCV sepa leer.

    Los iPhone suben HEIC por defecto y OpenCV no lo abre: devolveria None y
    el analisis fallaria con un 'no he encontrado ninguna cara' enganoso.
    Aqui se convierte a JPEG antes de tocarla.
    """
    if ruta.suffix.lower() not in {".heic", ".heif"}:
        return ruta
    try:
        from pillow_heif import register_heif_opener
        from PIL import Image
        register_heif_opener()
        with Image.open(ruta) as im:
            im = im.convert("RGB")
            destino = ruta.with_suffix(".jpg")
            im.save(destino, "JPEG", quality=92)
        ruta.unlink(missing_ok=True)
        return destino
    except Exception as e:
        raise HTTPException(
            400, "No he podido leer esa foto. Prueba a enviarla en JPG: en el "
                 "iPhone, Ajustes → Cámara → Formatos → Más compatible."
        ) from e


def _b64(ruta, ancho, calidad=80):
    img = cv2.imread(str(ruta))
    if img is None:
        raise HTTPException(400, f"No he podido leer la imagen {ruta.name}.")
    alto = int(img.shape[0] * ancho / img.shape[1])
    img = cv2.resize(img, (ancho, alto), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, calidad])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


def _plan(receta, hay_barba):
    """Calendario de citas, adaptado a lo que la receta pide construir."""
    hoy = date.today()

    def f(dias):
        d = hoy + timedelta(days=dias)
        return f"{d.day} {MESES[d.month - 1]}"

    citas = [{
        "fecha": f(0), "duracion": "45 min",
        "titulo": f"Corte base{' y barba' if hay_barba else ''}",
        "detalle": "Se fija la longitud de partida y se define el perfilado.",
    }]
    if hay_barba:
        citas.append({"fecha": f(21), "duracion": "15 min",
                      "titulo": "Repaso de barba y cuello",
                      "detalle": "El pelo sigue creciendo sin tocar. Solo se mantiene el perfilado."})
    citas += [
        {"fecha": f(42), "duracion": "40 min", "titulo": "Mantenimiento del patrón",
         "detalle": "Mismo corte. El frontal ya debería caer solo."},
        {"fecha": f(70), "duracion": "40 min", "titulo": "Punto de decisión",
         "detalle": "Valoramos si el frontal aguanta un centímetro más o si es su tope."},
        {"fecha": f(98), "duracion": "45 min", "titulo": "Afinado del perfilado",
         "detalle": "Con todo asentado, se ajustan las líneas definitivas."},
        {"fecha": f(140), "duracion": "60 min", "titulo": "Nueva medición",
         "detalle": "Se repite el análisis y se compara con este expediente."},
    ]
    return citas


def _simular(carpeta, frontal, perfil, receta, prompt_ia=None):
    """Genera el 'despues' y lo pasa por el verificador antes de publicarlo.

    Si el generador falla o la cara sale retocada por encima del umbral, se
    devuelve None y el informe sale sin simulacion: mejor sin ella que con una
    imagen que contradiga al texto.
    """
    if not os.environ.get("FAL_KEY"):
        return None

    vistas = {}
    for nombre, ruta in (("frontal", frontal), ("perfil", perfil)):
        if ruta is None:
            continue
        try:
            print(f"  -> generando {nombre}...", flush=True)
            url = simulacion.generar(ruta, receta, nombre, prompt_ia=prompt_ia)
            print(f"  -> {nombre} generado", flush=True)
            destino = carpeta / f"sim-{nombre}.jpg"
            with urlopen(url, timeout=60) as r, destino.open("wb") as f:
                shutil.copyfileobj(r, f)
        except simulacion.SinSaldo as e:
            print(f"  ⚠ {e}  → recarga en fal.ai/dashboard/billing")
            return None
        except Exception as e:
            print(f"  simulacion {nombre}: fallo -> {type(e).__name__}: {e}")
            continue

        if nombre == "frontal":
            aprobada, informe = simulacion.verificar(ruta, destino)
            (carpeta / "verificacion.json").write_text(
                json.dumps(informe, indent=2, ensure_ascii=False), encoding="utf-8")
            if not aprobada:
                print(f"  simulacion frontal RECHAZADA por el verificador: {informe}")
                continue
        vistas[nombre] = (ruta, destino)

    if "frontal" not in vistas:
        return None

    sim = {
        "antes": _b64(vistas["frontal"][0], 440, 78),
        "despues": _b64(vistas["frontal"][1], 440, 78),
        "pie_antes": "Tu foto tal cual la subiste.",
        "pie_despues": f"{receta['forma'].capitalize()}.",
    }
    if "perfil" in vistas:
        sim["antes_perfil"] = _b64(vistas["perfil"][0], 440, 78)
        sim["despues_perfil"] = _b64(vistas["perfil"][1], 440, 78)
    return sim


@app.post("/generar")
async def generar(
    nombre: str = Form(...),
    transmitir: List[str] = Form(default=[]),
    estilos: List[str] = Form(default=[]),
    minutos: int = Form(5),
    barba: str = Form("si"),
    cuello: str = Form("largo"),
    menos_favorita: str = Form(""),
    frontal: UploadFile = File(...),
    perfil: Optional[UploadFile] = File(None),
):
    arranque = time.time()
    _limpiar_caducadas()
    sesion = uuid.uuid4().hex[:12]
    if LIMITE_DIARIO and _generados_hoy() >= LIMITE_DIARIO:
        raise HTTPException(
            429, f"La demo ha alcanzado su tope de {LIMITE_DIARIO} análisis por día. "
                 f"Vuelve mañana o escríbenos.")

    ext = Path(frontal.filename or "").suffix.lower()
    if ext not in EXT_OK:
        historial.guardar(sesion, None, resultado="formato-no-admitido",
                          nota=f"extension {ext or 'sin extension'}")
        raise HTTPException(400, f"Formato no admitido ({ext}). Usa JPG, PNG o WEBP.")

    carpeta = SESIONES / sesion
    carpeta.mkdir(parents=True, exist_ok=True)

    origen = carpeta / f"frontal{ext}"
    with origen.open("wb") as f:
        shutil.copyfileobj(frontal.file, f)
    if origen.stat().st_size > MAX_BYTES:
        peso = origen.stat().st_size
        shutil.rmtree(carpeta, ignore_errors=True)
        historial.guardar(sesion, None, resultado="foto-demasiado-grande",
                          nota=f"{peso / 1e6:.1f} MB")
        raise HTTPException(400, "La foto pesa más de 12 MB.")
    origen = _normalizar(origen)

    # El perfil es opcional: solo se usa para la simulacion lateral.
    # NO se mide (ver la cabecera de analiza_perfil.py: los landmarks de
    # MediaPipe no se ajustan bien a esa pose y darian numeros falsos).
    ruta_perfil = None
    if perfil is not None and perfil.filename:
        ext_p = Path(perfil.filename).suffix.lower()
        if ext_p in EXT_OK:
            ruta_perfil = carpeta / f"perfil{ext_p}"
            with ruta_perfil.open("wb") as f:
                shutil.copyfileobj(perfil.file, f)
            if ruta_perfil.stat().st_size > MAX_BYTES:
                ruta_perfil.unlink()
                ruta_perfil = None
            else:
                try:
                    ruta_perfil = _normalizar(ruta_perfil)
                except HTTPException:
                    ruta_perfil = None   # el perfil es opcional: no rompe nada

    # --- Medicion real sobre la foto subida ---
    try:
        img, P, _, _ = detectar(origen)
    except SystemExit as e:
        shutil.rmtree(carpeta, ignore_errors=True)
        historial.guardar(sesion, None, resultado="sin-cara",
                          segundos=time.time() - arranque, nota=str(e)[:200])
        raise HTTPException(
            422, "No he encontrado una cara en esa foto. Necesito un primer plano "
                 "de frente, con buena luz y sin gafas de sol.") from e

    m = medir(P)
    c = clasificar(m)
    recorte, off = recortar(img, P, m)
    jpg = carpeta / "rostro.jpg"
    cv2.imwrite(str(jpg), recorte, [cv2.IMWRITE_JPEG_QUALITY, 88])

    respuestas = {
        "nombre": nombre.strip(), "transmitir": transmitir, "estilos": estilos,
        "minutos": minutos, "barba": barba, "cuello": cuello,
        "menos_favorita": menos_favorita.strip(),
    }
    r = analizar(m, c, respuestas)
    cal = mod_calibres.construir(m)

    # El analisis con LLM va DESPUES de las reglas, no en su lugar: recibe las
    # 16 proporciones ya medidas junto con las fotos, asi que puede citar
    # numeros que a ojo no se estiman. Si no hay clave o falla, `ia` es None y
    # el informe sale con las reglas, que funcionan solas.
    ia = analisis_ia.analizar(origen, ruta_perfil, m, c, respuestas, r["receta"])

    geo = {
        "imagen": {"ancho": recorte.shape[1], "alto": recorte.shape[0],
                   "datauri": _b64(jpg, 680, 82)},
        "capas": geometria(P, m, off),
    }

    # Los textos vienen del LLM o de las reglas, con formas distintas.
    # vista_informe los deja en la forma que espera la plantilla; es el unico
    # sitio donde se hace, y prueba_informe.py lo recorre con las dos.
    _txt = vista_informe.textos(ia, r["textos"])

    partes = nombre.strip().split()
    corto = f"{partes[0]} {partes[1][0]}." if len(partes) > 1 else (partes[0] if partes else "Cliente")
    hoy = date.today()

    datos = {
        "barberia": BARBERIA,
        "cliente": {"nombre": corto, "expediente": f"MST-{sesion[:4].upper()}",
                    "fecha": f"{hoy.day} {MESES[hoy.month - 1]} {hoy.year}"},
        "titular": _txt["titular"],
        "morfotipo": c["morfotipo"]["forma"],
        "n_proporciones": 16,
        "n_fuera": sum(1 for x in cal if not x["dentro"]),
        "calibres": cal,
        "diagnostico": _txt["diagnostico"],
        "objetivo": _txt["objetivo"],
        "evitar": _txt["evitar"],
        # Los estilos solo existen cuando ha respondido el LLM: son su aportacion
        # real, y el motor de reglas no los produce.
        "estilos": (ia or {}).get("estilos"),
        "mejor_estilo": (ia or {}).get("mejor", 0),
        "por_ia": bool(ia),
        "receta": r["receta"],
        "hallazgo_principal": (
            {"titulo": r["textos"]["principal"].titulo} if r["textos"]["principal"] else None),
        "plan": _plan(r["receta"], barba != "no"),
        "simulacion": None,   # la rellena el hilo de fondo
    }

    (carpeta / "datos.json").write_text(
        json.dumps({"respuestas": respuestas, "medidas": m["ratios"],
                    "clasificacion": c}, ensure_ascii=False, indent=2,
                   default=str), encoding="utf-8")

    # Todo el trabajo ocurre AQUI y el informe viaja en la propia respuesta.
    # La espera se muestra en el navegador del cliente mientras tanto (ver el
    # script del formulario), asi no hace falta ni polling ni estado compartido.
    print(f"[{sesion}] generando...", flush=True)
    datos["simulacion"] = _simular(carpeta, origen, ruta_perfil, r["receta"],
                                   prompt_ia=(ia or {}).get("prompt_imagen"))
    html = render_informe.construir(geo, datos)

    # Se guarda tambien en disco: sirve para volver a abrirlo desde la misma
    # instancia mientras viva, pero el informe ya se ha entregado igualmente.
    try:
        (carpeta / "informe.html").write_text(html, encoding="utf-8")
    except OSError:
        pass
    # El historial se escribe AQUI, antes de devolver: en Vercel no hay trabajo
    # de fondo garantizado (es lo que rompio la sala de espera). Suma ~1 s sobre
    # los ~60 que ya tarda, y no puede tumbar la entrega: historial.guardar()
    # nunca lanza.
    historial.guardar(
        sesion, carpeta, resultado="entregado",
        expediente=datos["cliente"]["expediente"], datos=datos,
        medidas=m["ratios"], clasificacion=c, respuestas=respuestas, html=html,
        segundos=time.time() - arranque, tuvo_perfil=ruta_perfil is not None,
        fotos={"frontal": origen, "perfil": ruta_perfil}, ia=ia)
    print(f"[{sesion}] entregado", flush=True)
    return HTMLResponse(html, headers=SIN_INDEXAR)
