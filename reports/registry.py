from collections.abc import Callable
from re import compile as compile_pattern
from threading import RLock

from django.core.exceptions import ValidationError

from reports.contracts import ReportExecutor


_EXECUTORS: dict[str, ReportExecutor] = {}
_EXECUTOR_LOCK = RLock()
_CANONICAL_KEY_PATTERN = compile_pattern(r'[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+')


def _is_canonical_key(key: object) -> bool:
    return type(key) is str and _CANONICAL_KEY_PATTERN.fullmatch(key) is not None


def register_executor(key: str) -> Callable[[ReportExecutor], ReportExecutor]:
    if not _is_canonical_key(key):
        raise RuntimeError('Chave de executor de relatório inválida.')

    def decorator(executor: ReportExecutor) -> ReportExecutor:
        with _EXECUTOR_LOCK:
            if key in _EXECUTORS:
                raise RuntimeError(f'Executor de relatório duplicado: {key}')
            _EXECUTORS[key] = executor
        return executor

    return decorator


def get_executor(key: str) -> ReportExecutor:
    if not _is_canonical_key(key):
        raise ValidationError({'executor_key': 'Executor de relatório não registrado.'})
    with _EXECUTOR_LOCK:
        try:
            return _EXECUTORS[key]
        except KeyError as exc:
            raise ValidationError(
                {'executor_key': 'Executor de relatório não registrado.'}
            ) from exc
