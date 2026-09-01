import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from django.conf import settings


class BackupRestoreCheckStatus(str, Enum):
    # Bandit B105: readiness status, not a password.
    PASS = 'pass'  # nosec B105
    FAIL = 'fail'
    WARNING = 'warning'


@dataclass(frozen=True)
class BackupRestoreCheck:
    code: str
    title: str
    status: BackupRestoreCheckStatus
    evidence: str

    def to_dict(self):
        return {
            'code': self.code,
            'title': self.title,
            'status': self.status.value,
            'evidence': self.evidence,
        }


@dataclass(frozen=True)
class BackupRestoreReadinessReport:
    checks: tuple[BackupRestoreCheck, ...]

    @property
    def passed(self):
        return all(check.status == BackupRestoreCheckStatus.PASS for check in self.checks)

    def to_dict(self):
        return {
            'passed': self.passed,
            'checks': [check.to_dict() for check in self.checks],
        }

    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def evaluate_backup_restore_readiness(project_root=None):
    root = Path(project_root or settings.BASE_DIR)
    backup_script = _read(root / 'scripts' / 'backup.sh')
    restore_path = root / 'scripts' / 'restore.sh'
    restore_script = _read(restore_path)
    restore_media_helper = _read(root / 'scripts' / 'restore_media.py')
    backup_scheduler_script = _read(root / 'scripts' / 'backup_scheduler.sh')
    deployment_docs = _read(root / 'docs' / 'deployment.md')
    backup_restore_docs = _read(root / 'docs' / 'architecture' / 'backup-restore.md')
    mkdocs_source = _read(root / 'mkdocs.yml')
    vps_compose = _read(root / 'docker-compose.vps.yml')
    env_example = _read(root / '.env.example')
    scan_source = '\n'.join(
        [
            backup_script,
            restore_script,
            backup_scheduler_script,
            deployment_docs,
            backup_restore_docs,
            vps_compose,
            env_example,
        ]
    )

    checks = [
        _check(
            'backup.postgres_dump_gzip',
            'Backup PostgreSQL compactado',
            'pg_dump' in backup_script
            and 'gzip >' in backup_script
            and 'postgres-${TIMESTAMP}.sql.gz' in backup_script,
            'scripts/backup.sh gera postgres-${TIMESTAMP}.sql.gz com pg_dump e gzip.',
            'scripts/backup.sh nao comprova dump PostgreSQL compactado.',
        ),
        _check(
            'backup.media_archive',
            'Backup de media',
            'tar -czf - /app/media' in backup_script
            and 'media-${TIMESTAMP}.tar.gz' in backup_script,
            'scripts/backup.sh arquiva /app/media em media-${TIMESTAMP}.tar.gz.',
            'scripts/backup.sh nao comprova backup de media.',
        ),
        _check(
            'backup.retention_rotation',
            'Rotacao por retencao',
            'RETENTION_DAYS' in backup_script
            and 'find "$BACKUP_DIR"' in backup_script
            and '-mtime "+${RETENTION_DAYS}" -delete' in backup_script,
            'scripts/backup.sh remove arquivos acima de RETENTION_DAYS.',
            'scripts/backup.sh nao comprova rotacao por tempo.',
        ),
        _check(
            'restore.script_exists',
            'Script de restauracao',
            restore_path.exists()
            and restore_script.startswith('#!/usr/bin/env bash')
            and 'set -euo pipefail' in restore_script,
            'scripts/restore.sh existe, usa bash e set -euo pipefail.',
            'scripts/restore.sh esta ausente ou nao e defensivo.',
        ),
        _check(
            'restore.requires_explicit_artifact',
            'Artefato explicito para restauracao',
            '--postgres' in restore_script
            and '--media' in restore_script
            and 'if [[ -z "$POSTGRES_BACKUP" && -z "$MEDIA_BACKUP" ]]' in restore_script,
            'scripts/restore.sh exige --postgres e/ou --media antes de restaurar.',
            'scripts/restore.sh nao exige artefato explicito de restauracao.',
        ),
        _check(
            'restore.requires_confirmation',
            'Confirmacao explicita para restore',
            '--yes' in restore_script
            and 'YES="true"' in restore_script
            and '"$YES" != "true"' in restore_script,
            'scripts/restore.sh bloqueia execucao destrutiva sem --yes.',
            'scripts/restore.sh nao comprova confirmacao explicita.',
        ),
        _check(
            'restore.supports_dry_run',
            'Dry-run de restauracao',
            '--dry-run' in restore_script
            and 'DRY_RUN="true"' in restore_script
            and 'DRY-RUN:' in restore_script,
            'scripts/restore.sh suporta --dry-run sem executar alteracoes.',
            'scripts/restore.sh nao comprova dry-run.',
        ),
        _check(
            'restore.pre_restore_backup',
            'Backup antes de restaurar',
            'pre-restore' in restore_script
            and 'scripts/backup.sh' in restore_script
            and 'BACKUP_SCRIPT' in restore_script,
            'scripts/restore.sh executa scripts/backup.sh em diretorio pre-restore antes da restauracao.',
            'scripts/restore.sh nao comprova backup pre-restore.',
        ),
        _check(
            'restore.postgres_restore',
            'Restore PostgreSQL',
            'gunzip -c' in restore_script
            and 'psql -v ON_ERROR_STOP=1' in restore_script
            and 'docker exec -i "$DB_CONTAINER"' in restore_script
            and 'DROP SCHEMA IF EXISTS public CASCADE' in restore_script
            and 'CREATE SCHEMA public' in restore_script,
            'scripts/restore.sh limpa schema public e restaura PostgreSQL com gunzip e psql ON_ERROR_STOP.',
            'scripts/restore.sh nao comprova restore PostgreSQL seguro.',
        ),
        _check(
            'restore.media_restore',
            'Restore de media',
            'docker cp' in restore_script
            and 'tar -xzf' in restore_script
            and 'restore_media.py' in restore_script
            and 'UnsafeArchiveError' in restore_media_helper
            and 'staging.replace(destination)' in restore_media_helper,
            'Restore de mídia cobre container e diretório local com validação e troca atômica.',
            'scripts/restore.sh nao comprova restore de media.',
        ),
        _check(
            'backup.local_scheduler',
            'Agendador de backup local',
            backup_scheduler_script.startswith('#!/usr/bin/env bash')
            and 'set -euo pipefail' in backup_scheduler_script
            and 'scripts/backup.sh' in backup_scheduler_script
            and 'flock' in backup_scheduler_script
            and 'last_backup_ok' in backup_scheduler_script,
            'scripts/backup_scheduler.sh agenda ciclos locais, usa lock e valida os artefatos produzidos.',
            'scripts/backup_scheduler.sh ausente ou nao atende ao contrato local.',
        ),
        _check(
            'backup.local_compose_service',
            'Servico backup_scheduler no Compose VPS',
            'backup_scheduler:' in vps_compose
            and 'scripts/backup_scheduler.sh' in vps_compose
            and 'media:/app/media:ro' in vps_compose
            and '/var/run/docker.sock' not in vps_compose,
            'docker-compose.vps.yml declara backup_scheduler com banco privado e midia somente leitura.',
            'docker-compose.vps.yml nao comprova o servico diario de backup local.',
        ),
        _check(
            'backup.local_environment',
            'Variaveis de ambiente do backup local',
            'BACKUP_CRON_HOUR' in env_example
            and 'BACKUP_CRON_MINUTE' in env_example
            and 'BACKUP_RETENTION_DAYS' in env_example,
            '.env.example documenta janela e retencao do backup local.',
            '.env.example nao expoe janela e retencao necessarias ao backup local.',
        ),
        _docs_check(deployment_docs, backup_restore_docs, mkdocs_source),
        _security_check(scan_source),
    ]
    return BackupRestoreReadinessReport(tuple(checks))


def _read(path):
    try:
        return path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return ''


def _check(code, title, passed, pass_evidence, fail_evidence):
    return BackupRestoreCheck(
        code=code,
        title=title,
        status=BackupRestoreCheckStatus.PASS if passed else BackupRestoreCheckStatus.FAIL,
        evidence=pass_evidence if passed else fail_evidence,
    )


def _docs_check(deployment_docs, backup_restore_docs, mkdocs_source):
    passed = (
        'scripts/backup.sh' in deployment_docs
        and 'scripts/restore.sh' in deployment_docs
        and 'check_backup_restore_readiness' in deployment_docs
        and 'Objetivo de recuperação' in backup_restore_docs
        and 'pre-restore' in backup_restore_docs
        and 'docs/architecture/backup-restore.md' in backup_restore_docs
        and 'architecture/backup-restore.md' in mkdocs_source
    )
    return _check(
        'docs.backup_restore_plan',
        'Plano documentado de backup e restauracao',
        passed,
        'docs/deployment.md, docs/architecture/backup-restore.md e MKDocs documentam backup, restore, pre-restore e check_backup_restore_readiness.',
        'Plano de backup/restauracao nao esta documentado de forma navegavel.',
    )


def _security_check(source):
    secret_patterns = (
        r'sk-[A-Za-z0-9]{20,}',
        r'AKIA[0-9A-Z]{16}',
        r'ghp_[A-Za-z0-9]{30,}',
        r'-----BEGIN (RSA |EC |OPENSSH |)PRIVATE KEY-----',
    )
    leaked = [pattern for pattern in secret_patterns if re.search(pattern, source)]
    return _check(
        'security.no_real_secrets',
        'Sem segredos reais em scripts e docs',
        not leaked,
        'Scripts e documentacao usam variaveis/placeholders, sem tokens reais detectados.',
        'Possivel segredo real detectado por padrao: ' + ', '.join(leaked),
    )
