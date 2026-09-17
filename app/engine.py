"""Medições legadas preservadas; recomendações e relatório em português."""
import base64
import io
import json
import math
import os
import sys
from pathlib import Path
import httpx
from PIL import Image, ImageOps
from .config import ROOT, IMAGE_URL, IMAGE_PROVIDER, IMAGE_ENABLED
sys.path.insert(0, str(ROOT / '03-motor'))
from analiza_rostro import detectar, medir, clasificar, _json_safe
from simulacion import verificar
from motor_recomendacion import analizar as recommend

SHAPES = {'cuadrado':'quadrado','rectangular':'retangular','ovalado':'oval',
          'triangular de base ancha':'triangular','de corazón':'coração','ovalado-cuadrado':'oval com mandíbula marcada'}

def normalize(raw, destination):
    import pillow_heif
    pillow_heif.register_heif_opener()
    Image.MAX_IMAGE_PIXELS = 24_000_000
    try:
        im = Image.open(io.BytesIO(raw))
        if im.width * im.height > 24_000_000: raise ValueError('Foto acima de 24 megapixels. Reduza a resolução.')
        im = ImageOps.exif_transpose(im).convert('RGB')
        if min(im.size) < 240: raise ValueError('Use uma foto com pelo menos 240 pixels em cada lado.')
        im.thumbnail((1600,1600))
        im.save(destination, 'JPEG', quality=92)
    except (OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError('Não foi possível abrir a foto. Envie JPEG, PNG, WEBP ou HEIC válido.') from exc

def analyze(path, answers):
    try: _, points, landmarks, _ = detectar(path)
    except SystemExit as exc: raise ValueError('Use uma foto frontal com exatamente um rosto, sem filtros e bem iluminado.') from exc
    eye = points['canto_ext_izq'] - points['canto_ext_der']
    angle = abs(math.degrees(math.atan2(float(eye[1]),float(eye[0]))))
    if min(angle,abs(180-angle)) > 12:
        raise ValueError('Mantenha a cabeça reta, com os olhos na mesma altura, e tente novamente.')
    m = medir(points)
    if not all(math.isfinite(float(v)) and float(v)>0 for v in m['ratios'].values()):
        raise ValueError('A foto não permite medir as proporções. Tente outra captura frontal.')
    c = clasificar(m)
    recipe = recommend(m,c,{'minutos':2 if answers['maintenance']=='low' else 5,
                              'barba':'si' if answers['beard']=='yes' else 'no',
                              'estilos':[], 'transmitir':[]})['receta']
    ratio = m['ratios']['indice_facial']
    if ratio >= 1.55:
        cut, reason = 'Textura com volume moderado', 'A proporção altura/largura sugere um rosto alongado. Volume lateral moderado é uma opção para explorar.'
        english = 'a textured medium crop, moderate top height, natural sides with a low taper'
    elif ratio <= 1.30:
        cut, reason = 'Topo texturizado com laterais graduais', 'A proporção altura/largura sugere um rosto mais curto. Um pouco de altura no topo pode compor o estilo desejado.'
        english = 'a textured crop with slightly elevated top, gradual low taper sides'
    else:
        cut, reason = 'Corte versátil de acabamento natural', 'A proporção altura/largura permite explorar diferentes volumes; a preferência e a rotina orientam a escolha.'
        english = 'a versatile natural textured haircut with a subtle low taper'
    titles = {
        'volumen en la zona alta con laterales pegados a la altura del pómulo':'Volume no topo com laterais contidas',
        'media longitud con caída frontal marcada, sin volumen en la raíz':'Comprimento médio com queda frontal',
        'media longitud texturizada con caída frontal':'Comprimento médio com textura e queda frontal',
        'volumen alto con raíz levantada':'Volume no topo com raiz elevada',
        'longitud corta-media, pulida':'Comprimento curto a médio com acabamento alinhado',
        'media longitud, versión corta y de caída natural':'Corte prático com queda natural',
    }
    cut = titles.get(recipe['forma'],cut)
    directives=set(recipe['directivas'])
    side='Degradê baixo e transição suave, mantendo o volume natural.'
    if 'ESTRECHAR_LATERALES' in directives and 'NO_ESTRECHAR_LATERALES' not in directives:
        side='Degradê médio e gradual, sem raspar até a pele.'
    fringe='Frontal com queda natural, a ajustar com o cliente.'
    if 'NO_FLEQUILLO' in directives: fringe='Frontal sem franja, com direção para cima ou para trás.'
    elif 'FLEQUILLO' in directives: fringe='Queda frontal desfiada, sem borda reta marcada.'
    english += f". Top length approximately {recipe['largo_cm'][0]} to {recipe['largo_cm'][1]} cm"
    if 'NO_ALTURA_ARRIBA' in directives: english += '. No additional height at the roots'
    if 'NO_ESTRECHAR_LATERALES' in directives: english += '. Keep side density, no high skin fade'
    if 'NO_FLEQUILLO' in directives: english += '. No bangs; forehead visible'
    elif 'FLEQUILLO' in directives: english += '. Soft feathered fringe falling forward'
    if answers['maintenance']=='low':
        care='Priorize acabamento natural e finalização simples; confirme com o barbeiro como o cabelo se comporta sem produto.'
    else:
        care='Combine com o barbeiro uma finalização com produto leve e o tempo necessário para reproduzi-la em casa.'
    beard='Contorno natural e comprimento uniforme, respeitando a densidade existente.' if answers['beard']=='yes' else 'Rosto sem barba, conforme sua preferência.'
    return json.loads(json.dumps({'shape':SHAPES.get(c['morfotipo']['forma'],'misto'), 'cut':cut,
       'reason':reason,'care':care,'beard':beard,'preference':answers['preference'],
       'length_cm':recipe['largo_cm'],'sides':side,'fringe':fringe,'measurements':m['ratios'],'landmarks':len(landmarks), 'prompt_style':english,
       'version':'1.1.0','simulation':False},default=_json_safe))

def simulate(folder, result, beard):
    if not IMAGE_ENABLED: return 'Simulação não configurada. A orientação continua disponível.'
    prompt=('Edit only hair and beard. Preserve the same face, nose, eyes, jaw, skin, age, expression, '
            'lighting and background. Do not beautify or reshape the face. Hair: '+result['prompt_style']+'. '+
            ('Keep a short natural beard.' if beard=='yes' else 'Keep clean shaven.'))
    try:
        with httpx.Client(timeout=180) as client:
            encoded=base64.b64encode((folder/'photo.jpg').read_bytes()).decode()
            if IMAGE_PROVIDER=='fal':
                response=client.post('https://fal.run/fal-ai/flux-2/klein/4b/edit',
                    headers={'Authorization':'Key '+os.environ['FAL_KEY']},
                    json={'prompt':prompt,'image_urls':['data:image/jpeg;base64,'+encoded],
                          'image_size':{'width':768,'height':768},'num_images':1,'sync_mode':True})
                response.raise_for_status()
                item=response.json()['images'][0]['url']
            else:
                response=client.post(IMAGE_URL.rstrip('/')+'/generate',json={
                    'model':'flux2-klein','prompt':prompt,'images':[encoded],
                    'width':768,'height':768,'steps':4,'seed':42})
                response.raise_for_status()
                item=response.json()['image']
        if not isinstance(item,str) or item.startswith('http'):
            return 'O gerador não devolveu uma imagem incorporada válida.'
        raw=base64.b64decode(item.split(',')[-1],validate=True)
        normalize(raw,folder/'simulation.jpg')
        ok, check=verificar(folder/'photo.jpg',folder/'simulation.jpg')
        result['verification']=check
        if not ok:
            (folder/'simulation.jpg').unlink(missing_ok=True)
            return 'Imagem rejeitada pelo filtro de proporções. Nenhuma simulação foi publicada.'
        result['simulation']=True
        return 'Simulação por IA: passou pelo filtro geométrico; confirme visualmente com o cliente.'
    except Exception:
        (folder/'simulation.jpg').unlink(missing_ok=True)
        return 'Simulação indisponível neste atendimento. Relatório gerado normalmente.'
