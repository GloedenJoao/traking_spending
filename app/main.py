from datetime import date, datetime
from typing import Optional

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .database import Base, engine, get_session
from .models import Account, Card, Salary, Transaction, Transfer
from .services import (
    add_transaction,
    add_transfer,
    build_simulation,
    ensure_defaults,
    save_account,
    update_card,
    update_checking_balance,
    update_salary,
)

app = FastAPI(title="Simulador de Gastos")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)


@app.get("/")
def read_home(request: Request, db: Session = Depends(get_session)):
    checking, card, salary = ensure_defaults(db)
    cdb_accounts = db.query(Account).filter_by(type="cdb").order_by(Account.id).all()
    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "checking": checking,
            "cdb_accounts": cdb_accounts,
            "card": card,
            "salary": salary,
        },
    )


@app.post("/accounts/checking")
def update_checking(balance: float = Form(...), db: Session = Depends(get_session)):
    update_checking_balance(db, balance)
    return RedirectResponse("/", status_code=303)


@app.post("/accounts")
def create_cdb_account(
    name: str = Form(...),
    balance: float = Form(0.0),
    db: Session = Depends(get_session),
):
    save_account(db, name=name, balance=balance, acc_type="cdb")
    return RedirectResponse("/", status_code=303)


@app.post("/accounts/{account_id}/balance")
def update_account_balance(
    account_id: int,
    balance: float = Form(...),
    db: Session = Depends(get_session),
):
    account = db.query(Account).filter_by(id=account_id).first()
    if account:
        account.balance = balance
        db.commit()
    return RedirectResponse("/", status_code=303)


@app.post("/card")
def update_card_info(
    name: str = Form(...),
    due_day: int = Form(...),
    invoice: float = Form(0.0),
    db: Session = Depends(get_session),
):
    update_card(db, name=name, due_day=due_day, invoice=invoice)
    return RedirectResponse("/", status_code=303)


@app.post("/salary")
def update_salary_info(
    amount: float = Form(0.0),
    pay_day: int = Form(...),
    db: Session = Depends(get_session),
):
    update_salary(db, amount=amount, pay_day=pay_day)
    return RedirectResponse("/", status_code=303)


@app.get("/simulation")
def view_simulation(
    request: Request,
    days: int = 60,
    db: Session = Depends(get_session),
):
    today = date.today()
    daily_data, accounts, card, future_events = build_simulation(db, today, days)
    checking, _, salary = ensure_defaults(db)
    return templates.TemplateResponse(
        "simulation.html",
        {
            "request": request,
            "daily_data": daily_data,
            "accounts": accounts,
            "card": card,
            "future_events": future_events,
            "days": days,
            "checking": checking,
            "salary": salary,
        },
    )


@app.post("/transactions")
def create_transaction(
    description: str = Form(...),
    amount: float = Form(...),
    date_value: str = Form(...),
    target_type: str = Form(...),
    account_id: Optional[int] = Form(None),
    card_id: Optional[int] = Form(None),
    db: Session = Depends(get_session),
):
    parsed_date = datetime.strptime(date_value, "%Y-%m-%d").date()
    add_transaction(
        db,
        description=description,
        amount=amount,
        date_value=parsed_date,
        target_type=target_type,
        account_id=account_id if target_type == "account" else None,
        card_id=card_id if target_type == "card" else None,
    )
    return RedirectResponse("/simulation", status_code=303)


@app.post("/transfers")
def create_transfer(
    description: str = Form(...),
    amount: float = Form(...),
    date_value: str = Form(...),
    source_account_id: int = Form(...),
    target_account_id: int = Form(...),
    db: Session = Depends(get_session),
):
    parsed_date = datetime.strptime(date_value, "%Y-%m-%d").date()
    add_transfer(
        db,
        description=description,
        amount=amount,
        date_value=parsed_date,
        source_account_id=source_account_id,
        target_account_id=target_account_id,
    )
    return RedirectResponse("/simulation", status_code=303)


@app.get("/transactions/{transaction_id}/delete")
def delete_transaction(transaction_id: int, db: Session = Depends(get_session)):
    tx = db.query(Transaction).filter_by(id=transaction_id).first()
    if tx:
        db.delete(tx)
        db.commit()
    return RedirectResponse("/simulation", status_code=303)


@app.get("/transfers/{transfer_id}/delete")
def delete_transfer(transfer_id: int, db: Session = Depends(get_session)):
    tf = db.query(Transfer).filter_by(id=transfer_id).first()
    if tf:
        db.delete(tf)
        db.commit()
    return RedirectResponse("/simulation", status_code=303)


@app.get("/health")
def health_check():
    return {"status": "ok"}
