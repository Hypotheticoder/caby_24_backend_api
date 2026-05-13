from pydantic import BaseModel


class WithdrawRequestPayload(BaseModel):
    amount: float


class PayUSuccessPayload(BaseModel):
    txnid: str
    amount: float
