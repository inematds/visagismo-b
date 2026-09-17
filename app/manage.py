import argparse
import getpass
import json
import secrets
import sqlite3
from pathlib import Path
from .config import DATA
from .db import db, init
from .auth import password_hash

def main():
    parser=argparse.ArgumentParser(description='Administração do Visagismo B')
    sub=parser.add_subparsers(dest='cmd',required=True)
    create=sub.add_parser('create-user');create.add_argument('--email',required=True);create.add_argument('--barbearia',required=True);create.add_argument('--profissional',required=True);create.add_argument('--tenant',help='ID de barbearia existente; omita para criar outra')
    reset=sub.add_parser('reset-password');reset.add_argument('--email',required=True)
    sub.add_parser('list-tenants')
    backup=sub.add_parser('backup');backup.add_argument('destination')
    args=parser.parse_args();init()
    if args.cmd=='list-tenants':
        with db() as con:
            for row in con.execute('SELECT id,name FROM tenants'):print(row['id'],row['name'])
        return
    if args.cmd=='backup':
        target=Path(args.destination)
        if target.exists():parser.error('Destino já existe. Escolha um novo arquivo.')
        with db() as source,sqlite3.connect(target) as dest:source.backup(dest)
        target.chmod(0o600);print('Backup consistente criado. Fotos devem ser copiadas separadamente, com worker parado.');return
    password=getpass.getpass('Senha (mínimo 12 caracteres): ')
    if len(password)<12 or len(password)>256:parser.error('Use entre 12 e 256 caracteres.')
    if password!=getpass.getpass('Repita a senha: '):parser.error('Senhas diferentes.')
    with db() as con:
        if args.cmd=='create-user':
            tid=args.tenant or secrets.token_hex(12)
            if args.tenant:
                if not con.execute('SELECT 1 FROM tenants WHERE id=?',(tid,)).fetchone():parser.error('Barbearia inexistente.')
            else:con.execute('INSERT INTO tenants(id,name,professional) VALUES (?,?,?)',(tid,args.barbearia,args.profissional))
            con.execute('INSERT INTO users VALUES (?,?,?,?)',(secrets.token_hex(16),tid,args.email.lower().strip(),password_hash(password)))
        else:
            user=con.execute('SELECT id FROM users WHERE email=?',(args.email.lower().strip(),)).fetchone()
            if not user:parser.error('Usuário não encontrado.')
            con.execute('UPDATE users SET password=? WHERE id=?',(password_hash(password),user['id']))
            con.execute('DELETE FROM sessions WHERE user_id=?',(user['id'],))
    print('Acesso atualizado. Nenhuma senha foi gravada em texto puro.')
if __name__=='__main__':main()
