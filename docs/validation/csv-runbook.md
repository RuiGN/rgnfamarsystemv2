# Runbook de validação CSV

A matriz `requirements-matrix.yml` relaciona requisito, framework, controle e
evidência. Execute `python manage.py check_csv_validation --fail-on-error` antes
de uma revisão formal.

As fases IQ/OQ/PQ devem registrar ambiente, pré-condições, resultado esperado,
resultado observado, autor, timestamp e SHA-256 do artefato. A matriz apoia
GAMP 5 e ALCOA+, mas não constitui certificação ANVISA nem substitui revisão
por responsável qualificado.
