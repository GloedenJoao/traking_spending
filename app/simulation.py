from datetime import date, timedelta
from typing import Dict, List, Tuple

from .models import (
    Account,
    CreditCard,
    Salary,
    SimulationEvent,
    Transaction,
    Transfer,
    ValeBalance,
)
from .utils import adjust_to_previous_business_day, penultimate_business_day, daterange

VALE_REFEICAO_VALUE = 1236.40
VALE_ALIMENTACAO_VALUE = 974.16


def ensure_defaults(db_session):
    if not db_session.query(Account).filter_by(type="corrente").first():
        db_session.add(Account(name="Conta Corrente", type="corrente", balance=0.0))
    card = db_session.query(CreditCard).first()
    if not card:
        db_session.add(CreditCard(name="Cartão de Crédito", due_day=10, open_amount=0.0))
    elif card.open_amount > 0:
        card.open_amount = -abs(card.open_amount)
    if not db_session.query(Salary).first():
        db_session.add(Salary(amount=0.0, payday=5))
    for vale_type in ["vale_refeicao", "vale_alimentacao"]:
        if not db_session.query(ValeBalance).filter_by(vale_type=vale_type).first():
            db_session.add(ValeBalance(vale_type=vale_type, balance=0.0))
    db_session.commit()


def build_monthly_events(
    start_date: date,
    days: int,
    salary: Salary,
    credit_card: CreditCard,
    corrente_account_id: int,
) -> Dict[date, List[Dict[str, object]]]:
    events: Dict[date, List[Dict[str, object]]] = {}
    end_date = start_date + timedelta(days=days)

    current = start_date.replace(day=1)
    while current <= end_date:
        salary_date = adjust_to_previous_business_day(
            date(current.year, current.month, salary.payday)
        )
        if start_date <= salary_date <= end_date:
            events.setdefault(salary_date, []).append(
                {
                    "description": "Salário",
                    "amount": salary.amount,
                    "tag": "account:corrente",
                    "account_id": corrente_account_id,
                }
            )

        penultimate = penultimate_business_day(current.year, current.month)
        if start_date <= penultimate <= end_date:
            events.setdefault(penultimate, []).append(
                {
                    "description": "Crédito Vale Refeição",
                    "amount": VALE_REFEICAO_VALUE,
                    "tag": "vale:vale_refeicao",
                    "account_id": None,
                }
            )
            events[penultimate].append(
                {
                    "description": "Crédito Vale Alimentação",
                    "amount": VALE_ALIMENTACAO_VALUE,
                    "tag": "vale:vale_alimentacao",
                    "account_id": None,
                }
            )

        due_day = adjust_to_previous_business_day(
            date(current.year, current.month, credit_card.due_day)
        )
        if start_date <= due_day <= end_date:
            events.setdefault(due_day, []).append(
                {
                    "description": "Pagamento fatura",
                    "amount": -1.0,
                    "tag": "credit_card:pay",
                    "account_id": corrente_account_id,
                }
            )

        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return events


def consolidate_events(
    db_session, start_date: date, days: int, accounts: List[Account]
):
    end_date = start_date + timedelta(days=days)
    salary = db_session.query(Salary).first()
    credit_card = db_session.query(CreditCard).first()

    corrente = next((acc for acc in accounts if acc.type == "corrente"), None)
    corrente_id = corrente.id if corrente else None

    db_session.query(SimulationEvent).filter(
        SimulationEvent.date.between(start_date, end_date)
    ).delete()

    monthly_events = build_monthly_events(
        start_date, days, salary, credit_card, corrente_id
    )
    for day, items in monthly_events.items():
        for evt in items:
            db_session.add(
                SimulationEvent(
                    date=day,
                    description=evt["description"],
                    amount=evt["amount"],
                    tag=evt["tag"],
                    account_id=evt.get("account_id"),
                )
            )

    transactions = (
        db_session.query(Transaction)
        .filter(Transaction.date.between(start_date, end_date))
        .all()
    )
    for txn in transactions:
        db_session.add(
            SimulationEvent(
                date=txn.date,
                description=txn.description,
                amount=txn.amount,
                tag=f"txn:{txn.target_type}",
                account_id=txn.account_id,
            )
        )

    transfers = (
        db_session.query(Transfer)
        .filter(Transfer.date.between(start_date, end_date))
        .all()
    )
    for mov in transfers:
        db_session.add(
            SimulationEvent(
                date=mov.date,
                description=mov.description,
                amount=-mov.amount,
                tag=f"transfer:from:{mov.from_account_id}",
                account_id=mov.from_account_id,
            )
        )
        db_session.add(
            SimulationEvent(
                date=mov.date,
                description=mov.description,
                amount=mov.amount,
                tag=f"transfer:to:{mov.to_account_id}",
                account_id=mov.to_account_id,
            )
        )

    db_session.commit()


def simulate(db_session, start_date: date, days: int):
    accounts = db_session.query(Account).all()
    salary = db_session.query(Salary).first()
    credit_card = db_session.query(CreditCard).first()
    vale_ref = db_session.query(ValeBalance).filter_by(vale_type="vale_refeicao").first()
    vale_alim = db_session.query(ValeBalance).filter_by(vale_type="vale_alimentacao").first()

    account_balances = {acc.id: acc.balance for acc in accounts}
    vale_balances = {
        "vale_refeicao": vale_ref.balance if vale_ref else 0.0,
        "vale_alimentacao": vale_alim.balance if vale_alim else 0.0,
    }
    card_balance = -abs(credit_card.open_amount) if credit_card else 0.0

    consolidate_events(db_session, start_date, days, accounts)
    events = (
        db_session.query(SimulationEvent)
        .filter(
            SimulationEvent.date >= start_date,
            SimulationEvent.date <= start_date + timedelta(days=days),
        )
        .order_by(SimulationEvent.date, SimulationEvent.id)
        .all()
    )

    events_by_date: Dict[date, List[SimulationEvent]] = {}
    for event in events:
        events_by_date.setdefault(event.date, []).append(event)

    rows = []
    event_log: List[Tuple[date, str, float, str]] = []

    for day in daterange(start_date, days):
        for evt in events_by_date.get(day, []):
            actual_amount = evt.amount
            if evt.tag == "account:corrente" and evt.account_id:
                account_balances[evt.account_id] += evt.amount
            elif evt.tag.startswith("vale:"):
                vale_key = evt.tag.split(":")[1]
                vale_balances[vale_key] += evt.amount
            elif evt.tag == "credit_card:pay":
                if evt.account_id and card_balance != 0:
                    payment = abs(card_balance)
                    account_balances[evt.account_id] -= payment
                    actual_amount = -payment
                    card_balance = 0.0
                else:
                    actual_amount = 0.0
            elif evt.tag == "txn:account" and evt.account_id:
                account_balances[evt.account_id] += evt.amount
            elif evt.tag == "txn:credit_card":
                card_balance += evt.amount
            elif evt.tag == "txn:vale_refeicao":
                vale_balances["vale_refeicao"] += evt.amount
            elif evt.tag == "txn:vale_alimentacao":
                vale_balances["vale_alimentacao"] += evt.amount
            elif evt.tag.startswith("transfer:from") and evt.account_id:
                account_balances[evt.account_id] += evt.amount
            elif evt.tag.startswith("transfer:to") and evt.account_id:
                account_balances[evt.account_id] += evt.amount
            event_log.append((day, evt.description, actual_amount, evt.tag))

        rows.append(
            {
                "date": day,
                "accounts": {acc.id: account_balances[acc.id] for acc in accounts},
                "vales": dict(vale_balances),
                "credit_card": card_balance,
            }
        )

    return rows, event_log
