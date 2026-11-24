"""JWT configuration isolation and startup behavior tests."""
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_pytest_bootstrap_sets_secret_before_importing_auth_or_application():
    script = """
import os
import runpy
import sys
runpy.run_path('tests/test_backend/conftest.py')
assert 'JWT_SECRET_KEY' in os.environ
assert 'backend.auth.security' not in sys.modules
import backend.auth.security as security
assert security.SECRET_KEY == os.environ['JWT_SECRET_KEY']
import backend.api.main
print('bootstrap-ok')
"""
    env = os.environ.copy()
    env.pop("JWT_SECRET_KEY", None)
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "bootstrap-ok"


def test_security_import_fails_when_deployment_secret_is_missing():
    # Disable dotenv loading in the isolated process so a developer's local
    # .env file cannot hide the missing deployment environment variable.
    script = """
import dotenv
dotenv.load_dotenv = lambda *args, **kwargs: None
import backend.auth.security
"""
    env = os.environ.copy()
    env.pop("JWT_SECRET_KEY", None)
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "JWT_SECRET_KEY is not configured" in result.stderr
