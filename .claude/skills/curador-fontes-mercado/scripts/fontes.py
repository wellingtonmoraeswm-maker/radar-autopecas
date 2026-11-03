"""Atalho da skill para o catalogo de fontes do Radar (a logica fica em coleta/catalogo.py).

Uso (na raiz do repositorio):
    python .claude/skills/curador-fontes-mercado/scripts/fontes.py validar
    python .claude/skills/curador-fontes-mercado/scripts/fontes.py testar <url>
    python .claude/skills/curador-fontes-mercado/scripts/fontes.py verificar [--ids S01,S16] [--gravar]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from coleta.catalogo import main  # noqa: E402

sys.exit(main())
