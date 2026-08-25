# Observabilidade SRE

Execute `python manage.py check_sre_health --fail-on-error` para verificar
cache, broker Celery, backend de resultados e logging. O comando é um health
report de configuração; métricas de infraestrutura devem ser coletadas pelo
orquestrador autorizado.
