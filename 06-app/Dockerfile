# Imagen de la demo de visagismo.
#
# No va en serverless (ver README): el limite de 4,5 MB por peticion de Vercel
# no admite dos fotos de movil, su disco no persiste entre invocaciones y el
# hilo de fondo que hace el trabajo de ~55 s no tiene garantia de sobrevivir.
FROM python:3.11-slim

# opencv y mediapipe necesitan estas bibliotecas del sistema en Debian 12.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Instalacion mínima, y el motivo ──────────────────────────────────────────
# mediapipe declara como obligatorias opencv-contrib-python, jax, jaxlib,
# sentencepiece y sounddevice. Ninguna la usa esta app, y opencv-contrib-python
# ADEMAS colisiona con opencv-python-headless: los dos escriben en la misma
# carpeta cv2/ y gana el que se instale ultimo, de forma no determinista.
# (Verificado: en el entorno de desarrollo acabaron conviviendo las dos.)
#
# Por eso mediapipe se instala con --no-deps y se anaden a mano solo las que
# necesita de verdad. matplotlib SI hace falta pese a no usarla nosotros:
# mediapipe.solutions.drawing_utils importa matplotlib.pyplot al cargarse,
# y sin ella el paquete ni siquiera se puede importar. Comprobado.
RUN pip install --no-cache-dir --no-deps mediapipe==0.10.21 \
    && pip install --no-cache-dir \
        "numpy<2" \
        opencv-python-headless==4.10.0.84 \
        matplotlib \
        absl-py \
        "attrs>=19.1.0" \
        "flatbuffers>=2.0" \
        "protobuf<5,>=4.25.3" \
        fastapi \
        "uvicorn[standard]" \
        python-multipart \
        jinja2 \
        fal-client \
        pillow-heif

COPY 03-motor/ ./03-motor/
COPY 06-app/ ./06-app/

WORKDIR /app/06-app
RUN mkdir -p sesiones

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["sh", "-c", "uvicorn servidor:app --host 0.0.0.0 --port ${PORT:-8000}"]
