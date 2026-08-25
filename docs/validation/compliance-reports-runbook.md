# Relatórios de conformidade

Execute `python manage.py generate_compliance_report --format markdown` ou
`--format json --output evidence/report.json`. Use `--framework` e `--status`
para recortes operacionais. Cada relatório contém timestamp e SHA-256; preserve
o arquivo como evidência auxiliar de auditoria.
