from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict, List, Tuple

from sqlalchemy.orm import Session

from .models import Account, Card, Salary, Transaction, Transfer


def ensure_defaults(db: Session) -> Tuple[Account, Card, Salary]:
    checking = (
        db.query(Account).filter_by(type="checking").order_by(Account.id).first()
    )
    if not checking:
        checking = Account(name="Conta Corrente", type="checking", balance=0.0)
        db.add(checking)
        db.commit()
        db.refresh(checking)

    card = db.query(Card).order_by(Card.id).first()
    if not card:
        card = Card(name="Cartão Principal", due_day=5, current_invoice=0.0)
        db.add(card)
        db.commit()
        db.refresh(card)

    salary = db.query(Salary).order_by(Salary.id).first()
    if not salary:
        salary = Salary(amount=0.0, pay_day=5)
        db.add(salary)
        db.commit()
        db.refresh(salary)

    return checking, card, salary


def get_business_day(year: int, month: int, target_day: int) -> date:
    """Return previous weekday if target falls on weekend."""
    tentative = date(year, month, target_day)
    while tentative.weekday() >= 5:  # 5=Saturday,6=Sunday
        tentative -= timedelta(days=1)
    return tentative


def gather_salary_events(start: date, end: date, salary: Salary) -> List[dict]:
    events = []
    current = date(start.year, start.month, 1)
    while current <= end:
        pay_date = get_business_day(current.year, current.month, salary.pay_day)
        if start <= pay_date <= end:
            events.append(
                {
                    "date": pay_date,
                    "kind": "salary",
                    "amount": salary.amount,
                    "description": "Crédito de salário",
                }
            )
        # move to first day of next month
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return events


def gather_card_payments(start: date, end: date, card: Card) -> List[dict]:
    events = []
    current = date(start.year, start.month, 1)
    while current <= end:
        pay_date = date(current.year, current.month, card.due_day)
        if start <= pay_date <= end:
            events.append(
                {
                    "date": pay_date,
                    "kind": "card_payment",
                    "description": "Pagamento da fatura",
                }
            )
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return events


def gather_transactions(start: date, end: date, db: Session) -> List[Transaction]:
    return (
        db.query(Transaction)
        .filter(Transaction.date >= start, Transaction.date <= end)
        .order_by(Transaction.date)
        .all()
    )


def gather_transfers(start: date, end: date, db: Session) -> List[Transfer]:
    return (
        db.query(Transfer)
        .filter(Transfer.date >= start, Transfer.date <= end)
        .order_by(Transfer.date)
        .all()
    )


def build_simulation(
    db: Session, start: date, days: int
) -> Tuple[List[dict], Dict[int, Account], Card, List[dict]]:
    checking, card, salary = ensure_defaults(db)
    accounts = {acc.id: acc for acc in db.query(Account).order_by(Account.id).all()}

    end_date = start + timedelta(days=days - 1)

    salary_events = gather_salary_events(start, end_date, salary)
    card_payment_events = gather_card_payments(start, end_date, card)
    transactions = gather_transactions(start, end_date, db)
    transfers = gather_transfers(start, end_date, db)

    daily_data: List[dict] = []
    future_events: List[dict] = []

    balances = {acc.id: acc.balance for acc in accounts.values()}
    invoice_value = card.current_invoice

    # create event index per day for easier lookup
    event_map: Dict[date, List[dict]] = {}

    for ev in salary_events:
        event_map.setdefault(ev["date"], []).append({**ev, "order": 1})
        future_events.append({"date": ev["date"], "description": ev["description"], "amount": ev["amount"]})

    for tr in transactions:
        item = {
            "date": tr.date,
            "kind": "transaction",
            "target_type": tr.target_type,
            "account_id": tr.account_id,
            "card_id": tr.card_id,
            "amount": tr.amount,
            "description": tr.description,
            "order": 2,
        }
        event_map.setdefault(tr.date, []).append(item)
        future_events.append({"date": tr.date, "description": tr.description, "amount": tr.amount})

    for tf in transfers:
        item = {
            "date": tf.date,
            "kind": "transfer",
            "amount": tf.amount,
            "source": tf.source_account_id,
            "target": tf.target_account_id,
            "description": tf.description,
            "order": 3,
        }
        event_map.setdefault(tf.date, []).append(item)
        future_events.append({"date": tf.date, "description": tf.description, "amount": tf.amount})

    for ev in card_payment_events:
        event_map.setdefault(ev["date"], []).append({**ev, "order": 4})
        future_events.append({"date": ev["date"], "description": ev["description"], "amount": None})

    current_date = start
    while current_date <= end_date:
        day_events = sorted(event_map.get(current_date, []), key=lambda x: x.get("order", 99))
        for ev in day_events:
            if ev["kind"] == "salary":
                balances[checking.id] = balances.get(checking.id, 0) + ev["amount"]
            elif ev["kind"] == "transaction":
                if ev["target_type"] == "account" and ev["account_id"]:
                    balances[ev["account_id"]] = balances.get(ev["account_id"], 0) + ev["amount"]
                elif ev["target_type"] == "card":
                    invoice_value += ev["amount"]
            elif ev["kind"] == "transfer":
                balances[ev["source"]] = balances.get(ev["source"], 0) - ev["amount"]
                balances[ev["target"]] = balances.get(ev["target"], 0) + ev["amount"]
            elif ev["kind"] == "card_payment":
                balances[checking.id] = balances.get(checking.id, 0) - invoice_value
                invoice_value = 0

        daily_entry = {
            "date": current_date.strftime("%Y%m%d"),
            "invoice": invoice_value,
            "accounts": {acc_id: balances.get(acc_id, 0) for acc_id in accounts},
        }
        daily_data.append(daily_entry)
        current_date += timedelta(days=1)

    future_events.sort(key=lambda x: x["date"])
    return daily_data, accounts, card, future_events


def save_account(db: Session, name: str, balance: float, acc_type: str = "cdb"):
    account = Account(name=name, type=acc_type, balance=balance)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def update_checking_balance(db: Session, balance: float):
    checking, _, _ = ensure_defaults(db)
    checking.balance = balance
    db.commit()


def update_card(db: Session, name: str, due_day: int, invoice: float):
    _, card, _ = ensure_defaults(db)
    card.name = name
    card.due_day = due_day
    card.current_invoice = invoice
    db.commit()


def update_salary(db: Session, amount: float, pay_day: int):
    _, _, salary = ensure_defaults(db)
    salary.amount = amount
    salary.pay_day = pay_day
    db.commit()


def add_transaction(
    db: Session,
    description: str,
    amount: float,
    date_value: date,
    target_type: str,
    account_id: int | None = None,
    card_id: int | None = None,
):
    tx = Transaction(
        description=description,
        amount=amount,
        date=date_value,
        target_type=target_type,
        account_id=account_id,
        card_id=card_id,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


def add_transfer(
    db: Session,
    description: str,
    amount: float,
    date_value: date,
    source_account_id: int,
    target_account_id: int,
):
    transfer = Transfer(
        description=description,
        amount=amount,
        date=date_value,
        source_account_id=source_account_id,
        target_account_id=target_account_id,
    )
    db.add(transfer)
    db.commit()
    db.refresh(transfer)
    return transfer


def remove_transaction(db: Session, transaction_id: int):
    tx = db.query(Transaction).filter_by(id=transaction_id).first()
    if tx:
        db.delete(tx)
        db.commit()


def remove_transfer(db: Session, transfer_id: int):
    tf = db.query(Transfer).filter_by(id=transfer_id).first()
    if tf:
        db.delete(tf)
        db.commit()
