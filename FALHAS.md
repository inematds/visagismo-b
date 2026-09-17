# Falhas corrigidas

| data | o que quebrou | menor correção | prompt ou infra |
|---|---|---|---|
| 2026-09-17 | Runner do GitHub também não tinha EGL para teste facial | Instalar dependências nativas antes do pytest no workflow | infra |
| 2026-09-17 | Contêiner slim importava MediaPipe mas não executava a análise | Instalar libegl1, libgles2 e libgl1 e testar uma foto no contêiner | infra |
| 2026-09-17 | Compose de validação procurava .env da produção inexistente | Permitir ENV_FILE para validar com .env.example | infra |
| 2026-09-17 | Guia ultrapassava a largura do celular com comandos longos | Aplicar min-width:0 aos filhos de grid e limitar pre | prompt |
| 2026-09-17 | MediaPipe 0.10.21 do kit não instala em Linux ARM64 e instalação automática duplica OpenCV | Fixar MediaPipe 1.0.1 com Tasks API, um único OpenCV headless e instalação sem resolução transitiva | infra |
