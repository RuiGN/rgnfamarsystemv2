from celery import shared_task


@shared_task(name='fiscal.tasks.send_fiscal_document_email')
def send_fiscal_document_email(delivery_id):
    from fiscal.models import FiscalEmailDelivery
    from fiscal.services import FiscalEmissionService

    delivery = FiscalEmailDelivery.objects.get(pk=delivery_id)
    FiscalEmissionService().send_delivery_email(delivery)
    return delivery.pk
