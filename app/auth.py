import hashlib
import hmac
import secrets
import time
from fastapi import HTTPException, Request
from .db import db

def password_hash(password):
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
    return salt + ':' + digest

def password_ok(password, stored):
    salt, digest = stored.split(':')
    test = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
    return hmac.compare_digest(test, digest)

def current(request: Request):
    token = hashlib.sha256(request.cookies.get('vb_session', '').encode()).hexdigest()
    with db() as con:
        row = con.execute('''SELECT users.*,sessions.csrf FROM sessions JOIN users ON users.id=sessions.user_id
                             WHERE token=? AND expires>?''', (token,time.time())).fetchone()
    if not row: raise HTTPException(401, 'Entre na sua conta para continuar.')
    return dict(row)

def csrf(request, value):
    user = current(request)
    if not hmac.compare_digest(user['csrf'], value):
        raise HTTPException(403, 'Sessão do formulário expirada. Atualize a página.')
    return user

def consultation(cid, user):
    with db() as con:
        row = con.execute('SELECT * FROM consultations WHERE id=? AND tenant_id=?', (cid,user['tenant_id'])).fetchone()
    if not row: raise HTTPException(404,'Atendimento não encontrado.')
    return dict(row)
