"""Inicia o painel a partir de qualquer pasta (ex.: pelo Claude Code ou por um atalho).

    .venv/Scripts/python painel/iniciar.py [--porta 8765]
"""

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
os.chdir(RAIZ)
sys.path.insert(0, str(RAIZ))

from painel.servidor import main  # noqa: E402

sys.exit(main())
