from datetime import date, timedelta
from typing import Dict, List, Tuple

from .models import (
    Account,
    CreditCard,
    FutureEvent,
    Salary,
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


def sync_default_events(
    db_session, start_date: date, days: int, salary: Salary, credit_card: CreditCard
):
    end_date = start_date + timedelta(days=days)

    db_session.query(FutureEvent).filter(
        FutureEvent.source == "default",
        FutureEvent.date >= start_date,
        FutureEvent.date <= end_date,
    ).delete()

    events: List[FutureEvent] = []
    current = start_date.replace(day=1)
    while current <= end_date:
        salary_date = adjust_to_previous_business_day(
            date(current.year, current.month, salary.payday)
        )
        if start_date <= salary_date <= end_date:
            events.append(
                FutureEvent(
                    date=salary_date,
                    description="Salário",
                    amount=salary.amount,
                    target="account:corrente",
                )
            )

        penultimate = penultimate_business_day(current.year, current.month)
        if start_date <= penultimate <= end_date:
            events.append(
                FutureEvent(
                    date=penultimate,
                    description="Crédito Vale Refeição",
                    amount=VALE_REFEICAO_VALUE,
                    target="vale:vale_refeicao",
                )
            )
            events.append(
                FutureEvent(
                    date=penultimate,
                    description="Crédito Vale Alimentação",
                    amount=VALE_ALIMENTACAO_VALUE,
                    target="vale:vale_alimentacao",
                )
            )

        due_day = adjust_to_previous_business_day(
            date(current.year, current.month, credit_card.due_day)
        )
        if start_date <= due_day <= end_date:
            events.append(
                FutureEvent(
                    date=due_day,
                    description="Pagamento fatura",
                    amount=-1.0,
                    target="credit_card:pay",
                )
            )

        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)

    if events:
        db_session.add_all(events)
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

    sync_default_events(db_session, start_date, days, salary, credit_card)

    end_date = start_date + timedelta(days=days)
    default_events = (
        db_session.query(FutureEvent)
        .filter(FutureEvent.date >= start_date, FutureEvent.date <= end_date)
        .order_by(FutureEvent.date, FutureEvent.id)
        .all()
    )

    events_by_day: Dict[date, List[FutureEvent]] = {}
    for evt in default_events:
        events_by_day.setdefault(evt.date, []).append(evt)

    transactions = db_session.query(Transaction).all()
    transfers = db_session.query(Transfer).all()

    rows = []
    event_log: List[Tuple[date, str, float, str]] = []

    for day in daterange(start_date, days):
        for evt in events_by_day.get(day, []):
            actual_amount = evt.amount
            if evt.target == "account:corrente":
                corrente = next((acc for acc in accounts if acc.type == "corrente"), None)
                if corrente:
                    account_balances[corrente.id] += evt.amount
            elif evt.target.startswith("vale:"):
                vale_key = evt.target.split(":")[1]
                vale_balances[vale_key] += evt.amount
            elif evt.target == "credit_card:pay":
                corrente = next((acc for acc in accounts if acc.type == "corrente"), None)
                if corrente and card_balance != 0:
                    payment = abs(card_balance)
                    account_balances[corrente.id] -= payment
                    actual_amount = -payment
                    card_balance = 0.0
                else:
                    actual_amount = 0.0
            event_log.append((day, evt.description, actual_amount, evt.target))

        for txn in [t for t in transactions if t.date == day]:
            if txn.target_type == "account" and txn.account_id:
                account_balances[txn.account_id] += txn.amount
            elif txn.target_type == "credit_card":
                card_balance += txn.amount
            elif txn.target_type == "vale_refeicao":
                vale_balances["vale_refeicao"] += txn.amount
            elif txn.target_type == "vale_alimentacao":
                vale_balances["vale_alimentacao"] += txn.amount
            event_log.append((day, txn.description, txn.amount, f"txn:{txn.target_type}"))

        for mov in [m for m in transfers if m.date == day]:
            if mov.from_account_id in account_balances and mov.to_account_id in account_balances:
                account_balances[mov.from_account_id] -= mov.amount
                account_balances[mov.to_account_id] += mov.amount
                event_log.append(
                    (day, mov.description, -mov.amount, f"transfer:from:{mov.from_account_id}")
                )
                event_log.append(
                    (day, mov.description, mov.amount, f"transfer:to:{mov.to_account_id}")
                )

        rows.append(
            {
                "date": day,
                "accounts": {acc.id: account_balances[acc.id] for acc in accounts},
                "vales": dict(vale_balances),
                "credit_card": card_balance,
            }
        )

    return rows, event_log
