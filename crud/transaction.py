from sqlalchemy.orm import Session
from models.transaction import Transaction
from schemas.transaction import TransactionCreate


def create_transaction(db: Session, tx_in: TransactionCreate) -> Transaction:
    # Build the database object, but let the Router decide when to commit!
    db_obj = Transaction(**tx_in.model_dump())
    db.add(db_obj)
    return db_obj


def get_driver_transactions(db: Session, driver_id: str, limit: int = 50):
    # Fetch the ledger history, newest first
    return (
        db.query(Transaction)
        .filter(Transaction.driver_id == driver_id)
        .order_by(Transaction.created_at.desc())
        .limit(limit)
        .all()
    )


def create_pending_withdrawal(db: Session, driver_id: str, amount: float):
    new_tx = Transaction(
        driver_id=driver_id,
        order_id=None,
        amount=amount,
        transaction_type="withdrawal",
        payment_mode="bank",
        title="Bank Transfer (Pending)",
        status="pending",
    )
    db.add(new_tx)
    db.commit()
    db.refresh(new_tx)
    return new_tx


def create_successful_settlement(db: Session, driver_id: str, amount: float):
    new_tx = Transaction(
        driver_id=driver_id,
        order_id=None,
        amount=amount,
        transaction_type="settlement",
        payment_mode="payu",
        title="Platform Fees Paid",
        status="completed",
    )
    db.add(new_tx)
    db.commit()
    db.refresh(new_tx)
    return new_tx
