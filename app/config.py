import os
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parent.parent
# Ambiente explícito vence; credenciais globais são lidas, nunca copiadas.
for path in [ROOT / '.env', Path.home() / 'projetos/openpcbotv2/.env', Path.home() / 'projetos/wifi/.env']:
    load_dotenv(path, override=False)
DATA = Path(os.getenv('VISAGISMO_DATA', str(ROOT / 'data'))).resolve()
DATA.mkdir(parents=True, exist_ok=True)
IMAGE_URL = os.getenv('VISAGISMO_IMAGE_URL', '')
MAX_UPLOAD = 12 * 1024 * 1024
PHOTO_HOURS = int(os.getenv('VISAGISMO_PHOTO_HOURS', '24'))
REPORT_DAYS = int(os.getenv('VISAGISMO_REPORT_DAYS', '90'))

IMAGE_PROVIDER = os.getenv('VISAGISMO_IMAGE_PROVIDER', 'none')
IMAGE_ENABLED = IMAGE_PROVIDER == 'fal' and bool(os.getenv('FAL_KEY')) or IMAGE_PROVIDER == 'inemaimg' and bool(IMAGE_URL)
