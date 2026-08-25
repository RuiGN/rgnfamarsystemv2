# Release 1.0 e suporte

Execute `python manage.py check_release_1 --release-version 1.0.0 --fail-on-error`
antes do encerramento. Incidentes devem registrar severidade, impacto,
responsável, evidência, comunicação e resolução. O rollback usa a última tag
aprovada e repete healthchecks, backup/restore e smoke tests.
