"""Dashboard security regressions, with a synthetic database and no network.

Run with: python -m unittest discover -s tests -v
The application's startup is intercepted before importing it: no .env is loaded,
no SQLite file is opened, no Gemini client is created, and no worker is started.
"""

import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_isolated_app():
    memory_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    google_stub = types.ModuleType("google")
    google_stub.genai = types.SimpleNamespace(Client=Mock(return_value=None))
    spec = importlib.util.spec_from_file_location("isolated_dashboard_app", ROOT / "app.py")
    module = importlib.util.module_from_spec(spec)
    with (
        patch.dict(os.environ, {}, clear=True),
        patch.dict(sys.modules, {"google": google_stub}),
        patch("dotenv.load_dotenv", return_value=False) as load_env,
        patch("sqlmodel.create_engine", return_value=memory_engine) as make_engine,
        patch("threading.Thread") as make_thread,
        patch("requests.sessions.Session.request", side_effect=AssertionError("network forbidden")),
    ):
        spec.loader.exec_module(module)
    load_env.assert_called_once_with()
    make_engine.assert_called_once_with("sqlite:///database.db")
    make_thread.return_value.start.assert_called_once_with()
    module.app.config.update(TESTING=True)
    return module


MODULE = load_isolated_app()
TOKEN = "synthetic-test-token-for-dashboard-only"


def tearDownModule():
    MODULE.engine.dispose()


class DashboardSecurityTests(unittest.TestCase):
    def setUp(self):
        SQLModel.metadata.drop_all(MODULE.engine)
        SQLModel.metadata.create_all(MODULE.engine)
        MODULE.app.config["DASHBOARD_TOKEN"] = TOKEN
        self.client = MODULE.app.test_client()
        self.headers = {"Authorization": f"Bearer {TOKEN}"}

    def assert_no_dashboard_data_access(self, status, **kwargs):
        with patch.object(MODULE, "Session", side_effect=AssertionError("database forbidden")) as session:
            response = self.client.get("/dashboard", **kwargs)
        self.assertEqual(response.status_code, status)
        session.assert_not_called()
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertNotIn("Histórico de Conversas", response.get_data(as_text=True))
        return response

    def seed_conversation(self, ip="192.0.2.1", message="synthetic message", reply="synthetic reply"):
        with Session(MODULE.engine) as session:
            user = MODULE.User(ip_address=ip)
            session.add(user)
            session.commit()
            session.refresh(user)
            session.add(MODULE.Conversation(
                user_id=user.id, user_message=message, ai_response=reply
            ))
            session.commit()

    def test_disabled_without_configured_token(self):
        for token in (None, "", "  "):
            with self.subTest(token=token):
                MODULE.app.config["DASHBOARD_TOKEN"] = token
                self.assert_no_dashboard_data_access(404, headers=self.headers)

    def test_missing_authorization_is_rejected_before_database_access(self):
        response = self.assert_no_dashboard_data_access(401)
        self.assertEqual(response.headers["WWW-Authenticate"], 'Bearer realm="dashboard"')

    def test_invalid_authorization_is_rejected_before_database_access(self):
        for authorization in ("Bearer wrong", f"Basic {TOKEN}", "Bearer", "Bearer ", "Bearer não-ascii"):
            with self.subTest(authorization=authorization):
                self.assert_no_dashboard_data_access(401, headers={"Authorization": authorization})

    def test_query_string_cannot_supply_token(self):
        self.assert_no_dashboard_data_access(401, query_string={"token": TOKEN})

    def test_valid_bearer_uses_constant_time_comparison(self):
        with patch.object(MODULE.hmac, "compare_digest", wraps=MODULE.hmac.compare_digest) as compare:
            response = self.client.get("/dashboard", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        compare.assert_called_once_with(TOKEN.encode(), TOKEN.encode())
        self.assertIn("Nenhuma conversa encontrada.", response.get_data(as_text=True))

    def test_bearer_scheme_is_case_insensitive(self):
        response = self.client.get("/dashboard", headers={"Authorization": f"bearer {TOKEN}"})
        self.assertEqual(response.status_code, 200)

    def test_message_and_ai_output_are_escaped(self):
        self.seed_conversation(message="<script>alert('user')</script>", reply='<img src=x onerror="alert(1)">')
        response = self.client.get("/dashboard", headers=self.headers)
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&lt;img src=x onerror=&#34;alert(1)&#34;&gt;", html)
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img ", html)

    def test_ip_is_escaped_in_attribute_and_text(self):
        malicious_ip = '\"><script>alert("ip")</script>'
        self.seed_conversation(ip=malicious_ip)
        response = self.client.get("/dashboard", headers=self.headers, query_string={"ip": malicious_ip})
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('value="&#34;&gt;&lt;script&gt;alert(&#34;ip&#34;)&lt;/script&gt;" selected', html)
        self.assertNotIn("<script>", html)

    def test_authorized_ip_filter_preserves_query_behavior(self):
        self.seed_conversation(ip="192.0.2.1", message="first synthetic conversation")
        self.seed_conversation(ip="192.0.2.2", message="second synthetic conversation")
        response = self.client.get("/dashboard", headers=self.headers, query_string={"ip": "192.0.2.2"})
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("first synthetic conversation", html)
        self.assertIn("second synthetic conversation", html)
        self.assertIn('value="192.0.2.2" selected', html)

    def test_authorized_responses_are_not_cached_or_embeddable(self):
        response = self.client.get("/dashboard", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertIn("Authorization", response.vary)
        self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
        self.assertIn("default-src 'none'", response.headers["Content-Security-Policy"])

    def test_public_liveness_routes_still_work_without_dashboard_token(self):
        MODULE.app.config["DASHBOARD_TOKEN"] = None
        self.assertEqual(self.client.get("/ping").status_code, 200)
        self.assertEqual(self.client.get("/health").status_code, 200)


if __name__ == "__main__":
    unittest.main()
