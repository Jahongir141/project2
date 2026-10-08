import re

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import waiter_required
from orders.models import ACTIVE_STATUSES, Order

from .models import Section

STATE_LABELS = {
    "free": "BO‘SH",
    "busy": "BAND",
    "sent": "BUYURTMA YUBORILGAN",
    "ready": "TAYYOR",
    "pay": "TO‘LOV KUTILMOQDA",
}


def _natural(table):
    parts = re.split(r"(\d+)", table.name)
    return (table.sort_order, [int(p) if p.isdigit() else p.lower() for p in parts])


@waiter_required
def home(request):
    if request.user.is_admin_role:
        return redirect("dashboard:home")
    return redirect("sectors")


@waiter_required
def sectors(request):
    sections = Section.objects.filter(active=True).annotate(
        table_count=Count("tables", filter=Q(tables__active=True), distinct=True)
    )
    busy = {
        row["table__section_id"]: row["n"]
        for row in Order.objects.filter(status__in=ACTIVE_STATUSES)
        .values("table__section_id")
        .annotate(n=Count("id"))
    }
    for section in sections:
        section.busy_count = busy.get(section.pk, 0)
    return render(request, "locations/sectors.html", {"sections": sections})


@waiter_required
def sector_detail(request, pk):
    section = get_object_or_404(Section, pk=pk, active=True)
    active_orders = {
        o.table_id: o
        for o in Order.objects.active().filter(table__section=section).select_related("waiter")
    }
    cells = []
    for table in sorted(section.tables.filter(active=True), key=_natural):
        order = active_orders.get(table.pk)
        state = order.table_state if order else "free"
        cells.append(
            {
                "table": table,
                "order": order,
                "state": state,
                "label": STATE_LABELS[state],
                "mine": bool(order and order.waiter_id == request.user.id),
            }
        )
    return render(
        request,
        "locations/sector_detail.html",
        {"section": section, "cells": cells, "legend": STATE_LABELS},
    )
