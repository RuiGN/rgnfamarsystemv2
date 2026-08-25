# RAG Knowledge Chat Design

## Objetivo

Implementar um assistente RAG autenticado e multi-tenant para responder perguntas sobre o ERP farmaceutico, BPF/GMP, qualidade, regulatorio, farmacovigilancia, Farmacopeia Brasileira e normas internacionais pertinentes.

## Escopo

- Criar um app Django `knowledge` para fontes, documentos, chunks, sessoes de chat, mensagens, citacoes e auditoria.
- Ingerir fontes publicas oficiais: Anvisa, DOU, Biblioteca Digital Anvisa, ICH, PIC/S, WHO, FDA/eCFR.
- Incluir Farmacopeia Brasileira 8a edicao aprovada pela RDC Anvisa no 1.026/2026 como fonte prioritaria.
- Registrar livros comerciais protegidos, como GAMP 5, apenas como metadados e referencias, salvo permissao explicita de uso do conteudo.
- Integrar chat com OpenCode por variaveis de ambiente, sem gravar segredo no repositorio.
- Adicionar um widget flutuante de chat em todas as paginas autenticadas.

## Arquitetura

O app `knowledge` mantem o corpus regulatorio separado dos agentes de IA existentes. A recuperacao usa busca lexical em chunks, com vetor deterministico local para ranking complementar e compatibilidade com bancos sem extensoes especificas. O endpoint de chat monta contexto com citacoes, chama o provedor OpenCode quando configurado e usa fallback local auditavel quando nao houver chave ou quando o provedor falhar.

## Fontes Iniciais

- Anvisa/DOU: RDC 658/2022, RDC 972/2025, IN 134/2022, RDC 406/2020 e pagina oficial de farmacovigilancia.
- Farmacopeia Brasileira: pagina oficial da Anvisa e colecao da Biblioteca Digital Anvisa para a 8a edicao.
- ICH: Q9(R1) e Q10.
- PIC/S: PE 009-17 Part I e publicacoes oficiais.
- WHO: GMP main principles.
- FDA/eCFR: 21 CFR Part 210 e 21 CFR Part 211.

## Seguranca

- A chave de API deve ser revogada e substituida, pois foi exposta em conversa.
- O sistema usa `OPENCODE_API_KEY`, `OPENCODE_BASE_URL`, `OPENCODE_MODEL` e `OPENCODE_TIMEOUT_SECONDS`.
- O chat exige usuario autenticado e acesso ao tenant atual.
- Toda pergunta e resposta fica auditada por tenant, usuario, fontes recuperadas e status da execucao.

## Interface

O widget flutuante usa um botao discreto com icone de mensagem, painel compacto, historico de mensagens, estado de carregamento e bloco de fontes. A linguagem da interface e objetiva e operacional, adequada a um ERP regulado.

## Testes

- Models: validacao multi-tenant, deduplicacao por hash e criacao de chunks.
- Recuperacao: ranking lexical e citacoes.
- Chat API: autenticacao, isolamento por tenant, resposta com fontes e fallback local.
- UI: presenca do widget e assets no template base.
