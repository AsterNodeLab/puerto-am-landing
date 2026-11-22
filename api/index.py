"""Punto de entrada de Vercel: expone la app FastAPI del backend como función."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app import app  # noqa: E402,F401
