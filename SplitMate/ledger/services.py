"""Pure money logic, kept out of the views so it is easy to test."""
from collections import defaultdict
from decimal import Decimal, ROUND_DOWN

from django.db.models import Sum

from .models import Expense, ExpenseShare, Settlement

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def split_equally(total, user_ids):
    """Split `total` across user_ids to the cent; leftover cents go to the first people."""
    user_ids = list(user_ids)
    count = len(user_ids)
    base = (total / count).quantize(CENT, rounding=ROUND_DOWN)
    leftover_cents = int((total - base * count) / CENT)
    result = {}
    for index, uid in enumerate(user_ids):
        result[uid] = base + (CENT if index < leftover_cents else ZERO)
    return result


def group_balances(group):
    """Return {user_id: net}. Positive = the group owes them, negative = they owe the group."""
    net = defaultdict(lambda: ZERO)
    for row in Expense.objects.filter(group=group).values("paid_by").annotate(t=Sum("amount")):
        net[row["paid_by"]] += row["t"]
    for row in ExpenseShare.objects.filter(expense__group=group).values("user").annotate(t=Sum("amount")):
        net[row["user"]] -= row["t"]
    for row in Settlement.objects.filter(group=group).values("payer").annotate(t=Sum("amount")):
        net[row["payer"]] += row["t"]
    for row in Settlement.objects.filter(group=group).values("receiver").annotate(t=Sum("amount")):
        net[row["receiver"]] -= row["t"]
    return dict(net)


def simplify_debts(balances):
    """Greedy settle-up: returns [(debtor_id, creditor_id, amount)] with the fewest payments."""
    creditors = sorted([[u, b] for u, b in balances.items() if b > 0], key=lambda x: -x[1])
    debtors = sorted([[u, -b] for u, b in balances.items() if b < 0], key=lambda x: -x[1])
    payments = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        pay = min(debtors[i][1], creditors[j][1])
        if pay > 0:
            payments.append((debtors[i][0], creditors[j][0], pay))
        debtors[i][1] -= pay
        creditors[j][1] -= pay
        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1
    return payments
