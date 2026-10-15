import csv
from collections import OrderedDict
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import (ExpenseForm, GroupForm, JoinGroupForm, ProfileForm,
                    RegisterForm, SettlementForm)
from .models import Expense, ExpenseShare, Group, Membership, Settlement
from .services import group_balances, simplify_debts

ZERO = Decimal("0.00")


def _member_group(request, pk):
    """Fetch a group, only if the current user belongs to it."""
    return get_object_or_404(Group, pk=pk, memberships__user=request.user)


def _user_net_across_groups(user):
    owed_to_me = ZERO
    i_owe = ZERO
    for group in Group.objects.filter(memberships__user=user):
        net = group_balances(group).get(user.pk, ZERO)
        if net > 0:
            owed_to_me += net
        else:
            i_owe += -net
    return owed_to_me, i_owe


def landing(request):
    if request.user.is_authenticated:
        return redirect("home")
    return render(request, "ledger/landing.html")


def register(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Welcome to SplitMate! Create a group or join one with a code.")
        return redirect("home")
    return render(request, "registration/register.html", {"form": form})


@login_required
def home(request):
    groups = Group.objects.filter(memberships__user=request.user).prefetch_related("members")
    cards = []
    for g in groups:
        net = group_balances(g).get(request.user.pk, ZERO)
        cards.append({"group": g, "net": net, "member_count": g.members.count()})
    owed_to_me, i_owe = _user_net_across_groups(request.user)
    recent = (Expense.objects.filter(group__in=groups).select_related("group", "paid_by")[:6])
    return render(request, "ledger/home.html", {
        "cards": cards, "owed_to_me": owed_to_me, "i_owe": i_owe,
        "net_total": owed_to_me - i_owe, "recent": recent,
    })


@login_required
def group_create(request):
    form = GroupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        group = form.save(commit=False)
        group.owner = request.user
        group.save()
        Membership.objects.create(group=group, user=request.user)
        messages.success(request, f"Group created. Share invite code {group.invite_code} with your friends.")
        return redirect("group_detail", pk=group.pk)
    return render(request, "ledger/group_form.html", {"form": form})


@login_required
def group_join(request):
    form = JoinGroupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        group = form.group
        _, created = Membership.objects.get_or_create(group=group, user=request.user)
        messages.success(request, f"You joined {group.name}!" if created else "You are already in that group.")
        return redirect("group_detail", pk=group.pk)
    return render(request, "ledger/group_join.html", {"form": form})


@login_required
def group_detail(request, pk):
    group = _member_group(request, pk)
    members = list(group.members.all().order_by("first_name", "username"))
    balances = group_balances(group)
    member_rows = [{"user": m, "net": balances.get(m.pk, ZERO)} for m in members]
    by_id = {m.pk: m for m in members}
    suggestions = [{"from": by_id[d], "to": by_id[c], "amount": a}
                   for d, c, a in simplify_debts(balances) if d in by_id and c in by_id]

    expenses = group.expenses.select_related("paid_by").prefetch_related("shares__user")
    total_spent = expenses.aggregate(t=Sum("amount"))["t"] or ZERO
    cat_labels = dict(Expense.CATEGORY_CHOICES)
    cat_rows = list(expenses.values("category").annotate(t=Sum("amount")).order_by("-t"))
    for row in cat_rows:
        row["label"] = cat_labels.get(row["category"], row["category"])
        row["percent"] = int(row["t"] / total_spent * 100) if total_spent else 0

    tab = request.GET.get("tab", "expenses")
    return render(request, "ledger/group_detail.html", {
        "group": group, "member_rows": member_rows, "suggestions": suggestions,
        "expenses": expenses, "settlements": group.settlements.select_related("payer", "receiver"),
        "total_spent": total_spent, "cat_rows": cat_rows, "my_net": balances.get(request.user.pk, ZERO),
        "tab": tab if tab in ("expenses", "balances", "people", "history") else "expenses",
        "is_owner": group.owner_id == request.user.pk,
    })


@login_required
@require_POST
def group_leave(request, pk):
    group = _member_group(request, pk)
    net = group_balances(group).get(request.user.pk, ZERO)
    if net != 0:
        messages.error(request, "Settle your balance before leaving this group.")
        return redirect("group_detail", pk=pk)
    if group.owner_id == request.user.pk and group.members.count() > 1:
        messages.error(request, "Owners can't leave while others are still in the group.")
        return redirect("group_detail", pk=pk)
    Membership.objects.filter(group=group, user=request.user).delete()
    if group.members.count() == 0:
        group.delete()
    messages.success(request, "You left the group.")
    return redirect("home")


def _save_shares(expense, shares):
    expense.shares.all().delete()
    ExpenseShare.objects.bulk_create([
        ExpenseShare(expense=expense, user_id=uid, amount=amt) for uid, amt in shares.items()
    ])


@login_required
def expense_create(request, pk):
    group = _member_group(request, pk)
    initial = {"paid_by": request.user, "split_type": "equal", "participants": group.members.all()}
    form = ExpenseForm(request.POST or None, group=group, initial=initial)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            expense = form.save(commit=False)
            expense.group = group
            expense.created_by = request.user
            expense.save()
            _save_shares(expense, form.shares)
        messages.success(request, "Expense added and split.")
        return redirect("group_detail", pk=pk)
    return render(request, "ledger/expense_form.html", {"form": form, "group": group, "editing": False})


@login_required
def expense_update(request, pk, expense_pk):
    group = _member_group(request, pk)
    expense = get_object_or_404(Expense, pk=expense_pk, group=group)
    if request.user.pk not in (expense.created_by_id, group.owner_id):
        messages.error(request, "Only the person who added this expense or the group owner can edit it.")
        return redirect("group_detail", pk=pk)
    initial = {"participants": User.objects.filter(expense_shares__expense=expense)}
    for share in expense.shares.all():
        initial[f"share_{share.user_id}"] = share.amount
    form = ExpenseForm(request.POST or None, instance=expense, group=group, initial=initial)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            expense = form.save()
            _save_shares(expense, form.shares)
        messages.success(request, "Expense updated.")
        return redirect("group_detail", pk=pk)
    return render(request, "ledger/expense_form.html", {"form": form, "group": group, "editing": True, "expense": expense})


@login_required
def expense_delete(request, pk, expense_pk):
    group = _member_group(request, pk)
    expense = get_object_or_404(Expense, pk=expense_pk, group=group)
    if request.user.pk not in (expense.created_by_id, group.owner_id):
        messages.error(request, "You can't delete this expense.")
        return redirect("group_detail", pk=pk)
    if request.method == "POST":
        expense.delete()
        messages.success(request, "Expense deleted.")
        return redirect("group_detail", pk=pk)
    return render(request, "ledger/expense_confirm_delete.html", {"group": group, "expense": expense})


@login_required
def settlement_create(request, pk):
    group = _member_group(request, pk)
    initial = {"payer": request.user}
    # Pre-fill from a suggested payment link: ?to=<id>&amount=<x>
    if request.GET.get("to", "").isdigit():
        initial["receiver"] = int(request.GET["to"])
    try:
        if request.GET.get("amount"):
            initial["amount"] = Decimal(request.GET["amount"])
    except Exception:
        pass
    form = SettlementForm(request.POST or None, group=group, initial=initial)
    if request.method == "POST" and form.is_valid():
        settlement = form.save(commit=False)
        settlement.group = group
        settlement.save()
        messages.success(request, "Payment recorded.")
        return redirect("group_detail", pk=pk)
    return render(request, "ledger/settlement_form.html", {"form": form, "group": group})


@login_required
def export_csv(request, pk):
    group = _member_group(request, pk)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="splitmate-{group.pk}.csv"'
    writer = csv.writer(response)
    writer.writerow(["Date", "Title", "Category", "Paid by", "Amount", "Split type", "Shares"])
    for e in group.expenses.select_related("paid_by").prefetch_related("shares__user"):
        shares = "; ".join(f"{s.user.first_name or s.user.username}: {s.amount}" for s in e.shares.all())
        writer.writerow([e.date, e.title, e.get_category_display(), e.paid_by.first_name or e.paid_by.username,
                         e.amount, e.get_split_type_display(), shares])
    return response


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("profile")
    return render(request, "ledger/profile.html", {"form": form})
