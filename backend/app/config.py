"""Fail-closed configuration: no shared default keys, no client-selected roles."""
import json
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')
DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{ROOT / "governsim.db"}')
API_KEYS = json.loads(os.getenv('GOVERNSIM_API_KEYS', '{}'))
SEED_DEMO = os.getenv('SEED_DEMO', 'false').lower() == 'true'
FRONTEND_DIST = Path(os.getenv('FRONTEND_DIST', str(ROOT / 'frontend' / 'dist')))
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'offline')
LLM_API_KEY = os.getenv('LLM_API_KEY', '')
LLM_MODEL = os.getenv('LLM_MODEL', '')
