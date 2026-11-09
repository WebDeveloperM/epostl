from django.db import models
from django.utils.translation import gettext_lazy as _


class Subject(models.Model):
    name = models.CharField(_("Fan nomi"), max_length=255)
    code = models.CharField(_("Fan kodi"), max_length=30, blank=True)
    department = models.ForeignKey("organization.Department", on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="subjects", verbose_name=_("Kafedra"))
    description = models.TextField(_("Tavsif"), blank=True)
    is_active = models.BooleanField(_("Faol"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "subjects"
        ordering = ["name"]
        verbose_name = _("Fan")
        verbose_name_plural = _("Fanlar")
        constraints = [
            models.UniqueConstraint(fields=["code"], condition=~models.Q(code=""), name="uniq_subject_code"),
        ]

    def __str__(self):
        return f"{self.code} {self.name}".strip()
