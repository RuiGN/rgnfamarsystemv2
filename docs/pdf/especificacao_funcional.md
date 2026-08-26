---
title: RGN Farma System — Especificação Funcional
subtitle: Processos, módulos, perfis, regras de negócio, fluxos operacionais e critérios de aceite funcional
author: RGN SYSTEMS TECNOLOGIA INOVA SIMPLES (I.S.)
date: 28/07/2026
version: 1.2
---

# RGN Farma System — Especificação Funcional

## Sumário

1. Identificação
2. Objetivo funcional
3. Visão funcional do produto
4. Perfis de usuário
5. Regras funcionais transversais
6. Módulos e capacidades
7. Fluxos funcionais críticos
8. Requisitos por domínio
9. Relatórios e indicadores
10. Permissões funcionais
11. Auditoria e rastreabilidade
12. Critérios de aceite funcional
13. Pendências recomendadas para homologação

## Identificação

| Campo | Informação |
|---|---|
| Produto | RGN Farma System |
| Documento | Especificação Funcional |
| Versão documental | 1.2 |
| Data | 28/07/2026 |
| Empresa desenvolvedora | RGN SYSTEMS TECNOLOGIA INOVA SIMPLES (I.S.) |
| CNPJ | 67.956.492/0001-64 |
| Endereço | Rua Doutor Joao Marques, 60, Ilha do Retiro — Recife/PE, CEP 50750-320 |

### Histórico de revisões

| Versão | Data | Alteração |
|---|---|---|
| 1.0 | 21/07/2026 | Emissão inicial da especificação funcional. |
| 1.1 | 27/07/2026 | Fluxo operacional de Produção, mapas, segregação técnica de qualidade e disposição transacional QA. |
| 1.2 | 28/07/2026 | Catálogo curado de relatórios, execução controlada, agendamentos, artefatos protegidos e critérios de aceite. |

## Objetivo funcional

Este documento descreve o comportamento funcional esperado do RGN Farma System sob a perspectiva de negócio, operação e homologação. A especificação complementa o manual do usuário e a especificação técnica, descrevendo quais processos o sistema suporta, quais usuários participam, quais registros são mantidos e quais critérios devem ser verificados na homologação funcional.

## Visão funcional do produto

O RGN Farma System é um ERP farmacêutico web single-instance. A aplicação centraliza processos operacionais e regulados, permitindo que as áreas da empresa trabalhem sobre uma base única de dados, com controle de permissões, histórico, rastreabilidade e padronização de fluxos.

![Mapa macro dos módulos](assets/mapa_modulos.png)

O sistema cobre o ciclo operacional completo:

1. cadastro de dados mestres;
2. formulação e roteiros;
3. planejamento MPS/MRP;
4. compras e recebimento;
5. estoque e genealogia de lotes;
6. produção;
7. controle e garantia da qualidade;
8. documentos, desvios, CAPA, mudanças, auditorias e riscos;
9. fiscal, financeiro, custos e CRM;
10. regulatório, farmacovigilância, recalls e pós-mercado;
11. manutenção, treinamentos, workflow, relatórios, integrações e IA.

## Perfis de usuário

| Perfil | Responsabilidades funcionais típicas |
|---|---|
| Administrador do sistema | Usuários, grupos, permissões, cadastros administrativos e suporte técnico funcional |
| Produção | Ordens de produção, apontamentos, consumo, status produtivo e encerramento operacional |
| PCP/Planejamento | Políticas, MPS, MRP, capacidade, sugestões e acompanhamento de necessidades |
| Compras | Requisições, cotações, pedidos, fornecedores e recebimentos |
| Almoxarifado/Estoque | Lotes, saldos, movimentações, reservas, segregações e genealogia |
| Custos | Custo padrão, simulações, custo real, variações e fechamento |
| Financeiro | Contas, títulos, liquidações, fluxo de caixa e fechamento financeiro |
| Fiscal | Cadastros fiscais, documentos fiscais, emissão, cancelamento, livros e apurações |
| Comercial/CRM | Clientes, oportunidades, propostas, pedidos e reclamações |
| Controle de Qualidade | Especificações, amostras, análises, resultados, laudos e investigações laboratoriais |
| Garantia da Qualidade | Revisões, liberações de lote, bloqueios, treinamentos críticos e aprovações |
| Documentação | Documentos controlados, revisões, distribuição, confirmação de leitura e trilha documental |
| Compliance/GxP | Desvios, CAPA, mudanças, auditorias, riscos e histórico de status |
| Regulatório | Dossiês, registros, petições, exigências, compromissos, alertas e relatórios |
| Farmacovigilância | Casos, causalidade, investigação, ações e relatórios de segurança |
| Manutenção | Ativos, planos, ordens, paradas, calibração e indicadores |
| Gestores | Aprovações, indicadores, relatórios, pendências e auditoria gerencial |

## Regras funcionais transversais

### Autenticação e acesso

- Cada usuário deve acessar com credencial individual.
- A interface exibe somente módulos e recursos autorizados.
- Ações críticas só aparecem quando o usuário possui permissão e o registro está em status compatível.
- Usuários, grupos e permissões são administrados pelo Django Admin.

### Ciclo de vida dos registros

- Registros operacionais possuem status ou estágio compatível com seu processo.
- Ações como aprovar, rejeitar, iniciar, concluir, cancelar, publicar, arquivar, bloquear e desbloquear devem validar pré-requisitos.
- O sistema deve impedir transições inválidas.
- O usuário deve receber mensagem clara quando uma regra bloquear uma ação.

### Rastreabilidade

- Ações críticas devem registrar usuário, data/hora e contexto.
- Registros GxP devem preservar histórico e evidência.
- Trilhas de auditoria devem ser somente leitura quando aplicável.
- Arquivos protegidos devem manter registro de acesso, visualização, download, substituição e expiração.

### Integridade de dados

- Cadastros mestres devem evitar duplicidade.
- Campos obrigatórios devem ser validados.
- Relacionamentos entre produto, lote, ordem, documento, análise, desvio, CAPA e risco devem ser preservados.
- Registros aprovados, publicados, fechados ou cancelados podem ter edição restringida.

## Módulos e capacidades

| Módulo | Capacidades funcionais |
|---|---|
| Auxiliary | Catálogos auxiliares, áreas, processos, departamentos, papéis, países, estados, cidades, moedas e parâmetros básicos |
| Accounts | Usuário autenticado, identidade de acesso e integração com Admin para permissões |
| Masters | Produtos, materiais, parceiros, unidades, categorias, sites, almoxarifados e localizações |
| Formulations | Fórmulas mestras, componentes, perdas previstas, roteiros e etapas |
| Production | Ordens de produção, workflow produtivo e consumo real |
| Planning | Políticas, MPS, MRP, sugestões e capacidade |
| Procurement | Requisições, cotações, qualificação de fornecedor, pedidos e recebimentos |
| Inventory | Lotes, saldos, movimentações e genealogia |
| Costing | Custo padrão, simulações, custo real, fechamento e relatórios de custo |
| Finance | Plano de contas, títulos, liquidações, caixa, fluxo e fechamento |
| Fiscal | Cadastros fiscais, documentos, impostos, emissão, XML/DANFE, apurações e livros |
| CRM | Clientes, contatos, campanhas, oportunidades, propostas, contratos, pedidos e reclamações |
| Quality | Especificações, amostras, análises, resultados, investigações e documentos de qualidade |
| QA | Revisões QA, checklist, liberação de lote, bloqueios e regras de treinamento crítico |
| Documents | Documentos controlados, anexos, relacionamentos, aprovações, distribuição e trilha |
| Deviations | Desvios, evidências, investigação, impacto, aprovações e vínculos |
| CAPA | Registros CAPA, ações, evidências, eficácia, aprovações e notificações |
| Changes | Controle de mudanças, avaliações, ações, aprovações e impacto de estoque |
| Audits | Programas, planos, checklists, achados, evidências, ações e relatórios |
| Risks | Registro, avaliação, controles, mitigação, vínculos, revisões e alertas |
| Regulatory | Produtos regulatórios, dossiês, registros, petições, exigências, compromissos e alertas |
| Pharmacovigilance | Casos, classificação, causalidade, investigação, ações e relatórios de segurança |
| Recalls | Reclamações, devoluções, campanhas, clientes impactados, comunicações e efetividade |
| Maintenance | Ativos, planos, ordens, paradas, uso e relatórios |
| Training | Cargos, funções, competências, requisitos, matriz, turmas e atividades críticas |
| Files | Arquivos protegidos, regras de acesso, links seguros e auditoria |
| Reports | Dashboards, widgets, relatórios, execuções, agendamentos e notificações |
| Workflow | Notificações, filas de aprovação, tarefas, delegações, comentários, anexos e jobs |
| Integrations | Conectores, clientes de API, rotação de segredo, logs e eventos |
| AI Agents | Perfis de agentes, execuções, sugestões revisáveis e auditoria de prompts |
| Knowledge | Fontes regulatórias, documentos, chunks, chat RAG e logs de ingestão |
| Governance | Parâmetros, catálogos, logs de auditoria e cargas demo auditadas |
| Compliance | Políticas, histórico de status, ações críticas e checklist transversal |

## Fluxos funcionais críticos

### Fluxo de produção

1. PCP ou Produção cria a ordem.
2. Usuário autorizado aprova a ordem.
3. Produção aloca lotes aprovados e executa **Separar matérias-primas** para
   reservar os materiais.
4. Usuário autorizado libera a ordem, após validação de produto, fórmula e
   roteiro.
5. A execução é iniciada; quando necessário, pode ser pausada e retomada.
6. Produção registra processos, colaboradores, consumo real, perdas e
   devoluções e executa **Baixar matérias-primas**. A soma de consumo, perda e
   devolução deve reconciliar cada reserva.
7. Produção conclui a ordem e registra o rendimento real.
8. Produção recebe os produtos acabados. Estoque, genealogia e evidência de
   recebimento são criados em quarentena.
9. A decisão de liberar a qualidade do lote acabado ocorre exclusivamente no
   fluxo de QA.
10. Em ordem concluída ou encerrada, usuário autorizado pode capturar o custo
    planejado e real de um período contábil aberto.

Critérios de aceite:

- não permitir iniciar ordem não liberada;
- reservar e baixar somente saldo aprovado, não vencido e suficiente;
- exigir baixa dos componentes ativos da fórmula antes do recebimento do
  produto acabado;
- manter o lote acabado em quarentena; Produção não pode aprová-lo;
- impedir que a API, a UI genérica ou o Admin de Estoque alterem diretamente
  a disposição do lote, o status e as quantidades derivadas de seus saldos ou
  as dimensões que identificam um saldo persistido;
- ao aprovar, rejeitar, bloquear ou desbloquear em QA, exigir ator ativo
  relido no banco e estado de origem válido, bloquear liberação, lote, saldos
  e evidências relacionadas, atualizar a disposição de todo o conjunto e
  registrar uma auditoria na mesma transação;
- manter produto, lote, revisão QA, documento de qualidade e ordem de produção
  imutáveis depois da criação da liberação, além de impedir reescrita da
  evidência de decisões terminais;
- rejeitar a liberação quando algum saldo possuir disposição divergente, sem
  normalização automática ou gravação parcial;
- registrar usuário e data nas transições e ações relevantes;
- preservar vínculos entre ordem, consumos, movimentos, lote acabado e
  genealogia;
- repetir reserva, baixa, recebimento ou cálculo coerente deve retornar os
  mesmos registros, sem duplicar movimentos, saldo, genealogia ou auditoria;
- rejeitar uma transição de ciclo de vida repetida fora do estado de origem;
- não apagar nem reescrever movimento postado. Correções posteriores devem
  preservar o original e usar movimento novo com justificativa.

Lacuna funcional conhecida: o cancelamento atual não cria compensações de
estoque e ainda não há action de Produção para estorno auditado de movimentos
postados. O ajuste de estoque existente é um primitivo genérico, não o fluxo
regulado de compensação da ordem. A API REST genérica de movimentos também
ainda permite atualização e exclusão conforme as permissões de modelo; a
imutabilidade pós-postagem precisa ser reforçada nessa fronteira.

#### Workspace e mapas da ordem

A workspace possui quatro abas independentes e sempre visíveis:
**Matérias-primas**, **Produtos acabados**, **Processos** e
**Colaboradores**. Cada aba aplica permissões próprias de consulta e escrita,
valida os registros novamente sob lock transacional e registra uma entrada
funcional de auditoria. Sem a permissão de consulta, a aba mostra um aviso e
não consulta nem renderiza seus registros. Resultados recebidos e processos
concluídos ou não executados são imutáveis; processos não executados exigem
ator e justificativa.

Os mapas de controle e resultados são somente leitura e imprimíveis. O acesso
exige `production.view_productionorder` e
`production.view_production_maps`. Materiais, produtos acabados, processos,
colaboradores, movimentos, genealogia, custos e eventos exigem ainda suas oito
permissões de seção; uma seção não autorizada não é consultada.

O mapa de controle apresenta identificação da ordem, fórmula, roteiro,
programação, responsáveis, materiais e lotes, processos/equipamentos/tempos,
colaboradores, movimentações, genealogia, custos, eventos e observações. O mapa
de resultados apresenta também rendimento, perdas, retrabalho, devoluções,
variações de material, tempos de processo e mão de obra e custos planejado,
real e variação.

### Fluxo de qualidade de amostras

1. Amostra é criada.
2. Coleta é registrada.
3. Recebimento pelo laboratório é registrado.
4. Análise é iniciada.
5. Resultados são registrados.
6. Revisão técnica é executada.
7. Amostra é aprovada ou rejeitada.
8. OOS/OOT/alerta deve direcionar investigação quando aplicável.

Critérios de aceite:

- exigir especificação e parâmetros obrigatórios;
- impedir aprovação sem resultado/revisão quando a regra exigir;
- preservar rastreabilidade de analista, revisor e aprovador.

### Fluxo documental

1. Documento controlado é criado.
2. Documento é submetido.
3. Revisão é executada.
4. Aprovação é registrada.
5. Documento é publicado.
6. Distribuição é feita ao público-alvo.
7. Usuários confirmam leitura.
8. Nova revisão, obsolescência, cancelamento ou arquivamento ocorre conforme necessidade.

Critérios de aceite:

- impedir publicação sem aprovação;
- registrar trilha documental;
- preservar anexos e relacionamentos;
- bloquear edição indevida em documento publicado.

### Fluxo de desvio e CAPA

1. Desvio é registrado.
2. Evidências são anexadas.
3. Investigação é iniciada.
4. Impacto é avaliado.
5. Aprovações são coletadas.
6. CAPA é criada quando necessário.
7. Ações CAPA são executadas.
8. Eficácia é verificada.
9. Desvio/CAPA são encerrados.

Critérios de aceite:

- impedir encerramento sem investigação e aprovações requeridas;
- vincular CAPA ao desvio quando aplicável;
- registrar prazos, responsáveis e evidências;
- preservar histórico de status.

### Fluxo fiscal

1. Documento fiscal é criado.
2. Itens e impostos são conferidos.
3. Documento é revisado.
4. Documento é aprovado.
5. Lançamento fiscal é executado.
6. Emissão NF-e é executada quando aplicável.
7. Status é consultado.
8. XML/DANFE ficam disponíveis conforme permissão.
9. Cancelamento e envio por e-mail seguem autorização e regra fiscal.

Critérios de aceite:

- exigir cadastros fiscais válidos;
- preservar eventos de emissão;
- controlar acesso a XML/DANFE;
- registrar auditoria fiscal.

### Fluxo regulatório

1. Produto regulatório é cadastrado.
2. Dossiê é criado.
3. Evidências e requisitos são vinculados.
4. Petição é submetida.
5. Exigências são respondidas.
6. Compromissos são acompanhados.
7. Alertas de prazo são gerados.
8. Relatório regulatório é consolidado.

Critérios de aceite:

- controlar prazos e vencimentos;
- registrar status de exigências;
- vincular evidências e documentos;
- permitir rastreabilidade da decisão regulatória.

## Requisitos por domínio

### Dados mestres

- O sistema deve permitir cadastro global de produtos, parceiros, unidades, categorias, sites, almoxarifados e localizações.
- O sistema deve impedir duplicidades incompatíveis com a regra de negócio.
- O sistema deve disponibilizar dados mestres para todos os módulos dependentes.

### Produção e estoque

- O sistema deve controlar ordens de produção e seus status.
- O sistema deve registrar reserva, consumo real, perdas e devoluções,
  reconciliando as quantidades e preservando os movimentos vinculados.
- O sistema deve receber o produto acabado em quarentena e impedir que
  Produção aprove sua qualidade.
- O sistema deve manter lotes, saldos e movimentações.
- O sistema deve impedir mutação genérica dos campos de disposição do lote e
  dos campos derivados de status, quantidade e reserva do saldo.
- O sistema deve permitir rastrear genealogia entre lotes consumidos e gerados.
- O sistema deve disponibilizar workspace de quatro abas e mapas de controle e
  resultados segregados por permissão.
- O sistema deve calcular rendimento, tempos e custos planejado, real e
  variação sem expor uma seção não autorizada.

### Qualidade e GxP

- O sistema deve controlar especificações, amostras, análises e resultados.
- O sistema deve controlar revisões QA, liberações e bloqueios.
- A liberação QA deve alterar atomicamente a liberação, o lote e todos os seus
  saldos, com locks, ator, trilha de auditoria e rejeição de divergência
  preexistente.
- O sistema deve registrar desvios, CAPA, mudanças, auditorias e riscos.
- O sistema deve preservar evidência, histórico e trilha quando aplicável.

### Financeiro, fiscal e custos

- O sistema deve controlar títulos, liquidações e fluxo de caixa.
- O sistema deve controlar custo padrão, custo real e fechamento.
- O sistema deve controlar documentos fiscais, impostos, emissão e auditoria fiscal.

### Regulatório e pós-mercado

- O sistema deve controlar dossiês, registros, petições e exigências.
- O sistema deve controlar farmacovigilância e recalls.
- O sistema deve gerar alertas e relatórios de acompanhamento.

### Suporte operacional

- O sistema deve controlar manutenção, treinamentos, workflow e relatórios.
- O sistema deve registrar integrações e eventos técnicos.
- O sistema oferece chat RAG somente leitura para consultar o manual ERP, com citações, histórico e revisão humana quando a orientação apoiar uma decisão regulada.
- O chat exige `knowledge.view_ragchatsession`, mantém isolamento por usuário e não executa SQL, workflows nem alteração de registros.

## Relatórios e indicadores

O sistema deve permitir acompanhamento gerencial por dashboards, widgets, relatórios, execuções e agendamentos.

### Catálogo operacional curado

O sistema deve disponibilizar 15 relatórios curados para Financeiro, Fiscal,
Estoque e Rastreabilidade, Compras e Produção. O catálogo deve mostrar somente
definições ativas para as quais o usuário possua a permissão do domínio.
Consultar exige permissão de visualização da definição; executar exige também
permissão para adicionar execução.

Nenhuma definição operacional pode fornecer SQL, caminho de model, lista de
campos ou expressão executável. O código do executor é resolvido exclusivamente
em uma lista registrada no servidor.

Requisitos funcionais e de segurança:

- cada relatório deve aceitar somente os filtros declarados pelo servidor;
- filtros obrigatórios, tipos `date`, `text`, `integer` e `choice` e opções de
  escolha devem ser validados antes da execução;
- escolhas devem começar vazias; escolhas obrigatórias exigem ação explícita e
  escolhas opcionais vazias não devem compor os filtros executados;
- os formatos disponíveis no catálogo curado devem ser PDF, XLSX e CSV;
- definição, filtros, formato e solicitante da execução devem permanecer
  imutáveis durante o processamento;
- execução deve registrar estado `pending`, `running`, `completed`, `failed`
  ou `cancelled`, instantes, total de linhas, hash e mensagem pública de erro;
- somente `ConnectionError`, `TimeoutError` e `OSError` devem ser
  classificadas como falhas recuperáveis; exceções Django de banco não devem
  receber essa classificação apenas por sua origem;
- uma falha recuperável deve devolver a execução a `pending`; somente a task
  Celery deve enfileirar retry automático, enquanto a execução direta
  síncrona pela interface ou API deve retornar erro seguro sem enfileirar nova
  tentativa;
- falhas definitivas e tentativas Celery esgotadas devem terminar em `failed`
  sem expor detalhe interno;
- o caminho assíncrono deve usar a task Celery registrada, guardar seu ID e
  impedir processamento concorrente pelo lock/lease da execução;
- a conclusão agendada deve atualizar datas do agendamento e criar notificações
  internas para destinatários ou, na ausência deles, para o solicitante;
- o artefato deve ser protegido com AES-256-GCM e hash SHA-256, e o download
  deve exigir execução concluída, arquivo ativo e permissões de execução e
  arquivo;
- APIs, serializers e respostas de link/download não devem expor o caminho
  interno do storage;
- respostas de download devem impedir cache compartilhado ou persistente,
  aplicar `nosniff` e usar nome/MIME seguros;
- claims, retries, falhas e conclusão devem tentar registrar auditoria
  funcional em modo best-effort; uma falha da auditoria deve ser registrada e
  monitorada sem bloquear o lifecycle, sem promessa de outbox ou replay;
- upload cifrado, downloads e acessos negados devem usar os eventos diretos de
  `ProtectedFileAuditTrail` implementados para o arquivo protegido.

O cadastro de `ReportSchedule` representa frequência, próxima execução,
filtros, formato, proprietário e destinatários. No escopo funcional atual, o
serviço pode enfileirar uma execução no Celery quando chamado sem execução
imediata, enquanto a ação REST `trigger_now` executa imediatamente. Não existe
no módulo uma task periódica que consulte `next_run_at`; a expressão cron é
obrigatória para a frequência `cron`, mas o avanço atual usa um dia e não
interpreta a expressão. A homologação de automação de calendário deve, portanto,
incluir a orquestração aprovada que chama o disparo.

Indicadores esperados:

- ordens por status;
- MRP e sugestões pendentes;
- saldos e lotes críticos;
- custos padrão versus real;
- títulos vencidos e fluxo de caixa;
- documentos fiscais e obrigações;
- amostras pendentes e resultados OOS/OOT;
- desvios por severidade;
- CAPAs vencidas;
- mudanças em implementação;
- auditorias e achados;
- riscos críticos;
- compromissos regulatórios;
- casos de farmacovigilância;
- recalls em andamento;
- treinamentos vencidos;
- jobs e integrações com falha.

## Permissões funcionais

As permissões funcionais seguem o modelo:

| Ação funcional | Permissão operacional |
|---|---|
| Consultar registros | visualizar |
| Criar registros | adicionar |
| Editar registros | alterar |
| Remover registros quando permitido | excluir |
| Executar workflow | alterar ou permissão composta |
| Gerar registros relacionados | alterar origem e adicionar destino |
| Consultar auditoria | visualizar trilha |
| Consultar o assistente RAG | `knowledge.view_ragchatsession` |
| Administrar usuários/grupos | permissões do Django Admin |

Para homologação, recomenda-se validar pelo menos três perfis:

1. usuário sem permissão no módulo;
2. usuário de consulta;
3. usuário operador/aprovador com ações críticas.

## Auditoria e rastreabilidade

O comportamento funcional esperado é:

- registrar ator das ações críticas;
- registrar data/hora;
- preservar status anterior e novo quando aplicável;
- registrar motivo ou justificativa quando solicitado;
- impedir edição de trilhas imutáveis;
- manter evidências anexadas com integridade;
- permitir consulta por usuários autorizados.

## Critérios de aceite funcional

| Critério | Resultado esperado |
|---|---|
| Login | usuário válido acessa `/app/`; usuário inválido não acessa |
| Menu por permissão | usuário vê somente módulos permitidos |
| Consulta | usuário com `view` lista e abre detalhe |
| Criação | usuário com `add` cria registro válido |
| Alteração | usuário com `change` altera registro permitido |
| Exclusão | usuário com `delete` exclui somente quando regra permite |
| Ação crítica | botão aparece e executa somente com permissão/status válido |
| Auditoria | ação crítica deixa evidência rastreável |
| Validação | dados obrigatórios e regras de domínio bloqueiam inconsistência |
| Catálogo de relatórios | somente os 15 relatórios ativos autorizados aparecem para o perfil |
| Filtros de relatório | campo não declarado, tipo incorreto, escolha inválida ou obrigatório vazio é rejeitado antes da execução |
| Relatório | PDF, XLSX e CSV executam com filtros válidos e retornam conteúdo e quantidade de linhas coerentes |
| Concorrência de relatório | a mesma execução não conclui duas vezes; lease expirado permite retomada e tenta registrar auditoria best-effort |
| Falha de relatório | somente `ConnectionError`, `TimeoutError` e `OSError` voltam a `pending`; Celery agenda retry automático, mas UI/API síncrona retorna erro seguro sem enfileirar; falha definitiva ou retries esgotados termina em `failed` |
| Artefato de relatório | somente execução concluída e arquivo ativo/autorizado permitem download AES-256-GCM com hash SHA-256 |
| Resposta de download | resposta não expõe caminho interno, usa `no-store`, `nosniff`, nome e MIME seguros |
| Auditoria de lifecycle | falha injetada em `GovernanceAuditLog.record` é registrada e monitorada, não interrompe claim/retry/falha/conclusão e não pressupõe outbox ou replay |
| Auditoria de arquivo protegido | upload cifrado, download e negação usam os eventos diretos de `ProtectedFileAuditTrail` conforme o fluxo implementado |
| Notificação de relatório | conclusão gera notificação interna aos destinatários ou solicitante sem reverter o resultado se a notificação falhar |
| Integração | evento técnico registra sucesso/falha sem expor segredo |
| Documentos | publicação, distribuição e leitura respeitam fluxo |
| Qualidade | aprovação de amostra exige pré-requisitos funcionais |
| Desvio/CAPA | encerramento exige investigação, ações e aprovações quando aplicável |

## Pendências recomendadas para homologação

- Formalizar matriz de perfis e permissões por área.
- Validar em homologação os grupos que receberão `knowledge.view_ragchatsession` e o aviso de somente leitura.
- Definir política de exposição da documentação de API em produção.
- Validar fluxos com massa de dados representativa.
- Executar testes de backup/restore com evidência.
- Registrar protocolo CSV com IQ/OQ/PQ quando aplicável.
- Validar relatórios críticos com usuários-chave.
- Validar trilhas de auditoria de registros GxP.
- Simular falha de auditoria do lifecycle de relatório, confirmar a continuidade
  do estado, o alerta/log operacional e a abertura de desvio ou incidente para
  reconciliação da evidência ausente.
