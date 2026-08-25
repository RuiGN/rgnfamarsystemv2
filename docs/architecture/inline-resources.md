# Relações 1-N no template operacional

## Contrato

O CRUD operacional usa `InlineResourceConfig` para declarar recursos filhos no
mesmo formulário do recurso pai. A declaração informa chave estável, model
filho, campo de vínculo, campos editáveis, textos de interface e quantidade
inicial de formulários.

O helper genérico constrói os formsets com prefixos independentes e aplica os
widgets e metadados do design system. O template `app/resource_form.html` é
compartilhado por todos os módulos; não existem templates específicos por
relação.

## Integridade e permissões

- Pai e filhos são persistidos dentro de uma única `transaction.atomic()`.
- Todos os formulários são validados antes da escrita.
- Uma falha ao salvar qualquer filho reverte o pai e os demais filhos.
- Inclusão, alteração e exclusão exigem, respectivamente, as permissões Django
  `add`, `change` e `delete` do model filho.
- Recursos GxP não oferecem exclusão física no CRUD genérico; devem usar
  arquivamento, cancelamento, obsolescência ou expurgo controlado do domínio.
- Criações e alterações da UI geram `GovernanceAuditLog` com ator, alvo,
  campos alterados e contagem de mudanças nos filhos, na mesma transação.
- Campos de decisão, confirmação, conclusão e eficácia não são editáveis nos
  inlines regulados; essas transições usam os métodos e endpoints do domínio.
- Formsets de relações `OneToOneField`, como a avaliação de impacto do desvio,
  respeitam a cardinalidade máxima definida pelo Django.

## Cobertura prioritária

| Recurso pai | Recursos filhos no formulário |
| --- | --- |
| Fórmula mestre | componentes |
| Ordem de produção | consumos de material |
| Pedido de compra | itens |
| Recebimento de compra | itens |
| Documento controlado | anexos, aprovações e distribuições |
| Desvio | investigações, impacto, aprovações e evidências |
| CAPA | ações, evidências, aprovações e verificações de eficácia |
| Plano de auditoria | checklist, achados e evidências |
| Achado de auditoria | ações de acompanhamento |
| Risco | avaliações, controles, mitigações, revisões e alertas |
| Dossiê regulatório | registros, petições, exigências, evidências e compromissos |
| Caso de farmacovigilância | classificações, causalidade, investigações, ações e relatos |
| Campanha de recall | clientes impactados, comunicações e relatório de efetividade |

As ações de auditoria ficam no formulário do achado porque o vínculo de domínio
é `AuditFollowUpAction.finding`; o plano continua acessível pela relação do
achado, sem duplicação de chave estrangeira.

## Verificação

O arquivo `tests/test_formula_inline_components_ui.py` valida o inventário do
PRD, renderização e carregamento dos filhos existentes, criação, edição,
exclusão permitida, retenção GxP, rollback transacional e permissões.
