"""Teste temporário: não abre porta nem mantém serviço ativo."""
from pathlib import Path
from fastapi.testclient import TestClient
from PIL import Image
from skimage import data
from app.main import app
from app.engine import analyze
photo=Path('/tmp/visagismo-smoke.jpg')
Image.fromarray(data.astronaut()).save(photo)
result=analyze(photo,{'maintenance':'low','beard':'no','preference':'Natural'})
assert result['landmarks']>=468
with TestClient(app) as client:
    assert client.get('/health').status_code==200
    assert client.get('/entrar').status_code==200
print('Docker OK: análise facial real, banco e API; nenhum serviço persistente.')
