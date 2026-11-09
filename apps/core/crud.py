"""
Administrator uchun ma’lumotnomalar (fakultet, kafedra, fan, kompetensiya
va h.k.) bo‘yicha qayta ishlatiladigan CRUD view'lar.

    urlpatterns += crud_urls("faculty", "faculties", Faculty, FacultyForm, ...)
"""
from functools import reduce
from operator import or_

from django.contrib import messages
from django.db.models import ProtectedError, Q
from django.shortcuts import redirect

from apps.core.utils import tr
from django.urls import path, reverse
from django.utils.translation import gettext as _
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from apps.audit.services import log_action

from .permissions import AdminRequiredMixin


def _resolve(obj, accessor):
    if callable(accessor):
        return accessor(obj)
    value = obj
    for part in accessor.split("."):
        value = getattr(value, part, None)
        if value is None:
            return None
        if callable(value):
            value = value()
    return value


class CrudMixin(AdminRequiredMixin):
    crud_name = ""
    title = ""
    title_plural = ""
    icon = "bi-table"
    description = ""

    def url_name(self, action):
        ns = self.request.resolver_match.namespace
        return f"{ns}:{self.crud_name}_{action}" if ns else f"{self.crud_name}_{action}"

    def get_success_url(self):
        return reverse(self.url_name("list"))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            crud_title=self.title,
            crud_title_plural=self.title_plural,
            crud_icon=self.icon,
            crud_description=self.description,
            list_url=reverse(self.url_name("list")),
            create_url=reverse(self.url_name("create")),
        )
        return ctx


class CrudListView(CrudMixin, ListView):
    template_name = "base/crud_list.html"
    paginate_by = 25
    columns: list = []
    search_fields: tuple = ()
    select_related: tuple = ()
    translate_fields: tuple = ()  # standart (seed) nomlar — joriy tilda ko‘rsatiladi

    def get_queryset(self):
        qs = super().get_queryset()
        if self.select_related:
            qs = qs.select_related(*self.select_related)
        q = self.request.GET.get("q", "").strip()
        if q and self.search_fields:
            qs = qs.filter(reduce(or_, (Q(**{f"{f}__icontains": q}) for f in self.search_fields)))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        update_name, delete_name = self.url_name("update"), self.url_name("delete")
        rows = []
        for obj in ctx["object_list"]:
            cells = []
            for _label, accessor in self.columns:
                value = _resolve(obj, accessor)
                if accessor in self.translate_fields and isinstance(value, str):
                    value = tr(value)
                cells.append({"value": value, "is_bool": isinstance(value, bool)})
            rows.append(
                {
                    "obj": obj,
                    "cells": cells,
                    "edit_url": reverse(update_name, args=[obj.pk]),
                    "delete_url": reverse(delete_name, args=[obj.pk]),
                }
            )
        ctx.update(
            headers=[label for label, _a in self.columns],
            rows=rows,
            search_enabled=bool(self.search_fields),
            q=self.request.GET.get("q", ""),
        )
        return ctx


class CrudCreateView(CrudMixin, CreateView):
    template_name = "base/crud_form.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action(self.request, "create", self.object)
        messages.success(self.request, _("«%(obj)s» qo‘shildi.") % {"obj": self.object})
        return response


class CrudUpdateView(CrudMixin, UpdateView):
    template_name = "base/crud_form.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action(self.request, "update", self.object, changed=form.changed_data)
        messages.success(self.request, _("«%(obj)s» saqlandi.") % {"obj": self.object})
        return response


class CrudDeleteView(CrudMixin, DeleteView):
    template_name = "base/confirm_delete.html"

    def form_valid(self, form):
        obj = self.get_object()
        label, pk = str(obj), obj.pk
        try:
            obj.delete()
            obj.pk = pk
            log_action(self.request, "delete", obj)
        except ProtectedError:
            messages.error(
                self.request,
                _("«%(obj)s» o‘chirilmadi: unga bog‘langan yozuvlar mavjud. "
                  "Uning o‘rniga nofaol holatga o‘tkazing.") % {"obj": label},
            )
            return redirect(self.get_success_url())
        messages.success(self.request, _("«%(obj)s» o‘chirildi.") % {"obj": label})
        return redirect(self.get_success_url())


def crud_urls(name, url_prefix, model, form_class, *, columns, title, title_plural,
              search_fields=(), select_related=(), icon="bi-table", description="",
              ordering=None, translate=()):
    attrs = {
        "model": model,
        "crud_name": name,
        "title": title,
        "title_plural": title_plural,
        "icon": icon,
        "description": description,
    }
    list_attrs = {**attrs, "columns": columns, "search_fields": search_fields,
                  "select_related": select_related, "translate_fields": tuple(translate)}
    if ordering:
        list_attrs["ordering"] = ordering
    list_view = type(f"{model.__name__}CrudList", (CrudListView,), list_attrs)
    create_view = type(f"{model.__name__}CrudCreate", (CrudCreateView,), {**attrs, "form_class": form_class})
    update_view = type(f"{model.__name__}CrudUpdate", (CrudUpdateView,), {**attrs, "form_class": form_class})
    delete_view = type(f"{model.__name__}CrudDelete", (CrudDeleteView,), attrs)
    return [
        path(f"{url_prefix}/", list_view.as_view(), name=f"{name}_list"),
        path(f"{url_prefix}/new/", create_view.as_view(), name=f"{name}_create"),
        path(f"{url_prefix}/<int:pk>/edit/", update_view.as_view(), name=f"{name}_update"),
        path(f"{url_prefix}/<int:pk>/delete/", delete_view.as_view(), name=f"{name}_delete"),
    ]
