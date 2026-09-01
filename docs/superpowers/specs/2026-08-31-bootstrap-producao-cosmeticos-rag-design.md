# Bootstrap de Produção Cosmético e Corpus Funcional da IA — Design

## 1. Contexto

O ERP já possui uma carga curada no app `auxiliary`, um carregador de
referências oficiais, o app `knowledge`, um gerador de manual a partir do
registry da interface e publicação vetorial em Redis. Esses componentes ainda
não formam um gate único de deploy. A carga atual também não contempla
catálogos mestres de outros domínios, como unidades de medida, e os guias
passo a passo não cobrem todas as funcionalidades registradas.

Este desenho transforma os dados de referência e o conhecimento funcional em
artefatos versionados do release. A implantação só poderá ser publicada depois
de carregar os catálogos, construir o corpus e validar o modo de recuperação da
IA configurado para o ambiente.

## 2. Objetivos

- preencher automaticamente, no deploy, catálogos oficiais e mestres em
  português do Brasil adequados à indústria de cosméticos;
- manter a carga determinística, idempotente, auditável e segura para
  reexecução;
- preservar cadastros do usuário fora do namespace reservado;
- construir um corpus funcional que cubra todos os módulos, recursos e ações
  expostos pela interface do release;
- publicar o índice vetorial sem expor geração parcial;
- impedir a publicação pública de um release com bootstrap incompleto.

## 3. Decisões aprovadas

- o bootstrap criará somente referências e cadastros mestres;
- não serão criados dados operacionais ou de demonstração;
- registros gerenciados usarão códigos reservados e serão atualizados para o
  conteúdo canônico do release;
- registros fora do namespace reservado serão preservados integralmente;
- catálogos e snapshots ficarão versionados no repositório;
- atualizações de fontes externas serão feitas fora do deploy, revisadas e
  incorporadas a um release;
- dados mestres e corpus PostgreSQL são gates obrigatórios;
- a indexação vetorial é obrigatória no modo normal;
- sem OpenAI ou Redis, o deploy somente poderá continuar com
  `RAG_CHAT_LOCAL_ONLY=true` e recuperação local validada;
- a IA permanecerá somente leitura e responderá em pt-BR com citações;
- o Cloudflare Tunnel só será disponibilizado depois do bootstrap e do smoke
  test local.

## 4. Abordagens avaliadas

### 4.1 Catálogos versionados no repositório — escolhida

O deploy consome pacotes declarativos locais com código, conteúdo, fonte,
versão e hash. A execução não depende da disponibilidade de serviços externos
e sempre produz o mesmo resultado para o mesmo SHA.

### 4.2 Consulta de fontes externas durante o deploy — rejeitada

Apesar de potencialmente mais atual, tornaria o release dependente de rede,
latência, indisponibilidade e mudanças não revisadas nas fontes.

### 4.3 Dados inseridos por migrations — rejeitada

Migrations são adequadas à evolução de schema e a pequenas transformações
irreversíveis, mas não à manutenção recorrente de grandes catálogos e do corpus
funcional da IA.

## 5. Escopo dos catálogos

### 5.1 App `auxiliary`

- países, unidades federativas, municípios e moedas;
- áreas e processos operacionais;
- departamentos e funções organizacionais;
- condições de pagamento e entrega;
- níveis de impacto;
- tipos e valores de catálogo cosmético;
- módulos e models efetivamente registrados na aplicação.

O bootstrap não criará nem alterará registros operacionais de backup.

### 5.2 App `masters`

- unidades de medida usadas em massa, volume, quantidade, concentração,
  temperatura, pressão, tempo, comprimento e área;
- famílias, grupos e categorias de materiais/produtos;
- linhas de produtos cosméticos;
- formas cosméticas;
- apresentações;
- faixas/concentrações de referência;
- áreas de aplicação.

Os códigos terão namespace reservado e estável. Exemplos de símbolos incluem
`kg`, `g`, `mg`, `µg`, `L`, `mL`, `µL`, `un`, `%`, `°C`, `Pa`, `kPa`, `bar`,
`min` e `h`. Nome, símbolo e finalidade deverão ser validados contra a fonte
de metrologia registrada no pacote.

### 5.3 Outros domínios auxiliares seguros

- `costing`: elementos de custo;
- `crm`: grupos de clientes e canais de venda;
- `finance`: plano de contas e categorias financeiras de referência;
- `training`: cargos, funções e competências típicas da indústria cosmética;
- `fiscal`: unidades fiscais e códigos oficiais selecionados, sempre com
  versão e fonte identificáveis.

Somente models explicitamente registrados no catálogo de bootstrap poderão ser
gravados. A classificação não será inferida apenas pelo nome do model.

### 5.4 Exclusões obrigatórias

Não serão criados:

- produtos ou matérias-primas;
- parceiros, clientes, fornecedores ou fabricantes;
- plantas, armazéns ou localizações específicas da empresa;
- fórmulas, roteiros ou especificações;
- lotes, saldos ou movimentos de estoque;
- documentos, evidências, desvios, CAPAs ou auditorias;
- ordens, pedidos, títulos, notas ou registros fiscais transacionais;
- treinamentos realizados, usuários ou dados pessoais;
- qualquer registro que possa ser interpretado como evidência GxP real.

## 6. Pacotes, namespace e proveniência

Cada pacote declarará:

- identificador e versão do catálogo;
- namespace de códigos gerenciados;
- fonte e data de referência;
- licença ou condição de uso quando aplicável;
- conteúdo canônico em pt-BR;
- hash SHA-256 do manifesto normalizado;
- contagens esperadas por model.

O loader localizará registros pela chave natural estável, aplicará o conteúdo
canônico, marcará o registro como ativo quando o model possuir esse campo,
executará `full_clean()` e persistirá somente após validação. Alterações manuais
em registros do namespace gerenciado serão substituídas no próximo deploy.
Registros externos ao namespace não serão alterados, desativados ou apagados.

## 7. Arquitetura do bootstrap

Um comando orquestrador de produção executará, em ordem:

1. validar manifestos, hashes, namespaces e dependências;
2. carregar referências oficiais versionadas;
3. carregar os catálogos cosméticos do app `auxiliary`;
4. carregar unidades e categorias de `masters`;
5. carregar os catálogos seguros dos demais domínios;
6. validar contagens, relacionamentos e exclusões;
7. construir o corpus funcional no PostgreSQL;
8. validar a cobertura funcional do corpus;
9. publicar uma nova geração vetorial ou validar o modo local;
10. registrar o resultado do bootstrap.

As etapas relacionais de catálogos serão executadas em uma transação atômica.
A construção do corpus será validada integralmente antes de ser considerada
publicável. Operações externas de embeddings e Redis ocorrerão fora da
transação longa do catálogo.

O comando aceitará o SHA do release e recusará identificador vazio, duplicado
com manifesto divergente ou incompatível com a versão declarada.

## 8. Corpus funcional da IA

### 8.1 Fonte autorizada

O corpus será gerado exclusivamente a partir de:

- registry real de módulos, recursos, campos, inlines, ações e permissões;
- documentação funcional e de arquitetura versionada;
- guias passo a passo revisados;
- URLs públicas e metadados do release.

Não serão ingeridos `.env`, credenciais, logs, dumps, arquivos privados, dados
pessoais, registros operacionais ou o código-fonte integral.

### 8.2 Conteúdo mínimo por funcionalidade

Cada recurso registrado deverá possuir:

- finalidade e contexto de uso;
- caminho de menu e URL;
- permissão de consulta e permissões das ações;
- pré-requisitos e dependências;
- campos de lista, detalhe e cadastro;
- relacionamentos e itens vinculados;
- procedimento passo a passo;
- ações e transições de estado;
- validações relevantes;
- erros comuns e orientação segura;
- limitações e operações sujeitas a aprovação.

Recursos somente leitura serão identificados explicitamente. A documentação
não prometerá ações inexistentes na interface.

### 8.3 Cobertura obrigatória

Um manifesto de cobertura será calculado a partir do registry. O gate exigirá
100% dos módulos, recursos e ações registrados. Recurso sem guia, ação sem
descrição, URL órfã, permissão divergente ou documento sem conteúdo impedirá o
bootstrap.

Cada chunk conterá módulo, recurso, ação quando aplicável, permissões, versão
do release, hash do conteúdo, idioma `pt-BR`, tipo de fonte e URL pública.

### 8.4 Resposta ao usuário

O assistente continuará somente leitura. As respostas:

- serão em português do Brasil;
- usarão apenas contexto elegível recuperado;
- apresentarão citações para os trechos utilizados;
- informarão quando não houver contexto validado suficiente;
- não criarão ou modificarão registros;
- não inventarão menus, campos, permissões ou procedimentos.

## 9. Indexação e modos de operação

### 9.1 Modo vetorial

Quando `RAG_CHAT_LOCAL_ONLY=false`, `OPENAI_API_KEY`, Redis de conhecimento,
modelo e dimensões de embedding serão obrigatórios. O bootstrap gerará uma
nova `KnowledgeIndexGeneration`, gravará chunks, manifesto e vetores em um
índice isolado e somente então trocará o alias ativo.

Falha durante embeddings, escrita, manifesto ou ativação manterá o índice
anterior ativo e marcará a nova geração como falha sem publicar conteúdo
parcial.

### 9.2 Modo local

Quando `RAG_CHAT_LOCAL_ONLY=true`, o bootstrap não exigirá embeddings. Ele
executará perguntas representativas contra a recuperação PostgreSQL e falhará
se não houver contexto elegível, resposta segura ou citações coerentes.

## 10. Fluxo de deploy

O script de deploy executará:

1. validação do host, `.env`, Compose e checkout;
2. criação e validação do backup obrigatório;
3. promoção do SHA aprovado por fast-forward;
4. retirada temporária do Cloudflare Tunnel;
5. build e inicialização da infraestrutura e aplicação;
6. migrations sob advisory lock;
7. bootstrap de catálogos, corpus e índice;
8. `check --deploy` e smoke tests pela origem local;
9. inicialização do Cloudflare Tunnel;
10. health checks público e interno;
11. registro do SHA e do diretório de backup.

O domínio público não será reaberto enquanto o bootstrap estiver incompleto.

## 11. Tratamento de falhas e rollback

- manifesto ou catálogo inválido: nenhuma alteração relacional do lote será
  confirmada;
- fonte versionada incompleta: o deploy falhará antes da carga;
- documentação ausente: o corpus novo não será considerado pronto;
- falha vetorial: o índice ativo anterior será preservado;
- falha do modo local: o deploy será interrompido;
- falha antes da publicação pública: o código anterior será reimplantado;
- banco e mídia não serão restaurados automaticamente;
- os artefatos de backup e o log do bootstrap serão preservados;
- mensagens e logs não conterão segredos nem respostas integrais do provedor.

Os upserts de referência serão compatíveis com reexecução e rollback de
código. Mudanças destrutivas de schema ou dados não fazem parte deste escopo.

## 12. Auditoria e observabilidade

Cada execução registrará:

- SHA e identificador do release;
- operador e timestamps;
- versões e hashes dos catálogos;
- contagens criadas, atualizadas e inalteradas por model;
- cobertura de módulos, recursos e ações;
- quantidade de documentos e chunks;
- modo da IA;
- geração e manifesto do índice, quando aplicável;
- resultado, duração e erro seguro.

A reexecução do mesmo SHA e mesmos manifestos deverá produzir as mesmas
contagens finais e não duplicar registros.

## 13. Segurança e conformidade

- somente fontes explicitamente autorizadas poderão compor o corpus;
- a IA não terá ferramentas mutáveis nem SQL arbitrário;
- permissões de uso do chat continuarão aplicadas no servidor;
- sessões e histórico permanecerão isolados por usuário;
- nenhum segredo será interpolado em mensagens de erro;
- snapshots oficiais terão proveniência e data de referência;
- alterações nos catálogos gerenciados serão rastreáveis pelo release;
- nenhum dado sintético será apresentado como registro industrial real;
- o desenho preserva integridade de dados, ALCOA+, GAMP 5 e práticas de
  validação compatíveis com o contexto GxP do ERP.

## 14. Estratégia de testes

### 14.1 Catálogos

- criação de amostras e relacionamentos representativos;
- pt-BR e acentuação nos campos visíveis;
- validação de unidade, símbolo, fonte e versão;
- idempotência em duas execuções;
- atualização do namespace reservado;
- preservação de registros do usuário;
- rollback integral diante de item inválido;
- ausência de escrita nos models excluídos;
- hashes e contagens dos manifestos.

### 14.2 Conhecimento

- cobertura de todos os módulos, recursos e ações;
- falha diante de guia ausente ou divergente;
- exclusão de segredos e fontes inelegíveis;
- chunks com metadados e hash do release;
- reconstrução idempotente do corpus;
- respostas pt-BR com citações;
- resposta segura sem contexto suficiente.

### 14.3 Índice e deploy

- publicação blue-green e troca atômica do alias;
- preservação do índice anterior em falha;
- validação do fallback PostgreSQL;
- ordem obrigatória das etapas do deploy;
- Cloudflare indisponível durante o bootstrap;
- falha fechada nos modos incompatíveis;
- Compose renderizado com o serviço de bootstrap;
- reexecução segura do release.

Os testes de integração usarão PostgreSQL e Redis isolados. Chamadas à OpenAI
serão simuladas nos testes automatizados; um smoke real será executado somente
no ambiente autorizado com credencial válida.

## 15. Critérios de aceitação

- `manage.py check --deploy` sem problemas;
- nenhuma migration pendente;
- testes focados de catálogos, conhecimento e deploy passando em PostgreSQL;
- 100% dos módulos, recursos e ações do registry cobertos pelo corpus;
- perguntas representativas por domínio respondidas em pt-BR com citação;
- Compose válido e bootstrap repetível;
- ausência de dados operacionais ou GxP sintéticos;
- deploy bloqueado diante de catálogo incompleto, corpus incompleto ou modo de
  IA incompatível;
- documentação técnica, funcional e operacional atualizada;
- domínio público reaberto somente após o aceite local.

## 16. Referências técnicas

- Django 6, comandos de gestão e checks:
  `https://docs.djangoproject.com/en/6.0/howto/custom-management-commands/` e
  `https://docs.djangoproject.com/en/6.0/ref/checks/`;
- OpenAI, recuperação semântica por embeddings:
  `https://developers.openai.com/api/docs/guides/embeddings`;
- documentação de arquitetura do projeto em `docs/architecture/`;
- registry funcional em `base/ui/registry.py`.
