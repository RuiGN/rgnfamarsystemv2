# Bootstrap Cosmético e Assistentes Funcional e Regulatório — Design

## 1. Contexto

O RGN Farma System já possui carga auxiliar cosmética, modelos de cadastros
mestres, geração de manual funcional, ingestão de documentos e publicação de
índice semântico. Em produção, porém, os catálogos, o corpus e as gerações de
índice ainda estão vazios. O chat atual é restrito ao manual do sistema e
rejeita deliberadamente fontes regulatórias.

Este desenho complementa o documento
`2026-08-31-bootstrap-producao-cosmeticos-rag-design.md`. Ele registra a decisão
de disponibilizar dois modos independentes no mesmo chat e inclui o corpus
regulatório federal aplicável à indústria brasileira de produtos de higiene
pessoal, cosméticos e perfumes.

## 2. Objetivos

- carregar dados oficiais e cadastros mestres comuns da indústria cosmética em
  português do Brasil;
- preservar registros empresariais e dados operacionais existentes;
- documentar todas as funcionalidades expostas pelo release;
- disponibilizar um modo de ajuda funcional e outro de conformidade
  regulatória, ambos somente leitura e com citações;
- versionar fontes, vigência, hashes e data de corte do corpus;
- impedir a publicação de um release com bootstrap incompleto;
- implantar com backup verificado, rollback e evidência interna e pública.

## 3. Decisões aprovadas

- O mesmo componente de chat oferecerá os modos `Ajuda do Sistema` e
  `Conformidade Regulatória`.
- Cada modo usará fontes, filtros de elegibilidade, prompts e índices
  independentes.
- O modo funcional não interpretará legislação.
- O modo regulatório não afirmará que uma exigência legal é uma funcionalidade
  existente do ERP.
- As respostas serão em português do Brasil, somente leitura e fundamentadas
  nos chunks citados.
- O corpus regulatório será composto apenas por fontes oficiais federais ou
  referências técnicas licenciadas apenas como metadados.
- O escopo de vigência terá data de corte explícita: 2 de setembro de 2026.
- Alterações normativas posteriores exigirão novo snapshot revisado e novo
  release; o deploy não consultará a internet.
- Não haverá fine-tuning automático nem indexação irrestrita do código-fonte.
- Não serão criados dados operacionais, usuários ou dados demonstrativos.

## 4. Arquitetura dos modos de IA

### 4.1 Ajuda do Sistema

O modo funcional recuperará exclusivamente documentos elegíveis do manual do
ERP. O corpus será derivado do registry efetivo da interface e da documentação
versionada. O gate exigirá cobertura de 100% dos módulos, recursos e ações
registrados, incluindo finalidade, caminho, permissões, campos, estados,
pré-requisitos, validações, limitações e procedimento passo a passo.

Quando não houver instrução validada, o assistente informará a limitação. Ele
não inventará menus, permissões ou ações e não consultará o corpus regulatório.

### 4.2 Conformidade Regulatória

O modo regulatório recuperará exclusivamente documentos oficiais elegíveis e
vigentes no snapshot. Cada fonte registrará código, título, órgão emissor,
jurisdição, tipo, publicação, início de vigência, situação, normas relacionadas,
URL oficial, data da última verificação, hash e data de corte.

As respostas distinguirão obrigação normativa, orientação não vinculante e
referência técnica. Toda resposta apresentará citações e um aviso conciso de
que o conteúdo auxilia a consulta, mas não substitui a avaliação do responsável
técnico, regulatório ou jurídico. Quando a fonte não permitir conclusão segura,
o assistente informará a insuficiência em vez de inferir.

### 4.3 Isolamento

O modo escolhido será validado no servidor. O cliente não poderá selecionar um
filtro arbitrário nem misturar tipos de fonte. Histórico, recuperação,
montagem do prompt e resposta manterão o modo da sessão. Documentos inativos,
substituídos, sem vigência confirmada ou fora da data de corte não serão
elegíveis para respostas normativas correntes.

## 5. Escopo regulatório

O inventário cobrirá atos federais e orientações oficiais diretamente
relacionados à fabricação, regularização e pós-mercado de cosméticos, incluindo:

- boas práticas de fabricação e habilitação sanitária;
- regularização, registro, notificação, rotulagem e composição em português;
- controle microbiológico e requisitos de segurança;
- listas de substâncias proibidas, restritas, conservantes, corantes, filtros
  ultravioletas e ativos específicos;
- produtos sujeitos a requisitos específicos, como protetores solares,
  repelentes, alisantes, produtos infantis e bronzeadores;
- cosmetovigilância, eventos adversos, investigação e comunicação;
- fabricação para exportação e regras federais especiais aplicáveis;
- legislação federal superveniente diretamente relacionada ao setor, inclusive
  produção artesanal e uso de animais em testes, quando regulamentada e
  vigente na data de corte;
- notas técnicas, perguntas e respostas, manuais e guias oficiais, sempre
  identificados como orientação não normativa quando for o caso.

A linha de base incluirá a verificação das RDCs Anvisa nº 48/2013, 752/2022,
646/2022 e alterações, 894/2024, 907/2024, 1.029/2026 e 1.030/2026, além dos
atos relacionados identificados no inventário oficial. A lista final não será
inferida apenas desta enumeração: um manifesto de cobertura registrará os atos
consultados, os incluídos, os revogados ou substituídos e a justificativa de
exclusão.

Normas estaduais, municipais, ambientais, trabalhistas, tributárias e de
conselhos profissionais ficam fora do corpus inicial, salvo quando uma fonte
federal de cosméticos as incorporar expressamente. ISO 22716 e GAMP 5 serão
armazenadas apenas como referências bibliográficas e metadados, sem ingestão de
conteúdo protegido não licenciado.

## 6. Dados de referência e mestres

O bootstrap carregará, por manifestos versionados e transação atômica:

- países, unidades federativas, municípios e moedas;
- áreas, processos, departamentos, funções, condições comerciais, níveis de
  impacto e catálogos cosméticos;
- unidades de medida para massa, volume, quantidade, concentração,
  temperatura, pressão, tempo, comprimento e área;
- famílias, grupos, categorias, linhas, formas cosméticas, apresentações,
  concentrações e áreas de aplicação;
- elementos de custo, canais comerciais, competências e referências fiscais
  seguras explicitamente autorizadas.

O loader validará todo o lote antes de gravar, usará códigos estáveis de
namespace reservado, executará `full_clean()` e fará upsert idempotente.
Registros fora do namespace serão preservados integralmente.

Não serão criados produtos, matérias-primas, fórmulas, roteiros, parceiros,
plantas, armazéns, lotes, saldos, ordens, títulos, documentos GxP, usuários,
treinamentos realizados ou evidências empresariais.

## 7. Fluxo de bootstrap

Um comando orquestrador receberá o SHA do release e executará:

1. validação dos manifestos, hashes, namespaces, dependências e data de corte;
2. carga dos snapshots oficiais de localização e moeda;
3. carga dos catálogos `auxiliary`, `masters` e demais domínios autorizados;
4. validação de contagens, relacionamentos, idempotência e exclusões;
5. geração e validação de cobertura do corpus funcional;
6. ingestão e validação do corpus regulatório;
7. criação de gerações de índice isoladas por modo;
8. consultas representativas com citações;
9. ativação atômica das novas gerações;
10. registro auditável do resultado do bootstrap.

Falha relacional abortará a transação completa. Falha de ingestão ou indexação
manterá as gerações anteriores ativas. Reexecutar o mesmo SHA e os mesmos
manifestos não duplicará registros ou chunks.

## 8. Deploy e rollback

O deploy validará host, checkout, `.env`, Compose e disponibilidade dos
serviços. Antes da promoção, produzirá backup PostgreSQL e de mídia, validará
os arquivos e gravará checksums SHA-256 fora do checkout.

O fluxo de publicação será:

1. registrar SHA e gerações atualmente ativas;
2. promover `origin/main` somente por fast-forward;
3. retirar temporariamente o Cloudflare Tunnel;
4. construir e iniciar o runtime privado;
5. aplicar migrations sob lock;
6. executar o bootstrap do release;
7. executar checks e smoke tests internos;
8. iniciar o túnel;
9. verificar prontidão do túnel, origem e HTTPS público;
10. registrar SHA, contagens, gerações e diretório do backup.

Em falha, o script fechará a publicação, restaurará os aliases de índice quando
aplicável, voltará ao SHA anterior sem apagar dados, reconstruirá o runtime
anterior e somente reabrirá o túnel após a origem responder. Banco e mídia não
serão restaurados automaticamente; uma restauração destrutiva exigirá decisão
operacional explícita.

## 9. Segurança e conformidade

- `.env`, credenciais, logs privados, dumps, dados pessoais e registros
  operacionais não entrarão em nenhum corpus.
- O assistente não terá SQL arbitrário nem ferramentas mutáveis.
- Permissões de chat e isolamento de histórico continuarão aplicados no
  servidor.
- Conteúdo externo será sanitizado e tratado como dado, nunca como instrução
  para o sistema.
- Prompts e logs não incluirão segredos nem respostas integrais do provedor.
- A proveniência, o hash e a data de corte permitirão reproduzir o conhecimento
  usado em cada release.
- O corpus regulatório apoiará consulta e treinamento interno, mas não será
  apresentado como parecer jurídico ou aprovação sanitária.

## 10. Estratégia de testes

### 10.1 Catálogos

- conteúdo pt-BR, símbolos, fontes, versões e chaves oficiais;
- idempotência, atualização do namespace e preservação de registros externos;
- atomicidade diante de item inválido;
- contagens e hashes dos manifestos;
- busca negativa de escrita em models operacionais excluídos.

### 10.2 Corpus funcional

- cobertura de 100% dos módulos, recursos e ações do registry;
- falha para guia, permissão, URL ou ação ausente;
- metadados de release e citações por chunk;
- recuperação de perguntas representativas de cada módulo.

### 10.3 Corpus regulatório

- manifesto de vigência e relações de revogação/substituição;
- separação entre norma, orientação e referência protegida;
- exclusão de fonte inativa, futura, revogada ou sem confirmação;
- recuperação por tema com citação oficial e data de corte;
- recusa segura para pergunta fora do corpus ou pedido de parecer definitivo.

### 10.4 Isolamento e produção

- impossibilidade de misturar filtros funcional e regulatório;
- validação server-side do modo;
- preservação das gerações ativas em falha;
- migrations, Django checks, lint, segurança, documentação e Compose;
- backup íntegro, runtime privado, túnel, origem e domínio público.

## 11. Critérios de aceitação

- todas as tabelas de referência e mestres autorizadas possuem as contagens
  esperadas em produção;
- nenhuma tabela operacional excluída recebe dados sintéticos;
- os loaders são idempotentes e preservam cadastros externos ao namespace;
- o manual cobre 100% do registry do release;
- o manifesto regulatório cobre o inventário oficial verificado na data de
  corte e registra inclusões, substituições e exclusões;
- os dois modos respondem consultas representativas com citações coerentes e
  não cruzam seus corpora;
- migrations, testes relevantes, checks de segurança e documentação passam;
- o commit é publicado em `origin/main` sem force-push;
- o backup pré-release é íntegro;
- containers, origem, prontidão do túnel e HTTPS público estão saudáveis;
- SHA, contagens e gerações ativas do VPS correspondem ao release implantado.
