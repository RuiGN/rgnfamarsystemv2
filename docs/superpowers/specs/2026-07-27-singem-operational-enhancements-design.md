# Evoluções operacionais inspiradas no SINGEM — Design

## Situação

Aprovado pelo usuário em 27 de julho de 2026.

## Objetivo

Incorporar ao RGN Farma System as capacidades úteis identificadas na análise
comparativa com o SINGEM, preservando a arquitetura Django, a experiência web
moderna e os controles farmacêuticos já existentes.

A entrega deve:

- oferecer uma visão operacional única da ordem de produção;
- integrar materiais, produtos acabados, processos, colaboradores, estoque e
  custos sem duplicar regras de domínio;
- disponibilizar um catálogo inicial de 15 relatórios reais;
- importar XML de NF-e de entrada com conferência humana antes de qualquer
  lançamento;
- manter permissões, atomicidade, rastreabilidade e integridade de dados.

## Abordagem escolhida

Será adotada uma integração operacional incremental. Os modelos e serviços
existentes serão ampliados e orquestrados por serviços de aplicação
transacionais.

Foram descartadas:

- uma implementação apenas visual, pois criaria botões sem efeitos operacionais
  confiáveis;
- a reprodução integral do SINGEM, pois introduziria aproximadamente 95
  relatórios e um escopo de MES desnecessário para esta etapa;
- a reprodução de janelas empilhadas e `iframes`, incompatível com o shell web
  responsivo existente.

## Escopo funcional

### 1. Ordem de produção operacional

A ordem de produção receberá:

- prioridade operacional;
- responsável;
- visão agrupada em abas;
- ações de separação, consumo, recebimento, custo e consulta dos mapas;
- indicadores resumidos de quantidade, rendimento, andamento e custo.

As abas serão:

#### Matérias-primas

Reutilizar `MaterialConsumption` e ampliá-lo com a alocação física:

- lote de estoque;
- almoxarifado e localização;
- quantidade reservada;
- quantidade baixada;
- referência das movimentações de reserva e consumo;
- situação operacional da linha.

Somente lotes aprovados, não vencidos, operacionalmente disponíveis e com saldo
suficiente poderão ser separados ou consumidos.

#### Produtos acabados

Criar `ProductionOutput` para representar:

- produto e ordem de produção;
- lote/sublote;
- quantidade planejada e produzida;
- unidade;
- almoxarifado e localização de destino;
- fabricação e validade;
- situação de recebimento;
- lote e movimento de estoque gerados.

O recebimento de produção criará o lote em quarentena. A aprovação do produto
acabado continuará pertencendo ao fluxo de Qualidade/QA.

#### Processos

Criar `ProductionOperationExecution` ligado a uma etapa do roteiro, mantendo um
snapshot operacional dos dados relevantes:

- sequência, operação, centro de trabalho e equipamento;
- tempo planejado;
- início, fim e tempo real;
- situação da execução;
- observações e responsável pelo apontamento.

O snapshot preservará a evidência da ordem mesmo se uma versão futura do roteiro
for criada.

#### Colaboradores

Criar `ProductionLaborEntry` ligado à ordem e, opcionalmente, à execução do
processo:

- usuário;
- função executada;
- equipamento;
- início, fim e duração;
- custo-hora aplicável;
- observações.

Nesta etapa, o usuário autenticável do sistema será a referência do
colaborador. Não será criado um cadastro paralelo de funcionários.

### 2. Ações da ordem

As ações serão expostas pela API REST e pelo catálogo de ações da UI. Todas
serão executadas em `transaction.atomic()`, com bloqueio pessimista dos saldos
afetados e proteção contra repetição.

#### Separar matérias-primas

- permitida para ordem aprovada ou liberada;
- reserva os saldos informados;
- cria movimentos de reserva vinculados à ordem e ao consumo;
- falha integralmente se qualquer linha for inválida;
- uma repetição não pode duplicar reservas.

#### Baixar matérias-primas

- permitida para ordem em execução;
- consome as reservas ou saldos aprovados;
- registra quantidade real, perdas e devoluções;
- cria movimentos vinculados ao consumo;
- mantém os lotes de entrada disponíveis para genealogia.

#### Receber produto acabado

- permitida após conclusão da produção;
- cria ou associa o lote produzido;
- gera entrada de produção em quarentena;
- registra genealogia entre lotes consumidos e lote produzido;
- não executa liberação de qualidade.

#### Calcular custo

- cria ou atualiza `ProductionCostCapture`;
- agrega consumo real, perdas, mão de obra e tempo de processo;
- respeita período de custo fechado;
- registra as fontes e o instante do cálculo;
- não substitui a aprovação ou o fechamento contábil.

#### Mapa de controle

Apresentará o registro operacional do lote:

- identificação da ordem, fórmula e roteiro vigentes;
- matérias-primas e respectivos lotes;
- processos, equipamentos, colaboradores e horários;
- movimentações de estoque;
- eventos de aprovação, liberação, início, pausa, conclusão e recebimento;
- exceções e observações.

#### Mapa de resultados

Apresentará comparativos entre planejado e realizado:

- consumo e variação por material;
- perdas e devoluções;
- rendimento;
- tempo de processo e mão de obra;
- custo planejado, real e variação;
- situação do lote produzido e apontamentos de qualidade.

Os mapas serão páginas de consulta com versão imprimível. Não serão formulários
de decisão regulatória.

## Catálogo inicial de relatórios

O catálogo será entregue como definições de sistema idempotentes, agrupadas por
módulo e executadas por uma lista explícita de executores permitidos.

### Financeiro

1. Contas a receber em aberto e vencidas.
2. Contas a pagar em aberto e vencidas.
3. Fluxo de caixa realizado e projetado.
4. Resultado financeiro por período.

### Fiscal

5. Documentos fiscais por período e situação.
6. Apuração de tributos.
7. Livro de entradas e saídas.

### Estoque e rastreabilidade

8. Posição de estoque por produto, lote e localização.
9. Lotes próximos do vencimento ou vencidos.
10. Genealogia e rastreabilidade de lotes.

### Compras

11. Pedidos de compra abertos ou atrasados.
12. Divergências de recebimento e desempenho de fornecedores.

### Produção e PCP

13. Ordens de produção por situação e atraso.
14. Consumo planejado versus realizado.
15. Rendimento, perdas e custo por ordem.

### Execução segura

O comportamento simulado atual de `ReportExecution.run()` será substituído por
uma camada de execução real:

1. resolver o executor por uma chave registrada no servidor;
2. validar e normalizar os filtros declarados pelo executor;
3. verificar a permissão do usuário para o módulo e o relatório;
4. executar somente consultas ORM parametrizadas;
5. gerar PDF, XLSX ou CSV;
6. armazenar o resultado como arquivo protegido;
7. registrar quantidade de linhas, hash, solicitante, horários e falhas.

Não será permitido informar caminhos de modelo, campos ou SQL arbitrário pela
interface. Definições oficiais serão marcadas como gerenciadas pelo sistema, e
seus campos técnicos não poderão ser editados na UI operacional.

O catálogo será criado por migração de dados idempotente ou por um seeder
versionado chamado pela migração. Atualizações futuras deverão preservar
agendamentos e históricos de execução.

Cada execução assíncrona usa um lease renovável e reserva previamente a
referência canônica definitiva do arquivo cifrado. A execução e a reserva ficam
bloqueadas no banco durante o upload, evitando que um worker retomado revogue a
posse enquanto outro ainda grava. Se o processo cair entre o storage e o commit,
a próxima tentativa consegue localizar e expurgar o blob pela referência já
persistida.

Se o backend renomear excepcionalmente a referência, a execução permanece
retryable e a reconciliação lista somente o diretório exclusivo
`protected/{file_number}/`, removendo apenas nomes cifrados canônicos antes de
liberar a reserva.

Uma reserva somente é desligada da execução depois que o blob foi removido e o
`ProtectedFile` foi marcado como excluído. Falhas de cleanup mantêm a reserva
vinculada a uma execução `pending` ou `failed`, portanto invisível na API de
arquivos e indisponível para leitura até reconciliação segura. Ao esgotar as
tentativas, a execução termina em `failed` sem expor o artefato intermediário.

## Importação de XML de NF-e de entrada

### Modelo de controle

Criar `PurchaseInvoiceXmlImport` com:

- arquivo XML protegido;
- hash SHA-256;
- chave de acesso;
- situação da importação;
- pedido de compra associado;
- documento fiscal e recebimento gerados;
- usuário, horários, avisos e erros estruturados;
- resumo imutável dos principais dados extraídos.

A chave de acesso e o hash impedirão importações duplicadas.

### Fluxo

1. O usuário envia o XML.
2. O sistema faz leitura segura, sem resolução de entidades externas.
3. São validados estrutura, modelo, chave de acesso, emitente, destinatário,
   CNPJ, datas, totais e duplicidade.
4. O fornecedor e o pedido são associados.
5. Os itens são relacionados aos produtos por mapeamentos confiáveis, como GTIN,
   código do fornecedor e vínculo existente no pedido.
6. A UI apresenta prévia, divergências e itens sem correspondência.
7. O usuário resolve pendências e confirma.
8. Em uma única transação são criados o documento fiscal e o recebimento em
   rascunho, com seus itens e impostos suportados.

O XML não lançará estoque, não aprovará o documento fiscal, não liberará
qualidade e não contabilizará valores automaticamente.

Falhas de validação manterão o registro como rejeitado ou pendente de correção,
sem criar documentos parciais.

## Interface

- Manter o shell Duralux/Bootstrap 5 e os componentes existentes.
- A edição da ordem usará abas acessíveis e responsivas, com tabelas inline.
- A página de detalhes exibirá ações conforme permissões e situação.
- Os mapas terão navegação direta na ordem e modo de impressão.
- Relatórios serão apresentados em catálogo por área, com filtros amigáveis;
  campos JSON técnicos não serão exigidos do usuário operacional.
- A importação XML será um fluxo guiado de envio, prévia e confirmação.
- Estados vazios e mensagens de erro devem orientar a correção sem expor
  detalhes internos.

## APIs e serviços

- Novos recursos de produção terão serializers e viewsets próprios.
- Ações compostas ficarão em serviços de aplicação, não nas views.
- A importação XML terá endpoints separados para envio, validação/prévia e
  confirmação.
- Downloads de relatórios e XML usarão o mecanismo de arquivos protegidos.
- As respostas de ações incluirão referências dos registros criados, sem
  devolver conteúdo sensível indevido.

## Permissões e auditoria

Além das permissões de modelo, serão previstas permissões específicas para:

- separar e baixar materiais;
- receber produto acabado;
- calcular custo da ordem;
- consultar mapas;
- executar e baixar relatórios;
- importar e confirmar XML de compra.

Transições e ações materiais registrarão usuário, data/hora, objeto, parâmetros
seguros, resultado e justificativa quando aplicável. Arquivos e artefatos terão
hash e controle de acesso.

O princípio de segregação de funções será preservado:

- Produção não libera qualidade.
- Compras não aprova documento fiscal automaticamente.
- Importação não lança estoque.
- Cálculo de custo não fecha período.

## Integridade, concorrência e idempotência

- Usar `transaction.atomic()` nas ações compostas.
- Usar `select_for_update()` em ordem, importação e saldos afetados.
- Criar restrições de unicidade para eventos que não podem se repetir.
- Validar unidade, produto, lote, endereço e situação em todas as fronteiras.
- Não apagar ou regravar movimentos já contabilizados; correções deverão usar
  movimentos compensatórios e justificativa.
- Não permitir alteração de evidências imutáveis após conclusão.

## Compatibilidade e migração

- As ordens atuais permanecerão válidas; novos campos terão valores padrão ou
  serão opcionais durante a migração.
- Consumos existentes continuarão visíveis e poderão ser enriquecidos sem
  recriação.
- Definições e execuções de relatório existentes serão preservadas.
- Nenhuma importação XML existente será presumida ou fabricada.
- Menus e permissões serão atualizados para os novos recursos.

## Testes

### Unidade e domínio

- validações dos novos modelos de produção;
- transições permitidas e proibidas;
- reserva, baixa, devolução, perda e recebimento idempotentes;
- rejeição de lote vencido, bloqueado ou sem saldo;
- genealogia do produto acabado;
- cálculo de custos e bloqueio de período fechado;
- parsing seguro e validação fiscal do XML;
- duplicidade por chave e hash;
- correspondência e divergência de itens;
- consultas e filtros dos 15 relatórios.

### Integração

- atomicidade de cada ação composta;
- integração produção–estoque–custos–QA;
- integração XML–compras–fiscal sem lançamento de estoque;
- execução e download de PDF, XLSX e CSV;
- permissões e segregação de funções;
- trilha de auditoria e arquivos protegidos.

### Interface

- renderização e permissões das abas e ações;
- acessibilidade básica da navegação por abas;
- prévia e confirmação da importação;
- catálogo, filtros, execução e download de relatórios;
- mapas de controle e resultados;
- responsividade e estados vazios.

## Critérios de aceitação

A entrega será aceita quando:

- uma ordem puder registrar materiais, produtos acabados, processos e
  colaboradores em uma visão integrada;
- reservas, consumos e entradas gerarem movimentos corretos e não duplicáveis;
- o produto acabado entrar em quarentena e depender do fluxo de QA;
- mapas de controle e resultados apresentarem dados reais da ordem;
- o custo for calculado a partir dos apontamentos e movimentações;
- os 15 relatórios executarem consultas reais e gerarem arquivos válidos;
- um XML válido criar rascunhos fiscal e de recebimento somente após
  confirmação;
- XML inválido, duplicado ou divergente não produzir documentos parciais;
- menus, permissões, migrations, APIs e documentação estiverem atualizados;
- `manage.py check`, verificação de migrations e a suíte relevante passarem.

## Fora de escopo

- reprodução dos aproximadamente 95 relatórios do SINGEM;
- importação automática sem conferência;
- transmissão ou manifestação de NF-e de entrada;
- liberação de qualidade pela Produção;
- folha de pagamento ou cadastro completo de RH;
- assinatura eletrônica regulatória adicional além dos controles já existentes;
- cópia do modelo de múltiplas janelas do SINGEM.
