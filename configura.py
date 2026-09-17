#!/usr/bin/env python3
"""
Aplica tu marca a todo el proyecto: la landing, el checkout, el formulario, la
sala de espera, el informe y el servidor.

    1. Edita marca.json
    2. python3 configura.py

Reejecutable las veces que haga falta: recuerda lo que aplico la ultima vez
(en .marca-aplicada.json) y sustituye eso por lo nuevo. No hay que descomprimir
el ZIP de cero para cambiar un color.

Tambien de una sola tacada, sin editar el fichero a mano:

    python3 configura.py --set nombre_display="Barberia Lopez" ciudad="Sevilla"

Y para ver que tocaria sin tocar nada:

    python3 configura.py --simular
"""

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
MARCA = RAIZ / "marca.json"
APLICADA = RAIZ / ".marca-aplicada.json"

# Ficheros del propio instalador: nunca se tocan, o se reescribirian los
# ejemplos de esta misma documentacion.
NO_TOCAR = {
    "configura.py", "marca.json", ".marca-aplicada.json",
    "EMPIEZA-AQUI.md", "INSTALAR.md", "CLAUDE.md", ".env.example",
}
EXTENSIONES = {".py", ".html", ".j2", ".md", ".json", ".txt"}
CARPETAS_FUERA = {"venv", ".git", "__pycache__", "sesiones", "modelos",
                  "node_modules", ".vercel"}

CLAVES_TEXTO = ["nombre_display", "nombre_logo", "ciudad", "barbero", "dominio"]
CLAVES_COLOR = ["color_principal", "color_principal_oscuro", "color_principal_claro",
                "color_secundario", "color_secundario_medio", "color_secundario_claro",
                "color_papel"]
TODAS = CLAVES_TEXTO + CLAVES_COLOR

# Lo que trae el ZIP recien descomprimido. Es el punto de partida cuando aun
# no existe .marca-aplicada.json.
ORIGEN = {
    "nombre_display": "Barbería Demo",
    "nombre_logo": "BARBERÍA DEMO",
    "ciudad": "Tu Ciudad",
    "barbero": "Tu Barbero",
    "dominio": "tu-dominio.com",
    "color_principal": "#C2102E",
    "color_principal_oscuro": "#8E0B21",
    "color_principal_claro": "#E63946",
    "color_secundario": "#16386B",
    "color_secundario_medio": "#2E6CB8",
    "color_secundario_claro": "#5AA9E6",
    "color_papel": "#F4F1EC",
}


def leer(ruta, defecto):
    if not ruta.exists():
        return dict(defecto)
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return {k: datos.get(k, defecto[k]) for k in defecto}


def ficheros():
    for p in sorted(RAIZ.rglob("*")):
        if not p.is_file() or p.suffix not in EXTENSIONES:
            continue
        if p.name in NO_TOCAR or p.name.startswith("."):
            continue
        if CARPETAS_FUERA & set(p.relative_to(RAIZ).parts):
            continue
        yield p


def parejas(antes, ahora):
    """De->a, ordenadas de mas larga a mas corta para no partir un texto que
    contiene a otro (p.ej. el logo dentro del nombre)."""
    fuera = []
    for k in TODAS:
        viejo, nuevo = str(antes[k]), str(ahora[k])
        if viejo and viejo != nuevo:
            fuera.append((viejo, nuevo, k))
    return sorted(fuera, key=lambda t: -len(t[0]))


def sustituir(texto, cambios):
    total = 0
    for viejo, nuevo, _ in cambios:
        # Los colores, sin distinguir mayusculas: en el CSS conviven #c2102e y #C2102E.
        if viejo.startswith("#"):
            patron = re.compile(re.escape(viejo), re.IGNORECASE)
            texto, n = patron.subn(nuevo, texto)
        else:
            n = texto.count(viejo)
            texto = texto.replace(viejo, nuevo)
        total += n
    return texto, total


def main():
    args = sys.argv[1:]
    simular = "--simular" in args

    nueva = leer(MARCA, ORIGEN)

    if "--set" in args:
        for arg in args[args.index("--set") + 1:]:
            if "=" not in arg:
                continue
            k, v = arg.split("=", 1)
            if k not in TODAS:
                print(f"  ! clave desconocida, la ignoro: {k}")
                continue
            nueva[k] = v
        if not simular:
            crudo = json.loads(MARCA.read_text(encoding="utf-8")) if MARCA.exists() else {}
            crudo.update({k: nueva[k] for k in TODAS})
            MARCA.write_text(json.dumps(crudo, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")

    # nombre_logo por defecto = el nombre en mayusculas, si no lo han tocado
    if nueva["nombre_logo"] == ORIGEN["nombre_logo"] and \
       nueva["nombre_display"] != ORIGEN["nombre_display"]:
        nueva["nombre_logo"] = nueva["nombre_display"].upper()

    antes = leer(APLICADA, ORIGEN)
    cambios = parejas(antes, nueva)

    if not cambios:
        print("Nada que cambiar: marca.json ya esta aplicado.")
        return

    print("Cambios a aplicar:")
    for viejo, nuevo, k in cambios:
        print(f"  {k:26} {viejo}  ->  {nuevo}")
    print()

    tocados = 0
    for p in ficheros():
        original = p.read_text(encoding="utf-8", errors="ignore")
        nuevo_texto, n = sustituir(original, cambios)
        if n:
            tocados += 1
            print(f"  {p.relative_to(RAIZ)}  ({n})")
            if not simular:
                p.write_text(nuevo_texto, encoding="utf-8")

    if simular:
        print(f"\n(simulacion) {tocados} ficheros se tocarian. No he escrito nada.")
        return

    APLICADA.write_text(json.dumps({k: nueva[k] for k in TODAS},
                                   ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(f"\nListo: {tocados} ficheros actualizados.")
    print("Arranca con:  cd 06-app && ./arrancar.sh")


if __name__ == "__main__":
    main()
