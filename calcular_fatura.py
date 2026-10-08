"""
calcular_fatura.py — fatura mensal do EV ChargeOps (frente 2: rateio e fatura).

Lê os CSVs de uso do carregador (uso_*.csv) com o leitor da frente 1, calcula o
que cada usuário paga no mês e grava a fatura. Todo o cálculo fica em src/rateio;
este arquivo só é a linha de comando.

    total = energia + ociosidade + taxa_sem_reserva + no_show + custo_fixo

Tarifas e taxas: config/parametros_rateio.csv (um parametros_rateio.csv na pasta de
uso sobrescreve só os parâmetros que trouxer).

Uso:
    python calcular_fatura.py [pasta_uso] [pasta_saida]
    (padrões: uso_carregador e fatura_saida, ao lado deste script)
Saídas: fatura_mensal.csv, detalhe_sessoes.csv, avisos.txt (separador ';', decimal ',')
"""
from __future__ import annotations

import sys

from src.rateio.__main__ import main

if __name__ == "__main__":
    sys.exit(main(sys.argv))
