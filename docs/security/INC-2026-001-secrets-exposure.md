# INC-2026-001 — Exposição de credenciais no repositório

**Estado:** contenção técnica concluída; aprovação regulatória formal pendente
**Severidade inicial:** crítica  
**Detectado em:** 2026-07-14  
**Proprietários:** Segurança/DPO, DevSecOps e Qualidade  
**Aprovação de encerramento:** Segurança/DPO e Qualidade

## Detecção

A inspeção do repositório identificou um backup de ambiente e artefatos de automação de navegador versionados. Esses arquivos incluem classes de credenciais capazes de acessar serviços externos e infraestrutura. Valores secretos não devem ser reproduzidos neste registro.

## Intervalo de exposição

O início corresponde ao primeiro commit que introduziu cada artefato. O término somente poderá ser registrado após revogação, rotação, saneamento do histórico remoto e validação do secret scanning. Segurança deve obter as datas exatas com `git log --all -- <arquivo>` no clone de investigação preservado.

## Classes potencialmente afetadas

- OAuth e armazenamento Google;
- banco PostgreSQL e RabbitMQ;
- SMTP e notificação de erros;
- Cloudflare/túnel;
- provedores de IA;
- chaves de criptografia e backup;
- demais tokens encontrados pela varredura integral.

O inventário operacional com identificadores de segredo, proprietários e evidências de revogação deve permanecer no cofre corporativo, nunca no Git.

## Contenção

- retirar artefatos sensíveis do índice Git na branch de remediação;
- impedir nova inclusão por `.gitignore`, `.dockerignore` e Gitleaks;
- congelar publicação de novas imagens até verificar que nenhum segredo foi incorporado;
- restringir acesso ao repositório e preservar logs para investigação.

## Erradicação e recuperação

1. revogar credenciais antigas antes de ativar substitutas;
2. rotacionar chaves criptográficas com recriptografia e possibilidade de rollback controlado;
3. reescrever o histórico somente em janela aprovada e após backup forense;
4. invalidar clones, caches, artefatos e imagens que contenham o histórico anterior;
5. executar Gitleaks em todas as refs e confirmar acesso dos serviços com as novas credenciais;
6. revisar logs do período e abrir incidente LGPD/GxP adicional se houver evidência de uso indevido.

Em 2026-07-14, o proprietário do sistema confirmou a revogação/rotação das credenciais afetadas e autorizou a reescrita coordenada do histórico. Os identificadores das evidências externas ainda devem ser anexados ao registro corporativo antes do encerramento do incidente.

Na mesma data, o proprietário aprovou o avanço das atividades técnicas. Essa autorização não substitui os identificadores de evidência nem as aprovações formais de Segurança/DPO e Qualidade exigidas para encerrar G0.

## Avaliação de impacto GxP e LGPD

Até a conclusão da análise de logs, não é possível excluir acesso indevido a dados pessoais ou registros regulados. Qualidade deve avaliar impacto sobre integridade, disponibilidade, autoria, confidencialidade, trilhas de auditoria e resultados emitidos durante o intervalo de exposição.

## CAPA preventiva

- secret scanning obrigatório em pre-commit e CI;
- proteção de push no servidor Git;
- credenciais de curta duração e menor privilégio;
- uso exclusivo de secret manager/orchestrator secrets;
- revisão trimestral de acessos e inventário;
- treinamento anual de desenvolvimento seguro;
- teste automatizado que rejeita artefatos sensíveis rastreados.

## Evidências para encerramento

- inventário externo com 100% das credenciais revogadas/rotacionadas;
- relatório de análise de logs aprovado;
- histórico remoto saneado e comunicado aos colaboradores;
- Gitleaks sem achados não justificados em todas as refs;
- pipeline com proteção de segredo ativa;
- avaliação GxP/LGPD e CAPA aprovadas;
- teste `tests/test_secret_hygiene.py` aprovado.

## Aprovações

O incidente permanece aberto até que Segurança/DPO e Qualidade registrem aprovação no sistema corporativo de incidentes. Aprovação não deve ser simulada por edição deste arquivo.
