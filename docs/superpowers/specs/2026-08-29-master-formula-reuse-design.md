# Reaproveitamento de fórmula mestra

## Objetivo

Permitir que um usuário autorizado inicie uma nova fórmula mestra a partir de
uma fórmula existente, reaproveitando os dados do cabeçalho e todos os
componentes sem gravar nenhuma cópia antes da confirmação do formulário.

O fluxo deve preservar rastreabilidade, gerar um novo código somente na
gravação, sugerir a próxima versão disponível e sempre iniciar a nova fórmula
como rascunho.

## Escopo

- Adicionar o botão **Reaproveitar** à coluna **Ações** da listagem de Fórmulas
  mestras, ao lado de **Detalhe**.
- Abrir um formulário de novo registro preenchido a partir da fórmula de
  origem.
- Copiar todos os componentes da fórmula de origem para formsets novos, sem
  reutilizar chaves primárias.
- Manter `copied_from` como vínculo interno com a fórmula de origem.
- Preservar o fluxo atual de criação atômica da fórmula e de seus componentes.

Não fazem parte deste escopo a duplicação imediata no banco, alterações na API
REST, reaproveitamento em outros recursos ou mudança do modelo de dados.

## Decisões de produto

### Dados do cabeçalho

O formulário será preenchido com produto, tamanho e unidade do lote,
rendimento esperado, vigências e observações da fórmula de origem.

Os seguintes campos terão tratamento específico:

- `code`: permanecerá vazio, desabilitado e será gerado pelo mecanismo
  automático existente somente ao salvar;
- `version`: receberá a maior versão existente para o produto da origem mais
  um e permanecerá editável;
- `status`: será exibido como `draft` em controle desabilitado,
  independentemente do status da origem;
- `copied_from`: será atribuído no servidor e não será exibido nem aceito do
  POST do usuário;
- campos de aprovação, auditoria e timestamps: não serão copiados.

Se o usuário trocar o produto ou a versão antes de salvar, prevalecerão os
valores informados no formulário, desde que atendam às validações e à unicidade
de produto e versão.

### Componentes

Todos os componentes serão apresentados como novas linhas no formset, copiando:

- número da linha;
- material;
- função do componente;
- quantidade;
- unidade;
- perda esperada;
- fator de conversão;
- estado ativo/inativo.

IDs, timestamps e o vínculo com a fórmula antiga não serão copiados. Ao salvar,
as novas linhas serão vinculadas exclusivamente à nova fórmula.

## Arquitetura

### Ação na listagem

A configuração de Fórmulas mestras declarará uma rota opcional de
reaproveitamento. A listagem genérica renderizará o botão somente quando o
recurso declarar essa rota e o usuário puder criar a fórmula.

A view de reaproveitamento repetirá defensivamente as permissões. Para copiar
os componentes, o usuário também deverá poder visualizá-los e adicioná-los. Se
essas permissões não estiverem presentes, a ação não será oferecida; um acesso
direto à URL será recusado com HTTP 403.

### View dedicada

Uma rota GET/POST dedicada a Fórmulas mestras reutilizará o comportamento de
`ResourceCreateView`, sem criar uma segunda rotina de persistência.

No GET, a view:

1. recuperará a fórmula de origem pelo queryset autorizado;
2. calculará a próxima versão disponível para o produto;
3. montará o `ModelForm` de criação com os valores iniciais aprovados;
4. montará o formset de componentes com linhas iniciais sem chave primária;
5. identificará a tela como novo registro reaproveitado.

No POST, a view:

1. ignorará qualquer tentativa de enviar código, status de origem ou
   `copied_from` arbitrário;
2. validará o formulário e todos os componentes normalmente;
3. atribuirá `status=draft`, `code=''` e `copied_from=<origem>` no servidor;
4. salvará fórmula e componentes na transação atômica já usada pelo CRUD;
5. redirecionará para o detalhe da nova fórmula.

O GET nunca produzirá registros persistidos. Cancelar ou abandonar a tela não
deixará fórmulas ou componentes órfãos.

### Concorrência da versão

A próxima versão é apenas uma sugestão inicial. Na gravação, a operação deverá
serializar a validação para o produto selecionado e repetir a verificação de
unicidade de produto e versão dentro da transação. Caso outro usuário tenha
gravado a mesma versão no intervalo, o formulário retornará uma mensagem de
conflito no campo `version`, sem HTTP 500 e sem persistir componentes.

## Permissões e segurança

- A origem deve estar acessível pelo queryset autorizado da configuração do
  recurso; uma origem inexistente ou fora do escopo retorna HTTP 404.
- A ação exige `view_masterformula`, `add_masterformula`,
  `view_formulacomponent` e `add_formulacomponent`.
- O botão não substitui as verificações da view.
- `copied_from` é controlado pelo servidor para impedir falsificação de
  rastreabilidade.
- Código e status são normalizados no servidor mesmo que sejam enviados em um
  POST manipulado.

## Auditoria e integridade de dados

A criação continuará produzindo o evento `ui.resource.created` existente, com
a contagem dos componentes novos. O campo `copied_from` persistido permitirá
identificar a fórmula de origem sem modificar ou apagar o registro anterior.

O reaproveitamento não altera a fórmula de origem, não compartilha componentes
entre versões e não copia responsáveis ou timestamps de aprovação. Essas
regras preservam ALCOA+ e impedem que uma nova versão nasça implicitamente
aprovada.

## Tratamento de erros

- Origem inexistente ou não visível: HTTP 404.
- Falta de permissões de criação/cópia: HTTP 403.
- Fórmula ou componentes inválidos: formulário 200 com erros nos campos.
- Versão concorrente: erro associado a `version`, sem gravação parcial.
- Falha ao salvar qualquer componente: rollback da fórmula e de todos os
  componentes.

## Testes

Os testes automatizados devem comprovar:

1. presença do botão **Reaproveitar** na coluna Ações para usuário autorizado;
2. ausência do botão sem as permissões necessárias;
3. recusa de acesso direto sem permissão;
4. formulário GET preenchido com os dados da origem;
5. código vazio, status rascunho e próxima versão sugerida;
6. `copied_from` ausente do formulário;
7. todos os componentes copiados como linhas novas e editáveis;
8. cancelamento/GET sem qualquer persistência;
9. POST criando novo código automático e vínculo `copied_from` correto;
10. componentes novos sem reutilização de IDs;
11. rollback integral quando uma linha é inválida;
12. conflito concorrente de versão tratado como erro de formulário;
13. origem e seus componentes permanecendo inalterados.

Também serão executados `manage.py check`, verificação de migrations, suíte de
formulários de fórmulas e validação real no navegador da listagem e do
formulário reaproveitado.

## Critérios de aceitação

- A listagem autorizada exibe **Reaproveitar** em cada fórmula mestra.
- O botão abre um novo registro sem gravá-lo antecipadamente.
- Cabeçalho e todos os componentes são preenchidos conforme a origem.
- A versão inicial é a próxima disponível e pode ser ajustada.
- O status inicial é Rascunho e o código é gerado somente ao salvar.
- A nova fórmula registra a origem em `copied_from` sem expor o campo ao
  usuário.
- Fórmula e componentes são gravados atomicamente.
- Permissões, validações, auditoria e concorrência não podem ser contornadas
  por acesso direto ou POST manipulado.
