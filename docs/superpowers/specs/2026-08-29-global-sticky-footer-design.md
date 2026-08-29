# Rodapé global no fim da viewport

## Contexto

O rodapé do sistema existe diretamente em `templates/base.html`, enquanto a
tela de login possui um documento HTML independente e não apresenta rodapé. O
layout atual mantém o rodapé no fluxo do documento, mas páginas com pouco
conteúdo podem deixá-lo acima do limite inferior da viewport.

Além disso, o rodapé autenticado exibe os links sem destino “Ajuda”, “Termos” e
“Privacidade”. Esses itens devem ser removidos da experiência.

## Objetivo

Exibir um rodapé consistente em todas as telas do sistema, inclusive no login,
mantendo-o no fim da viewport quando o conteúdo for curto e após o conteúdo
quando a página for longa, sem sobreposição.

## Decisões de design

### Componente compartilhado

O conteúdo do rodapé será extraído para `templates/includes/footer.html`. O
template-base autenticado e o template de login incluirão esse mesmo
componente, eliminando duplicação e garantindo que futuras alterações sejam
aplicadas de forma uniforme.

O componente exibirá somente:

- “Direitos autorais © [ano atual] RGN Farma System”;
- “Versão 1.0”.

Os textos e links “Ajuda”, “Termos” e “Privacidade” não farão parte do HTML
renderizado.

### Comportamento de layout

O rodapé adotará o padrão de sticky footer baseado em Flexbox:

- o contêiner vertical ocupará, no mínimo, a altura disponível da viewport;
- a área de conteúdo poderá crescer para preencher o espaço livre;
- o rodapé permanecerá no fluxo normal do documento;
- não serão usados `position: fixed`, deslocamentos `bottom` ou compensações de
  conteúdo destinadas a evitar sobreposição;
- em páginas longas, a rolagem levará naturalmente ao rodapé após o conteúdo.

No layout autenticado, a solução respeitará a altura e o deslocamento do
cabeçalho Duralux e continuará compatível com os estados normal, menu reduzido,
tablet e celular.

No login, o documento receberá um contêiner vertical próprio. A área central de
autenticação crescerá para ocupar o espaço disponível sem forçar uma altura de
viewport que, somada ao rodapé, gere rolagem artificial.

### Responsividade e acessibilidade

Em telas maiores, copyright e versão permanecerão distribuídos nas extremidades
do rodapé. Em celulares, os dois textos poderão ser empilhados para manter
legibilidade e evitar truncamento.

O rodapé continuará sendo um elemento semântico `<footer>`. A ordem de leitura
será conteúdo seguido do rodapé. O componente continuará oculto na impressão,
preservando o comportamento atual dos documentos operacionais.

### Compatibilidade com componentes flutuantes

O rodapé não receberá `z-index` nem posicionamento sobreposto. O botão do chat
RAG continuará flutuante e acessível sem depender da altura do rodapé. Tabelas,
paginação, formulários e botões de ação permanecerão integralmente visíveis.

## Testes

Os testes automatizados devem verificar:

1. existência do include compartilhado nos templates autenticado e de login;
2. presença do copyright e da versão no componente;
3. ausência de “Ajuda”, “Termos” e “Privacidade” no rodapé renderizado;
4. uso de contêiner vertical com altura mínima de viewport e conteúdo flexível;
5. permanência do rodapé no fluxo, sem `position: fixed`;
6. comportamento responsivo no celular;
7. ocultação do rodapé na impressão;
8. respostas HTTP válidas para o login e uma página autenticada representativa.

## Critérios de aceitação

- O rodapé aparece no login e em todos os templates que estendem o
  `templates/base.html`.
- Em páginas curtas, o limite inferior do rodapé coincide com o fim da viewport.
- Em páginas longas, o rodapé aparece somente depois de todo o conteúdo.
- Nenhum conteúdo ou controle fica coberto pelo rodapé.
- “Ajuda”, “Termos” e “Privacidade” não aparecem no rodapé.
- Copyright e versão permanecem visíveis e em português.
- O layout funciona em desktop, tablet e celular.
- Os testes relevantes e a verificação do Django passam.

## Fora de escopo

- Alterar a versão exibida ou criar versionamento dinâmico.
- Criar páginas de ajuda, termos de uso ou política de privacidade.
- Redesenhar cabeçalho, sidebar, chat RAG ou conteúdo das páginas.
- Modificar o rodapé de cartões, modais, tabelas ou outros componentes locais.
