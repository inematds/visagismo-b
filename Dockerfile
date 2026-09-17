FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 VISAGISMO_DATA=/data MPLCONFIGDIR=/tmp/matplotlib
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 libsndfile1 libegl1 libgles2 libgl1 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /app/
RUN pip install --no-cache-dir --no-deps -r requirements.txt
COPY app /app/app
COPY 03-motor /app/03-motor
RUN useradd --uid 10001 --create-home visagismo && mkdir /data && chown -R visagismo:visagismo /data /app
USER visagismo
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]
