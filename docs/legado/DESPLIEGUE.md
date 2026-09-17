# Despliegue

Una vez desplegado, tu URL será algo del estilo `https://tu-proyecto.vercel.app`.

Todo en Vercel, como contenedor sobre Vercel Functions. Sin plataformas nuevas
y sin factura extra.

---

## Las tres cosas que costó descubrir

Están aquí para que nadie las vuelva a sufrir.

### 1 · Vercel no detecta el `Dockerfile.vercel` por sí solo

Su documentación dice que sí. En esta cuenta no: el build salía en 58 ms con
`no files were prepared` y el sitio devolvía 404. Hay que **declarar el servicio
explícitamente** en `vercel.json`, y ese bloque no se puede quitar:

```json
{
  "services": { "motor": { "root": ".", "entrypoint": "Dockerfile.vercel" } },
  "rewrites": [{ "source": "/(.*)", "destination": { "service": "motor" } }]
}
```

> No era el permiso «Container Images», que fue la primera sospecha. El registro
> de contenedores ya estaba disponible en la cuenta.

### 2 · `vercel.json` no admite comentarios

Valida el esquema de forma estricta. Una clave `_comentario` que añadí para
documentar el bloque anterior tumbó tres despliegues seguidos con
`should NOT have additional property`. Las explicaciones van en el README.

### 3 · La protección de acceso viene activada

Los proyectos nacen con *Vercel Authentication* puesta y todo devuelve
«Login – Vercel». Se quita en *Settings → Deployment Protection*.

---

## Variables de entorno

*Settings → Environment Variables*

| Key | Obligatoria | Para qué |
|---|---|---|
| `FAL_KEY` | **Sí** | Genera las simulaciones. Sin ella el informe sale igual, pero sin imágenes |
| `HORAS_RETENCION` | No | Horas que se guardan las fotos. Por defecto 24 |
| `LIMITE_DIARIO` | No | Tope de informes al día. Sin definir = sin tope |
| `CLAVE_DEMO` | **Sí, mientras no sea pública** | Deja toda la demo tras una clave. **Si se borra, la demo queda abierta a cualquiera**, con `/generar` gastando ~0,30 € por informe |
| `SUPABASE_URL` | Para el historial | La URL de tu Supabase. Sin esto no se guarda el historial y la demo funciona igual |
| `SUPABASE_ANON_KEY` | Para el historial | La clave **pública**. ⚠️ **La de servicio NUNCA aquí**: salta RLS y daría acceso a toda la base de datos desde una demo pública |
| `DIAS_HISTORIAL` | No | Días que vive el HTML guardado (lleva las fotos dentro). Por defecto 90. `0` = solo la ficha de datos |
| `GUARDAR_FOTOS` | No | `si` para archivar también las fotos originales. Desactivado a propósito |
| `OPENAI_API_KEY` | Para el análisis con LLM | Sin ella el informe sale con el motor de reglas, que funciona. Con ella lo redacta el LLM viendo las fotos |
| `MODELO_IA` | No | Modelo a usar. Por defecto `gpt-5.5` |

Tras añadirlas: **Redeploy**.

---

## Cómo funciona por dentro

**`/generar` es síncrono.** Hace todo el trabajo y devuelve el informe en la
propia respuesta. Tarda ~60 s con las dos vistas.

> Antes encolaba en un hilo y mandaba a una sala de espera que consultaba cada
> 6 s. **Eso no funciona en Vercel**: escala a varias instancias, así que la
> sesión se creaba en el disco de una y la consulta caía en otra →
> «Esa sesión no existe». Sin estado compartido, no puede repetirse.

**El análisis lo hace un LLM viendo las fotos**, y recibe también las 16
proporciones ya medidas: así puede citar números que a ojo no se estiman. Devuelve
el diagnóstico, entre uno y tres estilos con su encaje, y el prompt con el que se
genera la imagen. Si no hay `OPENAI_API_KEY` o la llamada falla, el informe sale
con el motor de reglas y no se rompe nada.

> ⏱️ **Suma unos 50 s al informe.** Con simulación de imagen son ~110 s en total.
> La pantalla de espera lo cubre, pero conviene saberlo antes de enseñarlo.

**La instrucción de conservar la identidad la ponemos nosotros, no el LLM.** El
prompt que escribe el modelo se envuelve con `BASE_IDENTIDAD` y con la coletilla
de perfil: son las que sostienen al verificador y no pueden depender de lo que
redacte un modelo.

**La clave se comprueba en un middleware**, una sola vez, para todas las rutas
a la vez (menos `/clave` y `/robots.txt`). Ponerla ruta por ruta es lo que hace
que un día se añada una nueva y se quede fuera. Se entra una vez y queda una
cookie firmada durante 30 días; la firma se deriva de la propia clave, así que
al cambiar la clave caducan solas todas las cookies emitidas con la anterior.

> Dentro de un middleware hay que **devolver** la respuesta, no lanzar
> `HTTPException`: los manejadores de error de FastAPI cuelgan del router, que
> va por dentro del middleware, así que una excepción lanzada ahí sube por
> encima y sale como un 500 sin capturar. Con `raise` un POST a `/generar` sin
> clave daba error feo en vez de un 401 limpio.

**La espera se muestra en el navegador**, no la sirve el servidor: poste
girando, los pasos reales del motor y las 31 curiosidades rotando.

**El envío va por `fetch`, no por navegación normal.** Al enviar un formulario
de la forma clásica el navegador congela la página que abandona y deja de
repintarla: la espera se activaba pero nunca llegaba a verse.

**Las fotos se reducen en el móvil** a 1280 px antes de subirse, con un tope de
1,5 MB por foto. Vercel corta cualquier petición de más de 4,5 MB y una foto de
iPhone pesa entre 3 y 8 MB. Es el **único JavaScript de la demo**; el informe
que se manda por WhatsApp sigue sin una sola línea.

**HEIC funciona por partida doble**: el navegador lo convierte con
`createImageBitmap` (Safari lo abre), y si no puede, el servidor lo convierte
con `pillow-heif` antes de medir. OpenCV no lee HEIC.

---

## Al enseñarlo

**Ábrelo tú un minuto antes.** El contenedor se duerme a los 5 minutos sin
tráfico y la imagen pesa 780 MB: el primer acceso tarda en despertar.

**La pestaña se queda cargando ~60 s** mientras genera. La pantalla de espera lo
tapa, pero conviene saberlo.

**Cada informe cuesta ~0,30 €** en generación de imagen. Sin tope, por decisión
propia. Se activa definiendo `LIMITE_DIARIO`.

**«Barbería Demo» es ficticia** y así se dice en el propio informe. Para una
barbería real se cambian nombre, ciudad y barbero en `06-app/servidor.py`
(constante `BARBERIA`).

---

## Si algo falla

| Síntoma | Causa |
|---|---|
| El sitio devuelve 404 | Falta el bloque `services` de `vercel.json` |
| El build falla nada más empezar | Hay algo que `vercel.json` no reconoce |
| «Login – Vercel» | La protección de acceso sigue activada |
| Entra cualquiera sin pedir clave | Falta `CLAVE_DEMO` en Vercel, o se desplegó sin ella |
| Pide la clave y la correcta no entra | La variable tiene un espacio o un salto de línea de más al copiarla |
| El informe sale sin simulaciones | Falta `FAL_KEY` o fal.ai se quedó sin saldo. El log lo dice literalmente |
| «No he encontrado una cara en esa foto» | La foto no vale: hace falta primer plano de frente, buena luz, sin gafas de sol. Es el motor avisando, no un error |

El build de la imagen está verificado en Linux por GitHub Actions
(`.github/workflows/docker.yml`), así que un fallo de build sería del entorno de
Vercel, no del Dockerfile.

---

## Antes de cobrar por esto

Sigue pendiente lo del blueprint (`01-estrategia/blueprint.md`): contrato de
encargo art. 28 RGPD, evaluación de impacto, filtro de edad, y la transferencia
internacional que introduce fal.ai (procesa en EEUU).
