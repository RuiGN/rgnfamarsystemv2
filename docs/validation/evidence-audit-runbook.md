# Auditoria contínua de evidências

Execute `python manage.py check_evidence_audit --fail-on-error` antes de cada
revisão. O comando valida metadados obrigatórios, estado `approved`, caminho
dentro da raiz e SHA-256 do artefato. A revisão deve ser feita por pessoa
distinta do autor (`owner` e `reviewed_by`) e evidências expiradas devem ser
substituídas por nova versão, preservando o histórico.
