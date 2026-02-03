from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession, CurrentAdmin
from app.models import Client, Payment
from app.schemas.payment import PaymentCreate, PaymentUpdate, PaymentResponse, PaymentHistoryResponse
from app.utils.helpers import get_subscription_status


router = APIRouter()


@router.get("/clients/{client_id}/payments", response_model=PaymentHistoryResponse)
async def list_client_payments(
    client_id: int,
    db: DBSession,
    admin: CurrentAdmin
):
    """List all payments for a client."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.payments))
        .where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    payments = sorted(client.payments, key=lambda p: p.paid_at, reverse=True)

    current_valid_until = None
    if payments:
        latest = max(payments, key=lambda p: p.valid_until)
        current_valid_until = latest.valid_until

    sub_status, days_left = get_subscription_status(current_valid_until)

    return PaymentHistoryResponse(
        payments=[
            PaymentResponse(
                id=p.id,
                client_id=p.client_id,
                amount=p.amount,
                currency=p.currency,
                paid_at=p.paid_at,
                valid_from=p.valid_from,
                valid_until=p.valid_until,
                status=p.status,
                notes=p.notes
            )
            for p in payments
        ],
        current_valid_until=current_valid_until,
        status=sub_status,
        days_left=days_left
    )


@router.post("/clients/{client_id}/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    client_id: int,
    request: PaymentCreate,
    db: DBSession,
    admin: CurrentAdmin
):
    """Create a new payment for a client."""
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    payment = Payment(
        client_id=client_id,
        amount=request.amount,
        currency=request.currency,
        valid_from=request.valid_from,
        valid_until=request.valid_until,
        status="paid",
        notes=request.notes
    )

    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    return PaymentResponse(
        id=payment.id,
        client_id=payment.client_id,
        amount=payment.amount,
        currency=payment.currency,
        paid_at=payment.paid_at,
        valid_from=payment.valid_from,
        valid_until=payment.valid_until,
        status=payment.status,
        notes=payment.notes
    )


@router.put("/payments/{payment_id}", response_model=PaymentResponse)
async def update_payment(
    payment_id: int,
    request: PaymentUpdate,
    db: DBSession,
    admin: CurrentAdmin
):
    """Update a payment."""
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()

    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")

    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(payment, field, value)

    await db.commit()
    await db.refresh(payment)

    return PaymentResponse(
        id=payment.id,
        client_id=payment.client_id,
        amount=payment.amount,
        currency=payment.currency,
        paid_at=payment.paid_at,
        valid_from=payment.valid_from,
        valid_until=payment.valid_until,
        status=payment.status,
        notes=payment.notes
    )


@router.delete("/payments/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payment(
    payment_id: int,
    db: DBSession,
    admin: CurrentAdmin
):
    """Delete a payment."""
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()

    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")

    await db.delete(payment)
    await db.commit()
