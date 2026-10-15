import secrets
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

MONEY = dict(max_digits=12, decimal_places=2)
MIN_AMOUNT = [MinValueValidator(Decimal("0.01"))]


def make_invite_code():
    return secrets.token_hex(3).upper()  # e.g. 'A3F9C1'


class Group(models.Model):
    """A shared space: a flat, a trip, a project team..."""

    THEME_CHOICES = [
        ("🏠", "Home / Flat"),
        ("✈️", "Trip"),
        ("🍕", "Food & Outings"),
        ("🎓", "College / Project"),
        ("🎉", "Event / Party"),
        ("💼", "Work"),
    ]
    name = models.CharField(max_length=80)
    emoji = models.CharField(max_length=8, choices=THEME_CHOICES, default="🏠")
    description = models.CharField(max_length=200, blank=True)
    invite_code = models.CharField(max_length=8, unique=True, default=make_invite_code)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owned_groups")
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, through="Membership", related_name="split_groups")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class Membership(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["group", "user"], name="unique_group_member")]
        ordering = ["joined_at"]

    def __str__(self):
        return f"{self.user} in {self.group}"


class Expense(models.Model):
    CATEGORY_CHOICES = [
        ("food", "Food & Groceries"),
        ("rent", "Rent & Utilities"),
        ("travel", "Travel & Fuel"),
        ("stay", "Stay / Hotel"),
        ("fun", "Fun & Tickets"),
        ("shopping", "Shopping"),
        ("other", "Other"),
    ]
    SPLIT_CHOICES = [("equal", "Split equally"), ("exact", "Exact amounts")]

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="expenses")
    paid_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="paid_expenses")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_expenses")
    title = models.CharField(max_length=120)
    amount = models.DecimalField(validators=MIN_AMOUNT, **MONEY)
    category = models.CharField(max_length=12, choices=CATEGORY_CHOICES, default="other")
    split_type = models.CharField(max_length=8, choices=SPLIT_CHOICES, default="equal")
    date = models.DateField(default=timezone.localdate)
    note = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        indexes = [models.Index(fields=["group", "date"])]

    def __str__(self):
        return f"{self.title} ({self.amount})"


class ExpenseShare(models.Model):
    """How much of an expense one person owes."""

    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name="shares")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="expense_shares")
    amount = models.DecimalField(**MONEY)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["expense", "user"], name="unique_share_per_user")]

    def __str__(self):
        return f"{self.user} owes {self.amount}"


class Settlement(models.Model):
    """A real-world payback: `payer` handed `receiver` some money."""

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="settlements")
    payer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="settlements_sent")
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="settlements_received")
    amount = models.DecimalField(validators=MIN_AMOUNT, **MONEY)
    date = models.DateField(default=timezone.localdate)
    note = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.payer} paid {self.receiver} {self.amount}"
