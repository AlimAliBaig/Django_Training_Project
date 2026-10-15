from django.contrib import admin
from .models import Group, Membership, Expense, ExpenseShare, Settlement


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "emoji", "owner", "invite_code", "created_at")
    search_fields = ("name", "invite_code")
    inlines = [MembershipInline]


class ShareInline(admin.TabularInline):
    model = ExpenseShare
    extra = 0


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("title", "group", "paid_by", "amount", "category", "date")
    list_filter = ("category", "split_type", "date")
    search_fields = ("title", "group__name")
    inlines = [ShareInline]


@admin.register(Settlement)
class SettlementAdmin(admin.ModelAdmin):
    list_display = ("group", "payer", "receiver", "amount", "date")
