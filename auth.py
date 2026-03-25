"""
auth.py — Authentication boundary for V3.
Supports: none (open), reverse_proxy (header-based), basic (password).
Designed to wrap the Streamlit dashboard.
"""

import os
import hmac
import hashlib
import logging
from typing import Optional, Tuple

logger = logging.getLogger("auth")


def check_reverse_proxy_auth(
    headers: dict,
    header_name: str = "X-Forwarded-User",
    allowed_users: Optional[list] = None,
) -> Tuple[bool, str]:
    """
    Validate that a reverse proxy has set the expected user header.
    Returns (authenticated, username).
    """
    user = headers.get(header_name, "")
    if not user:
        return False, ""
    if allowed_users and user not in allowed_users:
        logger.warning(f"User '{user}' not in allowed_users list")
        return False, user
    return True, user


def check_basic_auth(provided_password: str) -> bool:
    """
    Validate a password against the DASHBOARD_PASSWORD env var.
    Uses constant-time comparison to prevent timing attacks.
    """
    expected = os.environ.get("DASHBOARD_PASSWORD", "")
    if not expected:
        logger.warning("DASHBOARD_PASSWORD not set — basic auth will reject all attempts")
        return False
    return hmac.compare_digest(provided_password.encode(), expected.encode())


def streamlit_auth_gate(auth_config) -> Optional[str]:
    """
    Apply authentication in Streamlit context.
    Returns the authenticated username, or None if auth is disabled.
    Blocks the app with st.stop() if auth fails.
    """
    if not auth_config.enabled or auth_config.provider == "none":
        return None

    import streamlit as st

    if auth_config.provider == "reverse_proxy":
        try:
            headers = dict(st.context.headers)
        except Exception:
            headers = {}
        ok, user = check_reverse_proxy_auth(
            headers,
            header_name=auth_config.header_name,
            allowed_users=auth_config.allowed_users or None,
        )
        if not ok:
            st.error("Access denied. This dashboard requires authentication via reverse proxy.")
            st.info(
                f"Expected header: `{auth_config.header_name}`. "
                "Contact your administrator if you believe this is an error."
            )
            st.stop()
        return user

    if auth_config.provider == "basic":
        if "authenticated" not in st.session_state:
            st.session_state.authenticated = False

        if not st.session_state.authenticated:
            st.markdown("### RivalSense — Login")
            password = st.text_input("Password", type="password", key="auth_password_input")
            if st.button("Login", key="auth_login_btn"):
                if check_basic_auth(password):
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Invalid password.")
            st.stop()
        return "authenticated_user"

    return None
