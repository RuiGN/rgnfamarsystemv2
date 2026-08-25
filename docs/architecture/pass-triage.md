# Triagem de `pass` no código Python

Data da triagem: 2026-07-21.

## Resumo

Foram encontrados inicialmente 205 nós `pass` por análise AST, excluindo `.venv`, `.git`, `.worktrees`, `__pycache__` e `migrations`. Durante a triagem, os 2 casos de maior prioridade em rotinas de backup/restore foram saneados com logging explícito. O saldo atual é de 203 nós `pass`.

| Categoria | Quantidade | Prioridade | Tratamento recomendado |
| --- | ---: | --- | --- |
| `serializer_validate_placeholder` | 118 | Média | Substituir progressivamente por validações explícitas de regras de negócio ou remover o método quando ele só retorna `attrs`. |
| `model_clean_placeholder` | 77 | Média | Implementar validações de domínio nos models regulados ou remover branches vazios quando a validação não existir. |
| `empty_exception_class` | 3 | Baixa | Aceitável quando a classe documenta uma exceção sem comportamento adicional. |
| `empty_view_class` | 2 | Baixa | Aceitável quando a classe só especializa herança; preferir docstring curta se permanecer. |
| `empty_admin_class` | 2 | Baixa | Aceitável quando registra admin herdando configuração comum. |
| `exception_swallow` | 0 | Alta | Casos identificados foram substituídos por logging explícito. |
| `other` | 1 | Baixa | `log_message` silencia logs do servidor OAuth local; comportamento aceitável se documentado. |

## Pontos de alta prioridade tratados

- `integrations/management/commands/decrypt_backup.py`: `OSError` ao remover arquivo criptografado restaurado agora gera `logger.warning(..., exc_info=True)`.
- `integrations/management/commands/upload_backup.py`: `OSError` ao remover arquivo criptografado temporário agora gera `logger.warning(..., exc_info=True)`.

Esses casos não quebram o fluxo principal, mas em operação regulada agora registram evidência de falha de limpeza para auditoria e investigação.

## Estratégia de saneamento

1. Tratar primeiro `exception_swallow` com logging estruturado e cobertura de teste.
2. Para `validate()` de serializers, remover métodos vazios ou implementar validações de consistência entre datas, status, responsáveis, tenant e integridade ALCOA+ quando aplicável.
3. Para `clean()` de models, priorizar módulos críticos: qualidade, QA, desvios, CAPA, regulatório, farmacovigilância e recalls.
4. Manter classes vazias de exceção/admin/view somente quando a herança for o comportamento pretendido; nesses casos, preferir docstring em vez de `pass` quando o objetivo precisar ficar explícito.
