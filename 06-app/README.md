# Demo comercial — Análisis de visagismo

El embudo completo, de punta a punta, para **enseñarlo**:

```
landing  →  pago (simulado)  →  cuestionario + fotos  →  sala de espera  →  informe real
```

Identidad visual: **papel hueso con rojo y azul de poste de barbero**, tipografías
Bricolage Grotesque + Archivo + JetBrains Mono. El poste gira de verdad, en CSS puro,
y aparece en las cuatro pantallas.

## Arrancar

```bash
./arrancar.sh
```

Abre `http://localhost:8000`. La primera vez tarda unos minutos creando el entorno.

## Qué es real y qué no

| Pieza | Estado |
|---|---|
| Medición facial (468 puntos) | **Real.** MediaPipe en local |
| Motor de recomendación | **Real.** Reglas explícitas sobre las medidas |
| Textos del informe | **Reales.** Generados desde los hallazgos medidos |
| Plan de citas | **Real.** Fechas calculadas desde hoy |
| Cobro | **Simulado.** No hay pasarela ni se piden datos de tarjeta |
| Sala de espera | **Real.** Se refresca sola cada 6 s, sin JavaScript |
| Curiosidades | **31, verificadas** contra fuentes primarias — ver abajo |
| Simulación de imagen IA | **Activa.** fal.ai · `nano-banana-pro/edit` · ~0,15 $/imagen |
| Verificador de identidad | **Activo.** Remide la cara generada; si se desvía, no se publica |
| Medición del perfil | **No existe.** La foto de perfil solo alimenta la simulación |
| Revisión del barbero | **No está.** En producción, nada se entrega sin su firma |

## Coste por informe

La simulación llama a fal.ai una vez por vista. Con frontal + perfil:
**~0,30 € por informe generado**. Si falta `FAL_KEY` en el entorno, el informe
sale igual pero sin simulación — no se rompe nada.

El informe tarda **unos 50 segundos** de punta a punta, casi todo esperando al
generador de imagen.

## Sobre la foto de perfil

Se pide, se guarda y se usa para la simulación lateral. **No se mide sobre ella.**
MediaPipe no ajusta bien la malla en esa pose: da números plausibles pero falsos
(ver la cabecera de `03-motor/analiza_perfil.py`, con la evidencia). Cuando haya
un método de medición de perfil que se sostenga, se añade.

## Aviso legal

Todo el flujo declara que la barbería es ficticia y que la medición es real.
En producción hacen falta: contrato de encargo (art. 28 RGPD), EIPD, filtro de edad
y borrado automático a 90 días. Ver `01-estrategia/blueprint.md`.


## La espera

`/generar` hace **todo el trabajo en la propia petición** y devuelve el informe en la
respuesta. Tarda ~60 s con las dos vistas.

> Antes encolaba en un hilo y mandaba a una sala de espera que hacía polling. **Eso no
> funciona en Vercel**: escala a varias instancias, así que el POST creaba la sesión en el
> disco de una y el refresco caía en otra → «Esa sesión no existe». Sin estado compartido,
> el problema no puede repetirse. Si algún día hace falta polling o historial entre
> peticiones, hay que meter almacenamiento externo (Supabase Storage).

La espera se muestra **en el navegador** mientras la petición viaja: poste girando, los
pasos reales del motor y las 31 curiosidades rotando con un salto de 7 (31 es primo, así
recorre todas sin repetir y cambiando de tema).

La página explica además cómo funciona el proceso **de verdad**: que esto es una demo, que
en una barbería real Toni revisa y firma el informe, y que llega por WhatsApp en dos o tres
días. Es el argumento de la revisión humana, puesto justo donde el cliente está esperando.

## Las curiosidades

`curiosidades.json` — 31 datos verificados contra fuentes primarias (CNRTL, Worshipful
Company of Barbers, revisiones dermatológicas, PubMed). Cada una guarda su fuente y su
nivel de fiabilidad, aunque no se muestren.

**Se descartaron cuatro mitos muy extendidos**, y conviene no reintroducirlos nunca:
- Que el rostro ideal sigue la proporción áurea → desmentido por una revisión de 2024.
- Que Claude Juillard acuñó «visagismo» → fue **Fernand Aubry, en 1936** (CNRTL).
- Que Alejandro Magno mandó afeitar a sus soldados → apócrifo.
- Que un cabello aguanta el peso de dos elefantes → extrapolación viral sin estudio.

En un producto que se vende por medir de verdad, colar un dato falso en la pantalla de
espera nos desmontaría solos.


## Publicar la demo

**Vercel no vale para esto.** No por el tamaño —caben 500 MB y los wheels de Linux
suman 263 MB— sino por tres muros:

| Límite de Vercel | Lo que necesitamos |
|---|---|
| **4,5 MB por petición**, fijo en todos los planes | Dos fotos de móvil (3-8 MB cada una) |
| `/tmp` no persiste entre invocaciones | Guardar el informe y servirlo por URL después |
| Sin garantía de trabajo en segundo plano en Python | Un hilo de **55 s** que sobrevive a la respuesta |

Ninguno se arregla subiendo de plan. Va en **contenedor**.

### Por qué el Dockerfile instala mediapipe con `--no-deps`

`mediapipe` declara como obligatorias `opencv-contrib-python`, `jax`, `jaxlib`,
`sentencepiece` y `sounddevice`. **Ninguna la usa esta app**, y `opencv-contrib-python`
además **colisiona** con `opencv-python-headless`: los dos escriben en la misma carpeta
`cv2/` y gana el que se instale último, de forma no determinista. En el entorno de
desarrollo acabaron conviviendo las dos versiones sin que nadie se diera cuenta.

Con `--no-deps` + la lista mínima, el entorno pasa de **783 MB a 384 MB**.

⚠️ **`matplotlib` sí hace falta** aunque no la usemos: `mediapipe.solutions.drawing_utils`
importa `matplotlib.pyplot` al cargarse, y sin ella mediapipe ni siquiera se puede
importar. Está comprobado — quitarla parece una optimización y rompe el arranque.

### Desplegar en Render

`render.yaml` en la raíz del proyecto, apuntando a `06-app/Dockerfile`, región
**Frankfurt** (la app procesa fotos de rostros y el proyecto exige tratamiento en la UE).

1. Subir el proyecto a un repositorio Git.
2. En Render: *New → Blueprint*, apuntar al repositorio. Lee `render.yaml` solo.
3. Definir `FAL_KEY` **a mano en el panel** (va con `sync: false`, nunca en el repo).
4. Confirmar el precio del plan en el propio panel antes de aceptar.

**Sin verificar:** el Dockerfile no se ha podido construir ni probar (no hay Docker en
la máquina de desarrollo). La receta de dependencias sí está verificada en un entorno
limpio; lo que falta por comprobar es el `build` en Linux.

### Protecciones de una demo pública

Configurables por variable de entorno:

| Variable | Por defecto | Para qué |
|---|---|---|
| `LIMITE_DIARIO` | 40 | Tope de informes al día. A ~0,30 € cada uno, sin esto un enlace público es una factura abierta |
| `HORAS_RETENCION` | 24 | Las fotos y los informes se borran solos. Se limpia en cada generación, sin cron que se pueda olvidar |
| `CLAVE_DEMO` | *(vacío)* | Si se define, toda la demo queda tras esa clave. Vacío = demo abierta |
| `SUPABASE_URL` | *(vacío)* | Historial de informes. Sin esto no se guarda nada y la demo funciona igual |
| `SUPABASE_ANON_KEY` | *(vacío)* | Clave **pública**. Solo puede insertar: no lee nada. La de servicio NO va aquí |
| `DIAS_HISTORIAL` | 90 | Días que se conserva el HTML (lleva las fotos dentro). `0` = guardar solo la ficha de datos |
| `GUARDAR_FOTOS` | *(no)* | `si` guarda también las fotos originales. Permite volver a medir casos viejos; es acumular caras |
| `FAL_KEY` | *(de `.env.local`)* | Sin ella el informe sale sin simulación, no se rompe |

### Historial de informes

Cada generación escribe una fila en `visagismo_informes` (Supabase, `eu-south`) y
sube el HTML a su bucket. **También se registran los fallos** — sobre todo el
«no he encontrado una cara», que es la cifra que dice si el producto aguanta
fotos de gente real. Estructura y políticas en `historial.sql`.

Por qué hace falta: el disco del contenedor de Vercel es efímero y por
instancia, así que sin esto los informes desaparecen y no hay nada que evaluar.

Se guardan dos cosas de naturaleza distinta, y por eso van separadas:

- **La ficha de datos** (medidas, morfotipo, receta, respuestas, coste, tiempo).
  No contiene la cara. Se guarda siempre y sin plazo. Es lo que sirve para evaluar.
- **El informe HTML**, que lleva las fotos incrustadas. Caduca a los
  `DIAS_HISTORIAL` días. **El nombre del cliente no se guarda** en ningún caso.

Para mirarlo hay tres vistas: `visagismo_por_dia`, `visagismo_morfotipos` y
`visagismo_fiabilidad`.

Nada de esto puede tumbar la entrega: si Supabase está caído, el cliente recibe
su informe igual y el log lo dice.

Para verlo, desde el Mac (necesita la clave de servicio, que solo está aquí):

```bash
./venv/bin/python historial.py --resumen
```

El borrado por plazo **tampoco lo hace el servidor** (su clave no tiene permiso
para borrar, y es deliberado):

```bash
./venv/bin/python historial.py --purgar
```

Además: `robots.txt` que lo prohíbe todo y cabecera `X-Robots-Tag: noindex` en cada
página. Son fotos de caras: esto no puede acabar indexado en Google.
