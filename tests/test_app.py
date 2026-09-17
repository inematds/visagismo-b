import hashlib
import importlib
import io
import json
import time
from pathlib import Path
import pytest
from PIL import Image
from skimage import data
from fastapi.testclient import TestClient
from app.main import app
from app.auth import password_hash
from app import payments

database=importlib.import_module('app.db')
main=importlib.import_module('app.main')
worker=importlib.import_module('app.worker')
public=importlib.import_module('app.public')

@pytest.fixture
def client(tmp_path,monkeypatch):
    for module in [database,main,worker,public]:monkeypatch.setattr(module,'DATA',tmp_path)
    with TestClient(app) as c:
        with database.db() as con:
            for tid,email in [('a','a@example.com'),('b','b@example.com')]:
                con.execute('INSERT INTO tenants(id,name,professional,price_cents) VALUES (?,?,?,?)',(tid,'Barbearia '+tid,'Profissional '+tid,5000))
                con.execute('INSERT INTO users VALUES (?,?,?,?)',(tid,tid,email,password_hash('test-only-password')))
        yield c

def login(c,email='a@example.com'):
    c.post('/entrar',data={'email':email,'password':'test-only-password'})
    with database.db() as con:return con.execute('SELECT csrf FROM sessions JOIN users ON users.id=sessions.user_id WHERE email=?',(email,)).fetchone()[0]

def photo():
    buf=io.BytesIO();Image.fromarray(data.astronaut()).save(buf,format='JPEG');return buf.getvalue()

def create(c,token,image=None,**overrides):
    values={'csrf_token':token,'client':'Cliente de teste','preference':'Corte prático','maintenance':'low','beard':'no','consent':'yes'}
    values.update(overrides)
    return c.post('/novo',data=values,files={'photo':('front.jpg',image if image is not None else photo(),'image/jpeg')},follow_redirects=False)

def test_complete_consultation_and_share(client):
    token=login(client);res=create(client,token)
    assert res.status_code==303
    url=res.headers['location'];cid=url.split('/')[-1]
    assert worker.run_one()
    page=client.get(url);assert 'Formato estimado' in page.text and '478 pontos' in page.text
    assert client.post(url+'/compartilhar',data={'csrf_token':token}).status_code==409
    res=client.post(url+'/aprovar',data={'csrf_token':token,'notes':'Manter o contorno natural.','next_visit':'2030-01-01','confirm':'yes'})
    assert 'O plano para você' in res.text
    assert client.post(url+'/aprovar',data={'csrf_token':token,'notes':'Outra','next_visit':'2030-01-01','confirm':'yes'}).status_code==409
    from bs4 import BeautifulSoup
    response=client.post(url+'/compartilhar',data={'csrf_token':token})
    share=BeautifulSoup(response.text,'html.parser').select_one('#url')['value']
    shared=client.get(share);assert 'Manter o contorno natural' in shared.text and '/foto/' not in shared.text
    client.post(url+'/revogar',data={'csrf_token':token});assert client.get(share).status_code==404
    client.post(url+'/pagamento',data={'csrf_token':token})
    assert 'Pagamento registrado no caixa' in client.get(url).text
    # Save synthetic test artifacts only, never published.
    artifacts=Path('artifacts');artifacts.mkdir(exist_ok=True)
    for filename,route in [('dashboard.html','/painel'),('report.html',url),('form.html','/novo'),('landing.html','/')]:
        (artifacts/filename).write_text(client.get(route).text)
    res=client.post(url+'/excluir',data={'csrf_token':token,'confirm':'yes'})
    assert res.status_code==200 and not (main.DATA/cid).exists()
    assert client.get(url).status_code==404

def test_auth_csrf_and_tenant_isolation(client):
    assert client.get('/painel',follow_redirects=False).status_code==303
    token=login(client);res=create(client,token);url=res.headers['location']
    assert create(client,'bad').status_code==403
    login(client,'b@example.com')
    assert client.get(url).status_code==404
    assert client.get(url+'/foto/photo').status_code==404
    assert 'Cliente de teste' not in client.get('/painel').text

def test_invalid_upload_and_authorization(client):
    token=login(client)
    assert create(client,token,b'not an image').status_code==400
    assert create(client,token,consent='').status_code==400
    assert create(client,token,maintenance='invalid').status_code==400
    assert create(client,token,b'x'*(12*1024*1024+1)).status_code==413

def test_no_face_reports_actionable_failure(client):
    token=login(client);buf=io.BytesIO();Image.new('RGB',(512,512),'white').save(buf,format='JPEG')
    url=create(client,token,buf.getvalue()).headers['location'];worker.run_one()
    page=client.get(url);assert 'exatamente um rosto' in page.text and 'Criar consulta com outra foto' in page.text

def test_multiple_faces_rejected():
    from app.engine import analyze
    import tempfile
    original=Image.fromarray(data.astronaut());canvas=Image.new('RGB',(1024,512));canvas.paste(original,(0,0));canvas.paste(original,(512,0))
    with tempfile.TemporaryDirectory() as folder:
        p=Path(folder)/'faces.jpg';canvas.save(p)
        with pytest.raises(ValueError,match='exatamente um rosto'):analyze(p,{'maintenance':'low','beard':'no','preference':'Natural'})

def test_retention_independent_of_new_visits(client):
    import os
    orphan=main.DATA/'upload-orphan';orphan.mkdir();os.utime(orphan,(time.time()-7200,time.time()-7200))
    token=login(client);url=create(client,token).headers['location'];worker.run_one();cid=url.split('/')[-1]
    with database.db() as con:con.execute('UPDATE consultations SET created=? WHERE id=?',(time.time()-2*86400,cid))
    worker.cleanup();assert not (main.DATA/cid).exists() and not orphan.exists()
    assert client.get(url).status_code==200
    with database.db() as con:con.execute('UPDATE consultations SET created=? WHERE id=?',(time.time()-100*86400,cid))
    worker.cleanup();assert client.get(url).status_code==404

def test_xss_escaped(client):
    token=login(client);url=create(client,token,client='<script>alert(1)</script>').headers['location']
    assert '<script>alert(1)</script>' not in client.get(url).text

def test_payment_signature_and_reconciliation(client):
    import hmac
    ts=str(int(time.time()*1000));pid='123';rid='request1';secret='test-secret'
    sig=hmac.new(secret.encode(),f'id:{pid};request-id:{rid};ts:{ts};'.encode(),hashlib.sha256).hexdigest()
    assert payments.verify_signature(pid,rid,f'ts={ts},v1={sig}',secret)
    assert not payments.verify_signature('999',rid,f'ts={ts},v1={sig}',secret)
    token=login(client);url=create(client,token).headers['location'];cid=url.split('/')[-1]
    event={'id':123,'external_reference':cid,'transaction_amount':50,'currency_id':'BRL','status':'approved'}
    assert not payments.reconcile(dict(event,transaction_amount=1))
    assert payments.reconcile(event) and payments.reconcile(event)
    with database.db() as con:assert con.execute('SELECT paid FROM consultations WHERE id=?',(cid,)).fetchone()[0]==1
    assert payments.reconcile(dict(event,status='refunded'))
    with database.db() as con:assert con.execute('SELECT paid FROM consultations WHERE id=?',(cid,)).fetchone()[0]==0

def test_image_failure_fallback(client,monkeypatch):
    from app import engine
    monkeypatch.setattr(engine,'IMAGE_ENABLED',True)
    monkeypatch.setattr(engine,'IMAGE_PROVIDER','inemaimg')
    monkeypatch.setattr(engine,'IMAGE_URL','http://127.0.0.1:1')
    folder=main.DATA/'image-test';folder.mkdir();(folder/'photo.jpg').write_bytes(photo())
    result={'prompt_style':'natural short haircut','simulation':False}
    note=engine.simulate(folder,result,'no')
    assert not result['simulation'] and 'indisponível' in note

def test_worker_recovers_interrupted_job(client):
    token=login(client);url=create(client,token).headers['location'];cid=url.split('/')[-1]
    with database.db() as con:con.execute("UPDATE consultations SET status='processing',updated=?,attempts=1 WHERE id=?",(time.time()-700,cid))
    worker.cleanup()
    with database.db() as con:assert con.execute('SELECT status FROM consultations WHERE id=?',(cid,)).fetchone()[0]=='queued'

def test_backup_restores_database(client,tmp_path):
    import sqlite3
    token=login(client);url=create(client,token).headers['location'];cid=url.split('/')[-1]
    snapshot=tmp_path/'snapshot.sqlite3'
    with database.db() as source,sqlite3.connect(snapshot) as target:source.backup(target)
    with sqlite3.connect(snapshot) as restored:
        assert restored.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert restored.execute('SELECT client FROM consultations WHERE id=?',(cid,)).fetchone()[0]=='Cliente de teste'

def test_public_payment_gate_and_delivery(client):
    landing=client.get('/b/a');assert 'Sua consulta começa aqui' in landing.text
    response=client.post('/b/a/iniciar',data={'client':'Cliente público'},follow_redirects=False)
    route=response.headers['location'];public_token=route.split('/')[-1]
    assert 'Primeiro, o pagamento' in client.get(route).text
    fields={'csrf_token':public_token,'client':'Cliente público','preference':'Prático','maintenance':'low','beard':'no','consent':'yes'}
    assert client.post(route+'/foto',data=fields,files={'photo':('photo.jpg',photo(),'image/jpeg')}).status_code==409
    with database.db() as con:cid=con.execute('SELECT id FROM consultations WHERE client=?',('Cliente público',)).fetchone()[0]
    staff=login(client)
    client.post('/atendimento/'+cid+'/pagamento',data={'csrf_token':staff})
    assert 'Primeiro, vamos ouvir' in client.get(route).text
    assert client.post(route+'/foto',data=dict(fields,csrf_token='bad'),files={'photo':('photo.jpg',photo(),'image/jpeg')}).status_code==403
    uploaded=client.post(route+'/foto',data=fields,files={'photo':('photo.jpg',photo(),'image/jpeg')})
    assert uploaded.status_code==200
    assert client.post(route+'/foto',data=fields,files={'photo':('photo.jpg',photo(),'image/jpeg')}).status_code==409
    worker.run_one()
    waiting=client.get(route);assert 'aguarda revisão' in waiting.text and 'Formato estimado' not in waiting.text
    client.post('/atendimento/'+cid+'/aprovar',data={'csrf_token':staff,'notes':'Orientação aprovada.','next_visit':'2030-01-01','confirm':'yes'})
    done=client.get(route);assert 'Orientação aprovada' in done.text and '/foto/' not in done.text
    assert client.get('/c/'+public_token+'invalid').status_code==404

def test_public_failed_photo_can_retry_without_new_payment(client):
    r=client.post('/b/a/iniciar',data={'client':'Reenvio'},follow_redirects=False);route=r.headers['location'];token=route.split('/')[-1]
    with database.db() as con:row=con.execute("SELECT id FROM consultations WHERE client='Reenvio'").fetchone();cid=row[0]
    staff=login(client);client.post('/atendimento/'+cid+'/pagamento',data={'csrf_token':staff})
    buf=io.BytesIO();Image.new('RGB',(512,512),'white').save(buf,format='JPEG')
    fields={'csrf_token':token,'client':'Reenvio','preference':'Prático','maintenance':'low','beard':'no','consent':'yes'}
    client.post(route+'/foto',data=fields,files={'photo':('photo.jpg',buf.getvalue(),'image/jpeg')});worker.run_one()
    client.post('/atendimento/'+cid+'/nova-foto',data={'csrf_token':staff})
    r=client.post(route+'/foto',data=fields,files={'photo':('photo.jpg',photo(),'image/jpeg')});assert r.status_code==200
    worker.run_one()
    with database.db() as con:
        row=con.execute('SELECT status,paid FROM consultations WHERE id=?',(cid,)).fetchone()
        assert row['status']=='pending_review' and row['paid']==1
