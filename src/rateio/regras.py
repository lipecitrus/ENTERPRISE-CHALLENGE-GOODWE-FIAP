"""
regras.py — regras de cobrança da seção 3 do Sistema de Leitura, uma função por regra.

Funções puras: recebem objetos do contrato (Sessao, EventoReserva) e os
Parametros; não leem arquivos nem acumulam estado. Os valores em R$ saem daqui
sem arredondar; a fatura arredonda cada cobrança com `centavos` e só então soma,
para que as linhas do detalhe fechem exatamente com o total.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from .contrato import EventoReserva, Sessao
from .parametros import FAIXAS, Parametros

PERDA_DE_ENERGIA = "PowerLoss"


def centavos(v: float) -> float:
    """Arredonda a centavos, meio para cima (R$ 2,955 -> 2,96), sem o viés binário do round()."""
    return float(Decimal(repr(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def faixa(t: datetime, par: Parametros) -> str:
    """Faixa horária do instante t. Fim de semana e feriado = fora de ponta o dia todo."""
    if t.weekday() >= 5 or t.date().isoformat() in par.feriados:
        return "fora_ponta"
    if t.hour in par.horas_ponta:
        return "ponta"
    if t.hour in par.horas_intermediaria:
        return "intermediaria"
    return "fora_ponta"


def kwh_por_faixa(s: Sessao, par: Parametros) -> dict[str, float]:
    """Regra 1: kWh de cada intervalo entre leituras, na faixa do ponto médio do intervalo.

    Intervalos com energia diminuindo contam zero (o leitor já gera o aviso).
    Com menos de 2 leituras, todo o kWh da sessão vai para a faixa do início.
    """
    kwh = dict.fromkeys(FAIXAS, 0.0)
    pts = s.leituras
    if len(pts) < 2:
        kwh[faixa(s.inicio, par)] += max(0.0, s.kwh)
        return kwh
    for a, b in zip(pts, pts[1:]):
        kwh[faixa(a.t + (b.t - a.t) / 2, par)] += max(0.0, b.energia_kwh - a.energia_kwh)
    return kwh


def custo_energia(kwh: dict[str, float], par: Parametros) -> float:
    return sum(k * par.preco[f] for f, k in kwh.items())


def tempo_ocioso_com_fila(s: Sessao, par: Parametros) -> timedelta:
    """Regra 2: tempo após fim_carga + carência, até o Fim, com fila_espera = 1.

    Conta cada intervalo de leitura cuja leitura FINAL tem fila_espera = 1, recortado
    à janela de ociosidade. Sessão interrompida por PowerLoss não tem ociosidade.
    """
    if s.motivo_parada == PERDA_DE_ENERGIA:
        return timedelta()
    ini = s.fim_carga + par.carencia
    espera = timedelta()
    for a, b in zip(s.leituras, s.leituras[1:]):
        if not b.fila_espera:
            continue
        t0, t1 = max(a.t, ini), min(b.t, s.fim)
        if t1 > t0:
            espera += t1 - t0
    return espera


def blocos_ociosidade(espera: timedelta, par: Parametros) -> int:
    """Cada bloco INICIADO conta."""
    return math.ceil(espera / par.bloco) if espera > timedelta() else 0


def custo_ociosidade(blocos: int, par: Parametros) -> float:
    return min(blocos * par.taxa_bloco, par.teto_ociosidade)


def taxa_sem_reserva(s: Sessao, par: Parametros) -> float:
    """Regra 3: sessão avulsa (sem agendamento_id) paga a taxa simples."""
    return 0.0 if s.reserva else par.taxa_sem_reserva


def motivo_cobranca_reserva(e: EventoReserva, par: Parametros) -> Optional[str]:
    """Regra 4: devolve o motivo se o evento de reserva gera no-show, ou None.

    ReservaNaoUtilizada sempre cobra; ReservaCancelada só se feita com menos de
    `antecedencia` do início da reserva. Cancelamento sem reserva_inicio conhecido
    não é cobrado (não dá para provar que foi tardio).
    """
    if e.tipo == "nao_utilizada":
        return "reserva não utilizada"
    if e.tipo == "cancelada" and e.reserva.inicio and e.timestamp > e.reserva.inicio - par.antecedencia:
        return "cancelamento tardio"
    return None


def motivo_nao_identificada(s: Sessao, usuarios_conhecidos: set[str] | dict) -> Optional[str]:
    """Regra 6: por que a sessão não pode ser cobrada de ninguém (None = pode)."""
    if not s.usuario_id:
        return "sem usuário"
    if s.usuario_id not in usuarios_conhecidos:
        return "usuário não cadastrado"
    if not s.identificacao:
        return "sem identificação"
    return None
