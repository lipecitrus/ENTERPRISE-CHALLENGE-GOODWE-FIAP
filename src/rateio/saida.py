"""
saida.py — grava a fatura em CSV (separador ';', decimal ',') e imprime o resumo.

Arquivos e cabeçalhos estáveis, para a frente 3 importar: fatura_mensal.csv,
detalhe_sessoes.csv, avisos.txt.
"""
from __future__ import annotations

import csv
from pathlib import Path

from .fatura import ResultadoRateio

CAB_FATURA = ["competencia", "unidade_id", "usuario_id", "nome", "sessoes", "kwh_total", "kwh_fora_ponta", "kwh_intermediaria",
              "kwh_ponta", "custo_energia", "ociosidade", "taxa_sem_agendamento", "no_show", "custo_fixo", "total"]
CAB_DETALHE = ["sessao_id", "usuario_id", "agendamento_id", "inicio", "fim", "duracao_min", "kwh", "custo_energia",
               "ociosidade", "taxa_sem_agendamento", "no_show", "total", "observacao"]


def num(v: float, casas: int = 2) -> str:
    return f"{v:.{casas}f}".replace(".", ",")


def brl(v: float) -> str:
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _dh(t) -> str:
    return f"{t:%Y-%m-%d %H:%M}" if t else ""


def gravar(r: ResultadoRateio, pasta_saida: str | Path) -> list[Path]:
    saida = Path(pasta_saida)
    saida.mkdir(parents=True, exist_ok=True)
    arq_fatura, arq_detalhe, arq_avisos = saida / "fatura_mensal.csv", saida / "detalhe_sessoes.csv", saida / "avisos.txt"

    with open(arq_fatura, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(CAB_FATURA)
        for x in r.faturas:
            w.writerow([x.competencia, x.unidade_id, x.usuario_id, x.nome, x.sessoes, num(x.kwh),
                        num(x.kwh_na_faixa("fora_ponta")), num(x.kwh_na_faixa("intermediaria")),
                        num(x.kwh_na_faixa("ponta")), num(x.energia), num(x.ociosidade), num(x.taxa_sem_reserva),
                        num(x.no_show), num(x.custo_fixo), num(x.total)])

    with open(arq_detalhe, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(CAB_DETALHE)
        for i in r.detalhe:
            sessao = i.tipo == "sessao"
            w.writerow([i.sessao_id, i.usuario_id, i.agendamento_id, _dh(i.inicio), _dh(i.fim),
                        i.duracao_min if sessao else "", num(i.kwh, 3), num(i.energia), num(i.ociosidade),
                        num(i.taxa_sem_reserva), num(i.no_show), num(i.total), i.observacao])

    arq_avisos.write_text("".join(a + "\n" for a in r.avisos), encoding="utf-8")
    return [arq_fatura, arq_detalhe, arq_avisos]


def resumo(r: ResultadoRateio, pasta_saida: str | Path | None = None) -> str:
    linhas = [f"Competência {r.competencia or '(sem dados)'}: {len(r.arquivos)} arquivo(s) de uso lidos, "
              f"{r.n_sessoes} sessões reconstruídas", "",
              f"{'unid':6}{'usuário':24}{'sess':>5}{'kWh':>8}{'energia':>10}{'ocios.':>8}{'s/res':>7}"
              f"{'no-show':>8}{'fixo':>7}{'TOTAL':>10}"]
    for x in r.faturas:
        linhas.append(f"{x.unidade_id:6}{x.nome[:23]:24}{x.sessoes:>5}{x.kwh:8.1f}{brl(x.energia):>10}"
                      f"{brl(x.ociosidade):>8}{brl(x.taxa_sem_reserva):>7}{brl(x.no_show):>8}"
                      f"{brl(x.custo_fixo):>7}{brl(x.total):>10}")
    linhas.append(f"{'':58}{'TOTAL A ARRECADAR':>25}  R$ {brl(r.total_arrecadar)}")
    if r.nao_identificadas:
        ni = r.nao_identificadas
        linhas.append(f"NAO_IDENTIFICADO: {len(ni)} sessão(ões), {sum(i.kwh for i in ni):.2f} kWh, "
                      f"R$ {brl(sum(i.energia for i in ni))} pendentes")
    onde = f" — ver {Path(pasta_saida) / 'avisos.txt'}" if r.avisos and pasta_saida else ""
    linhas.append(f"{len(r.avisos)} aviso(s){onde}")
    linhas += [f"  aviso: {a}" for a in r.avisos[:10]]
    return "\n".join(linhas)
