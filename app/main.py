import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from . import __version__
from .config import ROOT, DATA, MAX_UPLOAD, IMAGE_URL, IMAGE_ENABLED, PHOTO_HOURS, REPORT_DAYS
from .db import db, init
from .auth import current, csrf, consultation, password_ok
from .engine import normalize

@asynccontextmanager
async def lifespan(app):
    init()
    yield

app=FastAPI(title='Visagismo B',version=__version__,lifespan=lifespan)
app.mount('/static',StaticFiles(directory=ROOT/'app/static'),name='static')
templates=Jinja2Templates(directory=ROOT/'app/templates')
STATUSES={'queued':'Na fila','processing':'Analisando foto','pending_review':'Aguardando revisão',
          'delivered':'Entregue','failed':'Precisa de nova foto'}
templates.env.filters['datebr']=lambda x: datetime.fromtimestamp(x).strftime('%d/%m/%Y às %H:%M') if x else '—'
templates.env.globals.update(statuses=STATUSES,version=__version__)

def render(request,name,**context):
    return templates.TemplateResponse(request=request,name=name,context=context)

def tenant(user):
    with db() as con: return dict(con.execute('SELECT * FROM tenants WHERE id=?',(user['tenant_id'],)).fetchone())

@app.middleware('http')
async def headers(request, call_next):
    # Early bounded body guard. File reads are bounded independently as well.
    length=request.headers.get('content-length','0')
    if length.isdigit() and int(length)>MAX_UPLOAD+1024*1024:
        return HTMLResponse('Arquivo muito grande. Limite: 12 MB.',status_code=413)
    response=await call_next(request)
    response.headers.update({'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY',
       'Referrer-Policy':'no-referrer','Cache-Control':'no-store',
       'Content-Security-Policy':"default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; script-src 'self'; form-action 'self'; frame-ancestors 'none'"})
    return response

@app.exception_handler(HTTPException)
async def error(request,exc):
    if exc.status_code==401 and not request.url.path.startswith('/webhooks/'): return RedirectResponse('/entrar',status_code=303)
    return HTMLResponse(templates.get_template('error.html').render(message=exc.detail,code=exc.status_code,request=request),status_code=exc.status_code)

@app.get('/health')
def health(): return {'status':'ok','version':__version__}

@app.get('/',response_class=HTMLResponse)
def home(request:Request): return render(request,'landing.html')

@app.get('/privacidade',response_class=HTMLResponse)
def privacy(request:Request): return render(request,'privacy.html',photo_hours=PHOTO_HOURS,report_days=REPORT_DAYS)

@app.get('/entrar',response_class=HTMLResponse)
def login_page(request:Request): return render(request,'login.html',error=None)

@app.post('/entrar')
def login(request:Request,email:str=Form(...),password:str=Form(...)):
    origin=request.headers.get('origin')
    if origin and origin.rstrip('/') != str(request.base_url).rstrip('/'):
        raise HTTPException(403,'Origem não permitida.')
    email=email.lower().strip()
    key=hashlib.sha256(((request.client.host if request.client else '')+email).encode()).hexdigest()
    with db() as con:
        row=con.execute('SELECT * FROM login_attempts WHERE key=?',(key,)).fetchone()
        if row and row['expires']>time.time() and row['count']>=10: raise HTTPException(429,'Aguarde 15 minutos antes de tentar novamente.')
        con.execute('INSERT INTO login_attempts VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET count=CASE WHEN expires<? THEN 1 ELSE count+1 END,expires=excluded.expires',(key,1,time.time()+900,time.time()))
        user=con.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
    if not user or len(password)>256 or not password_ok(password,user['password']):
        return render(request,'login.html',error='E-mail ou senha incorretos.')
    token=secrets.token_urlsafe(32)
    with db() as con:
        con.execute('DELETE FROM login_attempts WHERE key=?',(key,))
        con.execute('INSERT INTO sessions VALUES (?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user['id'],secrets.token_urlsafe(32),time.time()+43200))
    response=RedirectResponse('/painel',status_code=303)
    response.set_cookie('vb_session',token,httponly=True,secure=request.url.scheme=='https',samesite='lax',max_age=43200)
    return response

@app.post('/sair')
def logout(request:Request,csrf_token:str=Form(...)):
    csrf(request,csrf_token)
    with db() as con: con.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(request.cookies['vb_session'].encode()).hexdigest(),))
    response=RedirectResponse('/entrar',status_code=303);response.delete_cookie('vb_session');return response

@app.get('/painel',response_class=HTMLResponse)
def dashboard(request:Request):
    user=current(request)
    with db() as con: rows=[dict(x) for x in con.execute('SELECT * FROM consultations WHERE tenant_id=? ORDER BY created DESC LIMIT 200',(user['tenant_id'],))]
    return render(request,'dashboard.html',user=user,brand=tenant(user),rows=rows)

@app.get('/novo',response_class=HTMLResponse)
def new(request:Request):
    user=current(request)
    return render(request,'new.html',user=user,brand=tenant(user),image_enabled=bool(IMAGE_ENABLED))

@app.post('/novo')
async def create(request:Request,csrf_token:str=Form(...),client:str=Form(...),preference:str=Form(...),
                 maintenance:str=Form(...),beard:str=Form(...),consent:str=Form(''),simulation:str=Form(''),
                 photo:UploadFile=File(...)):
    user=csrf(request,csrf_token)
    if consent!='yes': raise HTTPException(400,'Confirme a autorização e que o cliente tem 18 anos ou mais.')
    if not 2<=len(client.strip())<=100 or len(preference)>1000 or not preference.strip(): raise HTTPException(400,'Preencha nome e preferência nos limites indicados.')
    if maintenance not in ('low','medium') or beard not in ('yes','no'): raise HTTPException(400,'Selecione opções válidas.')
    with db() as con:
        count=con.execute('SELECT count(*) FROM consultations WHERE tenant_id=? AND created>?',(user['tenant_id'],time.time()-86400)).fetchone()[0]
    if count>=int(os.getenv('VISAGISMO_DAILY_LIMIT','50')): raise HTTPException(429,'Limite diário atingido.')
    raw=await photo.read(MAX_UPLOAD+1)
    if len(raw)>MAX_UPLOAD: raise HTTPException(413,'A foto deve ter no máximo 12 MB.')
    cid=secrets.token_hex(16);folder=DATA/cid;folder.mkdir(mode=0o700)
    try: normalize(raw,folder/'photo.jpg')
    except ValueError as exc:
        shutil.rmtree(folder);raise HTTPException(400,str(exc))
    answers={'preference':preference.strip(),'maintenance':maintenance,'beard':beard,
             'simulation':simulation=='yes' and bool(IMAGE_ENABLED),'authorized_at':time.time(),'adult':True}
    brand=tenant(user)
    with db() as con:
        con.execute('INSERT INTO consultations (id,tenant_id,client,answers,status,created,updated,price_cents) VALUES (?,?,?,?,?,?,?,?)',
                    (cid,user['tenant_id'],client.strip(),json.dumps(answers,ensure_ascii=False),'queued',time.time(),time.time(),brand['price_cents']))
    return RedirectResponse('/atendimento/'+cid,status_code=303)

@app.get('/atendimento/{cid}',response_class=HTMLResponse)
def detail(request:Request,cid:str):
    user=current(request);row=consultation(cid,user)
    return render(request,'detail.html',user=user,brand=tenant(user),row=row,
                  result=json.loads(row['result']) if row['result'] else None,answers=json.loads(row['answers']),shared=False,share_link=None,
                  photo_exists=(DATA/cid/'photo.jpg').exists())

@app.get('/atendimento/{cid}/status')
def status(request:Request,cid:str):
    row=consultation(cid,current(request));return {'status':row['status']}

@app.get('/atendimento/{cid}/foto/{kind}')
def photo_view(request:Request,cid:str,kind:str):
    consultation(cid,current(request))
    if kind not in ('photo','simulation'): raise HTTPException(404,'Imagem não encontrada.')
    p=DATA/cid/(kind+'.jpg')
    if not p.exists(): raise HTTPException(404,'Imagem removida conforme a retenção.')
    return FileResponse(p,media_type='image/jpeg')

@app.post('/atendimento/{cid}/aprovar')
def approve(request:Request,cid:str,csrf_token:str=Form(...),notes:str=Form(...),next_visit:str=Form(...),confirm:str=Form('')):
    user=csrf(request,csrf_token);row=consultation(cid,user)
    if row['status']!='pending_review': raise HTTPException(409,'Este relatório não está aguardando revisão.')
    if confirm!='yes' or not notes.strip() or len(notes)>4000: raise HTTPException(400,'Registre a orientação e confirme a revisão.')
    try:
        date=datetime.strptime(next_visit,'%Y-%m-%d').date()
        if date<datetime.now().date(): raise ValueError()
    except ValueError: raise HTTPException(400,'Escolha uma data de retorno a partir de hoje.')
    with db() as con:
        con.execute("UPDATE consultations SET status='delivered',notes=?,next_visit=?,reviewer=?,reviewed_at=?,updated=? WHERE id=? AND status='pending_review'",
                    (notes.strip(),next_visit,tenant(user)['professional'],time.time(),time.time(),cid))
    return RedirectResponse('/atendimento/'+cid,status_code=303)

@app.post('/atendimento/{cid}/pagamento')
def pay(request:Request,cid:str,csrf_token:str=Form(...)):
    user=csrf(request,csrf_token);consultation(cid,user)
    with db() as con: con.execute("UPDATE consultations SET paid=1,payment_method='caixa' WHERE id=?",(cid,))
    return RedirectResponse('/atendimento/'+cid,status_code=303)

@app.post('/atendimento/{cid}/excluir')
def delete(request:Request,cid:str,csrf_token:str=Form(...),confirm:str=Form('')):
    user=csrf(request,csrf_token);row=consultation(cid,user)
    if confirm!='yes': raise HTTPException(400,'Confirme a exclusão permanente.')
    if row['status'] in ('queued','processing'): raise HTTPException(409,'Aguarde o processamento terminar antes de excluir.')
    with db() as con: con.execute('DELETE FROM consultations WHERE id=?',(cid,))
    shutil.rmtree(DATA/cid,ignore_errors=True)
    return RedirectResponse('/painel',status_code=303)

@app.post('/atendimento/{cid}/compartilhar',response_class=HTMLResponse)
def share(request:Request,cid:str,csrf_token:str=Form(...)):
    user=csrf(request,csrf_token);row=consultation(cid,user)
    if row['status']!='delivered': raise HTTPException(409,'Aprove o relatório antes de compartilhar.')
    token=secrets.token_urlsafe(32)
    with db() as con: con.execute('UPDATE consultations SET share_hash=?,share_expires=? WHERE id=?',(hashlib.sha256(token.encode()).hexdigest(),time.time()+7*86400,cid))
    return render(request,'share.html',user=user,brand=tenant(user),cid=cid,url=str(request.base_url)+'r/'+token)

@app.post('/atendimento/{cid}/revogar')
def revoke(request:Request,cid:str,csrf_token:str=Form(...)):
    user=csrf(request,csrf_token);consultation(cid,user)
    with db() as con: con.execute('UPDATE consultations SET share_hash=NULL,share_expires=NULL WHERE id=?',(cid,))
    return RedirectResponse('/atendimento/'+cid,status_code=303)

@app.get('/r/{token}',response_class=HTMLResponse)
def public_report(request:Request,token:str):
    with db() as con:
        row=con.execute("SELECT * FROM consultations WHERE share_hash=? AND share_expires>? AND status='delivered'",(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
        if not row: raise HTTPException(404,'Link expirado ou revogado.')
        brand=dict(con.execute('SELECT * FROM tenants WHERE id=?',(row['tenant_id'],)).fetchone())
    return render(request,'detail.html',row=dict(row),result=json.loads(row['result']),brand=brand,shared=True,user=None,photo_exists=False)

@app.get('/configuracoes',response_class=HTMLResponse)
def settings(request:Request):
    user=current(request);return render(request,'settings.html',user=user,brand=tenant(user))

@app.post('/configuracoes')
def save_settings(request:Request,csrf_token:str=Form(...),name:str=Form(...),professional:str=Form(...),city:str=Form(''),contact:str=Form(''),price_cents:int=Form(0)):
    user=csrf(request,csrf_token)
    if not name.strip() or not professional.strip() or max(map(len,[name,professional,city,contact]))>150 or not 0<=price_cents<=1000000:
        raise HTTPException(400,'Revise os dados: textos até 150 caracteres e preço válido.')
    with db() as con: con.execute('UPDATE tenants SET name=?,professional=?,city=?,contact=?,price_cents=? WHERE id=?',(name.strip(),professional.strip(),city.strip(),contact.strip(),price_cents,user['tenant_id']))
    return RedirectResponse('/configuracoes',status_code=303)

from . import payments
import httpx
templates.env.globals['payment_enabled']=payments.enabled()

@app.post('/atendimento/{cid}/checkout',response_class=HTMLResponse)
def checkout(request:Request,cid:str,csrf_token:str=Form(...)):
    user=csrf(request,csrf_token);row=consultation(cid,user)
    try: url=payments.preference(row)
    except httpx.HTTPError: raise HTTPException(502,'Não foi possível criar a cobrança. Tente novamente.')
    return render(request,'checkout.html',user=user,brand=tenant(user),url=url,cid=cid)

@app.get('/pagamento/retorno',response_class=HTMLResponse)
def payment_return(request:Request):
    return render(request,'payment_return.html')

@app.post('/webhooks/mercadopago')
def webhook(request:Request):
    if not payments.enabled(): raise HTTPException(503,'Integração indisponível.')
    pid=request.query_params.get('data.id','')
    if not pid.isdigit() or not payments.verify_signature(pid,request.headers.get('x-request-id',''),request.headers.get('x-signature',''),os.environ['MERCADOPAGO_WEBHOOK_SECRET']):
        raise HTTPException(401,'Notificação inválida.')
    try:
        with httpx.Client(timeout=20) as client:
            response=client.get('https://api.mercadopago.com/v1/payments/'+pid,headers={'Authorization':'Bearer '+os.environ['MERCADOPAGO_ACCESS_TOKEN']})
            response.raise_for_status();payment=response.json()
        if str(payment.get('id'))!=pid: raise HTTPException(400,'Pagamento divergente.')
        payments.reconcile(payment)
    except httpx.HTTPError: raise HTTPException(502,'Consulta de pagamento indisponível. Reenvie a notificação.')
    return {'received':True}
