from datetime import date
from sqlalchemy import Column, Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .database import Base


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(
        String, nullable=False
    )  # checking, cdb, vale_transporte, vale_alimentacao, vale_refeicao
    balance = Column(Float, default=0.0)

    outgoing_transfers = relationship(
        "Transfer", foreign_keys="Transfer.source_account_id", back_populates="source"
    )
    incoming_transfers = relationship(
        "Transfer", foreign_keys="Transfer.target_account_id", back_populates="target"
    )
    transactions = relationship("Transaction", back_populates="account")


class Card(Base):
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    due_day = Column(Integer, nullable=False, default=5)
    current_invoice = Column(Float, default=0.0)

    transactions = relationship("Transaction", back_populates="card")


class Salary(Base):
    __tablename__ = "salaries"

    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Float, default=0.0)
    pay_day = Column(Integer, default=5)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    date = Column(Date, nullable=False)
    target_type = Column(String, nullable=False)  # account or card
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=True)

    account = relationship("Account", back_populates="transactions")
    card = relationship("Card", back_populates="transactions")


class Transfer(Base):
    __tablename__ = "transfers"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    date = Column(Date, nullable=False)
    source_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    target_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)

    source = relationship(
        "Account", foreign_keys=[source_account_id], back_populates="outgoing_transfers"
    )
    target = relationship(
        "Account", foreign_keys=[target_account_id], back_populates="incoming_transfers"
    )
