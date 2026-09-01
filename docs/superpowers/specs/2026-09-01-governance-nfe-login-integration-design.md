# Governança, importação de NF-e e login — Design

## 1. Contexto

O repositório legado `rgnfarmasystem` contém uma importação de XML de NF-e de
compras, uma apresentação mais rica para a página de login e uma configuração
explícita do formulário de parâmetros de governança. O `rgnfarmasystemv2` é o
produto de destino e representa o ERP single-instance para a indústria de
cosméticos.

Os dois projetos compartilham parte importante da arquitetura, mas não são
intercambiáveis. O legado ainda contém modelos e textos farmacêuticos que foram
retirados intencionalmente do produto de cosméticos. A integração deve,
portanto, selecionar os contratos úteis, adaptá-los ao domínio atual e reforçar
os pontos de consistência, segurança e auditoria identificados na análise.

## 2. Objetivos

- tornar os parâmetros de governança seguros e compreensíveis na interface
  operacional, sem alterar o contrato REST existente;
- importar NF-e modelo 55 autorizada para um pedido de compra aprovado,
  criando um recebimento em rascunho sem movimentar estoque;
- preservar o XML fiscal original em armazenamento protegido e auditável;
- adaptar a composição visual do login legado ao ERP de cosméticos, mantendo
  os contratos de autenticação, acessibilidade e rodapé do produto atual;
- manter o repositório legado somente como referência, sem modificá-lo.

## 3. Fora de escopo

- importar NFC-e, NFS-e, CT-e, MDF-e ou XML fiscal genérico;
- criar pedido de compra automaticamente a partir do XML;
- lançar estoque, liberar qualidade ou contabilizar a nota no momento da
  importação;
- consultar a SEFAZ ou fazer manifestação do destinatário;
- restaurar `TechnicalResponsible`, assinatura farmacêutica, farmacovigilância
  ou outras estruturas retiradas do domínio de cosméticos;
- restaurar o parâmetro legado `automatic_code_generation`;
- restaurar as rotas legadas de recuperação de senha;
- substituir os mecanismos atuais de autenticação ou limitação de tentativas.

## 4. Alternativas avaliadas

### 4.1 Cópia literal do legado

Seria a opção mais rápida, mas misturaria migrações incompatíveis, referências
farmacêuticas, CSS inline e contratos de UI que o projeto de destino já
substituiu. Também manteria fragilidades da importação, como a verificação de
duplicidade apenas na aplicação e o uso da quantidade total do pedido em vez
do saldo pendente.

### 4.2 Incorporação seletiva e reforçada — escolhida

Reutiliza o parser e a composição visual como referências, mas implementa cada
contrato sobre os modelos, migrações, permissões, armazenamento e design system
atuais. Essa abordagem preserva o domínio de cosméticos e permite reforçar
idempotência, concorrência, rastreabilidade e acessibilidade.

### 4.3 Motor fiscal genérico

Um pipeline extensível para vários documentos fiscais poderia ser útil no
futuro, mas acrescentaria abstrações e estados que não são necessários para o
fluxo confirmado: NF-e de entrada vinculada a pedido aprovado.

## 5. Parâmetros de governança

### 5.1 Contrato preservado

`GovernanceParameter` continuará sendo a autoridade de domínio. Permanecem:

- escopo, módulo e chave como identidade única;
- tipos `string`, `integer`, `decimal`, `boolean`, `json`, `days` e `choice`;
- valores e regras persistidos em `JSONField`;
- coerção, limites e escolhas validados pelo model;
- API REST atual e trilha global de auditoria.

Não será criada migração para substituir o modelo existente.

### 5.2 Formulário tipado

O registro de recursos aceitará uma classe base opcional de `ModelForm`. Um
formulário específico de governança será responsável por apresentar `value` e
`default_value` conforme `value_type`, enquanto o construtor genérico continuará
aplicando classes, acessibilidade, filtros de relacionamentos e regras comuns.

| Tipo | Controle de `value` | Valor persistido |
|---|---|---|
| `boolean` | switch | `bool` |
| `integer` | número, passo 1 | `int` |
| `days` | número, passo 1 | `int` |
| `decimal` | número decimal | string decimal canônica |
| `choice` | seleção a partir de `rules.choices` | item selecionado |
| `string` | texto | `str` |
| `json` | área de texto JSON | objeto ou lista |

O valor principal permanece obrigatório. Para booleanos, o valor padrão usará
um controle de três estados — “Não definido”, “Ativado” e “Desativado” — para
não converter silenciosamente ausência em `False`.

O tipo efetivo será obtido do POST quando o formulário estiver vinculado e da
instância na edição. Um JavaScript progressivo poderá trocar os controles ao
alterar `value_type`, mas a mesma reconstrução e validação será repetida no
servidor.

### 5.3 Interface e auditoria

O recurso declarará explicitamente os campos editáveis:

1. escopo;
2. módulo;
3. chave;
4. tipo;
5. valor;
6. valor padrão;
7. regras;
8. descrição;
9. ativo.

A listagem exibirá o valor atual depois da chave. Valores booleanos serão
apresentados em português. `updated_by` será atribuído ao usuário autenticado
no fluxo HTML, assim como já ocorre na API, sem ser um campo editável.

## 6. Importação de NF-e

### 6.1 Entrada aceita

A ação aceitará `multipart/form-data` com:

- `order_id`: pedido de compra aprovado;
- `xml`: arquivo `application/xml` ou `text/xml`, com até 10 MB.

O documento deve ser um `nfeProc` de NF-e modelo 55, conter chave de acesso de
44 dígitos e protocolo autorizado (`cStat=100`). XML sem autorização, com
DOCTYPE, entidade externa, conteúdo malformado ou estrutura incompatível será
rejeitado antes de qualquer gravação.

O parser usará `defusedxml`, localizará elementos pelo nome local para tolerar
namespaces válidos e produzirá objetos imutáveis de cabeçalho, itens e rastros.

### 6.2 Validações de negócio

Antes de criar o recebimento, o serviço validará:

- CNPJ/CPF do destinatário contra o documento ativo da instituição;
- CNPJ/CPF do emitente contra o fornecedor do pedido;
- situação aprovada do pedido;
- código de cada produto contra um item do pedido;
- unidade comercial contra a unidade do item;
- quantidade positiva;
- quantidade importada menor ou igual ao saldo ainda não recebido;
- datas de fabricação e validade e consistência do lote quando informados;
- soma dos itens e totais essenciais do documento dentro da precisão fiscal.

O pedido será bloqueado com `select_for_update()` durante a apuração do saldo.
Recebimentos cancelados não consumirão saldo; recebimentos em estados válidos
consumirão a quantidade recebida já registrada.

### 6.3 Idempotência e concorrência

`PurchaseReceipt` receberá:

- `nfe_access_key`, indexada e única quando não vazia;
- `nfe_xml_sha256`;
- referência protegida ao XML original.

A restrição condicional no PostgreSQL será a proteção final contra duas
requisições concorrentes para a mesma chave. O serviço traduzirá o
`IntegrityError` esperado para uma mensagem de negócio em português, sem
expor detalhes do banco.

### 6.4 Preservação do XML

O XML original será registrado como `ProtectedFile` do tipo documento fiscal,
origem upload, confidencialidade interna e vínculo lógico com o recebimento.
O conteúdo será armazenado com AES-256-GCM usando o mecanismo existente do
projeto. O SHA-256 do conteúdo claro ficará disponível para verificação de
integridade.

Criação do recebimento, itens, metadados e registro do arquivo ocorrerão como
uma unidade operacional. Se a gravação protegida falhar, a importação não será
apresentada como concluída e qualquer artefato de storage reservado será
compensado.

### 6.5 Resultado operacional

Uma importação válida criará:

- `PurchaseReceipt` em `DRAFT`;
- número fiscal a partir de número e série da NF-e;
- itens com produto, quantidade, preço, lote, fabricação e validade;
- quantidades aceita e rejeitada zeradas;
- status de entrada de estoque pendente;
- referência ao arquivo protegido e hash do XML;
- auditoria com usuário, pedido, recebimento e chave, sem copiar conteúdo do
  XML para logs.

Nenhum lote de estoque será criado e nenhuma etapa de qualidade será liberada
automaticamente.

### 6.6 API e interface HTML

`PurchaseReceiptViewSet` ganhará a ação de coleção `import_xml`, protegida por
`procurement.add_purchasereceipt`. A ação HTML reutilizará o catálogo atual de
ações com dois campos: pedido e arquivo XML.

O seletor de pedidos mostrará somente pedidos aprovados aos quais o usuário
tem acesso pelo contrato global da instância. Erros serão apresentados no
formulário e na API com a mesma mensagem de negócio.

## 7. Login

### 7.1 Contratos preservados

Permanecem inalterados:

- `UsernameLoginView` e autenticação por nome de usuário;
- CSRF;
- redirecionamento `next` seguro;
- redirecionamento do admin para o login único;
- limitação de tentativas por usuário e IP;
- mensagens em português;
- logo e nome configuráveis da instituição;
- rodapé global exigido pelo projeto atual.

### 7.2 Direção visual

A página atende operadores e gestores de uma indústria de cosméticos. Seu
único trabalho é permitir entrada segura no ERP; a área editorial apenas
comunica o contexto do produto sem competir com o formulário.

Paleta:

- Noite industrial: `#08162B`;
- Azul RGN: `#3454D1`;
- Ciano de rastreabilidade: `#36D6D0`;
- Superfície: `#F4F7FB`;
- Grafite: `#283C50`;
- Branco: `#FFFFFF`.

A tipografia reutilizará os ativos já presentes: peso 700 para a mensagem
principal, 600 para controles e 400 para apoio. Nenhuma fonte, biblioteca ou
recurso remoto novo será adicionado.

A assinatura visual será uma linha de rastreabilidade que conecta os processos
“Formulação”, “Produção”, “Qualidade” e “NF-e”. Ela substitui os dez cards
genéricos do legado e comunica uma propriedade real do produto.

### 7.3 Layout

```text
Desktop
┌──────────────────────────────────┬──────────────────┐
│ Logo e mensagem do ERP           │ Acesso ao sistema│
│ industrial para cosméticos       │                  │
│                                  │ Usuário          │
│ Formulação → Produção →          │ Senha            │
│ Qualidade → Rastreabilidade      │ [ Entrar ]       │
└──────────────────────────────────┴──────────────────┘
                         Rodapé institucional

Mobile
┌───────────────────────┐
│ Logo                  │
│ Acesso ao sistema     │
│ Usuário               │
│ Senha                 │
│ [ Entrar ]            │
└───────────────────────┘
│ Rodapé                │
```

Em desktop, o painel contextual ocupa o espaço flexível e o cartão de acesso
mantém largura estável. Abaixo de 992 px, o painel contextual é ocultado e o
formulário passa a ser o foco. Viewports curtos permitem rolagem sem esconder
campos ou botão.

Os estilos ficarão em um arquivo dedicado, sem bloco CSS extenso no template.
O fundo legado será copiado como ativo local. Foco por teclado será visível e
qualquer movimento decorativo será desativado sob `prefers-reduced-motion`.

## 8. Segurança e privacidade

- o parser nunca resolve entidades externas;
- XML e conteúdo fiscal não serão incluídos em logs;
- mensagens não revelarão caminhos, SQL ou detalhes internos;
- chaves, documentos e códigos serão normalizados antes de comparar;
- permissões serão verificadas tanto na interface quanto na API;
- arquivos serão acessíveis somente pelo fluxo protegido e auditado;
- o fluxo HTML continuará protegido pelo rate limit de autenticação;
- valores de governança continuarão escapados pelos templates Django.

## 9. Estratégia de testes

### Governança

- controles e coerção para todos os tipos;
- booleano principal e valor padrão triestado;
- `rules.choices` obrigatório e restritivo;
- erro reexibe o controle correspondente ao tipo submetido;
- listagem mostra o valor;
- autoria do usuário no fluxo HTML;
- API e validações atuais permanecem aprovadas.

### NF-e

- extração de cabeçalho, itens e rastros;
- rejeição de XML malicioso, grande, malformado ou não autorizado;
- rejeição de modelo diferente de 55;
- divergência de destinatário, fornecedor, produto e unidade;
- saldo parcial e soma de recebimentos anteriores;
- chave duplicada sequencial e concorrente;
- criação em rascunho sem estoque;
- conteúdo criptografado, hash e auditoria do arquivo;
- rollback e limpeza compensatória em falha de storage;
- endpoint e ação HTML multipart com permissões.

### Login

- renderização e autenticação válidas;
- erros associados aos campos e erro geral acessível;
- preservação do `next` seguro e do rate limit;
- logo institucional e fallback;
- rodapé global preservado;
- ausência de referências farmacêuticas;
- layout a 320 px, desktop e viewport móvel curto;
- foco visível e redução de movimento.

### Gates

- testes focados executados pelo ambiente PostgreSQL isolado do projeto;
- `python manage.py makemigrations --check --dry-run` pelo runner do projeto;
- `python manage.py check` pelo runner do projeto;
- busca negativa por termos farmacêuticos nos arquivos novos;
- suíte ampliada proporcional às áreas tocadas.

## 10. Critérios de aceitação

- parâmetros são editados com controles coerentes e continuam validados pelo
  model;
- a alteração HTML identifica o usuário responsável;
- uma NF-e modelo 55 autorizada e compatível cria exatamente um recebimento em
  rascunho;
- importações duplicadas ou acima do saldo são bloqueadas inclusive sob
  concorrência;
- o XML original é recuperável pelo mecanismo de arquivo protegido e seu hash
  é verificável;
- nenhum estoque é movimentado durante a importação;
- a ação está disponível na UI e na API somente para usuários autorizados;
- o login adaptado representa o ERP de cosméticos, funciona em mobile e mantém
  autenticação, rate limit, acessibilidade e rodapé;
- nenhuma estrutura farmacêutica removida retorna ao produto;
- o repositório de origem permanece sem alterações.
