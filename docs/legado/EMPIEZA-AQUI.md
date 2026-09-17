# Empieza aquí

Esto es un embudo de venta completo y funcionando: landing → pago → cuestionario
con fotos → informe generado en el momento. El caso es una barbería, pero la
maquinaria sirve para cualquier negocio que venda un diagnóstico.

**No tienes que entender el código. Se lo das a tu Claude y él lo monta.**

---

## Los tres pasos

### 1. Descomprime el ZIP

Deja la carpeta donde la encuentres. El Escritorio vale.

### 2. Ábrela con Claude Code

- **Claude Code (app de escritorio)** → *Abrir carpeta* → elige esta carpeta.
- Si usas la terminal: `cd` a esta carpeta y escribe `claude`.

### 3. Escríbele esto, tal cual

```
Lee INSTALAR.md y móntame esto en mi ordenador. Pregúntame lo que necesites.
```

Ya está. A partir de ahí él te hace las preguntas (cómo se llama tu negocio, tus
colores, qué claves tienes) y lo deja funcionando.

---

## Lo que te va a preguntar, para que lo tengas a mano

| Cosa | ¿Obligatoria? | Dónde se saca |
|---|---|---|
| Nombre, ciudad y colores de tu negocio | No, hay valores por defecto | De tu cabeza |
| Una foto tuya de frente | No, pero conviene | Tu móvil |
| Clave de **fal.ai** | No | fal.ai → API Keys. Es la que genera el "después". Sin ella el informe sale igual, pero sin las imágenes simuladas |
| Clave de **OpenAI** | No | platform.openai.com. Sin ella el informe lo redacta el motor de reglas, que funciona perfectamente |

**Puedes montarlo entero sin poner una sola clave y sin gastar un euro.** El
informe sale completo con las medidas, el diagnóstico y las recomendaciones. Lo
único que falta son las dos imágenes del "antes y después".

---

## Y si quieres entender cómo está pensado

- `README.md` — el mapa técnico: qué hace cada fichero.
- `01-estrategia/blueprint.md` — el negocio entero: la tesis, qué hace mal el
  referente del que salió esto, el proceso paso a paso, la economía unitaria con
  tres escenarios de precio, los riesgos y el marco legal.
- `DESPLIEGUE.md` — cómo ponerlo en internet, con las tres trampas que costaron
  media tarde cada una.

Empieza por el blueprint si lo que quieres es copiar el **modelo**, no el código.
