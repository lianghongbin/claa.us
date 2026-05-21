from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.finance.models import APPaymentAllocation, ARPaymentAllocation
from apps.finance.services_ap import recalc_ap_invoice_amount_paid
from apps.finance.services_ar import recalc_ar_invoice_amount_paid


@receiver(post_save, sender=ARPaymentAllocation)
@receiver(post_delete, sender=ARPaymentAllocation)
def ar_payment_allocation_changed(sender, instance, **kwargs):
    if instance.ar_invoice_id:
        recalc_ar_invoice_amount_paid(instance.ar_invoice_id)


@receiver(post_save, sender=APPaymentAllocation)
@receiver(post_delete, sender=APPaymentAllocation)
def ap_payment_allocation_changed(sender, instance, **kwargs):
    if instance.ap_invoice_id:
        recalc_ap_invoice_amount_paid(instance.ap_invoice_id)
