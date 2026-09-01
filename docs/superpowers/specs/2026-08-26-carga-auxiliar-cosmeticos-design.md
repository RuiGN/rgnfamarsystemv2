# Carga de Dados Auxiliares para Indústria Cosmética — Design

## Objetivo

Preencher exclusivamente as tabelas do app `auxiliary` com referências
oficiais e cadastros operacionais em português do Brasil adequados a uma
indústria de cosméticos. A carga deve ser segura para reexecução, preservar os
registros existentes e não criar dados em outros módulos do ERP.

## Escopo

Serão preenchidos:

- `Country`, `StateProvince`, `City` e `Currency` com referências oficiais;
- `BusinessArea`, `BusinessProcess`, `Department` e `OrganizationalRole` com
  uma estrutura organizacional cosmética curada;
- `CommercialTerm` com condições usuais de pagamento e entrega;
- `SystemModule` e `SystemModel` a partir do catálogo e dos models realmente
  instalados no projeto;
- `ImpactLevel`, `CatalogType` e `CatalogValue` com classificações operacionais
  em português.

Nenhum registro será criado em `masters`, `formulations`, `production`,
`inventory`, `quality` ou qualquer outro app.

## Fontes oficiais

O comando existente `load_official_reference_data` continuará sendo a fonte
para:

- países: API de Localidades do IBGE;
- 27 unidades federativas: API de Localidades do IBGE;
- municípios brasileiros: API de Localidades do IBGE;
- moedas vigentes: lista ISO 4217 publicada pela SIX.

Os nomes das moedas serão apresentados em português do Brasil por meio do
catálogo CLDR fornecido por Babel, mantendo código alfabético, código numérico,
casas decimais, símbolo conhecido e a referência à fonte ISO na descrição.
A carga validará cardinalidades mínimas antes de gravar e será atômica.

## Catálogo cosmético curado

### Áreas e departamentos

As áreas cobrirão: Direção Técnica, Pesquisa e Desenvolvimento, Produção,
Controle da Qualidade, Garantia da Qualidade, Assuntos Regulatórios, Suprimentos,
Armazenagem e Logística, Comercial, Financeiro, Recursos Humanos, Engenharia e
Manutenção, Meio Ambiente/Saúde/Segurança e Tecnologia da Informação.

Os departamentos serão vinculados às respectivas áreas e incluirão estruturas
típicas como Desenvolvimento de Formulações, Microbiologia, Físico-Químico,
Validação, Fabricação, Envase, Embalagem, Qualificação de Fornecedores,
Farmacovigilância/Cosmetovigilância e SAC.

### Processos

Serão cadastrados processos como desenvolvimento e transferência de fórmula,
qualificação de matérias-primas e materiais de embalagem, pesagem, fabricação,
envase, embalagem, controle microbiológico e físico-químico, liberação de lote,
gestão de desvios, CAPA, mudanças, reclamações, cosmetovigilância, recolhimento,
compras, recebimento, armazenagem e expedição.

### Funções organizacionais

Serão incluídas funções sem vínculo com pessoas reais: Gerente e Analista de
Garantia da Qualidade, Gerente e Analista de Controle da
Qualidade, Formulador Cosmético, Microbiologista, Supervisor de Produção,
Operador de Fabricação, Operador de Envase, Inspetor de Embalagem, Analista de
Assuntos Regulatórios, Comprador, Almoxarife, Planejador de Produção, Técnico de
Manutenção, Analista de SAC/Cosmetovigilância e Auditor Interno.

### Condições, impactos e catálogos

- pagamento: à vista e prazos de 7, 14, 21, 28, 30, 45, 60 e 90 dias;
- entrega: retirada, CIF e FOB, com descrições operacionais sem substituir o
  Incoterm pactuado no documento comercial;
- impacto: níveis Baixo, Médio, Alto e Crítico para severidade, criticidade,
  prioridade e risco, com pesos crescentes e cores compatíveis com a UI;
- catálogos: tipo de material cosmético, apresentação, origem da reclamação,
  classificação de desvio, tipo de embalagem, condição de armazenamento e
  unidade organizacional, com valores técnicos estáveis e rótulos pt-BR.

## Arquitetura da carga

Será criado o comando `load_cosmetics_auxiliary_data`. Ele usará dados
declarativos imutáveis e uma transação atômica. Cada registro curado terá um
código estável e será persistido com `update_or_create`; relações serão
resolvidas pelos mesmos códigos. Registros que não pertencem à carga não serão
apagados, desativados ou renomeados.

O comando aceitará `--with-official-references` para executar primeiro a carga
IBGE/ISO. A execução solicitada usará essa opção. Falha na obtenção ou validação
das fontes oficiais interromperá a operação antes da carga cosmética, evitando
que o operador interprete uma base parcial como completa.

## Integridade e conformidade

- códigos e valores técnicos serão estáveis, sem nomes de empresas ou pessoas;
- descrições deixarão clara a finalidade operacional dos cadastros;
- `full_clean()` será executado antes da persistência;
- chaves estrangeiras obrigatórias serão resolvidas antes de criar dependentes;
- nenhuma trilha operacional, lote, documento ou evidência GxP será fabricada;
- reexecuções produzirão as mesmas contagens e atualizarão apenas o conjunto
  gerenciado pelo comando.

## Testes e verificação

Os testes automatizados comprovarão:

1. criação dos registros representativos e vínculos corretos;
2. idempotência em duas execuções consecutivas;
3. preservação de registros preexistentes fora do conjunto curado;
4. ausência de escrita em apps não auxiliares;
5. tradução pt-BR dos nomes de moedas oficiais;
6. rollback integral diante de um registro inválido;
7. `manage.py check` e ausência de migrations novas.

Após a execução no banco local, serão reportadas as contagens por tabela e
amostras dos registros inseridos. A aplicação deverá continuar respondendo em
`http://127.0.0.1:8000/`.
