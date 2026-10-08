"""
validacoes.py — validações da seção 5.1 que dependem das regras de cobrança ou
de TODAS as sessões juntas. Só geram avisos (textos); nunca interrompem.

Já ficam no leitor (frente 1) e não são repetidas aqui: sessão sem Fim ou sem
CarroCheio, energia acumulada diminuindo, sessao_id com usuários diferentes.
Se o grupo decidir (pendência 3 da seção 8) que tudo fica no leitor, basta
mover este módulo; o cálculo só consome a lista de avisos.
"""
from __future__ import annotations

from typing import Iterable

from .contrato import Reserva, Sessao
from .parametros import Parametros

TOL_KWH = 0.05      # diferença de medidor tolerada (arredondamento do registrador)


def _min(td) -> int:
    return int(td.total_seconds() // 60)


def antecedencia_das_reservas(reservas: Iterable[Reserva], par: Parametros) -> list[str]:
    """Reserva criada com menos da antecedência mínima (uma vez por reserva)."""
    return [f"{r.id}: criada com menos de {_min(par.antecedencia)} min de antecedência"
            for r in reservas
            if r.criada_em and r.inicio and r.criada_em > r.inicio - par.antecedencia]


def continuidade_do_medidor(sessoes: list[Sessao]) -> list[str]:
    """Saltos do registrador entre sessões consecutivas e sessões sobrepostas.

    Só faz sentido com TODOS os arquivos carregados (um único ponto de recarga).
    """
    avisos = []
    for ant, s in zip(sessoes, sessoes[1:]):
        salto = s.reg_ini - ant.reg_fim
        if salto > TOL_KWH:
            avisos.append(f"{s.id}: medidor avançou {salto:.3f} kWh desde a sessão {ant.id} (consumo fora de sessão)")
        elif salto < -TOL_KWH:
            avisos.append(f"{s.id}: medidor voltou {-salto:.3f} kWh em relação à sessão {ant.id}")
        if s.inicio < ant.fim:
            avisos.append(f"{s.id}: sobreposta à sessão {ant.id}")
    return avisos


def inicio_antes_da_reserva(s: Sessao, par: Parametros) -> list[str]:
    r = s.reserva
    if r and r.inicio and s.inicio < r.inicio - par.tolerancia_inicio:
        return [f"{s.id}: iniciada mais de {_min(par.tolerancia_inicio)} min antes da reserva {r.id}"]
    return []


def leituras_insuficientes(s: Sessao) -> list[str]:
    if len(s.leituras) < 2:
        return [f"{s.id}: leituras insuficientes; energia na faixa do horário de início"]
    return []


def conciliacao(sessoes: list[Sessao], kwh_explicado: float) -> list[str]:
    """O medidor avançou o mesmo que a soma das sessões (cobradas + não identificadas)?"""
    if not sessoes:
        return []
    medido = sessoes[-1].reg_fim - sessoes[0].reg_ini
    if abs(medido - kwh_explicado) > TOL_KWH:
        return [f"Conciliação: o medidor avançou {medido:.2f} kWh; as sessões explicam {kwh_explicado:.2f} kWh; "
                f"diferença {medido - kwh_explicado:.2f} kWh"]
    return []
