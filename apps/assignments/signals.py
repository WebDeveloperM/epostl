from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def assign_group_tasks_to_new_member(sender, instance, created, update_fields=None, **kwargs):
    """Talaba guruhga qo‘shilsa yoki guruhi o‘zgarsa — guruhning faol topshiriqlarini biriktiradi."""
    if update_fields is not None and "group" not in update_fields:
        return
    if not instance.group_id or kwargs.get("raw"):
        return
    from .services import ensure_group_targets

    ensure_group_targets(instance)
