"""Unit tests for authentication and allowlist authorization."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from backend import security


def test_verify_token_requires_bearer_credentials() -> None:
    with pytest.raises(HTTPException) as error:
        security.verify_token(None)

    assert error.value.status_code == 401


def test_verify_token_accepts_valid_google_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claims = {
        "sub": "google-subject",
        "email": "person@example.com",
        "email_verified": True,
        "iss": "https://accounts.google.com",
    }
    monkeypatch.setattr(
        security.id_token, "verify_oauth2_token", lambda token, request, audience: claims
    )

    result = security.verify_token(
        HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")
    )

    assert result == claims


def test_verify_token_uses_configured_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claims = {
        "sub": "google-subject",
        "email": "person@example.com",
        "email_verified": True,
        "iss": "https://accounts.google.com",
    }
    captured: dict[str, object] = {}

    def fake_verify(token, request, audience):
        captured["request"] = request
        return claims

    monkeypatch.setattr(
        security.id_token, "verify_oauth2_token", fake_verify
    )
    monkeypatch.setattr(
        security.settings, "https_proxy", "http://proxy.example:3128"
    )
    monkeypatch.setattr(security.settings, "http_proxy", "")

    result = security.verify_token(
        HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")
    )

    request = captured["request"]
    assert result == claims
    assert request.session.trust_env is False
    assert request.session.proxies == {
        "http": "http://proxy.example:3128",
        "https": "http://proxy.example:3128",
    }


def test_verify_token_rejects_wrong_issuer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        security.id_token,
        "verify_oauth2_token",
        lambda token, request, audience: {"iss": "https://attacker.example"},
    )

    with pytest.raises(HTTPException) as error:
        security.verify_token(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")
        )

    assert error.value.status_code == 401


def test_authorization_accepts_allowlisted_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(security, "ALLOWED_EMAILS", {"person@example.com"})
    monkeypatch.setattr(security, "ALLOWED_DOMAINS", set())
    claims = {"email": "Person@Example.com", "email_verified": True}

    assert security.check_authorized_user(claims) == claims


def test_authorization_rejects_allowlisted_but_unverified_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(security, "ALLOWED_EMAILS", {"person@example.com"})
    monkeypatch.setattr(security, "ALLOWED_DOMAINS", set())

    with pytest.raises(HTTPException) as error:
        security.check_authorized_user(
            {"email": "person@example.com", "email_verified": False}
        )

    assert error.value.status_code == 401


def test_authorization_accepts_allowlisted_domain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(security, "ALLOWED_EMAILS", set())
    monkeypatch.setattr(security, "ALLOWED_DOMAINS", {"example.com"})
    claims = {"email": "person@example.com", "email_verified": True}

    assert security.check_authorized_user(claims) == claims


@pytest.mark.parametrize(
    "claims",
    [
        {},
        {"email": "", "email_verified": True},
        {"email": "person@example.com", "email_verified": False},
    ],
)
def test_authorization_rejects_missing_or_unverified_email(
    claims: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(security, "ALLOWED_EMAILS", set())
    monkeypatch.setattr(security, "ALLOWED_DOMAINS", set())

    with pytest.raises(HTTPException) as error:
        security.check_authorized_user(claims)

    assert error.value.status_code == 401


def test_authorization_rejects_valid_but_uninvited_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(security, "ALLOWED_EMAILS", {"invited@example.com"})
    monkeypatch.setattr(security, "ALLOWED_DOMAINS", set())

    with pytest.raises(HTTPException) as error:
        security.check_authorized_user(
            {"email": "other@example.com", "email_verified": True}
        )

    assert error.value.status_code == 403
