# Visagismo para barberías — Blueprint

> Blueprint del negocio · v1, 31-ago-2026
> Modelo elegido: white-label + servicio · JV en solitario de momento

---

## 1. La tesis

Sicker Black vende análisis de imagen **a consumidor final** con tráfico frío de TikTok.
Su cuello de botella es que **cada informe lo escribe una persona en Canva** (verificado en
los metadatos del PDF: `Creator: Canva`, `Author: vbolanoso`). No escala.

Y no puede arreglarlo, porque su propia promesa se lo prohíbe. Su landing dice literalmente:

> "Nada de inteligencia artificial. Nada de filtros automáticos. Un experto en visagismo
> analizará **personalmente** tu rostro."

Mientras tanto, en su TikTok se le ve en pantalla escribiendo el prompt de IA para generar
el "después" de sus clientes. **Está atrapado**: si automatiza, miente; si no automatiza,
no crece. Esa contradicción es su techo, y es nuestra puerta.

**El barbero tiene justo lo que a él le falta**: tráfico caliente, cautivo y recurrente,
con confianza ya construida y las manos literalmente sobre la cabeza del cliente.
Lo que al barbero le falta es el **criterio estructurado** y el **artefacto** que convierte
una opinión de pasillo en un servicio cobrable.

> **No vendemos análisis de visagismo. Vendemos al barbero la capacidad de cobrar por su
> criterio** — y una razón para que el cliente vuelva con fecha puesta.

---

## 2. Lo que hace mal el referente (y qué hacemos distinto)

| Lo que hace Sicker Black | Evidencia | Qué hacemos nosotros |
|---|---|---|
| Líneas dibujadas **a mano con el ratón** en CapCut. Salen torcidas, se ve el cursor. **Cero números** en 13 vídeos | Análisis frame a frame de los 13 TikToks | Medición real con visión por computador. Cada línea lleva su ratio y su desviación del canon |
| Vocabulario técnico **sin técnica**: "morfología facial", "rostro en diamante". Ni un término de antropometría real | Transcripción íntegra de los 13 audios | Métricas nombradas y auditables: índice facial, ratio bigonial/bizigomática, tercios, quintos |
| El análisis visual **no llega al producto pagado**. El PDF solo lleva las 2 fotos sin tocar | PDF de 5 páginas revisado | El overlay medido **es** el corazón del informe |
| La página "REFERENCIA" enseña a **otra persona** con el corte propuesto | Página 4 del PDF | Simulación sobre la cara del propio cliente, marcada como generada por IA |
| Diagnóstico circular: "la forma es cuadrada, *tal como viene indicada en tu análisis*" | Página 3 del PDF | El morfotipo sale de una regla explícita con sus números al lado |
| **Nada operativo**: ni qué pedirle al barbero, ni producto, ni cuándo volver | PDF completo | Ficha para el barbero + plan de 6 meses con fechas |
| Urgencia falsa: countdown de 2h que **se resetea en cada carga** | Verificado en la landing | Sin countdown. La escasez real (agenda del barbero) ya existe |
| Niega usar IA mientras la usa | Landing vs. TikTok | "Análisis asistido por IA, **revisado y firmado por tu barbero**" |

---

## 3. El proceso end-to-end

### FASE 0 — Alta de la barbería *(una vez, ~20 min)*
Marca, logo, colores, precios, huecos de agenda. Contrato de encargo (art. 28 RGPD) firmado.
Se genera su subdominio propio. El barbero hace **un análisis de prueba consigo mismo**:
es la mejor formación posible y le da su propio informe como material de venta.

### FASE 1 — Captura *(en la silla, 3 min)*
El barbero abre la app en su móvil o tablet. Guía de encuadre en pantalla (óvalo + nivel)
que **no deja disparar** si la cara está girada, la luz es mala o hay sombra dura.
Frontal + perfil + 3/4. Cuestionario corto **en voz**: el barbero pregunta, la app transcribe.

> **Esto es una diferencia de producto, no un detalle.** Sicker Black recibe fotos random
> por formulario y por eso su análisis tiene que ser vago. Foto controlada = medición fiable.

### FASE 2 — Motor *(automático, ~90 s)*
1. **Medición** — MediaPipe, 468 puntos, en servidor propio en la UE. Sale un JSON de métricas.
2. **Reglas** — clasificación determinista del morfotipo y detección de desviaciones del canon.
3. **Redacción** — el LLM escribe **solo sobre los hallazgos que el motor le pasa**.
   Nunca inventa una medida. *(Ver §5: es el antídoto contra el "se nota que es IA".)*
4. **Simulación** — image-to-image sobre la foto real, 2-3 variantes.
5. **Verificación de identidad** ⭐ — *(ver §4bis)* se vuelve a medir la cara generada y se
   compara con la original. Si alguna proporción se desvía por encima del umbral, se rechaza.
6. **Render** — informe web + ficha del barbero.

### FASE 3 — Compuerta humana *(el barbero, 5 min)* ⭐
El barbero ve el borrador, **ajusta lo que no comparte** y firma. Nada sale sin su OK.

> Esta fase es el producto entero. Es lo que nos hace honestos (no mentimos como el
> referente), lo que nos cubre legalmente, y lo que hace que el informe suene a barbero
> y no a robot. También es lo que el barbero puede defender delante del cliente.

### FASE 4 — Entrega *(automática)*
Link web con la marca de la barbería + PDF descargable. Por WhatsApp desde el número
de la barbería. El informe **no caduca**: es el historial del cliente.

### FASE 5 — Ejecución *(el corte)*
El barbero trabaja con la ficha operativa delante: medidas, máquina, guía de corte, producto.
Foto de resultado al terminar → se añade al informe como "antes / después real".

### FASE 6 — Recurrencia ⭐
El informe incluye **plan de 6 meses con fechas concretas** de vuelta y qué se hace en cada
visita. Recordatorio automático. **Aquí está el negocio**: el referente entrega y se acaba;
nosotros entregamos un calendario.

---

## 4. Arquitectura

```
[PWA de captura]  ──fotos+cuestionario──>  [API UE]
     guía de                                   │
     encuadre                                  ├─> MediaPipe (servidor propio UE) ─> métricas JSON
                                               ├─> Motor de reglas ─> hallazgos JSON
                                               ├─> LLM redactor (solo sobre hallazgos)
                                               ├─> Generador de imagen ─> simulación + marca IA
                                               └─> Render ─> informe web + ficha barbero + PDF
                                                          │
                                          [Compuerta: el barbero revisa y firma]
                                                          │
                                                    [Entrega WhatsApp]
                                                          │
                                                    [Plan 6 meses + recordatorios]
```

**Decisiones de arquitectura que son caras de cambiar después** (del informe legal):

- La medición corre **en servidor propio en la UE**. Ya funciona en local; se mantiene así.
  Elimina una capa entera de transferencia internacional.
- **Nunca** se guarda una plantilla biométrica reutilizable. Los 468 puntos se calculan,
  se usan y se descartan. Esto es lo que nos mantiene fuera del art. 9 RGPD.
- **Nunca** se construye "reconocer si este cliente ya vino". Cruza la línea al art. 9.
  El historial se vincula por ID de cliente, jamás por su cara.
- Borrado automático por TTL, no manual.
- Tres consentimientos **separados**: servicio / mejora del modelo / marketing.

---

## 4bis. El verificador de identidad — el foso real

Probamos la misma foto y el mismo prompt en dos modelos y **medimos las caras generadas con
nuestro propio motor**. Resultado (2026-08-31, sobre una foto real):

| | Nano Banana Pro | GPT Image 2 |
|---|---|---|
| Desviación media de las proporciones | 2,37 % | **1,37 %** |
| Nariz / distancia intercantal *(rasgo diagnosticado)* | **−0,8 %** | −2,9 % |
| Fidelidad al brief (longitud, caída frontal) | **Buena** | Pelo demasiado corto |
| Preservó ropa y fondo | **Sí** | Cambió la raya del polo |
| Coste | **0,8 créditos** | 3,2 créditos |

**El hallazgo:** GPT Image 2 preserva mejor la geometría global, pero **adelgazó la nariz** —
justo el rasgo que el informe señala como protagonista. Si el modelo *arregla* en la imagen lo
que el texto dice que hay que compensar con el pelo, el informe se contradice a sí mismo y el
cliente sale con una expectativa falsa. Ese es el fallo que mata el producto.

**La solución, que además es defendible como propiedad intelectual:** el mismo motor que mide
al cliente **audita la imagen generada**. Se remide la cara sintética, se compara ratio a ratio
con la real, y si alguna se desvía más del umbral se descarta y se regenera. Ningún competidor
puede hacer esto sin tener antes un motor de medición — y VPLP no lo tiene.

> Umbral propuesto de partida: rechazo si la desviación media supera el 3 % o si cualquier
> métrica individual supera el 6 %. A calibrar con volumen real.

**Limitación honesta:** las dos imágenes salieron con encuadre y resolución ligeramente
distintos, lo que introduce ruido en la comparación. El verificador debe normalizar por
distancia interpupilar antes de comparar. Con una sola cara no hay muestra: hay que repetir
la prueba con 20-30 rostros variados antes de fijar el umbral o elegir proveedor.

---

## 4ter. El informe se abre en el móvil, desde WhatsApp

Eso no es un detalle de maquetación: manda sobre el diseño entero.

- **Cero JavaScript.** El trazado de la retícula, los interruptores de capa y el contador
  animado son CSS puro (`stroke-dashoffset`, `:checked`, `@property`). Así abre en cualquier
  visor, incluso el que WhatsApp usa al descargar el fichero. Cumple además la regla de
  `feedback_html_no_javascript`.
- **Las líneas son SVG vectorial, no un PNG quemado.** Es lo que permite animarlas y apagarlas,
  y de paso bajó el informe de 570 KB a **350 KB** ganando funcionalidad.
- **El rostro entra en la primera pantalla.** El titular se recortó y la entradilla se movió
  debajo del visor: al abrirlo desde un chat, lo primero que se ve es la cara midiéndose sola.
- **La secuencia dura ~2,3 s.** Más larga y el lector hace scroll antes de que termine.
- **La capa "Anchuras" arranca apagada.** Con las cinco a la vez el rostro se satura; así la
  primera impresión es limpia y hay un motivo real para tocar los interruptores.
- **Un solo número animado** en todo el informe (el quinto central, 20 → 24). Si se mueve todo,
  no destaca nada — y ahí es donde un diseño empieza a oler a plantilla.
- **Pendiente:** las tipografías se cargan de Google Fonts. Sin datos, el informe cae a las
  fuentes del sistema y pierde carácter. Embeberlas sumaría ~200 KB: decidir con el peso real
  de envío delante.

---

## 4quater. El perfil: lo que se puede y lo que no *(probado 31-ago)*

Se intentaron las dos vías y **ninguna da números fiables hoy**:

- **Medir sobre la foto de perfil.** MediaPipe detecta 478 puntos pero ajusta mal
  la malla: la punta de la nariz cae en el puente, el mentón dentro de la barba y
  el gonion en mitad de la mejilla. Verificado dibujándolos.
- **Derivar el perfil de la coordenada Z del frontal.** El *orden* de profundidades
  sí es anatómicamente correcto y está verificado, pero la *escala* está comprimida
  (profundidad facial 0,69 × anchura, cuando la referencia es 0,93). Se probó un
  factor de calibración y **se descartó**: mover ese factor mueve todos los ángulos
  a la vez, y sin una medida real de referencia es ajustar un parámetro hasta que
  los números queden bonitos. Eso no es medir, y es justo lo que criticamos.

**Lo que sí hace el perfil hoy:** alimenta la simulación lateral, que salió muy bien
y da coherencia entre las dos vistas. Vale como material visual, no como medición.

**Para cerrarlo** hace falta una de tres: calibrar con calibre sobre 10-15 caras,
usar un modelo 3D con escala métrica (3DDFA, DECA), o meter una referencia de escala
en la propia foto.

---

## 5. El antídoto contra el "se nota que es IA"

El texto de Sicker Black suena a IA porque **el LLM se lo inventa todo**. Nuestra regla:

> El LLM **no mide**. Recibe un JSON de hallazgos medidos y solo puede escribir sobre ellos.
> Si un número no está en el JSON, no puede aparecer en el texto.

A eso se suman cuatro reglas de redacción:

1. **Un dato por afirmación.** "Tu quinto central mide 24% cuando el canon marca 20%" en
   lugar de "tienes la nariz protagonista".
2. **Nombrar lo incómodo sin suavizarlo.** Esto el referente lo hace bien y hay que copiarlo.
3. **Prohibido el halago sin dato.** Nada de "tienes una base facial muy buena".
4. **Cada recomendación con su número ejecutable**: cm, mm, número de máquina.

---

## 6. Economía unitaria

**Coste variable por informe** *(estimación a validar con tarifas reales)*:

| Partida | Coste |
|---|---|
| Medición (servidor propio) | ~0,00 € |
| Redacción LLM | 0,05 – 0,15 € |
| Simulación de imagen (2-3 variantes) | 0,10 – 0,45 € |
| Render, hosting, WhatsApp | ~0,05 € |
| **Total** | **~0,20 – 0,65 €** |

### Escenario A — Informe suelto a 40 €
- Cliente final paga 40 € · barbero se queda 30 € · nosotros 10 €
- Margen nuestro por informe: ~9,50 €
- **Riesgo**: la investigación de mercado **no encontró ni una sola barbería española que
  cobre aparte por asesoramiento de imagen**. Lo regalan como gancho. Hay que validarlo.

### Escenario B — Bundle "primera visita" a 75 € ⭐
- Corte (25 €) + análisis + ejecución guiada. El barbero sube ticket de 25 € a 75 €.
- Nosotros: 10 € por informe.
- **Por qué es el mejor**: no le pide al cliente que compre un producto nuevo, le pide que
  compre *mejor* el que ya venía a comprar. Y el barbero cobra por tiempo que ya invertía.

### Escenario C — Gratis como imán + suscripción
- El barbero lo regala para captar. Nosotros cobramos 49 €/mes con X informes incluidos.
- **Ancla de precio real del sector** (verificado): Booksy 34,99 €+IVA/mes, Treatwell desde
  29 €/mes. El sector paga ~30 € por software de gestión. 49 € solo se sostiene si el
  informe demuestra que trae o retiene clientes.

> **Recomendación: empezar por B**, con C como plan de fidelización a los 3 meses.
> A es el que copia al referente y es el que peor encaja con el hábito del sector.

---

## 7. Lo que hay que validar ANTES de construir

1. **Auditar VPLP** (Batatech S.L.) — competidor español que ya vende gestión de barbería
   + "visagismo con IA". *Auditoría en curso.*
2. **¿Paga alguien por esto?** — la señal de mercado es ambigua. 5 llamadas a barberos antes
   de escribir código de producto.
3. **Tarifa real de la API de imagen** — condiciona toda la economía unitaria.
4. **Cifra oficial del sector** — el "5.128 barberías / 3.500 M€" que circula por internet
   **es falso**: se rastreó hasta un sitio de plantillas de plan de negocio sin fuente.
   No usar en ningún documento. El INE separará barbería de estética a partir de jun-2026.
5. **El parecido de la simulación** — si el cliente no se reconoce, el producto muere.

---

## 8. Riesgos

| Riesgo | Gravedad | Mitigación |
|---|---|---|
| La simulación no preserva el parecido | **Alta** | Probar varios modelos; si no llega, entregar solo líneas + referencias |
| El barbero no usa la compuerta y firma a ciegas | Alta | Obligar a tocar al menos un campo antes de poder firmar |
| Expectativa: "me prometiste esta cara" | Alta | Marcado AI Act visible + texto de que es orientativo, no un resultado garantizado |
| El sector no paga por análisis | **Alta** | Validar con llamadas antes de construir. Escenario B lo esquiva |
| VPLP ya lo resolvió | Media | Auditoría en curso |
| Menores en barbería | Media | Filtro de edad antes de la captura; <14 requiere tutor |

---

## 9. Cumplimiento por diseño

- Base jurídica: **art. 6.1.b (ejecución de contrato)**, no consentimiento. Pedir
  consentimiento para lo que *es* el servicio contratado es doctrina equivocada (EDPB 2/2019).
- **Fuera del art. 9** mientras midamos sin identificar (EDPB 3/2019, apdo. 80).
- **EIPD obligatoria**: se activan ≥2 criterios de la lista AEPD (nuevas tecnologías + menores).
- **AI Act art. 50.4**: la simulación **debe ir marcada** como generada por IA.
  Ya exigible desde el 2-ago-2026.
- Autorización de imagen **separada** (LO 1/1982) para publicar antes/después en redes.

---

## 10. Plan de 30 días

| Semana | Qué |
|---|---|
| 1 | Auditar VPLP · 5 llamadas a barberos · tarifas reales de API |
| 2 | Si valida: informe piloto completo con 3 caras reales · elegir proveedor de imagen |
| 3 | Barbería piloto: alta, contrato de encargo, 10 informes reales |
| 4 | Medir: ¿cuántos convierten? ¿vuelven? Decidir escenario de precio y si se sigue |

**Compuerta de decisión**: si en la semana 3 ninguna de las 5 barberías consultadas dice que
lo vendería, se para. No se construye producto contra una intuición sin validar.
