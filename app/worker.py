"""Fila persistente SQLite. Execute um worker por volume de dados."""
import json
import shutil
import time
from .config import DATA, PHOTO_HOURS, REPORT_DAYS
from .db import db, init
from .engine import analyze, simulate

def cleanup():
    now=time.time()
    for folder in DATA.glob("upload-*"):
        if folder.is_dir() and folder.stat().st_mtime < now-3600:
            shutil.rmtree(folder,ignore_errors=True)
    with db() as con:
        con.execute('DELETE FROM sessions WHERE expires<?',(now,))
        con.execute('DELETE FROM login_attempts WHERE expires<?',(now,))
        expired=con.execute('SELECT id FROM consultations WHERE created<? AND status NOT IN (?,?)',
                            (now-REPORT_DAYS*86400,'processing','queued')).fetchall()
        for row in expired:
            shutil.rmtree(DATA/row['id'],ignore_errors=True)
            con.execute('DELETE FROM consultations WHERE id=?',(row['id'],))
        photos=con.execute('SELECT id,result FROM consultations WHERE created<? AND status NOT IN (?,?)',
                           (now-PHOTO_HOURS*3600,'processing','queued')).fetchall()
        for row in photos:
            shutil.rmtree(DATA/row['id'],ignore_errors=True)
            if row['result']:
                result=json.loads(row['result']); result['simulation']=False
                con.execute('UPDATE consultations SET result=? WHERE id=?',(json.dumps(result,ensure_ascii=False),row['id']))
        # Interrupted jobs are retried once, then surfaced to the professional.
        con.execute("UPDATE consultations SET status=CASE WHEN attempts<2 THEN 'queued' ELSE 'failed' END,error='Processamento interrompido. Reenvie a foto se necessário.' WHERE status='processing' AND updated<?",(now-600,))

def run_one():
    with db() as con:
        con.execute('BEGIN IMMEDIATE')
        row=con.execute("SELECT * FROM consultations WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
        if not row: return False
        row=dict(row)
        con.execute("UPDATE consultations SET status='processing',updated=?,attempts=attempts+1 WHERE id=?",(time.time(),row['id']))
    folder=DATA/row['id']
    try:
        answers=json.loads(row['answers'])
        result=analyze(folder/'photo.jpg',answers)
        note=simulate(folder,result,answers['beard']) if answers.get('simulation') else 'Simulação não solicitada.'
        with db() as con:
            con.execute("UPDATE consultations SET status='pending_review',result=?,simulation_note=?,error=NULL,updated=? WHERE id=? AND status='processing'",
                        (json.dumps(result,ensure_ascii=False),note,time.time(),row['id']))
    except Exception as exc:
        message=str(exc) if isinstance(exc,ValueError) else 'Não foi possível processar a foto. Tente uma nova captura.'
        with db() as con:
            con.execute("UPDATE consultations SET status='failed',error=?,updated=? WHERE id=?",(message,time.time(),row['id']))
    return True

def main():
    init(); last=0
    while True:
        if time.time()-last>60: cleanup();last=time.time()
        if not run_one(): time.sleep(2)

if __name__=='__main__': main()
