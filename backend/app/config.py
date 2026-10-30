"""Fail-closed configuration: no shared default keys, no client-selected roles."""
import json
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')
DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{ROOT / "governsim.db"}')
API_KEYS = json.loads(os.getenv('GOVERNSIM_API_KEYS', '{}') or '{}')
SEED_DEMO = os.getenv('SEED_DEMO', 'false').lower() == 'true'
FRONTEND_DIST = Path(os.getenv('FRONTEND_DIST', str(ROOT / 'frontend' / 'dist')))
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'offline')
LLM_API_KEY = os.getenv('LLM_API_KEY', '')
LLM_MODEL = os.getenv('LLM_MODEL', '')

# Run bootstrap to create this persistent encryption key. Never commit or rotate it blindly.
AUTH_KEY = os.getenv('GOVERNSIM_AUTH_KEY', '')
AUTH_COOKIE_SECURE = os.getenv('GOVERNSIM_AUTH_COOKIE_SECURE', 'false').lower() == 'true'
AUTH_ALLOWED_ORIGINS = {origin.strip() for origin in os.getenv('GOVERNSIM_AUTH_ORIGINS', 'http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173,http://127.0.0.1:5173').split(',') if origin.strip()}
ALLOW_LEGACY_API_KEYS = os.getenv('GOVERNSIM_ALLOW_LEGACY_API_KEYS', 'false').lower() == 'true'
