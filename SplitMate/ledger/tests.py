from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Expense, ExpenseShare, Group, Membership, Settlement
from .services import group_balances, simplify_debts, split_equally

D = Decimal


class MoneyLogicTests(TestCase):
    def test_equal_split_distributes_leftover_cents(self):
        shares = split_equally(D("100.00"), [1, 2, 3])
        self.assertEqual(sum(shares.values()), D("100.00"))
        self.assertEqual(sorted(shares.values()), [D("33.33"), D("33.33"), D("33.34")])

    def test_simplify_debts_clears_everyone(self):
        balances = {1: D("60"), 2: D("-20"), 3: D("-40")}
        payments = simplify_debts(balances)
        self.assertEqual(len(payments), 2)
        self.assertEqual(sum(p[2] for p in payments), D("60"))


class AppFlowTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user("riya", password="SafePass12345", first_name="Riya")
        self.b = User.objects.create_user("aman", password="SafePass12345", first_name="Aman")
        self.c = User.objects.create_user("outsider", password="SafePass12345")
        self.group = Group.objects.create(name="Flat", owner=self.a)
        Membership.objects.create(group=self.group, user=self.a)
        Membership.objects.create(group=self.group, user=self.b)

    def test_pages_require_login(self):
        self.assertEqual(self.client.get(reverse("home")).status_code, 302)

    def test_non_member_cannot_open_group(self):
        self.client.login(username="outsider", password="SafePass12345")
        self.assertEqual(self.client.get(reverse("group_detail", args=[self.group.pk])).status_code, 404)

    def test_join_with_invite_code(self):
        self.client.login(username="outsider", password="SafePass12345")
        self.client.post(reverse("group_join"), {"code": self.group.invite_code.lower()})
        self.assertTrue(Membership.objects.filter(group=self.group, user=self.c).exists())

    def test_add_equal_expense_and_balances(self):
        self.client.login(username="riya", password="SafePass12345")
        resp = self.client.post(reverse("expense_create", args=[self.group.pk]), {
            "title": "Groceries", "amount": "100.00", "paid_by": self.a.pk, "category": "food",
            "date": "2026-10-01", "split_type": "equal", "participants": [self.a.pk, self.b.pk],
        })
        self.assertEqual(resp.status_code, 302)
        balances = group_balances(self.group)
        self.assertEqual(balances[self.a.pk], D("50.00"))
        self.assertEqual(balances[self.b.pk], D("-50.00"))

    def test_exact_split_must_match_total(self):
        self.client.login(username="riya", password="SafePass12345")
        resp = self.client.post(reverse("expense_create", args=[self.group.pk]), {
            "title": "Dinner", "amount": "90.00", "paid_by": self.a.pk, "category": "food",
            "date": "2026-10-01", "split_type": "exact",
            f"share_{self.a.pk}": "30", f"share_{self.b.pk}": "30",
        })
        self.assertEqual(resp.status_code, 200)  # form re-rendered with an error
        self.assertFalse(Expense.objects.exists())

    def test_settlement_clears_balance(self):
        e = Expense.objects.create(group=self.group, paid_by=self.a, created_by=self.a, title="Rent", amount=D("100"))
        ExpenseShare.objects.create(expense=e, user=self.a, amount=D("50"))
        ExpenseShare.objects.create(expense=e, user=self.b, amount=D("50"))
        Settlement.objects.create(group=self.group, payer=self.b, receiver=self.a, amount=D("50"))
        self.assertTrue(all(v == 0 for v in group_balances(self.group).values()))

    def test_only_creator_or_owner_can_delete(self):
        e = Expense.objects.create(group=self.group, paid_by=self.a, created_by=self.a, title="X", amount=D("10"))
        self.client.login(username="aman", password="SafePass12345")
        self.client.post(reverse("expense_delete", args=[self.group.pk, e.pk]))
        self.assertTrue(Expense.objects.filter(pk=e.pk).exists())

    def test_all_main_pages_render(self):
        self.client.login(username="riya", password="SafePass12345")
        urls = [reverse("home"), reverse("group_create"), reverse("group_join"), reverse("profile"),
                reverse("expense_create", args=[self.group.pk]), reverse("settlement_create", args=[self.group.pk]),
                reverse("export_csv", args=[self.group.pk])]
        urls += [reverse("group_detail", args=[self.group.pk]) + f"?tab={t}" for t in ("expenses", "balances", "people", "history")]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 200, url)
