import json
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import Depends, FastAPI, Form, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .db import Base, engine, SessionLocal
from .models import Account, CreditCard, Salary, Transaction, Transfer, ValeBalance
from .simulation import ensure_defaults, simulate
from .utils import expand_date_ranges

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Tracking Spending")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
templates.env.filters["brl"] = lambda value: "R$ " + f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def get_db():
    db = SessionLocal()
    try:
        ensure_defaults(db)
        yield db
    finally:
        db.close()


@app.get("/")
async def read_root(request: Request, db: Session = Depends(get_db)):
    accounts = db.query(Account).all()
    card = db.query(CreditCard).first()
    salary = db.query(Salary).first()
    vales = db.query(ValeBalance).all()
    caixinhas = [acc for acc in accounts if acc.type == "caixinha"]
    corrente = next((acc for acc in accounts if acc.type == "corrente"), None)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "accounts": accounts,
            "caixinhas": caixinhas,
            "corrente": corrente,
            "card": card,
            "salary": salary,
            "vales": vales,
        },
    )


@app.post("/account/corrente")
async def update_corrente(balance: float = Form(...), db: Session = Depends(get_db)):
    corrente = db.query(Account).filter_by(type="corrente").first()
    if corrente:
        corrente.balance = balance
        db.commit()
    return RedirectResponse("/?tab=config", status_code=303)


@app.post("/account/caixinha")
async def add_caixinha(name: str = Form(...), balance: float = Form(0), db: Session = Depends(get_db)):
    db.add(Account(name=name, type="caixinha", balance=balance))
    db.commit()
    return RedirectResponse("/?tab=config", status_code=303)


@app.post("/account/caixinha/{account_id}")
async def edit_caixinha(account_id: int, name: str = Form(...), balance: float = Form(...), db: Session = Depends(get_db)):
    acc = db.query(Account).filter_by(id=account_id, type="caixinha").first()
    if acc:
        acc.name = name
        acc.balance = balance
        db.commit()
    return RedirectResponse("/?tab=config", status_code=303)


@app.post("/credit-card")
async def update_card(
    name: str = Form("Cartão de Crédito"),
    due_day: int = Form(10),
    open_amount: float = Form(0.0),
    db: Session = Depends(get_db),
):
    card = db.query(CreditCard).first()
    card.name = name
    card.due_day = due_day
    card.open_amount = -abs(open_amount)
    db.commit()
    return RedirectResponse("/?tab=config", status_code=303)


@app.post("/salary")
async def update_salary(amount: float = Form(...), payday: int = Form(...), db: Session = Depends(get_db)):
    salary = db.query(Salary).first()
    salary.amount = amount
    salary.payday = payday
    db.commit()
    return RedirectResponse("/?tab=config", status_code=303)


@app.get("/simulate")
async def show_simulation(request: Request, days: int = 60, db: Session = Depends(get_db)):
    today = date.today()
    rows, event_log = simulate(db, today, days)
    accounts = db.query(Account).all()
    vales = db.query(ValeBalance).all()
    transactions = db.query(Transaction).order_by(Transaction.date, Transaction.id).all()
    transfers = db.query(Transfer).order_by(Transfer.date, Transfer.id).all()
    account_lookup = {acc.id: acc.name for acc in accounts}

    simulation_groups = []

    for txn in transactions:
        key = (
            "transaction",
            txn.description,
            txn.amount,
            txn.target_type,
            txn.account_id,
        )
        simulation_groups.append(
            {
                "kind": "transaction",
                "key": key,
                "description": txn.description,
                "amount": txn.amount,
                "target_type": txn.target_type,
                "account_id": txn.account_id,
                "dates": [txn.date],
                "ids": [txn.id],
            }
        )

    for mov in transfers:
        key = (
            "transfer",
            mov.description,
            mov.amount,
            mov.from_account_id,
            mov.to_account_id,
        )
        simulation_groups.append(
            {
                "kind": "transfer",
                "key": key,
                "description": mov.description,
                "amount": mov.amount,
                "from_account_id": mov.from_account_id,
                "to_account_id": mov.to_account_id,
                "dates": [mov.date],
                "ids": [mov.id],
            }
        )

    merged_groups = {}
    for group in simulation_groups:
        key = group["key"]
        if key not in merged_groups:
            merged_groups[key] = group
        else:
            merged_groups[key]["dates"].extend(group["dates"])
            merged_groups[key]["ids"].extend(group["ids"])

    ordered_groups = []
    for group in merged_groups.values():
        group["dates"].sort()
        group["ids"].sort()
        group["first_date"] = group["dates"][0]
        group["date_count"] = len(group["dates"])
        ordered_groups.append(group)

    ordered_groups.sort(key=lambda item: (item["first_date"], item["description"]))

    return templates.TemplateResponse(
        "simulate.html",
        {
            "request": request,
            "rows": rows,
            "days": days,
            "accounts": accounts,
            "vales": vales,
            "transactions": transactions,
            "transfers": transfers,
            "simulation_groups": ordered_groups,
            "account_lookup": account_lookup,
            "event_log": sorted(event_log, key=lambda e: e[0]),
        },
    )


@app.post("/transactions")
async def add_transaction(
    description: str = Form(...),
    amount: float = Form(...),
    date_start: List[str] = Form(...),
    date_end: List[str] = Form(None),
    transaction_type: str = Form("debit"),
    target_type: str = Form(...),
    account_id: int = Form(None),
    db: Session = Depends(get_db),
):
    signed_amount = amount if transaction_type == "credit" else -amount
    dates = expand_date_ranges(date_start, date_end or [])
    for txn_date in dates:
        txn = Transaction(
            description=description,
            amount=signed_amount,
            date=txn_date,
            target_type=target_type,
            account_id=account_id if target_type == "account" else None,
        )
        db.add(txn)
    db.commit()
    return RedirectResponse("/simulate", status_code=303)


@app.post("/transactions/{transaction_id}/delete")
async def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    txn = db.query(Transaction).filter_by(id=transaction_id).first()
    if txn:
        db.delete(txn)
        db.commit()
    return RedirectResponse("/simulate", status_code=303)


@app.post("/transactions/bulk-delete")
async def bulk_delete_transactions(transaction_ids: List[int] = Form(...), db: Session = Depends(get_db)):
    for transaction_id in transaction_ids:
        txn = db.query(Transaction).filter_by(id=transaction_id).first()
        if txn:
            db.delete(txn)
    db.commit()
    return RedirectResponse("/simulate", status_code=303)


@app.post("/transfers")
async def add_transfer(
    description: str = Form(...),
    amount: float = Form(...),
    date_start: List[str] = Form(...),
    date_end: List[str] = Form(None),
    from_account_id: int = Form(...),
    to_account_id: int = Form(...),
    db: Session = Depends(get_db),
):
    if from_account_id == to_account_id:
        return RedirectResponse("/simulate", status_code=303)

    dates = expand_date_ranges(date_start, date_end or [])
    for transfer_date in dates:
        transfer = Transfer(
            description=description,
            amount=amount,
            date=transfer_date,
            from_account_id=from_account_id,
            to_account_id=to_account_id,
        )
        db.add(transfer)
    db.commit()
    return RedirectResponse("/simulate", status_code=303)


@app.post("/transfers/{transfer_id}/delete")
async def delete_transfer(transfer_id: int, db: Session = Depends(get_db)):
    transfer = db.query(Transfer).filter_by(id=transfer_id).first()
    if transfer:
        db.delete(transfer)
        db.commit()
    return RedirectResponse("/simulate", status_code=303)


@app.post("/transfers/bulk-delete")
async def bulk_delete_transfers(transfer_ids: List[int] = Form(...), db: Session = Depends(get_db)):
    for transfer_id in transfer_ids:
        transfer = db.query(Transfer).filter_by(id=transfer_id).first()
        if transfer:
            db.delete(transfer)
    db.commit()
    return RedirectResponse("/simulate", status_code=303)


@app.post("/simulations/clear")
async def clear_simulations(db: Session = Depends(get_db)):
    db.query(Transaction).delete()
    db.query(Transfer).delete()
    db.commit()
    return RedirectResponse("/simulate", status_code=303)


@app.post("/vales/{vale_type}")
async def update_vale(vale_type: str, balance: float = Form(...), db: Session = Depends(get_db)):
    vale = db.query(ValeBalance).filter_by(vale_type=vale_type).first()
    if vale:
        vale.balance = balance
        db.commit()
    return RedirectResponse("/?tab=config", status_code=303)


@app.get("/dashboard")
async def dashboard(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    account_ids: Optional[List[int]] = Query(None),
    db: Session = Depends(get_db),
):
    base_date = date.today()
    if start_date:
        try:
            base_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            base_date = date.today()

    tomorrow = date.today() + timedelta(days=1)

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            end_dt = base_date + timedelta(days=29)
    else:
        end_dt = base_date + timedelta(days=29)

    validation_notes = []

    if end_dt <= date.today():
        validation_notes.append("A data final deve ser maior que hoje; usamos o próximo dia disponível.")
        end_dt = tomorrow

    if end_dt <= base_date:
        validation_notes.append("A data final precisa ser posterior à data inicial; janela ajustada automaticamente.")
        end_dt = base_date + timedelta(days=1)

    requested_span = (end_dt - base_date).days + 1
    days = max(1, min(requested_span, 365))
    if requested_span > 365:
        validation_notes.append("Limitamos a janela a 365 dias a partir do início.")
    end_dt = base_date + timedelta(days=days - 1)

    rows, _ = simulate(db, base_date, days)
    accounts = db.query(Account).all()
    vale_labels = {
        "vale_refeicao": "Vale Refeição",
        "vale_alimentacao": "Vale Alimentação",
    }

    selected_accounts = set(account_ids) if account_ids else {acc.id for acc in accounts}

    labels = [row["date"].strftime("%d/%m") for row in rows]
    account_series = []
    vale_series = []

    for acc in accounts:
        balances = [row["accounts"].get(acc.id, 0.0) for row in rows]
        final_value = balances[-1] if balances else 0.0
        changes = []
        for current in balances:
            if current == 0:
                changes.append(None)
            else:
                changes.append(((final_value - current) / abs(current)) * 100)
        account_series.append({
            "id": acc.id,
            "name": acc.name,
            "balances": balances,
            "changes": changes,
        })

    vale_keys = rows[0]["vales"].keys() if rows else []
    for key in vale_keys:
        balances = [row["vales"].get(key, 0.0) for row in rows]
        latest = balances[-1] if balances else 0.0
        first = balances[0] if balances else None
        delta = latest - first if first is not None else None
        delta_pct = ((latest - first) / abs(first) * 100) if first not in (None, 0) else None

        changes = []
        start_changes = []
        for current in balances:
            if current == 0:
                changes.append(None)
            else:
                changes.append(((latest - current) / abs(current)) * 100)

            if first in (None, 0):
                start_changes.append(None)
            else:
                start_changes.append(((current - first) / abs(first)) * 100)

        vale_series.append(
            {
                "id": key,
                "name": vale_labels.get(key, key.replace("_", " ").title()),
                "balances": balances,
                "delta": delta,
                "delta_pct": delta_pct,
                "latest": latest,
                "prev": first,
                "changes": changes,
                "start_changes": start_changes,
            }
        )

    total_values = []
    for row in rows:
        total_values.append(sum(row["accounts"].values()) + row["credit_card"])

    total_prev = total_values[0] if total_values else None
    total_final = total_values[-1] if total_values else 0.0
    total_changes = []
    total_start_changes = []
    for current in total_values:
        if current == 0:
            total_changes.append(None)
        else:
            total_changes.append(((total_final - current) / abs(current)) * 100)

        if total_prev in (None, 0):
            total_start_changes.append(None)
        else:
            total_start_changes.append(((current - total_prev) / abs(total_prev)) * 100)

    summary_cards = []
    for series in account_series:
        latest = series["balances"][-1] if series["balances"] else 0.0
        first = series["balances"][0] if series["balances"] else None
        delta = latest - first if first is not None else None
        delta_pct = ((latest - first) / abs(first) * 100) if first not in (None, 0) else None
        summary_cards.append(
            {
                "name": series["name"],
                "latest": latest,
                "prev": first,
                "delta": delta,
                "delta_pct": delta_pct,
            }
        )

    total_delta = total_values[-1] - total_prev if total_prev is not None else None
    total_delta_pct = ((total_values[-1] - total_prev) / abs(total_prev) * 100) if total_prev not in (None, 0) else None

    selected_account_ids = list(selected_accounts)

    total_vale_values = [sum(row["vales"].values()) for row in rows]
    total_vale_prev = total_vale_values[0] if total_vale_values else None
    total_vale_final = total_vale_values[-1] if total_vale_values else 0.0
    total_vale_delta = total_vale_final - total_vale_prev if total_vale_prev is not None else None
    total_vale_delta_pct = (
        (total_vale_final - total_vale_prev) / abs(total_vale_prev) * 100
        if total_vale_prev not in (None, 0)
        else None
    )

    total_vale_changes = []
    total_vale_start_changes = []
    for current in total_vale_values:
        if current == 0:
            total_vale_changes.append(None)
        else:
            total_vale_changes.append(((total_vale_final - current) / abs(current)) * 100)

        if total_vale_prev in (None, 0):
            total_vale_start_changes.append(None)
        else:
            total_vale_start_changes.append(((current - total_vale_prev) / abs(total_vale_prev)) * 100)

    vale_summary_cards = [
        {
            "name": "Total dos vales",
            "latest": total_vale_values[-1] if total_vale_values else 0.0,
            "prev": total_vale_prev,
            "delta": total_vale_delta,
            "delta_pct": total_vale_delta_pct,
        }
    ]
    for series in vale_series:
        vale_summary_cards.append(
            {
                "name": series["name"],
                "latest": series["latest"],
                "prev": series["prev"],
                "delta": series["delta"],
                "delta_pct": series["delta_pct"],
            }
        )

    chart_payload = {
        "labels": labels,
        "accounts": account_series,
        "total": {
            "values": total_values,
            "changes": total_changes,
            "start_changes": total_start_changes,
        },
        "vales": {
            "series": vale_series,
            "total": {
                "values": total_vale_values,
                "changes": total_vale_changes,
                "start_changes": total_vale_start_changes,
            },
        },
    }

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "chart_data": json.dumps(chart_payload),
            "summary_cards": summary_cards,
            "total_summary": {
                "latest": total_values[-1] if total_values else 0.0,
                "prev": total_prev,
                "delta": total_delta,
                "delta_pct": total_delta_pct,
            },
            "accounts": accounts,
            "selected_account_ids": selected_account_ids,
            "selected_accounts_json": json.dumps(selected_account_ids),
            "vale_summary_cards": vale_summary_cards,
            "vale_total_summary": {
                "latest": total_vale_values[-1] if total_vale_values else 0.0,
                "prev": total_vale_prev,
                "delta": total_vale_delta,
                "delta_pct": total_vale_delta_pct,
            },
            "start_date": base_date.isoformat(),
            "end_date": end_dt.isoformat(),
            "min_end_date": tomorrow.isoformat(),
            "validation_message": " ".join(validation_notes) if validation_notes else None,
        },
    )


@app.post("/simulate/days")
async def update_days(days: int = Form(60)):
    return RedirectResponse(f"/simulate?days={days}", status_code=303)
