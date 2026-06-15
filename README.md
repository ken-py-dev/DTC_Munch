# DTC Munch 🍱

A school canteen ordering system built with Flask. Students and staff can browse the menu, add items to cart, place orders, and track their history. Admins manage the menu, orders, invoices, and user balances.

## Features

- **Menu browsing** — Filter by category, search by name/description, view daily specials
- **Cart & checkout** — Add items to session-based cart, pay via balance or manual (cash/bank transfer)
- **Order management** — Track order status (pending → confirmed → preparing → ready → completed)
- **Cancel & refund** — Request cancellation; admin approves and refunds balance + restocks
- **Ratings & reviews** — Rate completed orders and leave reviews
- **Favorites** — Save favorite items for quick access
- **Admin dashboard** — Revenue analytics, top-selling items, sales by category, charts
- **Admin CRUD** — Manage menu items, categories, orders, invoices, user top-ups
- **Invoice generation** — Printable invoices with unique reference numbers

## Quick Start

### Prerequisites

- Python 3.12+
- pip

_or_

- Docker + Docker Compose

### Setup (Python)

```
python -m venv .venv
.venv\Scripts\activate   # Windows
source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
cp .env.example .env
python app.py
```

### Setup (Docker)

```
docker compose up -d
```

Open http://localhost:5000 in either case.

## Demo Credentials

| Role | Username | Password |
|------|----------|----------|
| Admin | `admin` | `admin123` |
| Student | `demo` | `demo123` |

The database is seeded with sample menu items and demo accounts on first run.

## Project Structure

```
DTC_Munch/
├── app.py                  # Application factory & entry point
├── config.py               # Flask configuration
├── models.py               # SQLAlchemy ORM models + status transitions
├── forms.py                # WTForms form definitions
├── routes/
│   ├── __init__.py         # Shared decorators (admin_required)
│   ├── auth.py             # Login / register / logout
│   ├── menu.py             # Menu browsing
│   ├── orders.py           # Cart, checkout, history, ratings, favorites
│   └── admin.py            # Admin dashboard, menu, orders, invoices, users
├── templates/              # Jinja2 templates (admin, auth, menu, orders, errors)
├── static/
│   ├── style.css           # Responsive CSS
│   └── uploads/            # Uploaded menu item images
├── .env.example            # Environment variable template
├── .gitignore
├── pyproject.toml          # Ruff linter config
└── requirements.txt
```

## Order Lifecycle

```
pending / pending_payment
  ├──> confirmed → preparing → ready → completed
  └──> cancel_requested → cancelled
```

- **pending** — New order placed via balance payment
- **pending_payment** — New order placed via manual payment (awaiting admin confirmation)
- **confirmed** — Admin confirms the order
- **preparing** — Being prepared
- **ready** — Ready for pickup
- **completed** — Order fulfilled
- **cancel_requested** — User requested cancellation (admin approves or rejects)
- **cancelled** — Order cancelled; stock and balance refunded

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | Flask 3.1 |
| ORM | SQLAlchemy 2.0 + Flask-SQLAlchemy |
| Database | SQLite (development), swappable for production |
| Auth | Flask-Login + Werkzeug password hashing |
| Forms | WTForms + Flask-WTF (CSRF protected) |
| Frontend | Pure CSS (responsive, no JS framework) |
| Linting | Ruff (pyproject.toml) |

## License

MIT
