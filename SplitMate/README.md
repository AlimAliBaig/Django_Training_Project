# SplitMate — Shared Expense Splitter

A Django full-stack app for roommates, trips and college groups. Create a group, add shared
expenses, split them equally or by exact amounts, and get the **fewest payments** needed to settle up.
Built with Django templates, plain HTML/CSS/JS and SQLite. No REST framework, no external JS libraries.

## Features
- Sign up / log in, per-user data protection (only group members can see a group)
- Groups with an emoji theme and a 6-character **invite code** to join
- Expenses with category, payer, date, note; **equal split** among chosen people or **exact amounts**
  (cent-perfect rounding, validated to add up to the total)
- Live **balances** per member and **suggested settle-up** (debt simplification)
- Record real-world **payments** (settlements) — balances update instantly
- Spending-by-category bars, CSV export, edit/delete (creator or group owner only)
- Dark UI with a top navigation bar and amber/coral accents
- Django admin and a unit/integration test-suite

## Setup (Windows PowerShell)
```powershell
python -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 8002
```
Open http://127.0.0.1:8002/ (admin at /admin/). macOS/Linux: use `source venv/bin/activate`.

Run the tests with `python manage.py test`.

## How it works
Each person's **net balance** = what they paid − their share of expenses + payments they made − payments they received.
Positive means the group owes them; negative means they owe the group. `ledger/services.py` turns those
numbers into the smallest list of "A pays B" transfers.

## Project layout
- `config/` – settings and root URLs
- `ledger/models.py` – Group, Membership, Expense, ExpenseShare, Settlement
- `ledger/services.py` – split and settle-up algorithms
- `ledger/views.py`, `forms.py`, `urls.py` – app logic
- `ledger/templates/` and `static/ledger/` – UI

## Notes
Learning project for local use. Before deploying set a secure `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS` and HTTPS.
