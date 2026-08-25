from celery import shared_task


REPORT_TASK_MAX_RETRIES = 5
REPORT_TASK_RETRY_BASE_SECONDS = 15
REPORT_TASK_RETRY_MAX_SECONDS = 300


def _retry_countdown(retries):
    return min(
        REPORT_TASK_RETRY_BASE_SECONDS * (2 ** max(0, retries)),
        REPORT_TASK_RETRY_MAX_SECONDS,
    )


@shared_task(
    bind=True,
    name='reports.tasks.generate_report_execution',
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=REPORT_TASK_MAX_RETRIES,
    retry_backoff=True,
)
def generate_report_execution(self, execution_id):
    from reports.models import ReportExecution
    from reports.services import (
        ReportExecutionInProgress,
        ReportExecutionRetryableError,
        mark_retry_exhausted,
    )

    execution = ReportExecution.objects.select_related(
        'definition', 'schedule', 'requested_by'
    ).get(pk=execution_id)
    try:
        execution = execution.run()
    except ReportExecutionInProgress as error:
        raise self.retry(
            exc=error,
            countdown=min(error.retry_after, REPORT_TASK_RETRY_MAX_SECONDS),
        )
    except ReportExecutionRetryableError as error:
        if self.request.retries >= self.max_retries:
            mark_retry_exhausted(execution_id)
            raise
        raise self.retry(
            exc=error,
            countdown=_retry_countdown(self.request.retries),
        )
    return {
        'execution_id': execution.pk,
        'status': execution.status,
    }
