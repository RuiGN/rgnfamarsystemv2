# Remoção de ícones decorativos dos campos

## Objetivo

Remover de todo o sistema os ícones usados apenas como adorno visual antes de
campos de formulário, sem afetar ícones que representam ações, estados ou
controles interativos.

## Escopo

A alteração cobre:

- formulários de recursos;
- formulários de ações;
- painel de apontamento e execução;
- formulários inline empilhados, tabulares e de controle de qualidade;
- formulário de login;
- campo de upload de avatar;
- metadados de widgets gerados pela infraestrutura central de formulários.

Continuam fora do escopo os ícones de botões, menus, alertas, indicadores,
atalhos e controles acionáveis, incluindo limpar busca, anexar arquivo, enviar
mensagem e os indicadores nativos de campos temporais.

## Desenho técnico

O contrato decorativo será removido na origem, em `base/ui/forms.py`. A
configuração de widgets deixará de calcular e publicar `field.rgn_icon` e o
atributo HTML `data-icon`. Metadados funcionais, como máscaras, placeholders,
classes Bootstrap, tipos de input e atributos de acessibilidade, permanecem
inalterados.

Os templates reutilizáveis deixarão de testar `field.field.rgn_icon` e de criar
os elementos `.resource-input-group` e `.resource-input-icon`; cada campo será
renderizado diretamente. Os wrappers vazios atualmente existentes no login e
no formulário de avatar também serão removidos.

Não será usada uma regra CSS para ocultar os ícones, pois isso manteria markup e
metadados obsoletos, além de poder preservar bordas e espaçamentos de
`input-group`.

## Testes e critérios de aceitação

Os testes deverão comprovar que:

1. widgets configurados pela infraestrutura central não recebem `data-icon` nem
   `rgn_icon`;
2. formulários de recursos não renderizam `.resource-input-icon`,
   `data-field-icon` ou ícones decorativos antes dos campos;
3. login, avatar, ações, execução e formsets não mantêm wrappers decorativos;
4. máscaras, placeholders, classes dos widgets, validação e acessibilidade
   continuam funcionando;
5. ícones funcionais de botões e controles permanecem presentes;
6. os testes de interface e as verificações Django relevantes passam.

## Compatibilidade e risco

A mudança não altera modelos, migrations, APIs nem regras de negócio. O risco
principal é uma regressão de markup em formulários compartilhados; por isso, a
implementação será guiada por testes de renderização e por uma busca estática
final por referências ao contrato removido.
