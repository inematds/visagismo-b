# Contexto del proyecto

> Para cualquier sesión de Claude que trabaje en esta carpeta. Si acabas de
> descomprimir el kit y toca montarlo, ve a `INSTALAR.md`.

## Qué es

Motor de análisis facial + generador de informes de visagismo, en blanco de
marca. El profesional vende y firma; el motor mide.

```
landing → pago (simulado) → cuestionario + fotos → espera → informe
```

| Carpeta | Qué es |
|---|---|
| `01-estrategia/` | El negocio: tesis, proceso, economía unitaria, riesgos, marco legal |
| `03-motor/` | El motor: medición, recomendación, simulación, render |
| `04-mockup/` | Un informe de ejemplo |
| `06-app/` | La demo completa de punta a punta (FastAPI) |
| `marca.json` + `configura.py` | La marca. Editar el JSON y ejecutar el script |

## Las cuatro reglas duras

1. **Ninguna frase del informe afirma nada que no venga de una medida o de una
   respuesta del cliente.** Sin esto es un horóscopo.
2. **La simulación pasa por el verificador**: se remide la cara generada contra
   la real y se descarta si el modelo ha retocado el rasgo que el informe
   diagnostica. Es el foso del producto. No desactivarlo.
3. **La persona revisa y firma.** Argumento ético, cobertura legal, y lo que
   evita que el texto suene a robot.
4. **La clave de servicio de Supabase nunca llega a producción.** Producción
   escribe con la anon key y RLS solo le concede INSERT.

## Lo que NO funciona (no presentarlo como bueno)

- **El perfil no se mide.** Se probaron las dos vías y fallan: MediaPipe ajusta
  mal la malla en pose lateral, y derivar el perfil de la Z del frontal da el
  orden correcto pero la escala comprimida. La foto de perfil sí se pide: alimenta
  la simulación lateral, que sí sale bien. Detalle en la cabecera de
  `03-motor/analiza_perfil.py`.
- **El pago es simulado.** Cero `<form>` en el checkout, campos `disabled`.

## Trampas verificadas (no volver a pisarlas)

- **MediaPipe:** instalar con `pip install --no-deps mediapipe==0.10.21` y luego
  `requisitos.txt`. Declara `opencv-contrib-python`, que colisiona con
  `opencv-python-headless` — misma carpeta `cv2/`, gana el último. Del tirón:
  783 MB en vez de 384 MB. **Pero matplotlib hay que dejarla**: `drawing_utils` la
  importa al cargarse. Quitarla parece optimizar y rompe todo.
- **`vercel.json` no admite comentarios.** Una clave `_comentario` tumba el
  despliegue. Y **el bloque `services` no se puede quitar**: sin él Vercel no
  detecta el `Dockerfile.vercel` y el build sale en 58 ms sin preparar nada.
- **Arquitectura síncrona a propósito.** `/generar` devuelve el informe en la
  propia respuesta. El patrón de encolar + sala de espera con polling **no
  funciona en Vercel**: escala a varias instancias, no hay estado compartido y el
  refresco cae en otra máquina. La espera se muestra en el navegador.
- **Middleware de FastAPI: devolver la respuesta, nunca `raise HTTPException`.**
  Los manejadores de error cuelgan del router, que va por dentro del middleware,
  así que lo lanzado ahí sale como 500 sin capturar.
- **Fotos de iPhone (HEIC):** ya resuelto en los dos lados —`createImageBitmap`
  en el navegador, `pillow-heif` en el servidor. OpenCV no lee HEIC y daría un
  «no he encontrado ninguna cara» engañoso.
- **Configuración: leerla en cada llamada, no al importar.** `servidor.py`
  importaba `historial` antes de cargar el `.env.local` y el historial se
  quedaba apagado en silencio mientras los informes salían igual.
- **Supabase Storage:** subir **sin** `x-upsert`. Con upsert exige permiso de
  UPDATE y RLS lo rechaza.

## Datos que NO se usan jamás

- La **proporción áurea** en el rostro: desmentida (revisión de 2024).
- **Claude Juillard** como creador del visagismo: fue **Fernand Aubry, 1936**
  (verificado en CNRTL).
- Alejandro Magno mandando afeitar a sus soldados: apócrifo.
- El «5.128 barberías / 3.500 M€ / +30 % en 5 años» que circula por internet: sin
  fuente, rastreado a un sitio de plantillas de plan de negocio. El INE no separa
  barbería de estética hasta jun-2026 (CNAE 96.21).

Las 31 curiosidades de `06-app/curiosidades.json` llevan fuente y fiabilidad cada
una. **Si añades una, añade su fuente.**

## Legal, resuelto por diseño

- Fuera del art. 9 RGPD **mientras se mida sin identificar** (EDPB 3/2019 §80).
  Nunca guardar plantilla biométrica ni construir «reconocer si este cliente ya
  vino»: eso cruzaría al art. 9.
- Base jurídica art. 6.1.b, **no** consentimiento.
- EIPD obligatoria (≥2 criterios AEPD).
- **AI Act art. 50.4: la simulación debe marcarse como generada por IA.**
  Exigible desde el 2-ago-2026.
