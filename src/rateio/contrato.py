"""
contrato.py — ponto único de importação dos objetos do leitor (frente 1).

Hoje o leitor está em leitor_uso.py na raiz do repositório; o plano (seção 9) é
movê-lo para src/ingestao. Quando isso acontecer, nada muda no rateio.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    from src.ingestao.leitor_uso import (ErroLeitura, EventoReserva, Leitura, Reserva, ResultadoLeitura,
                                         Sessao, UsoSource, UsoUsuario)
except ImportError:
    _raiz = str(Path(__file__).resolve().parents[2])
    if _raiz not in sys.path:
        sys.path.insert(0, _raiz)
    from leitor_uso import (ErroLeitura, EventoReserva, Leitura, Reserva, ResultadoLeitura,  # noqa: E402
                            Sessao, UsoSource, UsoUsuario)

__all__ = ["ErroLeitura", "EventoReserva", "Leitura", "Reserva", "ResultadoLeitura", "Sessao", "UsoSource",
           "UsoUsuario"]
