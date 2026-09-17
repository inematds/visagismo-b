# Visagismo com IA — plano de execução

Data: 17/09/2026 · Projeto: `visagismo-b` · Status: planejamento, implementação ainda não iniciada.

## 1. Objetivo e idioma

Transformar o kit recebido em um serviço de consultoria de estilo vendido por barbearias: o cliente recebe recomendações práticas, revisadas pelo barbeiro, e um plano de manutenção. O produto apoia a decisão profissional; não promete um corte ideal universal nem resultados garantidos.

**Idioma escolhido: português do Brasil.** Interface, mensagens, relatórios, documentação e materiais comerciais em pt-BR. Novos identificadores técnicos em inglês; nomes legados em espanhol serão migrados gradualmente, preservando contratos e testes. Inglês na interface fica para uma etapa posterior.

Fonte inspecionada: `/home/nmaldaner/thinclient_drives/.clipboard/visagismo-barberias.zip`. A pasta local estava vazia. Este plano resulta da leitura estática do código e das instruções do ZIP; não equivale à validação do aplicativo em execução. O conteúdo fornecido pelo usuário foi suficiente: o curso no Skool não foi acessado.

## 2. O que existe e o que falta comprovar

| Área | Evidência no ZIP | Consequência para o plano |
|---|---|---|
| Aplicativo | FastAPI, HTML/JS e Jinja2 em `06-app/` | Reaproveitar antes de considerar reescrita |
| Medições | MediaPipe e modelo local em `03-motor/` | Validar repetibilidade e qualidade das fotos |
| Recomendações | Motor de regras e integração opcional com modelo de linguagem | Exigir rastreabilidade entre recomendação, medida e resposta |
| Relatório | Renderização HTML, geometria e plano de visitas | Localizar e incluir aprovação profissional real |
| Imagens | `simulacion.py` usa fal.ai com `nano-banana-pro/edit` | Isolar fornecedor e avaliar adaptação ao padrão flux2-klein |
| Verificação visual | Seis proporções; limites atuais de 3% de desvio médio e 6% máximo | Tratar como filtro geométrico experimental, não prova de identidade |
| Foto lateral | Medição explicitamente experimental; imagem lateral não passa pelo mesmo verificador frontal | Desabilitar simulação lateral no MVP até haver validação específica |
| Pagamento | Checkout simulado | Não aceitar como comprovação de pagamento |
| Histórico | Integração opcional com Supabase | Não confundir com painel multiempresa pronto |
| Marca branca | `marca.json` e script de substituição | Atende personalização de uma instalação; não comprova isolamento entre empresas |
| Retenção | Limpeza local acionada ao gerar novo relatório | Criar rotina agendada e política separada para banco, storage e backups |
| Publicação | Docker, configurações e workflow incluídos | Testar build e revisar infraestrutura antes de usar |
| Licença | Nenhum arquivo de licença encontrado no ZIP | Confirmar condições de reutilização comercial e distribuição antes de comercializar |

O código contém números de custo e alegações jurídicas do material original. Eles não foram verificados e não serão tratados como fatos atuais. O valor citado de €0,30 não é orçamento de operação.

## 3. Produto inicial

**Comprador:** dono ou gestor de barbearia. **Operador:** barbeiro. **Beneficiário:** cliente que quer escolher e manter um estilo compatível com sua rotina.

Oferta inicial: consulta de estilo com questionário, fotos orientadas, sugestões de corte/barba, explicação, simulação opcional, relatório aprovado e proposta de retorno. A consulta pode ser avulsa ou fazer parte de um pacote de atendimento.

Começar com 1–3 barbearias e atendimento assistido. Primeiro validar utilidade, tempo de atendimento e disposição de pagar; depois automatizar aquisição e cobrança.

### Incluído no MVP

- Marca, contato e identidade visual da barbearia.
- Questionário sobre preferências, rotina e manutenção desejada.
- Captura/upload frontal com orientação e rejeição de imagens inadequadas.
- Medições frontais, regras explicáveis e texto em português.
- Revisão pelo barbeiro, ajustes e aprovação registrados.
- Relatório HTML responsivo e versão imprimível.
- Plano de retorno definido ou confirmado pelo profissional.
- Simulação frontal opcional, com reprovação automática e revisão humana.
- Autenticação do operador, acesso controlado aos relatórios e exclusão de dados.
- Registro de duração, falhas e custo por atendimento.

### Após a validação inicial

Pagamento online real, painel multiempresa compartilhado, assinatura das barbearias, lembretes opt-in e acompanhamento longitudinal. Aplicativo nativo, marketplace, reconhecimento de clientes pelo rosto e expansão para saúde ficam fora deste projeto inicial.

## 4. Jornada e estados

Jornada comercial completa:

`landing → oferta → pagamento confirmado → questionário e fotos → análise → revisão profissional → relatório → retorno`

No primeiro piloto assistido, o operador pode abrir um atendimento e registrar uma cobrança realizada no caixa. Essa alternativa deve aparecer explicitamente como cobrança externa; nunca como transação online aprovada.

Estados sugeridos:

`draft → awaiting_payment → paid → submitted → processing → pending_review → delivered`

Falhas técnicas terão estado `failed`, com retomada controlada. Cancelamento, reembolso e exclusão terão registros próprios. O histórico de pagamento não será inferido do estado da análise.

O relatório apresenta observações medidas, preferências informadas, sugestões, esforço de manutenção e próxima visita. Não atribuir personalidade, saúde, origem étnica ou valor estético à pessoa a partir do rosto. Substituir linguagem de “defeito” e “correção” por escolhas de estilo.

## 5. Arquitetura proposta

Preservar **Python + FastAPI + MediaPipe + Jinja2 + HTML/JS**. Evitar migração de framework sem problema concreto.

### Piloto

Uma instalação isolada por barbearia, configurada por marca, usando contêiner e armazenamento persistente. Fluxo síncrono inicialmente, somente se medições de tempo e concorrência mostrarem que cabe no ambiente. Definir timeouts e quantidade máxima de análises simultâneas.

### Operação compartilhada

Adicionar PostgreSQL/Supabase, armazenamento privado, autenticação e isolamento por `tenant_id`. Introduzir worker e fila persistente quando houver execução longa ou concorrência; nunca depender de dicionário em memória ou disco efêmero entre instâncias. O navegador acompanha o estado persistido do atendimento.

Entidades previstas: `tenants`, `users`, `clients`, `consultations`, `photo_assets`, `measurements`, `recommendations`, `simulations`, `reports`, `reviews`, `visit_plans`, `payments`, `subscriptions` e `usage_events`. Versões das regras, modelos e relatórios devem acompanhar cada atendimento.

A configuração de marca deve ser lida em runtime ou por template, substituindo gradualmente as substituições textuais do script legado.

### Uso de IA

- As regras continuam funcionando sem serviços pagos.
- O modelo de texto recebe dados estruturados; validar suas afirmações contra a origem. JSON válido não garante conteúdo correto.
- Manter coerência entre receita estruturada, texto e prompt da simulação.
- Criar uma interface de edição de imagem com **flux2-klein como candidato padrão**, conforme preferência do projeto. Confirmar suporte à edição com referência e medir qualidade antes de adotá-lo em produção.
- Se a edição não preservar o rosto, entregar sem simulação. Não publicar imagem reprovada nem regenerar indefinidamente.
- Limitar tentativas e custo por atendimento; registrar também o custo de imagens rejeitadas.
- Carregar segredos em runtime, procurando primeiro nos dois arquivos globais autorizados; nunca copiar chaves para o projeto ou registrá-las em logs.

## 6. Etapas de implementação e aceite

Estimativa inicial: **6–8 semanas de trabalho de uma pessoa**, com escopo contido; o acompanhamento de retorno pode exigir mais tempo de calendário. Reestimar após executar a base.

| Etapa | Trabalho | Evidência necessária para avançar |
|---|---|---|
| 0 — Base reproduzível · 1–2 dias | Extrair o ZIP com segurança na raiz deste projeto, preservar referência do original, ler instruções, preparar ambiente, executar scripts existentes e inventariar dependências | Servidor inicia; relatório sem APIs é gerado; limitações e versões ficam documentadas |
| 1 — Português e posicionamento · 2–4 dias | Traduzir interface, relatório, erros, prompts de saída, datas e materiais; configurar marca; mapear valores de formulário | Jornada visível em pt-BR; formulários continuam alimentando as mesmas regras; nenhuma mudança de lógica por tradução |
| 2 — Confiabilidade do núcleo · 4–6 dias | Qualidade de captura, limites de upload, validação de textos, fallback, revisão do barbeiro e estados de falha | Foto inválida é rejeitada; indisponibilidade de IA mantém relatório útil; entrega exige aprovação |
| 3 — Piloto assistido · 5–7 dias | Login, armazenamento privado, acesso ao relatório, exclusão, custos e treinamento | Fluxo real com dados autorizados; acesso indevido bloqueado; retenção executada mesmo sem novos atendimentos |
| 4 — Simulação frontal · 3–5 dias | Adaptador de edição, teste do flux2-klein, avaliação humana e calibração do filtro geométrico | Comparação documentada em amostra variada; rejeições funcionam; relatório continua disponível sem imagem |
| 5 — Cobrança e operação compartilhada · 5–8 dias | Gateway, webhooks, idempotência, assinaturas, isolamento por empresa e painel mínimo | Pagamento sandbox confirmado no servidor; duplicidade não gera cobrança/entrega extra; empresa A não acessa B |
| 6 — Preparação para venda · 3–5 dias | Backup/restauração, observabilidade, limites, onboarding, oferta comercial e documentação | Ensaio de restauração; custos conhecidos; suporte definido; piloto avaliado |

A etapa 5 depende de evidência de utilidade no piloto. A simulação pode ser adicionada durante o piloto; não é condição para testar o valor da consulta.

### Primeira semana — ordem prática

1. Importar o kit sem criar outro repositório e registrar o estado original.
2. Executar a demo sem APIs externas e os scripts `prueba_motor.py` e `prueba_informe.py`, verificando pré-requisitos e fixtures.
3. Mapear strings visíveis e valores internos acoplados a textos em espanhol, especialmente em `simulacion.py`.
4. Traduzir a jornada principal e gerar um relatório pt-BR de ponta a ponta.
5. Documentar falhas observadas e priorizar o mínimo necessário para atendimento assistido.

## 7. Validação técnica e de qualidade

- **Motor:** entradas conhecidas, proporções finitas, rejeição de geometria inválida e repetibilidade sob pequenas mudanças de captura. Documentar que medições 2D dependem de pose, iluminação e câmera.
- **Captura:** JPEG, PNG, WEBP e HEIC; arquivo corrompido, extensão falsa, foto grande, nenhuma face, mais de uma face e rosto inclinado. O detector atual configurado para uma face não basta para rejeitar imagens com várias pessoas.
- **Relatório:** regras sem IA; IA indisponível; saída incoerente; nome com caracteres especiais; recomendação compatível com o questionário; revisão e impressão no celular.
- **Simulação:** rosto não detectado, proporção alterada, imagem aceitável, timeout e saldo esgotado. Avaliar também reconhecimento visual pelo cliente e barbeiro; proporções semelhantes não garantem identidade preservada.
- **Dados e acesso:** URL de outro atendimento, tentativa entre empresas, sessão expirada, exclusão dos arquivos e histórico, dados pessoais fora dos logs.
- **Pagamentos:** webhook com assinatura inválida, evento duplicado, evento fora de ordem, cancelamento, reembolso e reprocessamento após falha.
- **Operação:** reinício durante geração, duas solicitações simultâneas, restauração de backup e teto de custo.

Começar a avaliação facial e das simulações com 20–30 participantes autorizados, com variedade de formatos de rosto, tons de pele, texturas de cabelo, barba e condições de captura. É uma amostra exploratória; não demonstra validade universal. Registrar divergências entre sistema e profissional para ajustar regras e linguagem.

## 8. Dados pessoais e operação

Antes de usar fotos de clientes, revisar o tratamento no contexto brasileiro com responsável qualificado: finalidade, fundamento aplicável, comunicação ao cliente, terceiros que recebem fotos, prazos, exclusão e responsabilidades da barbearia e do fornecedor. Não transplantar as conclusões sobre RGPD do ZIP para a LGPD.

Separar fotos temporárias do histórico necessário ao acompanhamento. A retenção de 24 horas do legado é uma configuração inicial, não garantia de expurgo nem regra jurídica. Implementar exclusão agendada e verificar também Supabase, armazenamento e backups.

No piloto, trabalhar com adultos e fotos autorizadas. Desabilitar compartilhamento público e evitar identificação biométrica. Relatórios devem indicar quando uma imagem é simulação gerada por IA.

O Supabase legado usa políticas de inserção anônima; revisar esse desenho antes do serviço compartilhado. Não expor credenciais administrativas e testar autorização no servidor e no banco.

## 9. Modelo comercial e custos

Separar duas receitas:

1. **Fornecedor → barbearia:** implantação por configuração e treinamento; mensalidade por operação, suporte e franquia de uso; excedente por atendimento, se necessário.
2. **Barbearia → cliente:** consulta de estilo avulsa ou integrada ao corte e acompanhamento.

A recorrência precisa corresponder a entregas úteis: ajustar o plano, acompanhar crescimento, mudar estilo ou manter o corte. Não exigir uma nova análise completa a cada visita sem necessidade.

Definir preços depois de medir:

`custo por relatório entregue = (APIs + tentativas rejeitadas + infraestrutura alocada + suporte variável) / relatórios entregues`

`margem de contribuição = receita − taxas − tributos variáveis − custos variáveis`

`barbearias para equilíbrio = custos fixos mensais / contribuição média mensal por barbearia`

A contribuição deve ser positiva para a última fórmula fazer sentido. Incluir o tempo adicional do barbeiro ao avaliar o ganho para a barbearia. Implantação cobre trabalho inicial, não mascara uma mensalidade deficitária. Não prometer aumento de faturamento sem medir.

## 10. Piloto comercial e decisão de continuidade

Entrevistar cinco barbeiros antes de fixar oferta e preço. Selecionar 1–3 parceiros e realizar inicialmente cerca de 30 consultas assistidas, registrando:

- Quantos clientes receberam a oferta, aceitaram e pagaram.
- Tempo total e tempo de intervenção do barbeiro.
- Utilidade percebida e quantidade de recomendações corrigidas.
- Custo por atendimento e taxa de falha/rejeição de simulação.
- Retorno agendado e retorno efetivo em 30–60 dias.
- Interesse da barbearia em continuar pagando e motivos de desistência.

Metas provisórias para o piloto, a ajustar com os parceiros: pelo menos 90% das entradas válidas produzirem relatório sem intervenção técnica; 100% dos relatórios entregues terem revisão; pelo menos 80% das consultas avaliadas como úteis pelo cliente e pelo profissional; margem de contribuição positiva; ao menos dois parceiros interessados em continuidade paga se houver três participantes.

Não atribuir causalidade ao retorno sem comparação adequada. Separar intenção de renovação de renovação realmente paga. Se o texto for útil e a simulação falhar, manter o serviço sem imagem; se a consulta não gerar valor, ajustar a oferta antes de ampliar a plataforma.

## 11. Publicação e continuidade

Código e guia futuro permanecem neste repositório `visagismo-b`. Quando solicitado, o guia público será `guia/index.html`; o aplicativo Python precisará de ambiente próprio de execução — GitHub Pages serve somente conteúdo estático.

Publicação será via Git, respeitando a conta de destino e autoria dos commits. Não operar o painel do Vercel nem depender do status dele para concluir um push. Não foi criado remoto nem feito deploy nesta etapa de planejamento.

**Próxima entrega recomendada:** demo local em português, funcionando sem APIs pagas, com relatório revisável pelo barbeiro e limitações explícitas. Depois disso, iniciar o piloto e medir se o serviço merece a camada de cobrança e multiempresa.
