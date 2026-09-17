# INSTALAR.md — instrucciones para Claude

> Este fichero no está escrito para la persona, está escrito **para ti, Claude**.
> Alguien acaba de descomprimir este kit y te ha pedido que se lo montes. Sigue
> esto de arriba abajo. Está en español porque tu interlocutor lo está.

## Qué es esto y a qué aspiras

Un embudo completo: landing → pago simulado → cuestionario con fotos → informe de
visagismo generado en el momento por un motor que **mide de verdad** la cara
(MediaPipe, 16 proporciones) y redacta recomendaciones a partir de esas medidas.

**Tu objetivo:** que en menos de 20 minutos esta persona vea su propio embudo,
con su marca, corriendo en `http://localhost:8000`, y haya generado un informe
real. Desplegarlo en internet es opcional y viene después.

**Cómo trabajar:** haz las preguntas del paso 1 **todas juntas, en un solo
mensaje**. No vayas de una en una. Después ejecuta sin ir pidiendo permiso paso a
paso; solo párate en las decisiones marcadas 🛑.

---

## Paso 1 · La entrevista (todo en un mensaje)

Pregúntale, avisando de que **puede dejarlo todo en blanco** y responder "por
defecto" — el sistema funciona igual:

1. **Nombre del negocio**, ciudad y nombre de quien firma el informe.
2. **Colores de marca**, si tiene. Si no, se queda la paleta de poste de barbero
   (rojo `#C2102E` + azul `#16386B` sobre papel hueso `#F4F1EC`), que está
   pensada y funciona.
3. **¿Tiene clave de fal.ai?** Es lo que genera la imagen del "después". Sin
   ella todo funciona menos esas dos imágenes. Cuesta ~0,15 $ por imagen,
   ~0,30 € por informe con frontal y perfil.
4. **¿Tiene clave de OpenAI?** Sin ella redacta el motor de reglas, que está
   validado y funciona bien. Con ella la redacción la hace un LLM que ve la foto.
5. **¿Tiene una foto suya de frente?** Le hace falta para dos cosas: probar el
   motor y generar el ejemplo de la landing (el kit no trae ninguna cara).

> **Si no tiene ninguna clave, no insistas.** Dile que se monta igual, que genere
> un informe completo, y que las claves las puede añadir después en `.env.local`
> sin volver a tocar nada.

---

## Paso 2 · Comprobar que hay Python

```bash
python3 --version
```

Vale **Python 3.9 o superior** (verificado en 3.9.6, el que trae macOS de serie).
Si no hay ninguno:
- macOS: `brew install python@3.12` (o descargarlo de python.org)
- Windows: desde python.org, marcando *Add Python to PATH*
- Linux: `sudo apt install python3 python3-venv`

---

## Paso 3 · Aplicar su marca

Edita `marca.json` con lo que te haya dicho y ejecuta:

```bash
python3 configura.py
```

O en una sola línea, sin editar el fichero:

```bash
python3 configura.py --set nombre_display="Barbería López" ciudad="Sevilla" barbero="Paco López"
```

Toca la landing, el checkout, el formulario, la sala de espera, el informe y el
servidor. **Es reejecutable**: recuerda lo que aplicó la última vez, así que puede
cambiar de opinión sobre un color sin descomprimir el ZIP otra vez. Con
`--simular` ves qué tocaría sin escribir nada.

Si no te ha dado nada, sáltate este paso: los valores por defecto
(«Barbería Demo», «Tu Ciudad») ya avisan de que hay que cambiarlos.

---

## Paso 4 · Las claves

Copia la plantilla y rellena solo lo que tenga:

```bash
cp .env.example .env.local
```

🛑 **Nunca escribas una clave dentro de un fichero de código.** Todas van a
`.env.local`, que está en `.gitignore`. Si te pega una clave en el chat, métela
en `.env.local` y no la repitas al responderle.

---

## Paso 5 · Arrancar

```bash
cd 06-app && ./arrancar.sh
```

**La primera vez tarda varios minutos** creando el entorno: MediaPipe y OpenCV
pesan. Avísale antes de lanzarlo para que no crea que se ha colgado.

En Windows sin bash, el equivalente es:

```bash
cd 06-app
python3 -m venv venv
venv\Scripts\pip install --no-deps mediapipe==0.10.21
venv\Scripts\pip install -r requisitos.txt
venv\Scripts\uvicorn servidor:app --port 8000
```

> ⚠️ **Los dos `pip install` separados y el `--no-deps` no son un capricho.**
> MediaPipe exige `opencv-contrib-python`, que colisiona con
> `opencv-python-headless`: comparten la carpeta `cv2/` y gana el último
> instalado. Instalarlo del tirón mete las dos y sube la imagen de 384 MB a
> 783 MB. **Pero `matplotlib` hay que dejarla**: `mediapipe.solutions.drawing_utils`
> la importa al cargarse y sin ella MediaPipe no arranca. Quitarla parece
> optimizar y lo rompe todo.

Abre `http://localhost:8000` y comprueba que la landing carga con su marca.

---

## Paso 6 · Generar su visor de ejemplo

El kit **no trae ninguna cara** a propósito. El hueco de la landing muestra un
recuadro que explica cómo rellenarlo. Con su foto:

```bash
python3 03-motor/genera_visor_ejemplo.py SU-FOTO.jpg 06-app/estatico/_visor-ejemplo.html
```

Recarga la landing y ahí está su retícula. Es la pieza que vende: enséñasela.

---

## Paso 7 · Un informe completo, de punta a punta

Que recorra el embudo él mismo en el navegador: `/` → `/pago` → `/formulario` →
sube foto frontal (y de perfil si quiere) → espera.

Tarda **~50-60 segundos** con las dos vistas si hay `FAL_KEY`; bastante menos sin
ella. La pantalla de espera es real, no un truco: mientras se genera muestra el
proceso y una de 31 curiosidades verificadas.

**Si algo falla, mira aquí antes de improvisar:**

| Síntoma | Causa casi siempre |
|---|---|
| «No he encontrado ninguna cara» | Foto de perfil, muy oscura, o con la cara pequeña. Pide una frontal con luz |
| El informe sale sin las imágenes de simulación | Falta `FAL_KEY` o la cuenta se quedó sin saldo. **El log lo dice literalmente** — léelo antes de teorizar |
| Error al instalar MediaPipe | Python 3.13 todavía da guerra. Prueba con 3.11 o 3.12 |
| Avisos rojos de pip: «mediapipe requires jax / opencv-contrib-python…» | **Normales y buscados.** Es el `--no-deps` haciendo su trabajo. Si termina con el entorno creado, está bien |
| Se cuelga al subir una foto del iPhone | Es HEIC. Ya está resuelto en el código (`pillow-heif` en el servidor, `createImageBitmap` en el navegador), pero si el navegador es viejo, pídele un JPEG |

---

## Paso 8 · Desplegarlo (solo si lo pide)

🛑 **Pregúntale antes.** No despliegues nada por iniciativa propia: cuesta dinero
y publica una web a su nombre.

Si dice que sí, `DESPLIEGUE.md` tiene el procedimiento entero. Los tres puntos
que le van a costar y que ya están resueltos ahí:

1. **Vercel no detecta `Dockerfile.vercel` solo.** Hay que declarar el bloque
   `services` en `vercel.json`. Sin él el build sale en 58 ms sin preparar nada.
   **No quites ese bloque.**
2. **`vercel.json` no admite comentarios.** Una clave `_comentario` tumba el
   despliegue con `should NOT have additional property`.
3. **Los proyectos nacen con protección de acceso.** Todo devuelve
   «Login – Vercel» hasta que se quita en *Settings → Deployment Protection*.

Y avísale de dos cosas: que ponga `CLAVE_DEMO` desde el minuto uno (si no,
cualquiera que encuentre la URL le gasta ~0,30 € por informe), y que Vercel
despliega en Washington, no en la UE — con fotos de caras de por medio, eso hay
que decidirlo a conciencia, no por defecto.

---

## Las reglas del producto que NO debes romper al modificarlo

Estas tres no son estilo. Son lo que hace que el producto valga algo:

1. **Ninguna frase del informe puede afirmar nada que no venga de una medida o de
   una respuesta del cliente.** En cuanto empieza a rellenar con adjetivos, es
   un horóscopo. Si te piden "que suene mejor", que suene mejor con los números
   delante.
2. **La simulación pasa por el verificador.** El motor remide la cara generada y
   la compara con la real; si el modelo ha "embellecido" justo el rasgo que el
   informe diagnostica, se descarta. Un informe que se contradice a sí mismo no
   vale nada. **Esto es el foso del producto: no lo desactives para que salgan
   más imágenes bonitas.**
3. **La persona revisa y firma.** La máquina mide y redacta; el profesional
   decide. Es a la vez el argumento ético, la cobertura legal, y lo que hace que
   el texto no suene a robot.

Y una técnica:

4. **La clave de servicio de Supabase no llega nunca a producción.** Producción
   escribe con la clave pública y RLS solo le concede INSERT. La de servicio salta
   RLS y abriría la base de datos entera desde una web pública.

---

## Lo que está a medias, para que no lo vendas como terminado

- **El perfil no se mide.** La foto de perfil se pide y se usa para la simulación
  lateral, pero **sus números no son fiables**: MediaPipe ajusta mal la malla en
  pose lateral. Está documentado en la cabecera de `03-motor/analiza_perfil.py`.
  No lo actives ni presentes esos datos como buenos.
- **El pago es simulado.** No hay pasarela: cero `<form>` en el checkout y los
  campos de tarjeta van `disabled`. Enchufar Stripe es trabajo aparte.
- **Antes de usarlo con clientes reales** hacen falta contrato de encargo
  (art. 28 RGPD), evaluación de impacto, filtro de edad, y marcar la simulación
  como generada por IA (art. 50.4 del AI Act, exigible desde el 2-ago-2026).
  Todo detallado en `01-estrategia/blueprint.md` §9.

---

## Cuando termines

Dile en cuatro líneas: qué está funcionando, qué le falta por poner (claves que
no tenía), cuál es el siguiente paso concreto, y que `CLAUDE.md` tiene el
contexto para que cualquier sesión futura en esta carpeta sepa de qué va.

Y recuérdale lo único que de verdad importa: **el código es la parte fácil.**
Lo que hace que esto se venda está en `01-estrategia/blueprint.md`, y ahí la
primera compuerta es validar que alguien paga antes de construir más.
