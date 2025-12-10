from datetime import date
from typing import List

from fastapi import Depends, FastAPI, Form, Request
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


@app.post("/vales/{vale_type}")
async def update_vale(vale_type: str, balance: float = Form(...), db: Session = Depends(get_db)):
    vale = db.query(ValeBalance).filter_by(vale_type=vale_type).first()
    if vale:
        vale.balance = balance
        db.commit()
    return RedirectResponse("/?tab=config", status_code=303)


@app.get("/dashboard")
async def dashboard(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
        },
    )


@app.post("/simulate/days")
async def update_days(days: int = Form(60)):
    return RedirectResponse(f"/simulate?days={days}", status_code=303)
