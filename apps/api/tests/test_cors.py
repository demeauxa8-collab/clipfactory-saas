"""Browser preflight for the public site reaching a private Tailscale address."""

import subprocess
import sys


def test_private_network_preflight_only_for_allowed_origin():
    # Importing app.main constructs the app, so isolate its settings in a child.
    script = """
from types import SimpleNamespace
import app.settings as settings
settings.get_settings = lambda: SimpleNamespace(
    cors_origins_list=["https://preview.example"], env="prod", is_dev=False
)
from app.main import app
from fastapi.testclient import TestClient
client = TestClient(app)
headers = {
    "Origin": "https://preview.example",
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "authorization,content-type",
    "Access-Control-Request-Private-Network": "true",
}
allowed = client.options("/jobs", headers=headers)
assert allowed.status_code == 200
assert allowed.headers["access-control-allow-origin"] == "https://preview.example"
assert allowed.headers["access-control-allow-private-network"] == "true"
blocked = client.options("/jobs", headers={**headers, "Origin": "https://other.example"})
assert blocked.status_code == 400
assert "access-control-allow-origin" not in blocked.headers
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
