# Componentes operacionais do design system — especificação de design

## Objetivo

Aplicar ao RGN Farma System, na ordem aprovada, os padrões úteis encontrados em
`design_system/design-system.html` e `design_system/refs/duralux/index.html`,
transformando-os em componentes Django reutilizáveis e conectados a dados reais.
A interface inteira deve permanecer em português do Brasil, com acentuação
correta, linguagem operacional clara e acessibilidade compatível com fluxos GxP.

## Escopo aprovado e ordem de entrega

1. Componente reutilizável de KPI com progresso.
2. Componente de prazos e eventos operacionais.
3. Layout 8+4 nas telas de detalhe.
4. Filtros avançados configuráveis.
5. Prévia de notificações no cabeçalho.
6. Padronização central de estados e ícones.
7. Evolução dos dashboards e gráficos.
8. Substituição da trilha de auditoria demonstrativa por dados reais.

## Abordagens consideradas

### A. Componentes orientados por dados — selecionada

Criar contratos de apresentação imutáveis em Python, templates parciais e
construtores de contexto específicos. Dashboards, workspaces e detalhes passam
somente dados normalizados aos componentes. Essa abordagem reduz duplicação,
permite testes unitários e impede que regras de domínio sejam implementadas nos
templates.

### B. Alterações diretas em cada página

Seria mais rápida para uma única tela, mas repetiria HTML, mapeamentos de cores,
regras de permissão e textos. A manutenção futura de QA, QC, produção e workflow
ficaria divergente.

### C. Widgets configuráveis pelo banco

Ofereceria personalização dinâmica, porém exigiria modelos, migrations,
validação de configurações e uma superfície administrativa nova. Não há
necessidade aprovada que justifique essa complexidade.

## Direção visual e editorial

A identidade permanece a do ERP atual: base Duralux/Bootstrap, azul institucional,
superfícies claras, cartões discretos e ícones Feather. A assinatura operacional
será uma faixa vertical semântica nos itens de prazo, que expressará criticidade
junto com texto, ícone e data. Não serão introduzidas novas famílias tipográficas
nem um tema paralelo.

Todos os textos visíveis serão escritos em português do Brasil. As ações usarão
verbos claros, como “Ver detalhes”, “Limpar filtros” e “Ver todas as
notificações”. Estados vazios orientarão o usuário, por exemplo: “Nenhum prazo
operacional encontrado.” Não serão usados textos genéricos em inglês, dados
demonstrativos ou abreviações sem explicação.

Informações críticas usarão, no mínimo, a escala visual equivalente a `fs-12`.
Cor nunca será a única indicação de estado. Foco de teclado, rótulos, descrições
ARIA e preferência por movimento reduzido serão preservados.

## Arquitetura

### Contratos de apresentação

Um módulo focado em apresentação fornecerá estruturas imutáveis para:

- `ProgressMetric`: rótulo, valor atual, meta, percentual normalizado, unidade,
  tom, ícone, URL e texto auxiliar;
- `DeadlineItem`: título, descrição, data/hora, situação, tom, ícone, URL e
  identificação acessível;
- `NotificationPreview`: título, mensagem resumida, origem, momento, estado,
  tom e URL autorizada;
- `StatusPresentation`: rótulo, tom e ícone semânticos.

Esses contratos não consultarão o banco. Construtores em `base/ui` farão as
consultas e entregarão dados prontos aos templates. Percentuais serão limitados
ao intervalo de 0 a 100, com comportamento definido para meta igual a zero.

### Templates compartilhados

Parciais sob `templates/includes/components/` renderizarão:

- cartão de KPI com progresso;
- lista de prazos/eventos;
- resumo lateral de detalhe;
- painel de filtros;
- prévia de notificações;
- estado semântico com texto e ícone;
- trilha de auditoria real e estado vazio.

Templates não executarão cálculos de negócio nem formarão URLs a partir de
dados livres. Os links serão preparados no backend e só serão fornecidos após a
verificação de permissão.

## Fluxos por etapa

### 1. KPI com progresso

O contrato atual de KPI será ampliado sem quebrar métricas que possuem apenas
um valor. Quando houver meta, o cartão exibirá valor atual, meta, percentual e
barra de progresso acessível. Sem meta, continuará mostrando o KPI simples.

Os primeiros consumidores serão workspaces e dashboards. As métricas usarão
relações mensuráveis já presentes nos modelos, como ordens concluídas/total,
amostras finalizadas/total e notificações lidas/total. O componente não inventará
metas quando o domínio não fornecer denominador confiável.

### 2. Prazos e eventos operacionais

Os construtores selecionarão registros com datas reais e visíveis ao usuário.
Os itens serão classificados por vencidos, vencendo hoje e próximos, com texto,
data e ícone além da cor. A primeira aplicação será nos workspaces de operação,
qualidade e workflow, limitada a uma quantidade pequena e com link para a lista
completa.

Falhas isoladas de uma fonte não produzirão dados fictícios. Erros previstos de
banco durante inicialização serão tratados como coleção vazia; erros de
programação continuarão visíveis aos mecanismos de observabilidade.

### 3. Layout 8+4 nos detalhes

`resource_detail.html` passará a usar uma coluna principal de oito unidades e
uma lateral de quatro unidades em telas largas, retornando a uma coluna em telas
menores. A área principal manterá os campos e relacionamentos; a lateral reunirá
estado, responsável, datas críticas, identificação e ações autorizadas.

Quando não houver dados laterais suficientes, a área principal ocupará a largura
total. Nenhuma ação destrutiva será criada como controle visual de cartão.

### 4. Filtros avançados configuráveis

O filtro GET existente continuará sendo a fonte de verdade. Busca e filtros mais
usados permanecerão visíveis; filtros complementares ficarão em um painel
recolhível com contagem de filtros ativos. A configuração de cada recurso
definirá campos permitidos, tipo de controle e rótulo.

Somente campos explicitamente permitidos poderão participar das consultas. Datas
inválidas serão ignoradas de forma segura e permanecerão visíveis para correção.
A paginação e a exportação preservarão todos os parâmetros autorizados por meio
de uma query string normalizada, sem montagem manual repetida no template.
Filtros salvos por usuário ficam fora deste escopo.

### 5. Prévia de notificações

O sino abrirá uma prévia com as notificações mais recentes do usuário autenticado
e manterá o link para a Central de workflow. A consulta será limitada, ordenada e
filtrada por destinatário. O componente exibirá quantidade não lida, origem,
momento e estado, sem expor notificações de terceiros.

Quando o usuário não tiver acesso ao workflow, nenhuma consulta será executada e
o componente permanecerá oculto, preservando o comportamento de segurança atual.

### 6. Estados e ícones

O mapeamento textual atualmente embutido em `base.ui.views._status_tone` será
substituído por um resolvedor central. Ele retornará tom e ícone e terá precedência
explícita para estados regulatórios:

- sucesso: aprovado, liberado, concluído, encerrado ou vigente;
- alerta: pendente, em análise, em revisão ou próximo do prazo;
- perigo: rejeitado, bloqueado, vencido, OOS, cancelado ou crítico;
- informação: submetido ou em processamento;
- neutro: rascunho, arquivado ou sem classificação.

O texto original continuará visível; o ícone será complementar. Os consumidores
atuais manterão compatibilidade por uma função que continue fornecendo apenas o
tom quando necessário.

### 7. Dashboards e gráficos

Os dashboards reutilizarão os contratos de KPI e prazo, substituirão o texto
fixo “Atualizado agora” por um horário real gerado no servidor e manterão os dados
dos gráficos em `json_script`. Cada gráfico terá título descritivo e uma tabela
ou resumo textual equivalente para quem não puder interpretá-lo visualmente.

Não serão introduzidos gráficos decorativos nem atualizações simuladas. Consultas
serão agregadas no backend, com atenção ao número total de queries.

### 8. Trilha de auditoria real

O include demonstrativo será removido. A tela exibirá entradas provenientes de
fontes reais já existentes, começando por `DocumentAuditTrail` para documentos
controlados e `RecordStatusHistory` para históricos transversais. Adaptadores
normalizarão data/hora, ator, ação, alteração, motivo e evidência de assinatura.

Quando um recurso declarar trilha, mas não possuir uma fonte registrada, a tela
mostrará “Nenhum evento de auditoria disponível para este registro.” Ela nunca
gerará linhas com `{% now %}`, usuários fixos ou alterações simuladas.

As consultas usarão `select_related` para atores, ordenação decrescente e limite
inicial. A interface será somente leitura; exportação só aparecerá quando existir
uma rota real, autorizada e auditável.

## Permissões e segurança

- Todos os componentes consumirão somente objetos já filtrados pelo usuário.
- Links de detalhe e ações dependerão das permissões Django existentes.
- Notificações serão sempre filtradas por `recipient=request.user`.
- Filtros aceitarão apenas campos registrados, evitando consultas arbitrárias.
- Nenhuma ação crítica será implementada como `GET` ou `javascript:void(0)`.
- Dados de auditoria serão somente leitura e não serão sintetizados no template.

## Desempenho

- Prévia de notificações limitada às cinco entradas mais recentes.
- Listas de prazos limitadas por workspace, com acesso à listagem completa.
- Relacionamentos de ator e responsável carregados com `select_related`.
- Agregações de dashboard executadas no backend e cobertas por testes de consulta
  onde houver risco de crescimento N+1.
- Componentes vazios não dispararão consultas adicionais no template.

## Tratamento de erros e estados vazios

- Percentual sem denominador válido: KPI simples, sem barra enganosa.
- Fonte de prazo sem registros: mensagem de estado vazio em PT-BR.
- Notificações indisponíveis na inicialização: sino sem contagem e sem erro 500.
- Filtro inválido: valor preservado para correção e consulta segura.
- Auditoria sem adaptador: estado vazio verdadeiro, nunca conteúdo demonstrativo.
- Gráfico sem dados: resumo “Não há dados suficientes para exibir este gráfico.”

## Estratégia de testes

Cada etapa seguirá RED–GREEN–REFACTOR:

1. testes unitários dos contratos, percentuais e mapeamentos semânticos;
2. testes de contexto para escopo por usuário e permissão;
3. testes de resposta Django para textos, estrutura e ausência de conteúdo em
   inglês;
4. testes de acessibilidade estrutural para `aria-valuenow`, rótulos, navegação e
   estados vazios;
5. testes de query string para filtros, paginação e exportação;
6. testes das fontes reais de auditoria e ausência dos dados simulados;
7. regressão dos testes de dashboard, workspace, UI, workflow e documentos;
8. verificação visual responsiva nos principais breakpoints e nos temas claro e
   escuro.

## Documentação afetada

Ao final, serão atualizados `TEMPLATES.md`, a documentação de arquitetura de
templates, workflow, dashboards e auditoria, além dos critérios de validação
aplicáveis. Não serão modificados documentos já alterados pelo usuário quando a
mudança puder ser registrada em um documento novo ou não conflitante.

## Critérios de aceitação

- As oito etapas estão implementadas na ordem aprovada.
- Todos os textos visíveis novos estão em português do Brasil com acentuação.
- Dashboards e workspaces reutilizam o mesmo componente de KPI.
- Prazos e notificações respeitam usuário e permissões.
- Detalhes possuem composição 8+4 responsiva quando houver dados laterais.
- Filtros avançados preservam parâmetros autorizados na paginação e exportação.
- Estado, tom e ícone são resolvidos em um único ponto.
- Gráficos possuem alternativa textual ou tabular.
- A trilha demonstrativa não existe mais e somente dados persistidos são exibidos.
- Testes relevantes passam e a documentação é atualizada.

