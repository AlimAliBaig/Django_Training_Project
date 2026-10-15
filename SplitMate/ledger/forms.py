from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Group, Expense, Settlement
from .services import split_equally


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=40, required=True, label="Display name")

    class Meta:
        model = User
        fields = ("username", "first_name", "email", "password1", "password2")


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]


class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ["name", "emoji", "description"]
        widgets = {"description": forms.TextInput(attrs={"placeholder": "e.g. Flat 4B bills, Goa trip 2026"})}


class JoinGroupForm(forms.Form):
    code = forms.CharField(max_length=8, label="Invite code", widget=forms.TextInput(attrs={"placeholder": "A3F9C1"}))

    def clean_code(self):
        code = self.cleaned_data["code"].strip().upper()
        try:
            self.group = Group.objects.get(invite_code=code)
        except Group.DoesNotExist:
            raise forms.ValidationError("No group found with that code.")
        return code


def display_name(user):
    return user.first_name or user.username


class ExpenseForm(forms.ModelForm):
    participants = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(), widget=forms.CheckboxSelectMultiple, label="Split between"
    )

    class Meta:
        model = Expense
        fields = ["title", "amount", "paid_by", "category", "date", "split_type", "note"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "title": forms.TextInput(attrs={"placeholder": "Dinner at Café Mocha"}),
            "note": forms.TextInput(attrs={"placeholder": "Optional note"}),
        }

    def __init__(self, *args, group, **kwargs):
        super().__init__(*args, **kwargs)
        self.group = group
        members = group.members.all().order_by("first_name", "username")
        self.members = list(members)
        self.fields["paid_by"].queryset = members
        self.fields["participants"].queryset = members
        for field in (self.fields["paid_by"], self.fields["participants"]):
            field.label_from_instance = display_name
        # One optional amount box per member, used for "exact amounts".
        for m in self.members:
            self.fields[f"share_{m.pk}"] = forms.DecimalField(
                required=False, min_value=Decimal("0"), max_digits=12, decimal_places=2,
                label=display_name(m), widget=forms.NumberInput(attrs={"step": "0.01", "placeholder": "0.00"}),
            )
        self.exact_fields = [self[f"share_{m.pk}"] for m in self.members]

    def clean(self):
        cleaned = super().clean()
        amount = cleaned.get("amount")
        split_type = cleaned.get("split_type")
        participants = cleaned.get("participants")
        if not amount or not split_type:
            return cleaned
        if split_type == "equal":
            if not participants:
                self.add_error("participants", "Pick at least one person to split with.")
                return cleaned
            self.shares = split_equally(amount, [p.pk for p in participants])
        else:
            shares = {}
            for m in self.members:
                value = cleaned.get(f"share_{m.pk}")
                if value:
                    shares[m.pk] = value
            total = sum(shares.values(), Decimal("0"))
            if not shares:
                self.add_error("split_type", "Enter at least one person's share.")
            elif total != amount:
                self.add_error("split_type", f"Shares add up to {total}, but the expense is {amount}.")
            self.shares = shares
        return cleaned


class SettlementForm(forms.ModelForm):
    class Meta:
        model = Settlement
        fields = ["payer", "receiver", "amount", "date", "note"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"}), "note": forms.TextInput(attrs={"placeholder": "UPI / cash / bank transfer"})}

    def __init__(self, *args, group, **kwargs):
        super().__init__(*args, **kwargs)
        self.group = group
        members = group.members.all().order_by("first_name", "username")
        for name in ("payer", "receiver"):
            self.fields[name].queryset = members
            self.fields[name].label_from_instance = display_name
        self.fields["payer"].label = "Who paid"
        self.fields["receiver"].label = "Who received"

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("payer") and cleaned.get("payer") == cleaned.get("receiver"):
            raise forms.ValidationError("Payer and receiver must be different people.")
        return cleaned
