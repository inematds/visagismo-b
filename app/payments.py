"""Checkout Pro: confirmação via recurso consultado no servidor, nunca pelo redirect."""
import hashlib
import hmac
import os
import time
from decimal import Decimal
import httpx
from fastapi import HTTPException
from .db import db

def enabled():
    return bool(os.getenv('MERCADOPAGO_ACCESS_TOKEN') and os.getenv('MERCADOPAGO_WEBHOOK_SECRET') and os.getenv('PUBLIC_URL','').startswith('https://'))

def preference(row):
    if not enabled(): raise HTTPException(503,'Pagamento online não configurado nesta instalação.')
    if row['paid'] or row['price_cents']<=0: raise HTTPException(409,'Atendimento já pago ou sem preço configurado.')
    base=os.environ['PUBLIC_URL'].rstrip('/')
    with httpx.Client(timeout=25) as client:
        response=client.post('https://api.mercadopago.com/checkout/preferences',headers={
          'Authorization':'Bearer '+os.environ['MERCADOPAGO_ACCESS_TOKEN'],'X-Idempotency-Key':row['id']},json={
          'items':[{'id':row['id'],'title':'Consulta de estilo','quantity':1,'currency_id':'BRL','unit_price':row['price_cents']/100}],
          'external_reference':row['id'],'notification_url':base+'/webhooks/mercadopago',
          'back_urls':{s:base+'/pagamento/retorno' for s in ['success','pending','failure']}})
        response.raise_for_status()
        data=response.json()
    key='sandbox_init_point' if os.getenv('MERCADOPAGO_SANDBOX','true').lower()=='true' else 'init_point'
    url=data.get(key,'')
    from urllib.parse import urlparse
    parsed=urlparse(url)
    if parsed.scheme!='https' or not (parsed.hostname or '').endswith('.mercadopago.com.br'):
        raise HTTPException(502,'O provedor retornou um endereço de pagamento inválido.')
    return url

def verify_signature(pid,request_id,signature,secret):
    parts=dict(p.split('=',1) for p in signature.split(',') if '=' in p)
    ts=parts.get('ts','');sig=parts.get('v1','')
    try:
        stamp=float(ts);stamp=stamp/1000 if stamp>1e12 else stamp
        if abs(time.time()-stamp)>300:return False
    except ValueError:return False
    manifest=f'id:{pid.lower()};request-id:{request_id};ts:{ts};'
    expected=hmac.new(secret.encode(),manifest.encode(),hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected,sig)

def reconcile(payment):
    cid=payment.get('external_reference')
    with db() as con:
        row=con.execute('SELECT * FROM consultations WHERE id=?',(cid,)).fetchone()
        if not row:return False
        try: amount=Decimal(str(payment.get('transaction_amount')))*100
        except Exception:return False
        if payment.get('currency_id')!='BRL' or amount!=row['price_cents']:return False
        payment_id=str(payment['id'])
        if row['payment_id'] and row['payment_id']!=payment_id:return False
        state=payment.get('status')
        if state not in ['approved','refunded','charged_back']:return False
        con.execute("UPDATE consultations SET paid=?,payment_method='mercadopago',payment_id=?,status=CASE WHEN status='awaiting_payment' AND ?='approved' THEN 'awaiting_upload' ELSE status END WHERE id=?",
                    (int(state=='approved'),payment_id,state,cid))
    return True
