"""Entrada do cliente: capability token, pagamento confirmado antes da captura."""
import hashlib
import hmac
import json
import os
import secrets
import shutil
import time
from fastapi import APIRouter, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import RedirectResponse
import httpx
from .config import DATA, MAX_UPLOAD, IMAGE_ENABLED
from .db import db
from .engine import normalize
from . import payments

router=APIRouter()

def access(token):
    with db() as con:
        row=con.execute('SELECT * FROM consultations WHERE access_hash=? AND access_expires>?',
                        (hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
        if not row:raise HTTPException(404,'Link de atendimento expirado ou não encontrado. Contate a barbearia.')
        brand=con.execute('SELECT * FROM tenants WHERE id=?',(row['tenant_id'],)).fetchone()
    return dict(row),dict(brand)

def check(token,csrf_token):
    if not hmac.compare_digest(token,csrf_token):raise HTTPException(403,'Formulário inválido. Atualize a página.')
    return access(token)

@router.get('/b/{tid}')
def storefront(request:Request,tid:str):
    from .main import render
    with db() as con:brand=con.execute('SELECT * FROM tenants WHERE id=?',(tid,)).fetchone()
    if not brand:raise HTTPException(404,'Barbearia não encontrada.')
    return render(request,'storefront.html',brand=dict(brand))

@router.post('/b/{tid}/iniciar')
def begin(request:Request,tid:str,client:str=Form(...)):
    origin=request.headers.get('origin')
    if origin and origin.rstrip('/')!=str(request.base_url).rstrip('/'):raise HTTPException(403,'Origem não permitida.')
    if not 2<=len(client.strip())<=100:raise HTTPException(400,'Informe seu nome, entre 2 e 100 caracteres.')
    now=time.time();cid=secrets.token_hex(16);token=secrets.token_urlsafe(32)
    with db() as con:
        con.execute('BEGIN IMMEDIATE')
        brand=con.execute('SELECT * FROM tenants WHERE id=?',(tid,)).fetchone()
        if not brand:raise HTTPException(404,'Barbearia não encontrada.')
        key='public:'+hashlib.sha256((request.client.host if request.client else '').encode()).hexdigest()
        rate=con.execute('SELECT * FROM login_attempts WHERE key=?',(key,)).fetchone()
        if rate and rate['expires']>now and rate['count']>=10:raise HTTPException(429,'Aguarde 15 minutos para iniciar outra consulta.')
        count=con.execute('SELECT count(*) FROM consultations WHERE tenant_id=? AND created>?',(tid,now-86400)).fetchone()[0]
        if count>=int(os.getenv('VISAGISMO_DAILY_LIMIT','50')):raise HTTPException(429,'Agenda digital indisponível por hoje. Contate a barbearia.')
        con.execute('INSERT INTO login_attempts VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET count=CASE WHEN expires<? THEN 1 ELSE count+1 END,expires=excluded.expires',(key,1,now+900,now))
        state='awaiting_payment' if brand['price_cents']>0 else 'awaiting_upload'
        con.execute('''INSERT INTO consultations(id,tenant_id,client,answers,status,created,updated,price_cents,access_hash,access_expires)
                       VALUES (?,?,?,?,?,?,?,?,?,?)''',(cid,tid,client.strip(),'{}',state,now,now,brand['price_cents'],hashlib.sha256(token.encode()).hexdigest(),now+7*86400))
    return RedirectResponse('/c/'+token,status_code=303)

@router.get('/c/{token}')
def customer(request:Request,token:str):
    from .main import render
    row,brand=access(token)
    if row['status']=='awaiting_upload':
        return render(request,'new.html',user=None,brand=brand,public_token=token,submit_url='/c/'+token+'/foto',image_enabled=bool(IMAGE_ENABLED))
    if row['status']=='delivered':
        return render(request,'detail.html',row=row,result=json.loads(row['result']),brand=brand,shared=True,user=None,photo_exists=False)
    return render(request,'customer.html',row=row,brand=brand,public_token=token)

@router.post('/c/{token}/checkout')
def pay(request:Request,token:str,csrf_token:str=Form(...)):
    from .main import render
    row,brand=check(token,csrf_token)
    if row['status']!='awaiting_payment':raise HTTPException(409,'Este atendimento não aguarda pagamento.')
    try:url=payments.preference(row)
    except httpx.HTTPError:raise HTTPException(502,'Pagamento indisponível. Tente novamente em alguns minutos.')
    return render(request,'customer_checkout.html',brand=brand,url=url,public_token=token)

@router.post('/c/{token}/foto')
async def upload(request:Request,token:str,csrf_token:str=Form(...),client:str=Form(...),preference:str=Form(...),
                 maintenance:str=Form(...),beard:str=Form(...),consent:str=Form(''),simulation:str=Form(''),photo:UploadFile=File(...)):
    row,brand=check(token,csrf_token)
    if row['status']!='awaiting_upload' or (row['price_cents']>0 and not row['paid']):raise HTTPException(409,'Aguarde a confirmação do pagamento antes de enviar a foto.')
    if consent!='yes' or not 2<=len(client.strip())<=100 or not preference.strip() or len(preference)>1000:
        raise HTTPException(400,'Preencha nome, preferência e autorização corretamente.')
    if maintenance not in ('low','medium') or beard not in ('yes','no'):raise HTTPException(400,'Selecione opções válidas.')
    raw=await photo.read(MAX_UPLOAD+1)
    if len(raw)>MAX_UPLOAD:raise HTTPException(413,'Limite de 12 MB por foto.')
    # Normalize outside the transaction; the guarded update prevents duplicate submissions.
    temporary=DATA/('upload-'+secrets.token_hex(16));temporary.mkdir(mode=0o700)
    try:
        normalize(raw,temporary/'photo.jpg')
        answers={'preference':preference.strip(),'maintenance':maintenance,'beard':beard,'authorized_at':time.time(),
                 'adult':True,'simulation':simulation=='yes' and bool(IMAGE_ENABLED)}
        with db() as con:
            changed=con.execute("UPDATE consultations SET client=?,answers=?,status='queued',updated=? WHERE id=? AND status='awaiting_upload' AND (price_cents=0 OR paid=1)",
                (client.strip(),json.dumps(answers,ensure_ascii=False),time.time(),row['id'])).rowcount
            if not changed:raise HTTPException(409,'Foto já enviada ou pagamento alterado. Atualize o atendimento.')
            temporary.rename(DATA/row['id'])
    except ValueError as exc:raise HTTPException(400,str(exc))
    finally:shutil.rmtree(temporary,ignore_errors=True)
    return RedirectResponse('/c/'+token,status_code=303)

@router.get('/c/{token}/status')
def status(token:str):
    row,_=access(token);return {'status':row['status']}
