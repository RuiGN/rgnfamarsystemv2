from celery import shared_task


@shared_task(name='ai_agents.tasks.process_ai_agent_run')
def process_ai_agent_run(run_id):
    from ai_agents.models import AIAgentRun

    run = AIAgentRun.objects.select_related('agent', 'requested_by').get(pk=run_id)
    run.execute(user=run.requested_by)
    return run.pk


@shared_task(name='ai_agents.tasks.async_workflow_gate_check', bind=True, max_retries=2)
def async_workflow_gate_check(
    self,
    source_module: str,
    source_model: str,
    record_id: str,
    input_payload: dict,
    callback_task_name: str | None = None,
):
    """
    Executa verificação de workflow gate de forma assíncrona.
    """
    from ai_agents.services import run_workflow_gate_agent
    from celery import current_app

    try:
        result = run_workflow_gate_agent(
            source_module=source_module,
            source_model=source_model,
            record_id=record_id,
            input_payload=input_payload,
        )
        if result and callback_task_name:
            current_app.send_task(callback_task_name, args=[record_id, result])
        return result
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)
