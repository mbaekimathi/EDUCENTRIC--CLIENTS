"""Safaricom Daraja STK Push helpers — mirrors ACCOUNTS billing.mpesa initiate path."""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN

from django.utils import timezone

from .finance_models import DarajaSettings

logger = logging.getLogger(__name__)

_TOKEN_CACHE: dict = {"key": "", "token": "", "expires_at": None}


class MpesaApiError(Exception):
    """Raised when a Daraja API call fails or credentials are incomplete."""

    def __init__(self, message: str, *, payload=None, status_code: int | None = None):
        super().__init__(message)
        self.payload = payload or {}
        self.status_code = status_code


def _cache_token_key(settings_obj: DarajaSettings) -> str:
    cfg = settings_obj.active_config()
    return (
        f"{settings_obj.active_environment}:"
        f"{(cfg.get('consumer_key') or '')[:24]}"
    )


def _http_json(method: str, url: str, *, headers=None, data=None, auth=None, timeout=30):
    try:
        import requests
    except ImportError as exc:
        raise MpesaApiError(
            "The requests package is required for M-Pesa STK Push. "
            "Install it with: pip install requests"
        ) from exc

    try:
        response = requests.request(
            method,
            url,
            headers=headers,
            json=data,
            auth=auth,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise MpesaApiError(f"Could not reach Safaricom Daraja: {exc}") from exc

    try:
        payload = response.json() if response.content else {}
    except ValueError:
        payload = {"raw": (response.text or "")[:500]}

    if response.status_code >= 400:
        message = (
            payload.get("errorMessage")
            or payload.get("ResponseDescription")
            or payload.get("error_description")
            or f"HTTP {response.status_code}"
        )
        logger.warning(
            "Daraja %s %s failed status=%s payload=%s",
            method,
            url,
            response.status_code,
            payload,
        )
        raise MpesaApiError(
            str(message),
            payload=payload,
            status_code=response.status_code,
        )

    return payload


def get_access_token(settings_obj: DarajaSettings | None = None) -> str:
    settings_obj = settings_obj or DarajaSettings.load()
    if not settings_obj.is_enabled:
        raise MpesaApiError("M-Pesa is disabled in Accounts payment settings.")
    cfg = settings_obj.active_config()
    if not cfg["consumer_key"] or not cfg["consumer_secret"]:
        raise MpesaApiError("Daraja consumer key/secret are not configured.")

    cache_key = _cache_token_key(settings_obj)
    now = timezone.now()
    if (
        _TOKEN_CACHE.get("key") == cache_key
        and _TOKEN_CACHE.get("token")
        and _TOKEN_CACHE.get("expires_at")
        and _TOKEN_CACHE["expires_at"] > now
    ):
        return _TOKEN_CACHE["token"]

    url = f"{settings_obj.api_base_url}/oauth/v1/generate?grant_type=client_credentials"
    payload = _http_json(
        "GET",
        url,
        auth=(cfg["consumer_key"], cfg["consumer_secret"]),
    )
    token = (payload.get("access_token") or "").strip()
    if not token:
        raise MpesaApiError("Daraja did not return an access token.", payload=payload)

    expires_in = int(payload.get("expires_in") or 3599)
    _TOKEN_CACHE["key"] = cache_key
    _TOKEN_CACHE["token"] = token
    _TOKEN_CACHE["expires_at"] = now + timedelta(seconds=max(60, expires_in - 60))
    return token


def _stk_password(shortcode: str, passkey: str, timestamp: str) -> str:
    raw = f"{shortcode}{passkey}{timestamp}".encode("utf-8")
    return base64.b64encode(raw).decode("utf-8")


def initiate_stk_push(
    *,
    phone_number: str,
    amount: Decimal,
    account_reference: str,
    transaction_desc: str,
    settings_obj: DarajaSettings | None = None,
) -> dict:
    """
    Send a Lipa Na M-Pesa Online STK Push prompt using ACCOUNTS Daraja settings.
    Returns merchant/checkout request ids from Daraja.
    """
    settings_obj = settings_obj or DarajaSettings.load()
    if not settings_obj.stk_ready():
        missing = ", ".join(settings_obj.stk_missing_fields())
        raise MpesaApiError(
            "M-Pesa STK is not fully configured in Accounts. Missing: " f"{missing}."
        )

    cfg = settings_obj.active_config()
    phone = "".join(ch for ch in (phone_number or "") if ch.isdigit())
    if len(phone) < 12:
        raise MpesaApiError("Enter a valid M-Pesa phone number (2547…).")

    amount_int = int(Decimal(amount).quantize(Decimal("1"), rounding=ROUND_DOWN))
    if amount_int < 1:
        raise MpesaApiError("STK Push amount must be at least KES 1.")

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    token = get_access_token(settings_obj)
    payload = {
        "BusinessShortCode": cfg["shortcode"],
        "Password": _stk_password(cfg["shortcode"], cfg["passkey"], timestamp),
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount_int,
        "PartyA": phone,
        "PartyB": cfg["shortcode"],
        "PhoneNumber": phone,
        "CallBackURL": cfg["callback_url"],
        "AccountReference": (account_reference or "FEES")[:12],
        "TransactionDesc": "".join(
            ch for ch in (transaction_desc or "SchoolFees") if ch.isalnum()
        )[:13]
        or "SchoolFees",
    }
    url = f"{settings_obj.api_base_url}/mpesa/stkpush/v1/processrequest"
    response = _http_json(
        "POST",
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        data=payload,
    )

    response_code = str(response.get("ResponseCode", ""))
    if response_code not in {"0", "00"}:
        raise MpesaApiError(
            response.get("ResponseDescription")
            or response.get("CustomerMessage")
            or "STK Push was rejected by Daraja.",
            payload=response,
        )

    return {
        "merchant_request_id": str(response.get("MerchantRequestID") or ""),
        "checkout_request_id": str(response.get("CheckoutRequestID") or ""),
        "customer_message": str(response.get("CustomerMessage") or ""),
        "response_description": str(response.get("ResponseDescription") or ""),
        "raw": response,
    }
