"""Read-only mirrors of ACCOUNTS billing tables for the parent/student portal."""

from decimal import Decimal

from django.db import models


class FeeCategory(models.Model):
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=40)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = "accounts_fee_category"
        ordering = ["name"]

    def __str__(self):
        return f"{self.code} — {self.name}"


class FeeCharge(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        PARTIAL = "PARTIAL", "Partially paid"
        PAID = "PAID", "Paid"
        WAIVED = "WAIVED", "Waived"
        CANCELLED = "CANCELLED", "Cancelled"

    student_id = models.PositiveBigIntegerField(db_index=True)
    category = models.ForeignKey(
        FeeCategory,
        on_delete=models.DO_NOTHING,
        related_name="charges",
        db_constraint=False,
    )
    title = models.CharField(max_length=200)
    academic_year = models.CharField(max_length=20, blank=True)
    term = models.CharField(max_length=40, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "accounts_fee_charge"
        ordering = ["-created_at"]

    @property
    def balance(self):
        return self.amount - self.amount_paid


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = "CASH", "Cash"
        MPESA = "MPESA", "M-Pesa"
        BANK = "BANK", "Bank transfer"
        CHEQUE = "CHEQUE", "Cheque"
        OTHER = "OTHER", "Other"

    student_id = models.PositiveBigIntegerField(db_index=True)
    charge = models.ForeignKey(
        FeeCharge,
        on_delete=models.DO_NOTHING,
        related_name="payments",
        null=True,
        blank=True,
        db_constraint=False,
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.CASH)
    reference = models.CharField(max_length=120, blank=True)
    received_at = models.DateTimeField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "accounts_payment"
        ordering = ["-received_at"]


def student_finance_summary(student_id: int) -> dict:
    charges = list(
        FeeCharge.objects.filter(student_id=student_id)
        .select_related("category")
        .order_by("-created_at")
    )
    payments = list(
        Payment.objects.filter(student_id=student_id)
        .select_related("charge", "charge__category")
        .order_by("-received_at")
    )
    active = [
        c
        for c in charges
        if c.status not in (FeeCharge.Status.CANCELLED, FeeCharge.Status.WAIVED)
    ]
    total_charged = sum((c.amount for c in active), Decimal("0.00"))
    total_paid = sum((c.amount_paid for c in active), Decimal("0.00"))
    balance = total_charged - total_paid
    return {
        "charges": charges,
        "payments": payments,
        "total_charged": total_charged,
        "total_paid": total_paid,
        "balance": balance,
    }
