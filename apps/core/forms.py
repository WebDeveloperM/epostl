from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .files import ALL_CATEGORIES, accept_attribute, validate_uploaded_file
from .models import SystemSettings


class BootstrapFormMixin:
    """Widget'larga Bootstrap 5 klasslarini avtomatik qo‘shadi."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()

    def apply_bootstrap(self):
        for name, field in self.fields.items():
            widget = field.widget
            css = widget.attrs.get("class", "")
            if isinstance(widget, (forms.CheckboxInput,)):
                base = "form-check-input"
            elif isinstance(widget, (forms.CheckboxSelectMultiple, forms.RadioSelect)):
                base = "form-check-input"
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                base = "form-select"
            elif isinstance(widget, forms.FileInput):
                base = "form-control"
            else:
                base = "form-control"
            if base and base not in css.split():
                widget.attrs["class"] = f"{css} {base}".strip()
            if isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("rows", 4)

    def full_clean(self):
        super().full_clean()
        for name in self.errors:
            if name in self.fields:
                widget = self.fields[name].widget
                css = widget.attrs.get("class", "")
                if "is-invalid" not in css:
                    widget.attrs["class"] = f"{css} is-invalid".strip()


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, attrs=None, format="%Y-%m-%d"):
        super().__init__(attrs=attrs, format=format)


class DateTimeInput(forms.DateTimeInput):
    input_type = "datetime-local"

    def __init__(self, attrs=None, format="%Y-%m-%dT%H:%M"):
        super().__init__(attrs=attrs, format=format)


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """Bir nechta faylni qabul qiladi va har birini xavfsizlik tekshiruvidan o‘tkazadi.

    `cleaned_data[name]` — (UploadedFile, ValidatedFile) juftliklari ro‘yxati.
    """

    def __init__(self, *args, categories=ALL_CATEGORIES, max_files=20, **kwargs):
        self.categories = categories
        self.max_files = max_files
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def widget_attrs(self, widget):
        attrs = super().widget_attrs(widget)
        attrs["data-dropzone"] = "1"
        try:
            attrs["accept"] = accept_attribute(self.categories)
        except Exception:  # migratsiyalardan oldin (jadval yo‘q) xato bermasin
            pass
        return attrs

    def clean(self, data, initial=None):
        single_clean = super().clean
        if isinstance(data, (list, tuple)):
            files = [single_clean(d, initial) for d in data if d]
        else:
            files = [single_clean(data, initial)] if data else []
        files = [f for f in files if f]
        if self.required and not files:
            raise ValidationError(self.error_messages["required"], code="required")
        if len(files) > self.max_files:
            raise ValidationError(_("Bir martada ko‘pi bilan %(n)s ta fayl yuklash mumkin.") % {"n": self.max_files})
        errors, result = [], []
        for f in files:
            try:
                result.append((f, validate_uploaded_file(f, self.categories)))
            except ValidationError as exc:
                errors.extend(exc.messages)
        if errors:
            raise ValidationError(errors)
        return result


class SystemSettingsForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SystemSettings
        fields = [
            "platform_name",
            "organization_name",
            "max_upload_size_mb",
            "max_video_size_mb",
            "allowed_video_extensions",
            "deadline_reminder_hours",
            "allow_late_submission",
        ]

    def clean_allowed_video_extensions(self):
        from .files import EXTENSIONS, VIDEO

        value = self.cleaned_data["allowed_video_extensions"]
        exts = [e.strip().lower().lstrip(".") for e in value.split(",") if e.strip()]
        supported = {e for e, (cat, _m, _s) in EXTENSIONS.items() if cat == VIDEO}
        wrong = [e for e in exts if e not in supported]
        if wrong:
            raise ValidationError(_("Qo‘llab-quvvatlanmaydigan format: %(f)s") % {"f": ", ".join(wrong)})
        if not exts:
            raise ValidationError(_("Kamida bitta video formatini kiriting."))
        return ",".join(dict.fromkeys(exts))
