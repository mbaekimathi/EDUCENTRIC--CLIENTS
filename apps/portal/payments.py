"""Parent portal fee payments via ACCOUNTS M-Pesa STK Push."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db import OperationalError, ProgrammingError

from .finance_models import (
    DarajaSettings,
    FeeCharge,
    MpesaCallbackLog,
    SchoolAccount,
    StkPushRequest,
    student_finance_balance,
)
from .mpesa import MpesaApiError, initiate_stk_push
from .models import AcademicLevel, ParentGuardian, Student


def normalize_msisdn(raw: str) -> str:
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    if digits.startswith("254") and len(digits) >= 12:
        return digits[:12]
    if digits.startswith("0") and len(digits) >= 10:
        return "254" + digits[1:10]
    if len(digits) == 9:
        return "254" + digits
    return digits


def format_msisdn_display(phone: str) -> str:
    digits = normalize_msisdn(phone)
    if len(digits) == 12 and digits.startswith("254"):
        local = "0" + digits[3:]
        return f"{local[:4]} {local[4:7]} {local[7:]}"
    return (phone or "").strip() or "—"


def student_level_key_from_curriculum(level: AcademicLevel) -> str | None:
    """Map curriculum AcademicLevel to Student.academic_level choice value."""
    valid = {choice for choice, _ in Student.AcademicLevel.choices}
    name_key = (
        (level.name or "")
        .strip()
        .upper()
        .replace("-", " ")
        .replace("  ", " ")
        .replace(" ", "_")
    )
    if name_key in valid:
        return name_key
    code = (level.code or "").strip().upper()
    code_map = {
        "G1": "GRADE_1",
        "G2": "GRADE_2",
        "G3": "GRADE_3",
        "G4": "GRADE_4",
        "G5": "GRADE_5",
        "G6": "GRADE_6",
        "G7": "GRADE_7",
        "G8": "GRADE_8",
        "G9": "GRADE_9",
        "PP1": "PRE_PRIMARY_1",
        "PP2": "PRE_PRIMARY_2",
        "F1": "FORM_1",
        "F2": "FORM_2",
        "F3": "FORM_3",
        "F4": "FORM_4",
    }
    mapped = code_map.get(code)
    if mapped in valid:
        return mapped
    return None


def resolve_student_fees_account(student: Student) -> SchoolAccount | None:
    """Pick the active student-fees account covering this learner (and M-Pesa)."""
    try:
        accounts = list(
            SchoolAccount.objects.filter(
                category=SchoolAccount.Category.STUDENT_FEES,
                is_active=True,
            ).order_by("name")
        )
    except (OperationalError, ProgrammingError):
        return None

    mpesa_accounts = [
        account
        for account in accounts
        if SchoolAccount.PaymentMode.MPESA in (account.payment_modes or [])
    ]
    if not mpesa_accounts:
        return None

    level_ids = set()
    for account in mpesa_accounts:
        for level_id in account.academic_level_ids or []:
            try:
                level_ids.add(int(level_id))
            except (TypeError, ValueError):
                continue

    key_by_level_id = {}
    if level_ids:
        for level in AcademicLevel.objects.filter(id__in=level_ids):
            key = student_level_key_from_curriculum(level)
            if key:
                key_by_level_id[level.id] = key

    student_key = student.academic_level
    matched = []
    fallback = []
    for account in mpesa_accounts:
        linked = []
        for level_id in account.academic_level_ids or []:
            try:
                linked.append(int(level_id))
            except (TypeError, ValueError):
                continue
        if not linked:
            fallback.append(account)
            continue
        if any(key_by_level_id.get(level_id) == student_key for level_id in linked):
            matched.append(account)

    if matched:
        return matched[0]
    if fallback:
        return fallback[0]
    return mpesa_accounts[0]


def parent_payment_context(*, student: Student, parent: ParentGuardian | None) -> dict:
    """Template context for the finances pay panel (parents only)."""
    if parent is None:
        return {
            "can_pay_fees": False,
            "stk_ready": False,
            "stk_unavailable_reason": "",
            "pay_phone_display": "",
            "pay_phone_raw": "",
            "fee_account": None,
        }

    phone = normalize_msisdn(parent.phone_number or "")

    try:
        daraja = DarajaSettings.load()
        stk_ready = daraja.stk_ready()
        missing = daraja.stk_missing_fields()
    except DarajaSettings.DoesNotExist:
        daraja = None
        stk_ready = False
        missing = ["Accounts Daraja settings not found"]
    except (OperationalError, ProgrammingError):
        daraja = None
        stk_ready = False
        missing = ["Accounts payment tables unavailable"]

    account = resolve_student_fees_account(student)
    reason = ""
    can_pay = False
    if account is None:
        reason = "No student-fees account with M-Pesa is active in Accounts yet."
    elif not stk_ready:
        detail = ", ".join(missing) if missing else "incomplete configuration"
        reason = f"M-Pesa STK Push is not ready in Accounts ({detail})."
    else:
        can_pay = True

    return {
        "can_pay_fees": can_pay,
        "stk_ready": stk_ready,
        "stk_unavailable_reason": reason,
        "pay_phone_display": format_msisdn_display(parent.phone_number or ""),
        "pay_phone_raw": phone,
        "fee_account": account,
        "daraja_enabled": bool(daraja and daraja.is_enabled),
    }


def parse_payment_amount(raw: str) -> Decimal:
    amount = Decimal(str(raw).strip())
    if amount <= 0:
        raise InvalidOperation
    # M-Pesa STK uses whole shillings.
    return amount.quantize(Decimal("1"))


def stk_request_payload(stk: StkPushRequest, *, include_finance: bool = False) -> dict:
    failed = stk.status in {
        StkPushRequest.Status.FAILED,
        StkPushRequest.Status.CANCELLED,
    }
    success = (
        stk.status == StkPushRequest.Status.SUCCESS and bool(stk.mpesa_receipt)
    )
    finance = {}
    if include_finance or success:
        totals = student_finance_balance(stk.student_id)
        finance = {
            "total_charged": f"{totals['total_charged']:.2f}",
            "total_paid": f"{totals['total_paid']:.2f}",
            "balance": f"{totals['balance']:.2f}",
        }
    return {
        "id": stk.id,
        "status": stk.status,
        "status_label": stk.get_status_display(),
        "amount": f"{stk.amount:.2f}",
        "phone_number": stk.phone_number,
        "phone_display": format_msisdn_display(stk.phone_number),
        "merchant_request_id": stk.merchant_request_id,
        "checkout_request_id": stk.checkout_request_id,
        "mpesa_receipt": stk.mpesa_receipt,
        "result_code": stk.result_code,
        "result_desc": stk.result_desc,
        "failed": failed,
        "cancelled": stk.status == StkPushRequest.Status.CANCELLED,
        "failure_message": stk.result_desc if failed else "",
        "awaiting_receipt": bool(
            stk.status == StkPushRequest.Status.SUCCESS and not stk.mpesa_receipt
        ),
        **finance,
    }


def refresh_stk_from_callback_logs(stk: StkPushRequest) -> StkPushRequest:
    """
    Sync portal view of STK status from ACCOUNTS callback logs.

    Payment allocation is owned by the ACCOUNTS callback handler; this only
    mirrors status fields so the parent UI can stop polling.
    """
    stk.refresh_from_db()
    if stk.status != StkPushRequest.Status.PENDING and not (
        stk.status == StkPushRequest.Status.SUCCESS and not stk.mpesa_receipt
    ):
        return stk

    qs = MpesaCallbackLog.objects.all()
    callback = None
    if stk.checkout_request_id:
        callback = (
            qs.filter(checkout_request_id=stk.checkout_request_id)
            .order_by("-created_at")
            .first()
        )
    if callback is None and stk.merchant_request_id:
        callback = (
            qs.filter(merchant_request_id=stk.merchant_request_id)
            .order_by("-created_at")
            .first()
        )
    if callback is None:
        return stk

    # Prefer ACCOUNTS-updated STK row if callback already completed payment there.
    stk.refresh_from_db()
    if callback.status == MpesaCallbackLog.Status.SUCCESS:
        if stk.status == StkPushRequest.Status.PENDING or (
            stk.status == StkPushRequest.Status.SUCCESS and not stk.mpesa_receipt
        ):
            # ACCOUNTS normally completes the row; if still pending, surface receipt
            # for UI while Accounts finishes allocation on its side.
            update_fields = []
            if callback.mpesa_receipt and not stk.mpesa_receipt:
                stk.mpesa_receipt = callback.mpesa_receipt
                update_fields.append("mpesa_receipt")
            if stk.status != StkPushRequest.Status.SUCCESS:
                stk.status = StkPushRequest.Status.SUCCESS
                update_fields.append("status")
            if callback.result_desc and stk.result_desc != callback.result_desc:
                stk.result_desc = callback.result_desc
                update_fields.append("result_desc")
            if callback.result_code is not None:
                stk.result_code = callback.result_code
                update_fields.append("result_code")
            if callback.payment_id and not stk.payment_id:
                stk.payment_id = callback.payment_id
                update_fields.append("payment_id")
            if update_fields:
                update_fields.append("updated_at")
                stk.save(update_fields=update_fields)
        return stk

    if callback.status == MpesaCallbackLog.Status.FAILED and stk.status == StkPushRequest.Status.PENDING:
        cancelled = callback.result_code in {1032, 1031}
        stk.status = (
            StkPushRequest.Status.CANCELLED if cancelled else StkPushRequest.Status.FAILED
        )
        stk.result_code = callback.result_code
        stk.result_desc = callback.result_desc or (
            "Payment cancelled on the phone." if cancelled else "Payment failed."
        )
        stk.save(
            update_fields=["status", "result_code", "result_desc", "updated_at"]
        )
    return stk


def initiate_parent_stk_payment(
    *,
    student: Student,
    parent: ParentGuardian,
    amount_raw: str,
    phone_raw: str = "",
) -> dict:
    """
    Parent self-prompt STK to an entered M-Pesa phone (defaults to profile).
    Creates accounts_stk_push_request; ACCOUNTS callback records the payment.
    """
    if student.parent_guardian_id != parent.pk:
        raise PermissionError("You can only pay fees for your linked learner.")

    ctx_account = resolve_student_fees_account(student)
    if ctx_account is None:
        raise ValueError("No student-fees account with M-Pesa is available.")

    try:
        daraja = DarajaSettings.load()
    except DarajaSettings.DoesNotExist as exc:
        raise ValueError("Accounts Daraja settings are not configured.") from exc

    if not daraja.stk_ready():
        missing = ", ".join(daraja.stk_missing_fields())
        raise ValueError(f"M-Pesa STK Push is not ready ({missing}).")

    phone = normalize_msisdn(phone_raw or parent.phone_number or "")
    if len(phone) != 12 or not phone.startswith("254"):
        raise ValueError(
            "Enter a valid Kenyan M-Pesa number (e.g. 07XX XXX XXX)."
        )

    try:
        amount = parse_payment_amount(amount_raw)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("Enter a valid amount of at least KES 1.") from exc

    # Soft guard: allow overpaying slightly but block nonsense huge amounts.
    balance = student_finance_balance(student.pk)["balance"]
    open_charges = FeeCharge.objects.filter(student_id=student.pk).exclude(
        status__in=(FeeCharge.Status.CANCELLED, FeeCharge.Status.WAIVED)
    ).exists()
    if not open_charges and balance <= 0:
        raise ValueError("There are no open fee charges to pay for this learner.")
    if amount > max(balance, Decimal("1")) + Decimal("500000"):
        raise ValueError("That amount looks too large. Check and try again.")

    account_reference = f"STU{student.id}"[:12]
    try:
        initiated = initiate_stk_push(
            phone_number=phone,
            amount=amount,
            account_reference=account_reference,
            transaction_desc="SchoolFees",
            settings_obj=daraja,
        )
    except MpesaApiError:
        raise

    stk = StkPushRequest.objects.create(
        student_id=student.id,
        account=ctx_account,
        amount=amount,
        phone_number=phone,
        account_reference=account_reference,
        merchant_request_id=initiated["merchant_request_id"],
        checkout_request_id=initiated["checkout_request_id"],
        status=StkPushRequest.Status.PENDING,
        result_desc=initiated.get("customer_message") or "STK prompt sent.",
        notes="Initiated from parent portal",
        created_by_id=None,
    )
    return {
        "message": initiated.get("customer_message")
        or f"STK prompt sent to {format_msisdn_display(phone)}. Enter your M-Pesa PIN.",
        "stk": stk_request_payload(stk),
    }
