# Performance e escalabilidade

Execute `python manage.py check_performance --fail-on-error` para verificar
política de conexões, cache, paginação e configuração explícita de DEBUG. O
comando é um gate de configuração; testes de carga devem ser executados em
ambiente isolado com dados não produtivos.
