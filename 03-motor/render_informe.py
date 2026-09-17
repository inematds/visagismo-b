#!/usr/bin/env python3
"""
Genera el informe de visagismo en HTML a partir de la geometria medida.

Restricciones de diseno, todas nacidas de como se consume el informe
(se manda por WhatsApp y se abre en el movil):

  * CERO JavaScript. El trazado de las lineas, los interruptores de capa
    y el contador animado son CSS puro. Asi abre en cualquier visor.
  * Movil primero. El visor del rostro va fijo arriba y el texto pasa
    por debajo; en pantalla ancha pasa a columna lateral.
  * Peso contenido. Las lineas son SVG vectorial, no imagenes quemadas.

uso: render_informe.py <geometria.json> <uris.json> <salida.html>
"""

import json
import sys
from pathlib import Path

# Orden en que se traza cada capa. Es el orden del razonamiento del
# barbero: primero el eje, luego la estructura, luego las proporciones.
# Se abre desde el movil: la secuencia entera debe caber en ~2,3 s.
# Mas larga que eso y el lector hace scroll antes de que termine.
# (id, etiqueta, retardo, encendida_de_inicio, color)
# El color es el mismo con el que se pintan las lineas de esa capa: el ojo
# del boton lo hereda, y asi el boton dice a la vez que se toca, que controla
# y si esta encendido, sin necesidad de leyenda aparte.
#
# "Anchuras" arranca apagada: sus rotulos son los mas largos y con las cinco
# capas a la vez el rostro se satura. Asi la primera impresion es limpia y
# el lector tiene un motivo real para tocar los interruptores.
CAPAS = [
    ("eje",        "Eje",         0.15, True,  "#5B6472"),
    ("estructura", "Anchuras",    0.40, False, "#1F5FA8"),
    ("contorno",   "Mandíbula",   0.75, True,  "#C2102E"),
    ("tercios",    "Tercios",     1.10, True,  "#7FA8D6"),
    ("quintos",    "Quintos",     1.50, True,  "#E0737F"),
]


def css_capas():
    """Reglas por capa, generadas desde CAPAS para que no se desincronicen."""
    fuera = []
    for n, _, _, _, color in CAPAS:
        fuera.append(f"""
#c-{n}:checked ~ .chips .chip[for="c-{n}"]{{
  color:{color};border-color:{color};background:var(--fondo-3);
}}
#c-{n}:not(:checked) ~ .lienzo #g-{n}{{opacity:0;visibility:hidden}}
#c-{n}:not(:checked) ~ .chips .chip[for="c-{n}"] .ojo-x{{opacity:1}}
#c-{n}:not(:checked) ~ .chips .chip[for="c-{n}"] .ojo-p{{opacity:0}}
#c-{n}:focus-visible ~ .chips .chip[for="c-{n}"]{{outline:2px solid var(--acero);outline-offset:2px}}""")
    return "\n".join(fuera)


def svg_capa(nombre, elementos, retardo):
    """Un grupo SVG por capa, con los retardos de trazado escalonados."""
    piezas = [f'<g id="g-{nombre}" class="capa">']
    n_trazo = 0
    for el in elementos:
        d = retardo + n_trazo * 0.055
        if el["tipo"] == "linea":
            (x1, y1), (x2, y2) = el["a"], el["b"]
            piezas.append(
                f'<line class="tz" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                f'pathLength="100" style="--d:{d:.2f}s"/>'
            )
            n_trazo += 1
            if el.get("etiqueta"):
                clase = "rot rot-prin" if el.get("principal") else "rot"
                txt = el["etiqueta"]
                if el.get("valor"):
                    txt += f'  {el["valor"]}'
                x_t, y_t = x2 - 10, y2 - 13
                ancho = len(txt) * 18 + 16      # 30px de cuerpo en mono ~= 18px/car
                piezas.append(
                    f'<rect class="caja" x="{x_t - ancho + 8}" y="{y_t - 26}" '
                    f'width="{ancho}" height="34" rx="5" '
                    f'style="--d:{d + 0.45:.2f}s"/>'
                )
                piezas.append(
                    f'<text class="{clase}" x="{x_t}" y="{y_t}" '
                    f'style="--d:{d + 0.5:.2f}s">{txt}</text>'
                )
        elif el["tipo"] == "polilinea":
            pts = " ".join(f"{x},{y}" for x, y in el["puntos"])
            piezas.append(
                f'<polyline class="tz" points="{pts}" pathLength="100" '
                f'style="--d:{d:.2f}s"/>'
            )
            n_trazo += 1
        elif el["tipo"] == "valor":
            x, y = el["pos"]
            destacado = el.get("destacado")
            clase = "val val-alerta" if destacado else "val"
            cuerpo = 40 if destacado else 34
            ancho = len(el["texto"]) * cuerpo * 0.62 + 14
            piezas.append(
                f'<rect class="caja{" caja-alerta" if destacado else ""}" '
                f'x="{x - ancho/2}" y="{y - cuerpo + 4}" width="{ancho}" '
                f'height="{cuerpo + 8}" rx="5" style="--d:{d + 0.40:.2f}s"/>'
            )
            piezas.append(
                f'<text class="{clase}" x="{x}" y="{y}" '
                f'style="--d:{d + 0.45:.2f}s">{el["texto"]}</text>'
            )
    piezas.append("</g>")
    return "\n".join(piezas)


def construir_svg(datos):
    img = datos["imagen"]
    capas = datos["capas"]
    grupos = [svg_capa(n, capas.get(n, []), r) for n, _, r, _e, _c in CAPAS]
    return (
        f'<svg class="retic" viewBox="0 0 {img["ancho"]} {img["alto"]}" '
        f'role="img" aria-label="Retícula de medición sobre el rostro: eje de '
        f'simetría, anchuras estructurales, contorno mandibular, tercios '
        f'verticales y quintos horizontales.">\n'
        + "\n".join(grupos) + "\n</svg>"
    )


OJO = (
    '<svg class="ojo" viewBox="0 0 24 24" aria-hidden="true">'
    '<path class="ojo-o" d="M1.6 12S5.6 5.2 12 5.2 22.4 12 22.4 12 18.4 18.8 12 18.8 1.6 12 1.6 12Z"/>'
    '<circle class="ojo-p" cx="12" cy="12" r="3.1"/>'
    '<path class="ojo-x" d="M4.2 4.2 19.8 19.8"/>'
    '</svg>'
)


def construir_visor(datos):
    img = datos["imagen"]
    inputs = "\n".join(
        f'<input type="checkbox" class="sw" id="c-{n}"{" checked" if enc else ""}>'
        for n, _, _, enc, _c in CAPAS
    )
    chips = "\n".join(
        f'<label class="chip" for="c-{n}">{OJO}{et}</label>'
        for n, et, _, _e, _c in CAPAS
    )
    return f"""
<div class="visor">
  {inputs}
  <div class="lienzo">
    <img src="{img['datauri']}" alt="Fotografía frontal del rostro analizado." width="{img['ancho']}" height="{img['alto']}">
    {construir_svg(datos)}
  </div>
  <p class="chips-guia">Toca para mostrar u ocultar</p>
  <div class="chips" role="group" aria-label="Capas de medición">
    {chips}
  </div>
</div>"""


CSS = r"""
/* Colores de barberia: el poste es rojo, blanco y azul. De ahi sale todo.
   Fondo de papel hueso calido, nunca blanco puro. */
:root{
  --fondo:#F4F1EC; --fondo-2:#FFFFFF; --fondo-3:#E9E4DB;
  --borde:#D6CFC2; --borde-f:#B8AE9C;
  --tinta:#14181F; --tinta-2:#4A5361; --tinta-3:#7C8697;
  --rojo:#C2102E; --rojo-osc:#8E0B21; --rojo-claro:#E63946;
  --azul:#16386B; --azul-med:#2E6CB8; --azul-claro:#5AA9E6;
  /* alias de rol, para no tocar el resto de la hoja */
  --laton:var(--rojo); --laton-c:var(--rojo-osc);
  --acero:var(--azul-med); --oxido:var(--rojo);
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0;background:var(--fondo);color:var(--tinta);
  font-family:"Archivo",system-ui,-apple-system,"Segoe UI",sans-serif;
  font-size:16px;line-height:1.62;-webkit-font-smoothing:antialiased;
}
.env{max-width:1200px;margin:0 auto;padding:0 20px 80px}
h1,h2,h3{font-family:"Bricolage Grotesque","Archivo",system-ui,sans-serif;text-wrap:balance;margin:0;font-weight:400}
.mono{font-family:"JetBrains Mono",ui-monospace,Menlo,monospace;font-variant-numeric:tabular-nums}

/* ── Cabecera ── */
.top{display:flex;gap:14px;align-items:center;padding:18px 0 16px;border-bottom:1px solid var(--borde)}
.poste{
  width:11px;height:44px;border-radius:6px;flex:none;position:relative;overflow:hidden;
  background:repeating-linear-gradient(155deg,
    var(--rojo) 0 6px, #fff 6px 12px, var(--azul) 12px 18px, #fff 18px 24px);
  background-size:100% 24px;
  box-shadow:inset 0 0 0 1px rgba(20,24,31,.22), 0 1px 3px rgba(20,24,31,.2);
  animation:girar 2.6s linear infinite;
}
/* El brillo cilindrico es lo que lo hace parecer un tubo y no una barra. */
.poste::after{
  content:"";position:absolute;inset:0;border-radius:6px;
  background:linear-gradient(90deg,rgba(0,0,0,.30),rgba(255,255,255,.42) 42%,rgba(0,0,0,.24));
}
@keyframes girar{to{background-position:0 -24px}}
.top-n{font-family:"Bricolage Grotesque","Archivo",sans-serif;font-size:20px;font-weight:800;letter-spacing:.11em;line-height:1}
.top-s{font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:var(--tinta-3);margin-top:4px}
.top-m{margin-left:auto;text-align:right;font-size:10.5px;color:var(--tinta-3);letter-spacing:.04em;line-height:1.7}
.top-m b{color:var(--tinta-2);font-weight:600}

/* ── Apertura ── */
.hero{padding:22px 0 16px}
.eyebrow{font-size:10px;letter-spacing:.24em;text-transform:uppercase;color:var(--laton);font-weight:700;margin-bottom:14px}
.hero h1{font-size:clamp(27px,7.4vw,58px);line-height:1.04;letter-spacing:-.015em}
.hero h1 em{font-style:normal;color:var(--rojo);position:relative;white-space:nowrap}
.hero h1 em::after{content:"";position:absolute;left:0;right:0;bottom:.06em;height:.14em;
  background:var(--rojo);opacity:.18;border-radius:2px}
.hero p{margin:18px 0 0;font-size:16.5px;color:var(--tinta-2);max-width:56ch}
.hero p strong{color:var(--tinta);font-weight:500}

/* ── VISOR: fijo arriba en móvil, columna lateral en pantalla ancha ── */
.analisis{position:relative}
.visor{
  position:sticky;top:0;z-index:5;margin:0 -20px;padding:10px 20px 12px;
  background:var(--fondo);
  box-shadow:0 10px 18px -10px var(--fondo);
}
.lienzo{
  position:relative;margin:0 auto;max-width:min(100%,340px);
  border:3px solid var(--azul);border-radius:6px;overflow:hidden;background:#000;
  box-shadow:0 6px 20px -10px rgba(20,24,31,.45);
}
.lienzo img{display:block;width:100%;height:auto}
.retic{position:absolute;inset:0;width:100%;height:100%}

/* Trazado: pathLength=100 normaliza cualquier longitud a 100 unidades. */
.tz{
  fill:none;stroke:var(--laton-c);stroke-width:2;vector-effect:non-scaling-stroke;
  stroke-dasharray:100;stroke-dashoffset:100;
  animation:trazar .6s cubic-bezier(.5,0,.2,1) var(--d,0s) forwards;
}
#g-eje .tz{stroke:#fff;opacity:.55;stroke-dasharray:4 5;stroke-dashoffset:0;
  animation:aparecer .6s ease var(--d,0s) both}
#g-estructura .tz{stroke:#5AA9E6;stroke-width:2.5}
#g-contorno .tz{stroke:#FF5A6E;stroke-width:2.5}
#g-tercios .tz{stroke:#A8CCEC;stroke-width:1.8}
#g-quintos .tz{stroke:#FF9AA6;stroke-width:1.5;opacity:.9}

@keyframes trazar{to{stroke-dashoffset:0}}
@keyframes aparecer{from{opacity:0}to{opacity:.5}}
@keyframes surgir{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}

.caja{
  fill:rgba(10,13,20,.82);opacity:0;
  animation:surgir .45s ease var(--d,0s) forwards;
}
.caja-alerta{fill:var(--rojo);stroke:#fff;stroke-width:1.5}
.rot,.val{
  text-anchor:middle;
  font-family:"JetBrains Mono",monospace;font-size:30px;fill:#FFE3E7;
  opacity:0;animation:surgir .5s ease var(--d,0s) forwards;
  paint-order:stroke;stroke:rgba(8,10,14,.55);stroke-width:3px;stroke-linejoin:round;
}
#g-estructura .rot{fill:#CDE8FF}
.rot-prin{fill:#FFD7DC;font-weight:700}
.rot{text-anchor:end}
.val{font-size:34px;font-weight:700;fill:#FFC2CB}
.val-alerta{fill:#FFFFFF;font-size:40px;stroke:none}
#g-tercios .val{fill:#DCEDFC;font-size:30px}

/* Interruptores de capa: checkboxes ocultos, CSS puro, sin JavaScript.
   El ojo es el estandar universal de "mostrar/ocultar capa"; pintado del
   color de sus lineas, el boton dice a la vez que se toca y que controla. */
.sw{position:absolute;opacity:0;pointer-events:none;width:0;height:0}
.chips-guia{
  margin:12px 0 8px;text-align:center;font-size:10px;font-weight:700;
  letter-spacing:.2em;text-transform:uppercase;color:var(--tinta-3);
}
.chips{display:flex;flex-wrap:wrap;gap:7px;justify-content:center}
.chip{
  display:inline-flex;align-items:center;gap:7px;min-height:44px;padding:0 15px;
  border:1px solid var(--borde-f);border-radius:999px;background:var(--fondo-2);
  font-size:12.5px;letter-spacing:.04em;color:var(--tinta-3);cursor:pointer;
  user-select:none;-webkit-tap-highlight-color:transparent;
  transition:color .18s,border-color .18s,background .18s,transform .09s;
}
.chip:active{transform:scale(.94)}
.ojo{width:17px;height:17px;flex:none;fill:none;stroke:currentColor;
  stroke-width:1.7;stroke-linecap:round;overflow:visible}
.ojo-p{fill:currentColor;stroke:none;transition:opacity .18s}
.ojo-x{opacity:0;transition:opacity .18s;stroke-width:2}
{{CSS_CAPAS}}
.capa{transition:opacity .3s ease}

/* ── Lecturas ── */
.lect{padding-top:26px}
.resto{padding-top:8px;max-width:74ch;margin:0 auto}
section{margin-bottom:56px}
.cab{display:flex;gap:14px;align-items:baseline;margin-bottom:20px;padding-bottom:11px;border-bottom:1px solid var(--borde)}
.num{font-family:"JetBrains Mono",monospace;font-size:11px;font-weight:700;color:var(--laton);flex:none;padding-top:4px}
.cab h2{font-size:clamp(23px,5.5vw,32px);flex:1;letter-spacing:-.01em}
.cab .lat{font-size:10px;color:var(--tinta-3);letter-spacing:.13em;text-transform:uppercase;flex:none}
p{margin:0 0 15px}
.col{max-width:62ch}
strong{font-weight:600;color:var(--tinta)}

/* ── Calibres ── */
.cal{margin:26px 0;display:flex;flex-direction:column;gap:24px}
.cal-h{display:flex;justify-content:space-between;align-items:baseline;gap:14px;margin-bottom:8px}
.cal-n{font-size:14px;font-weight:600}
.cal-n small{display:block;font-weight:400;font-size:11.5px;color:var(--tinta-3);margin-top:2px}
.cal-v{font-family:"JetBrains Mono",monospace;font-size:16px;font-weight:700;flex:none}
.cal-v.ok{color:var(--acero)} .cal-v.des{color:var(--laton-c)}
.regla{position:relative;height:32px}
.pista{position:absolute;left:0;right:0;top:13px;height:4px;border-radius:2px;background:var(--fondo-3);box-shadow:inset 0 0 0 1px var(--borde)}
.canon{position:absolute;top:13px;height:4px;border-radius:2px;background:var(--acero);opacity:.35}
.mk{position:absolute;top:5px;width:2px;height:20px;background:var(--tinta);border-radius:1px}
.mk::after{content:"";position:absolute;left:50%;top:-6px;transform:translateX(-50%);
  width:9px;height:9px;border-radius:50%;background:var(--laton-c);box-shadow:0 0 0 2.5px var(--fondo)}
.mk.ok::after{background:var(--acero)}
.cal-pie{display:flex;justify-content:space-between;font-size:10.5px;color:var(--tinta-3);gap:10px}

/* El numero que cuenta: un solo dato animado en todo el informe.
   Los extremos se inyectan por render (ver `css_contador`), porque
   @keyframes no puede leer var() de forma fiable. */
@property --n{syntax:"<integer>";initial-value:0;inherits:false}
.cuenta{counter-reset:n var(--n);animation:contar 1.5s 2.1s cubic-bezier(.2,.8,.3,1) both}
.cuenta::after{content:counter(n) "%"}
{{CSS_CONTADOR}}

/* ── Bloques ── */
.veredicto{background:var(--fondo-2);border:1px solid var(--borde);border-left:3px solid var(--laton);border-radius:3px;padding:22px 24px;margin:24px 0}
.veredicto h3{font-size:19px;margin-bottom:9px}
.veredicto p:last-child{margin-bottom:0}

.figs{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:22px 0}
.fig{background:var(--fondo-2);border:1px solid var(--borde);border-radius:3px;overflow:hidden}
.fig img{display:block;width:100%;height:auto}
.fig figcaption{padding:10px 12px;font-size:11.5px;color:var(--tinta-2);border-top:1px solid var(--borde);line-height:1.45}
.fig figcaption b{display:block;color:var(--tinta);font-size:12px;margin-bottom:2px}
figure{margin:0}

.ia{display:flex;gap:11px;background:var(--fondo-3);border:1px solid var(--borde-f);border-left:3px solid var(--laton);padding:13px 15px;border-radius:3px;margin-top:16px;font-size:12.5px;color:var(--tinta-2);line-height:1.5}
.ia b{color:var(--tinta);display:block;margin-bottom:3px}
.ia-ico{flex:none;width:24px;height:24px;border-radius:50%;background:var(--laton);color:var(--fondo);display:grid;place-items:center;font-size:9px;font-weight:700;font-family:"JetBrains Mono",monospace}

.ficha{background:var(--fondo-2);border:1px solid var(--borde-f);border-radius:3px;overflow:hidden;margin-top:22px}
.ficha-top{background:var(--fondo-3);padding:14px 18px;border-bottom:1px solid var(--borde-f)}
.ficha-top b{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--laton-c);font-weight:700}
.ficha-top span{display:block;font-size:11.5px;color:var(--tinta-3);margin-top:3px}
.ficha dl{margin:0}
.ficha dt{padding:14px 18px 2px;font-size:10.5px;letter-spacing:.13em;text-transform:uppercase;color:var(--tinta-3);font-weight:700}
.ficha dd{margin:0;padding:0 18px 14px;font-size:14.5px;line-height:1.5;border-bottom:1px solid var(--borde)}
.ficha dd:last-child{border-bottom:none}
.ficha dd .mono{color:var(--laton-c);font-weight:700}

/* Los cortes propuestos. Sin sombras ni tarjetas flotantes: el informe es un
   documento de barberia, no un panel de aplicacion. */
.estilos{display:flex;flex-direction:column;gap:14px;margin-top:22px}
.estilo{background:var(--fondo-2);border:1px solid var(--borde);border-radius:3px;padding:18px 20px}
.estilo-top{border-color:var(--laton);border-left-width:4px}
.estilo-cab{display:flex;align-items:baseline;gap:14px}
.estilo-cab h3{margin:0;font-size:17px;letter-spacing:-.01em;flex:1}
.encaje{flex:none;font-weight:700;color:var(--acero);white-space:nowrap}
.encaje .mono{font-size:19px}
.encaje small{font-size:11px;color:var(--tinta-3);font-weight:400}
.sello{display:inline-block;margin-top:9px;background:var(--laton);color:#fff;
  font-size:9.5px;letter-spacing:.14em;text-transform:uppercase;font-weight:700;
  padding:3px 9px;border-radius:2px}
.estilo>p{margin:11px 0 0;font-size:14.5px;line-height:1.55;color:var(--tinta-2)}
.estilo-dl{margin:14px 0 0;border-top:1px dashed var(--borde);padding-top:12px}
.estilo-dl dt{font-size:10px;letter-spacing:.13em;text-transform:uppercase;
  color:var(--tinta-3);font-weight:700;margin-top:10px}
.estilo-dl dt:first-child{margin-top:0}
.estilo-dl dd{margin:4px 0 0;font-size:14px;line-height:1.5;color:var(--tinta-2)}
@media print{.estilo{break-inside:avoid}}

.evitar{display:flex;flex-direction:column;gap:13px;margin-top:20px}
.ev{display:flex;gap:12px;font-size:14.5px;line-height:1.5;color:var(--tinta-2)}
.ev-x{flex:none;width:20px;height:20px;border-radius:2px;border:1.5px solid var(--oxido);color:var(--oxido);display:grid;place-items:center;font-size:11px;font-weight:700;margin-top:2px}
.ev b{color:var(--tinta)}

.plan{margin-top:22px;border-top:1px solid var(--borde)}
.cita{display:grid;grid-template-columns:64px 1fr;gap:14px;padding:14px 2px;border-bottom:1px solid var(--borde);align-items:baseline}
.cita-f{font-family:"JetBrains Mono",monospace;font-size:12px;color:var(--laton-c);font-weight:700}
.cita b{display:block;font-size:14.5px;margin-bottom:2px}
.cita span{font-size:12.5px;color:var(--tinta-2);line-height:1.45}
.cita .dur{display:block;font-size:10.5px;color:var(--tinta-3);letter-spacing:.08em;text-transform:uppercase;margin-top:4px}
.cita.hoy{background:var(--fondo-2);margin:0 -8px;padding:14px 10px}

.firma{margin-top:56px;padding-top:24px;border-top:2px solid var(--borde-f)}
.firma-n{font-family:"Bricolage Grotesque","Archivo",sans-serif;font-size:24px;font-weight:800;letter-spacing:-.01em}
.firma-r{font-size:10.5px;color:var(--tinta-3);letter-spacing:.13em;text-transform:uppercase;margin-top:4px}
.firma-d{font-size:12.5px;color:var(--tinta-2);margin-top:14px;max-width:46ch}
.legal{margin-top:32px;padding-top:18px;border-top:1px solid var(--borde);font-size:11px;color:var(--tinta-3);line-height:1.7}
.legal p{margin:0 0 7px}

/* ── Pie de marca: aviso de demo + SoluTech IA ── */
.pie-marca{margin-top:72px;display:flex;flex-direction:column;gap:20px}
.pie-aviso{
  border:1px dashed var(--borde-f);border-radius:4px;padding:16px 18px;background:var(--fondo-2);
}
.pie-tag{
  display:inline-block;font-size:9.5px;letter-spacing:.19em;text-transform:uppercase;
  font-weight:700;color:var(--fondo);background:var(--laton);
  padding:4px 9px;border-radius:3px;margin-bottom:10px;
}
.pie-aviso p{margin:0;font-size:12.5px;color:var(--tinta-2);line-height:1.55}

.pie-st{
  border:1px solid var(--borde-f);border-radius:4px;padding:26px 22px;
  background:
    radial-gradient(120% 90% at 100% 0%, rgba(176,141,79,.11), transparent 60%),
    var(--fondo-2);
}
.pie-logo{
  font-family:"Bricolage Grotesque","Archivo",sans-serif;font-size:25px;font-weight:800;letter-spacing:-.01em;
}
.pie-logo span{color:var(--laton-c);font-style:italic;font-weight:400;margin-left:2px}
.pie-claim{
  margin:5px 0 0;font-size:10.5px;letter-spacing:.2em;text-transform:uppercase;
  color:var(--tinta-3);font-weight:600;
}
.pie-txt{margin:16px 0 0;font-size:13.5px;color:var(--tinta-2);line-height:1.6;max-width:52ch}
.pie-cta{
  display:inline-block;margin-top:18px;padding:12px 22px;min-height:44px;line-height:20px;
  border:none;border-radius:999px;background:var(--azul);color:#fff;
  text-decoration:none;font-size:14px;font-weight:700;letter-spacing:.02em;
  transition:background .2s,transform .09s;
}
.pie-cta:hover{background:var(--azul-med)}
.pie-cta:active{transform:scale(.97)}
.pie-cta:focus-visible{outline:2px solid var(--acero);outline-offset:3px}
.pie-legal{margin:14px 0 0;font-size:10.5px;color:var(--tinta-3);letter-spacing:.04em}

/* ── Pantalla ancha: el visor pasa a columna lateral ── */
@media (min-width:900px){
  body{font-size:17px}
  .analisis{display:grid;grid-template-columns:minmax(340px,42%) 1fr;gap:44px;align-items:start}
  .visor{margin:0;padding:22px 0;top:16px;background:none}
  .lienzo{max-width:100%}
  .lect{padding-top:22px}
  .figs{gap:18px}
  .ficha dl{display:grid;grid-template-columns:minmax(110px,auto) 1fr}
  .ficha dt{padding:14px 8px 14px 18px;border-bottom:1px solid var(--borde);display:flex;align-items:flex-start}
  .ficha dd{padding:14px 18px 14px 8px}
  .ficha dl>:nth-last-child(-n+2){border-bottom:none}
  .cita{grid-template-columns:76px 1fr auto}
}
@media (max-width:420px){
  .rot{display:none}          /* a este tamaño los rótulos no caben: mandan los números */
  .val{font-size:40px}
  .val-alerta{font-size:46px}
  #g-tercios .val{font-size:36px}
}
@media (prefers-reduced-motion:reduce){
  *,*::before,*::after{animation-duration:.01ms!important;animation-delay:0s!important;transition-duration:.01ms!important}
  .poste{animation:none!important}
  .tz{stroke-dashoffset:0}
  .caja{
  fill:rgba(10,13,20,.82);opacity:0;
  animation:surgir .45s ease var(--d,0s) forwards;
}
.caja-alerta{fill:var(--rojo);stroke:#fff;stroke-width:1.5}
.rot,.val{opacity:1}
}
"""


def css_contador(calibres):
    """@keyframes del contador con los extremos reales de este informe."""
    for c in calibres:
        if c.get("contador"):
            d, h = c["contador"]["desde"], c["contador"]["hasta"]
            return (f"@property --n{{syntax:'<integer>';initial-value:{h};inherits:false}}\n"
                    f"@keyframes contar{{from{{--n:{d}}}to{{--n:{h}}}}}")
    return "@keyframes contar{from{--n:0}to{--n:0}}"


def construir(geo, datos):
    """Compone el HTML final. `datos` trae todo lo dinamico del informe."""
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    from markupsafe import Markup

    entorno = Environment(
        loader=FileSystemLoader(str(Path(__file__).parent / "plantillas")),
        autoescape=select_autoescape(["html"]),
    )
    css = CSS.replace("{{CSS_CAPAS}}", css_capas())
    css = css.replace("{{CSS_CONTADOR}}", css_contador(datos["calibres"]))

    plantilla = entorno.get_template("informe.html.j2")
    # css y visor son HTML/CSS ya construidos: no deben escaparse.
    return plantilla.render(css=Markup(css), visor=Markup(construir_visor(geo)), **datos)


def main():
    if len(sys.argv) < 4:
        raise SystemExit("uso: render_informe.py <geometria.json> <datos.json> <salida.html>")
    geo = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    datos = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    destino = Path(sys.argv[3])

    html = construir(geo, datos)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")
    kb = len(html.encode()) / 1024
    print(f"informe -> {destino}  ({kb:.0f} KB)")
    if kb > 500:
        print("  AVISO: por encima de 500 KB, pesado para envio por WhatsApp")


if __name__ == "__main__":
    main()
