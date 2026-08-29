# Identificadores automáticos atômicos

## Contexto

O sistema possui dois geradores em `base/sequences.py`: códigos globais no
formato `PREFIX-NNNN` e identificadores diários no formato
`PREFIX-AAAAMMDD-NNNN`. Os dois consultam os registros existentes antes de
salvar o próximo valor, o que permite colisões entre requisições concorrentes.
O gerador diário também usa a quantidade de registros e pode reutilizar um
número quando existe uma lacuna.

A interface já trata os campos automáticos como somente leitura, mas a fonte
de verdade dos identificadores operacionais ainda é um mapa separado em
`base/automatic_fields.py`.

## Objetivo

Centralizar e tornar atômica a alocação dos números automáticos, preservar os
formatos públicos existentes, impedir reutilização após exclusões normais e
declarar os metadados de cada identificador no próprio modelo.

## Decisões de design

### Contador persistente

O app `base` receberá o modelo `IdentifierSequence`, identificado por um
namespace textual único e contendo o último valor alocado. A atualização será
executada dentro de `transaction.atomic()` com bloqueio de linha por
`select_for_update()`.

Na primeira utilização de um namespace, o contador será inicializado com o
maior sufixo já existente no modelo. Isso permite implantar a funcionalidade
em bancos que já possuem dados sem reiniciar a numeração.

Os namespaces terão estes formatos:

- global: `app.Model:campo:global`;
- diário: `app.Model:campo:AAAAMMDD`.

O contador nunca será reduzido por exclusões de registros. Lacunas serão
aceitas e números cancelados não serão reaproveitados no fluxo normal.

### Metadados declarativos

`IdentifierSpec` descreverá campo, prefixo, largura, escopo temporal,
imutabilidade e gatilho de geração. Modelos com identificadores operacionais
declararão `AUTOMATIC_IDENTIFIERS` no próprio corpo da classe.

`automatic_generated_fields()` passará a consultar essa declaração, além do
`CODE_PREFIX` já usado por `AutoCodeMixin`. O certificado de treinamento será
declarado com gatilho `approval`, enquanto os demais identificadores serão
gerados na criação.

### Compatibilidade

As funções públicas `generate_code()` e `sequence_code()` serão preservadas
para evitar uma migração invasiva de todos os métodos `save()` nesta entrega.
Internamente, ambas usarão o mesmo alocador atômico. Os formatos externos e os
prefixos atuais não serão alterados.

Quando o mixin gerar `code` durante um `save(update_fields=...)`, o campo será
adicionado a `update_fields`. Operações `bulk_create()` continuarão fora do
contrato e serão documentadas como não suportadas para modelos com
identificadores automáticos.

### Integridade do certificado

`TrainingEnrollment.certificate_number` receberá uma `UniqueConstraint`
condicional, aplicada somente quando o valor não for vazio. Uma operação de
migração verificará duplicidades existentes antes de criar a constraint e
interromperá a migração com uma mensagem explícita se houver inconsistência.

### Erros e limites

O gerador validará o nome do campo, prefixo, largura e `max_length`. Se o valor
formatado não couber no campo, lançará uma exceção de configuração com contexto
do modelo e do campo, em vez de retornar um valor inválido.

## Testes

Os testes devem cobrir:

1. bootstrap a partir do maior código existente;
2. continuidade após exclusão do maior registro;
3. namespaces independentes para códigos globais e diários;
4. persistência do código com `update_fields`;
5. rejeição de código que ultrapasse `max_length`;
6. metadados declarativos consumidos pela UI, admin e serializers;
7. unicidade condicional do certificado;
8. duas alocações concorrentes no PostgreSQL;
9. compatibilidade com os testes atuais.

## Critérios de aceitação

- Nenhum gerador usa `count() + 1` ou varredura completa após o bootstrap.
- Duas transações PostgreSQL não recebem o mesmo número no mesmo namespace.
- Exclusões não fazem o contador voltar.
- Os formatos públicos atuais permanecem inalterados.
- O certificado não pode ser duplicado quando preenchido.
- Campos automáticos continuam somente leitura em formulário, API e admin.
- Migrations, `manage.py check` e testes relevantes passam.

## Fora de escopo

- Tornar a sequência estritamente sem lacunas.
- Gerar identificadores por `bulk_create()` ou SQL externo.
- Alterar os prefixos ou formatos exibidos aos usuários.
- Criar uma interface administrativa para editar contadores.
