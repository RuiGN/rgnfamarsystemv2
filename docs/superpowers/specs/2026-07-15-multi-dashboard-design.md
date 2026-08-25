# Hub de Dashboards por Área — Design

## Objetivo

Criar um hub de dashboards multi-tenant para oferecer visão executiva e operacional das áreas relevantes do RGN Farma System, usando o design system Duralux/Bootstrap 5 e ApexCharts já presentes no projeto.

## Escopo da primeira entrega

O sidebar receberá a entrada **Dashboards**, com acesso a seis visões:

- Executivo
- Operação/PCP
- Estoque
- Qualidade
- Regulatório/GxP
- Financeiro

Cada visão será uma página renderizada pelo Django, com widgets configuráveis por `DashboardWorkspace` e `DashboardWidget`. O conteúdo será filtrado pelo tenant atual e pelas permissões do usuário.

## Experiência visual

- Reutilizar tokens, espaçamentos, cards, badges e navegação do Duralux existente.
- Usar ApexCharts para séries temporais, barras, donut e indicadores compactos.
- Organizar a página em cabeçalho com período/filtros, faixa de KPIs e grade de gráficos/tabelas.
- Usar estados vazios explícitos quando não existirem registros; não gerar números fictícios.
- Garantir responsividade, foco visível por teclado e respeito a `prefers-reduced-motion`.

## Dados e segurança

- Aproveitar `ReportDefinition`, `DashboardWorkspace` e `DashboardWidget` existentes.
- Criar uma camada de consulta agregada por dashboard, com consultas somente leitura e filtros de período/unidade quando suportados.
- Aplicar o tenant do request em todas as consultas e nunca aceitar tenant pelo cliente.
- Restringir dashboards por módulo/perfil usando as permissões já existentes.
- Registrar erros de consulta e retornar estado degradado sem expor detalhes internos.

## Indicadores iniciais

- Executivo: total de ordens, lotes pendentes, desvios abertos, CAPA vencida e compromissos regulatórios.
- Operação/PCP: ordens por status, produção por período, atrasos e carga planejada.
- Estoque: itens abaixo do mínimo, lotes próximos do vencimento, valor/saldo e movimentos.
- Qualidade: análises pendentes, lotes aguardando liberação, desvios por severidade e CAPA por status.
- Regulatório/GxP: petições por status, exigências abertas, compromissos próximos e documentos vencidos.
- Financeiro: títulos em aberto, vencidos, fluxo por período e distribuição por tipo.

Quando um domínio ainda não possuir dados ou agregações implementadas, o widget exibirá estado vazio e será preparado para ativação incremental.

## Arquitetura

1. Resolver dashboard ativo pelo slug e pelo tenant.
2. Buscar definições de widgets permitidas ao usuário.
3. Executar agregadores registrados por módulo.
4. Renderizar payload serializado no template e inicializar gráficos ApexCharts no navegador.
5. Expor endpoint JSON somente leitura para atualização por filtros sem duplicar regras de autorização.

## Testes e aceite

- Testar isolamento entre tenants e autorização por módulo.
- Testar respostas vazias e erros de agregação.
- Testar cada rota do hub e a presença dos itens no sidebar.
- Testar payloads de KPI/gráfico com dados conhecidos.
- Verificar migrations, lint, testes Django e renderização responsiva.

