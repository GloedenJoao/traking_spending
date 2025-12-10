from datetime import date
from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import relationship

from .db import Base


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # corrente or caixinha
    balance = Column(Float, default=0.0)

    outgoing_transfers = relationship(
        "Transfer", foreign_keys="Transfer.from_account_id", back_populates="from_account"
    )
    incoming_transfers = relationship(
        "Transfer", foreign_keys="Transfer.to_account_id", back_populates="to_account"
    )


class CreditCard(Base):
    __tablename__ = "credit_cards"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, default="Cartão de Crédito")
    due_day = Column(Integer, default=1)
    open_amount = Column(Float, default=0.0)


class Salary(Base):
    __tablename__ = "salary"

    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Float, default=0.0)
    payday = Column(Integer, default=5)


class ValeBalance(Base):
    __tablename__ = "vale_balances"

    id = Column(Integer, primary_key=True, index=True)
    vale_type = Column(String, unique=True, nullable=False)  # refeicao or alimentacao
    balance = Column(Float, default=0.0)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    date = Column(Date, nullable=False)
    target_type = Column(String, nullable=False)  # account, credit_card, vale_refeicao, vale_alimentacao
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)

    account = relationship("Account")


class Transfer(Base):
    __tablename__ = "transfers"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    date = Column(Date, nullable=False)
    from_account_id = Column(Integer, ForeignKey("accounts.id"))
    to_account_id = Column(Integer, ForeignKey("accounts.id"))

    from_account = relationship("Account", foreign_keys=[from_account_id], back_populates="outgoing_transfers")
    to_account = relationship("Account", foreign_keys=[to_account_id], back_populates="incoming_transfers")


class FutureEvent(Base):
    __tablename__ = "future_events"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False)
    description = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    target = Column(String, nullable=False)
    source = Column(String, default="default")
