#!/usr/bin/env python3
"""
Genera el fragmento HTML del VISOR DE EJEMPLO que va en la landing.

Es la misma pieza que el cliente recibe en su informe —la retícula
trazándose sola sobre un rostro real, con sus capas encendibles— pero
autocontenida, para poder incrustarla en la página de venta.

Es el argumento comercial entero en un solo bloque: se ve de un vistazo
qué compras, sin leer una línea.

uso: genera_visor_ejemplo.py <foto.jpg> <salida.html>
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import cv2                                              # noqa: E402
import base64                                           # noqa: E402
from analiza_rostro import detectar, medir              # noqa: E402
from exporta_geometria import recortar, geometria       # noqa: E402
import render_informe                                   # noqa: E402


CSS_VISOR = """
.vx{--vx-papel:#F4F1EC;--vx-linea:#D6CFC2;--vx-linea-f:#B8AE9C;
    --vx-tinta:#14181F;--vx-tinta-3:#7C8697;--vx-azul:#16386B;
    max-width:380px;margin:0 auto}
.vx .lienzo{position:relative;border:3px solid var(--vx-azul);border-radius:8px;
  overflow:hidden;background:#000;box-shadow:0 10px 30px -14px rgba(20,24,31,.5)}
.vx .lienzo img{display:block;width:100%;height:auto}
.vx .retic{position:absolute;inset:0;width:100%;height:100%}
.vx .sw{position:absolute;opacity:0;pointer-events:none;width:0;height:0}
.vx .chips-guia{margin:14px 0 9px;text-align:center;font-size:10px;font-weight:700;
  letter-spacing:.2em;text-transform:uppercase;color:var(--vx-tinta-3)}
.vx .chips{display:flex;flex-wrap:wrap;gap:7px;justify-content:center}
.vx .chip{display:inline-flex;align-items:center;gap:7px;min-height:44px;padding:0 15px;
  border:1px solid var(--vx-linea-f);border-radius:999px;background:#fff;
  font-size:12.5px;letter-spacing:.04em;color:var(--vx-tinta-3);cursor:pointer;
  user-select:none;-webkit-tap-highlight-color:transparent;
  transition:color .18s,border-color .18s,background .18s,transform .09s}
.vx .chip:active{transform:scale(.94)}
.vx .ojo{width:17px;height:17px;flex:none;fill:none;stroke:currentColor;
  stroke-width:1.7;stroke-linecap:round;overflow:visible}
.vx .ojo-p{fill:currentColor;stroke:none;transition:opacity .18s}
.vx .ojo-x{opacity:0;transition:opacity .18s;stroke-width:2}
.vx .capa{transition:opacity .3s ease}
"""


def main():
    if len(sys.argv) < 3:
        raise SystemExit("uso: genera_visor_ejemplo.py <foto.jpg> <salida.html>")
    foto, destino = Path(sys.argv[1]), Path(sys.argv[2])

    img, P, _, _ = detectar(foto)
    m = medir(P)
    recorte, off = recortar(img, P, m)

    tmp = destino.parent / "_rostro_ejemplo.jpg"
    destino.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(tmp), recorte, [cv2.IMWRITE_JPEG_QUALITY, 84])
    datauri = "data:image/jpeg;base64," + base64.b64encode(tmp.read_bytes()).decode()
    tmp.unlink()

    geo = {"imagen": {"ancho": recorte.shape[1], "alto": recorte.shape[0],
                      "datauri": datauri},
           "capas": geometria(P, m, off)}

    css = render_informe.CSS
    # Del CSS del informe solo nos llevamos lo que pinta la reticula.
    ini = css.index("/* Trazado:")
    fin = css.index("/* ── Lecturas ── */")
    css_reticula = css[ini:fin].replace("{{CSS_CAPAS}}", render_informe.css_capas())
    css_reticula = "\n".join(
        (".vx " + l if l and not l.startswith((" ", "}", "@", "#c-", "/*")) else l)
        for l in css_reticula.splitlines())
    css_reticula = css_reticula.replace("#c-", ".vx #c-")

    html = (f'<style>{CSS_VISOR}{css_reticula}</style>\n'
            f'<div class="vx">{render_informe.construir_visor(geo)}</div>')
    destino.write_text(html, encoding="utf-8")
    print(f"visor de ejemplo -> {destino}  ({len(html)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
