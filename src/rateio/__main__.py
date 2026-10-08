"""
Uso (a partir da raiz do repositório):
    python -m src.rateio [pasta_uso] [pasta_saida]
    (padrões: uso_carregador e fatura_saida, na raiz)
"""
from __future__ import annotations

import sys

from .contrato import ErroLeitura
from .fatura import calcular_da_pasta
from .parametros import RAIZ, ErroParametros
from .saida import gravar, resumo


def main(argv: list[str]) -> int:
    base = argv[1] if len(argv) > 1 else RAIZ / "uso_carregador"
    saida = argv[2] if len(argv) > 2 else RAIZ / "fatura_saida"
    try:
        r = calcular_da_pasta(base)
    except (ErroLeitura, ErroParametros) as e:
        print(f"[ERRO] {e}  (para gerar dados: python gerar_uso_carregador.py)")
        return 1
    gravar(r, saida)
    print(resumo(r, saida))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
