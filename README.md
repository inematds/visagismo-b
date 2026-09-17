# Visagismo B · v1.0.0

Consultoria de estilo para barbearias, em português, com análise facial real, revisão profissional e implantação em **VPS**.

**[Guia público](https://inematds.github.io/visagismo-b/guia/)** · [Instalação na VPS](VPS.md) · [Plano original](PLANO.md)

## O que está implementado

- FastAPI, interface responsiva e painel por barbearia.
- Login com senha protegida por scrypt, sessões revogáveis e proteção CSRF.
- Questionário, upload JPEG/PNG/WEBP/HEIC e validação de tamanho/resolução.
- MediaPipe Tasks com 478 pontos detectados; cálculo e classificação herdados do kit.
- Recomendações em português, preferências do cliente e decisão final do barbeiro.
- Fila persistente em SQLite e worker separado, com retomada de processamento interrompido.
- Revisão obrigatória, notas profissionais, retorno e relatório imprimível/PDF pelo navegador.
- Histórico isolado por barbearia, exclusão e retenção automática.
- Links revogáveis de 7 dias para relatórios **sem fotos**.
- Simulação frontal opcional com flux2-klein via fal.ai, ou inemaimg remoto; filtro geométrico e fallback sem imagem.
- Cobrança no caixa e integração opcional Mercado Pago Checkout Pro, com assinatura de webhook, consulta do pagamento no servidor e conferência do valor.
- Docker Compose, Caddy/HTTPS, volume persistente, backup e workflow de testes.

A jornada desta versão é **assistida pelo profissional**: entrar → criar atendimento → questionário/foto → análise → revisão → entrega → retorno. Cobrança fica no atendimento. O checkout público antes da captura, a assinatura automática das barbearias e o agendamento com lembretes não fazem parte desta versão; a mensalidade B2B pode ser administrada comercialmente fora do sistema.

## Instalação

O destino é uma VPS Linux com Docker Compose, domínio e portas 80/443 disponíveis. Recomenda-se começar com 2 vCPUs, 4 GB RAM e 20 GB de disco, validando carga real. Não precisa de GPU quando a simulação usa fal.ai; sem provedor, a consulta funciona sem imagem gerada.

```bash
git clone https://github.com/inematds/visagismo-b.git
cd visagismo-b
cp .env.example .env
# Edite DOMAIN e PUBLIC_URL; configure integrações opcionais.
chmod 600 .env
docker compose up -d --build
docker compose exec app python -m app.manage create-user \
  --email voce@barbearia.com.br --barbearia 'Sua Barbearia' --profissional 'Seu nome'
```

A senha é solicitada sem aparecer no terminal. Não há login padrão. Acesse o domínio configurado e conclua os dados da barbearia. Detalhes, cobrança, backup e atualização em [VPS.md](VPS.md).

## Verificação

```bash
python3 -m venv .venv
.venv/bin/pip install --no-deps -r requirements.txt
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q tests
```

As dependências estão fixadas; `--no-deps` evita instalar um segundo pacote OpenCV pelo MediaPipe. O teste usa uma imagem pública de teste do scikit-image, nunca fotos de clientes. Não usar o `requisitos.txt` antigo para a aplicação nova.

## Estrutura

- `app/`: aplicação atual, interface pt-BR, autenticação, fila, pagamentos e administração.
- `03-motor/`: motor facial original reaproveitado; detector ajustado para rejeitar mais de um rosto.
- `tests/`: fluxo completo, isolamento, acesso, uploads, retenção, assinatura e conciliação.
- `guia/` e `capa/`: página pública e capa do projeto.
- `06-app/`, `01-estrategia/`, `configura.py`, `marca.json`: referência do kit legado em espanhol, não usada pelo Compose atual.
- `docs/legado/`: instruções originais preservadas para referência, não são o caminho de implantação atual.

## Limites e tratamento de dados

As proporções são estimativas 2D influenciadas pela captura; não validam beleza, personalidade ou saúde. Comparar proporções da imagem gerada **não garante identidade preservada**. Simulação lateral fica desabilitada. A pessoa revisa antes da entrega.

Fotos são removidas após 24 horas, relatórios após 90 dias (configurável); worker verifica a cada minuto. Backups precisam de retenção própria. O administrador deve completar os dados do responsável e a política de privacidade antes do atendimento comercial.

O Mercado Pago usa a conta configurada na instalação: não existe divisão automática de recebíveis entre barbearias. Para operadores comerciais independentes, use uma instalação e credenciais por empresa. Pagamento online exige credenciais e validação sandbox na conta de destino; testes automatizados usam respostas controladas.

## Origem

Adaptado do ZIP `visagismo-barberias.zip` fornecido pelo usuário. O kit não traz arquivo de licença; esta adaptação não declara uma licença sobre o material original. Verifique os termos de origem antes de redistribuir ou comercializar o kit.
