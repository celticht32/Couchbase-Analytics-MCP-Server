# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Tests for login/logout/session enforcement."""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestLoginGet:
    def test_login_page_renders(self, gui_client: TestClient) -> None:
        r = gui_client.get("/login")
        assert r.status_code == 200
        assert "Sign in" in r.text
        assert 'name="username"' in r.text
        assert 'name="password"' in r.text

    def test_login_page_when_already_authenticated_redirects(self, gui_client: TestClient) -> None:
        # Log in first
        gui_client.post(
            "/login",
            data={"username": "admin", "password": "test-pass"},
            follow_redirects=False,
        )
        # Now /login should redirect to /
        r = gui_client.get("/login", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/"


class TestLoginPost:
    def test_valid_credentials(self, gui_client: TestClient) -> None:
        r = gui_client.post(
            "/login",
            data={"username": "admin", "password": "test-pass"},
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert r.headers["location"] == "/"
        # Session cookie set
        assert "cb_analytics_session" in r.cookies

    def test_wrong_password(self, gui_client: TestClient) -> None:
        r = gui_client.post(
            "/login",
            data={"username": "admin", "password": "wrong"},
            follow_redirects=False,
        )
        assert r.status_code == 401
        assert "Invalid" in r.text
        # Username is preserved
        assert 'value="admin"' in r.text

    def test_wrong_username(self, gui_client: TestClient) -> None:
        r = gui_client.post(
            "/login",
            data={"username": "evil", "password": "test-pass"},
            follow_redirects=False,
        )
        assert r.status_code == 401

    def test_empty_credentials(self, gui_client: TestClient) -> None:
        r = gui_client.post("/login", data={"username": "", "password": ""})
        # Empty values are rejected (form validation requires both)
        assert r.status_code in (401, 422)


class TestLogout:
    def test_logout_clears_session(self, authenticated_client: TestClient) -> None:
        # Logged in — GET / works
        r = authenticated_client.get("/", follow_redirects=False)
        assert r.status_code == 200

        # Log out
        r = authenticated_client.post("/logout", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/login"

        # Now / should redirect to /login
        r = authenticated_client.get("/", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/login"


class TestSessionEnforcement:
    def test_unauthenticated_dashboard_redirects(self, gui_client: TestClient) -> None:
        r = gui_client.get("/", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/login"

    def test_unauthenticated_query_redirects(self, gui_client: TestClient) -> None:
        r = gui_client.get("/query", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/login"

    def test_unauthenticated_admin_redirects(self, gui_client: TestClient) -> None:
        r = gui_client.get("/admin", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/login"

    def test_unauthenticated_logs_redirects(self, gui_client: TestClient) -> None:
        r = gui_client.get("/logs", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/login"

    def test_unauthenticated_logs_tail_redirects(self, gui_client: TestClient) -> None:
        r = gui_client.get("/logs/tail", follow_redirects=False)
        assert r.status_code == 303

    def test_unauthenticated_post_run_redirects(self, gui_client: TestClient) -> None:
        r = gui_client.post(
            "/query/run",
            data={"statement": "SELECT 1"},
            follow_redirects=False,
        )
        assert r.status_code == 303
