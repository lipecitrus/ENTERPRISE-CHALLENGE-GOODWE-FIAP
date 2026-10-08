"""
fatura.py — cálculo da fatura mensal por usuário (frente 2: rateio e fatura).

Entrada: ResultadoLeitura do leitor (contrato da frente 1) + Parametros.
Saída:   ResultadoRateio, com uma Fatura por usuário, o detalhe de cada cobrança
         (CobrancaSessao), as sessões NAO_IDENTIFICADO e os avisos.

    total = energia + ociosidade + taxa_sem_reserva + no_show + custo_fixo

Cada cobrança é arredondada a centavos ao ser criada; a fatura só soma valores já
arredondados, então as linhas do detalhe fecham exatamente com o total.

Os objetos Fatura e CobrancaSessao são o que a frente 3 grava no banco e mostra
no painel/app; nenhum deles depende do formato do CSV.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import regras, validacoes
from .contrato import ResultadoLeitura, Sessao, UsoSource
from .parametros import FAIXAS, Parametros, carregar_parametros
from .regras import centavos

NAO_IDENTIFICADO = "NAO_IDENTIFICADO"


@dataclass
class CobrancaSessao:
    """Uma linha do detalhe: uma sessão de recarga ou uma cobrança de reserva (no-show).

    Valores em R$ já arredondados a centavos; kWh sem arredondar.
    """
    tipo: str                                   # sessao | no_show
    usuario_id: str                             # NAO_IDENTIFICADO quando não cobrada de ninguém
    unidade_id: str
    sessao_id: str = ""
    agendamento_id: str = ""
    inicio: Optional[datetime] = None
    fim: Optional[datetime] = None
    duracao_min: int = 0
    kwh: float = 0.0
    kwh_faixa: dict[str, float] = field(default_factory=lambda: dict.fromkeys(FAIXAS, 0.0))
    energia: float = 0.0
    minutos_ociosos: int = 0
    blocos_ociosidade: int = 0
    ociosidade: float = 0.0
    taxa_sem_reserva: float = 0.0
    no_show: float = 0.0
    observacao: str = ""

    def __post_init__(self):
        for campo in ("energia", "ociosidade", "taxa_sem_reserva", "no_show"):
            setattr(self, campo, centavos(getattr(self, campo)))

    @property
    def total(self) -> float:
        return centavos(self.energia + self.ociosidade + self.taxa_sem_reserva + self.no_show)


@dataclass
class Fatura:
    """Fatura mensal de um usuário (uma unidade) em uma competência (AAAA-MM)."""
    usuario_id: str
    nome: str
    unidade_id: str
    custo_fixo: float
    competencia: str = ""
    itens: list[CobrancaSessao] = field(default_factory=list)

    def _soma(self, campo: str) -> float:
        return centavos(sum(getattr(i, campo) for i in self.itens))

    @property
    def sessoes(self) -> int:
        return sum(1 for i in self.itens if i.tipo == "sessao")

    @property
    def kwh(self) -> float:
        return sum(i.kwh for i in self.itens)

    def kwh_na_faixa(self, f: str) -> float:
        return sum(i.kwh_faixa[f] for i in self.itens)

    @property
    def energia(self) -> float:
        return self._soma("energia")

    @property
    def ociosidade(self) -> float:
        return self._soma("ociosidade")

    @property
    def taxa_sem_reserva(self) -> float:
        return self._soma("taxa_sem_reserva")

    @property
    def no_show(self) -> float:
        return self._soma("no_show")

    @property
    def total(self) -> float:
        return centavos(self.energia + self.ociosidade + self.taxa_sem_reserva + self.no_show + self.custo_fixo)


@dataclass
class ResultadoRateio:
    competencia: str                            # AAAA-MM; "" se não houver dados datados
    faturas: list[Fatura]                       # uma por usuário, ordenadas por usuario_id
    nao_identificadas: list[CobrancaSessao]     # pendentes para o gestor
    avisos: list[str]
    n_sessoes: int
    arquivos: list[str]
    parametros: Parametros

    @property
    def detalhe(self) -> list[CobrancaSessao]:
        """Todas as cobranças, em ordem cronológica (sessões e no-shows)."""
        itens = [i for f in self.faturas for i in f.itens] + self.nao_identificadas
        return sorted(itens, key=lambda i: (i.inicio or datetime.min, i.sessao_id))

    @property
    def total_arrecadar(self) -> float:
        return centavos(sum(f.total for f in self.faturas))

    @property
    def kwh_total(self) -> float:
        return sum(f.kwh for f in self.faturas) + sum(i.kwh for i in self.nao_identificadas)

    def fatura(self, usuario_id: str) -> Fatura:
        return next(f for f in self.faturas if f.usuario_id == usuario_id)

    def cobranca(self, sessao_id: str) -> CobrancaSessao:
        return next(i for i in self.detalhe if i.sessao_id == sessao_id)


def cobrar_sessao(s: Sessao, par: Parametros) -> CobrancaSessao:
    """Aplica as regras 1 a 3 a uma sessão identificada."""
    kwh = regras.kwh_por_faixa(s, par)
    espera = regras.tempo_ocioso_com_fila(s, par)
    blocos = regras.blocos_ociosidade(espera, par)
    minutos = int(espera.total_seconds() // 60)
    return CobrancaSessao(
        tipo="sessao", usuario_id=s.usuario_id, unidade_id=s.unidade_id, sessao_id=s.id,
        agendamento_id=s.reserva.id if s.reserva else "", inicio=s.inicio, fim=s.fim, duracao_min=s.duracao_min,
        kwh=s.kwh, kwh_faixa=kwh, energia=regras.custo_energia(kwh, par),
        minutos_ociosos=minutos, blocos_ociosidade=blocos, ociosidade=regras.custo_ociosidade(blocos, par),
        taxa_sem_reserva=regras.taxa_sem_reserva(s, par),
        observacao=f"{minutos} min parado com fila" if blocos else "")


def cobrar_nao_identificada(s: Sessao, par: Parametros, motivo: str) -> CobrancaSessao:
    """Regra 6: energia na tarifa normal, sem taxas, não atribuída a ninguém."""
    kwh = regras.kwh_por_faixa(s, par)
    return CobrancaSessao(
        tipo="sessao", usuario_id=NAO_IDENTIFICADO, unidade_id="", sessao_id=s.id,
        agendamento_id=s.reserva.id if s.reserva else "", inicio=s.inicio, fim=s.fim, duracao_min=s.duracao_min,
        kwh=s.kwh, kwh_faixa=kwh, energia=regras.custo_energia(kwh, par), observacao=motivo)


def competencia_dos_dados(lido: ResultadoLeitura) -> tuple[str, list[str]]:
    """Mês (AAAA-MM) da fatura: o do início das sessões e reservas.

    Sessão que começa num mês e termina no seguinte pertence ao mês do início.
    Se os dados misturarem meses, vale o mais frequente e sai um aviso.
    """
    meses = Counter(f"{s.inicio:%Y-%m}" for s in lido.sessoes)
    meses.update(f"{(e.reserva.inicio or e.timestamp):%Y-%m}" for e in lido.eventos_reserva)
    if not meses:
        return "", []
    competencia = meses.most_common(1)[0][0]
    if len(meses) > 1:
        outros = ", ".join(f"{m} ({n})" for m, n in sorted(meses.items()) if m != competencia)
        return competencia, [f"Dados de mais de um mês: competência {competencia}; também há registros de {outros}"]
    return competencia, []


def calcular_rateio(lido: ResultadoLeitura, par: Parametros, competencia: str | None = None) -> ResultadoRateio:
    """Calcula as faturas. `competencia` (AAAA-MM) é deduzida dos dados se não for informada."""
    avisos = list(lido.avisos)
    deduzida, avisos_mes = competencia_dos_dados(lido)
    competencia = competencia or deduzida
    avisos += avisos_mes
    faturas = {uid: Fatura(uid, u.nome, u.unidade_id, centavos(par.custo_fixo), competencia)
               for uid, u in sorted(lido.usuarios.items())}
    nao_ident: list[CobrancaSessao] = []

    avisos += validacoes.antecedencia_das_reservas(lido.reservas.values(), par)
    avisos += validacoes.continuidade_do_medidor(lido.sessoes)

    for s in lido.sessoes:
        avisos += validacoes.leituras_insuficientes(s)
        motivo = regras.motivo_nao_identificada(s, faturas)
        if motivo:
            avisos.append(f"{s.id}: {motivo}; energia ({s.kwh:.2f} kWh) vai para {NAO_IDENTIFICADO}")
            nao_ident.append(cobrar_nao_identificada(s, par, motivo))
            continue
        avisos += validacoes.inicio_antes_da_reserva(s, par)
        faturas[s.usuario_id].itens.append(cobrar_sessao(s, par))

    for e in lido.eventos_reserva:
        motivo = regras.motivo_cobranca_reserva(e, par)
        if not motivo:
            continue
        if e.usuario_id not in faturas:
            avisos.append(f"{e.reserva.id}: {motivo} sem usuário conhecido; no-show não cobrado")
            continue
        faturas[e.usuario_id].itens.append(CobrancaSessao(
            tipo="no_show", usuario_id=e.usuario_id, unidade_id=e.unidade_id, agendamento_id=e.reserva.id,
            inicio=e.reserva.inicio or e.timestamp, no_show=par.taxa_no_show, observacao=motivo))

    for f in faturas.values():
        f.itens.sort(key=lambda i: (i.inicio or datetime.min, i.sessao_id))

    avisos += validacoes.conciliacao(lido.sessoes, sum(s.kwh for s in lido.sessoes))
    return ResultadoRateio(competencia, list(faturas.values()), nao_ident, avisos, len(lido.sessoes),
                           list(lido.arquivos), par)


def calcular_da_pasta(pasta_uso: str | Path, par: Parametros | None = None,
                      competencia: str | None = None) -> ResultadoRateio:
    """Atalho: lê a pasta com o leitor da frente 1 e calcula com os parâmetros da config."""
    pasta_uso = Path(pasta_uso)
    par = par or carregar_parametros(pasta_uso if pasta_uso.is_dir() else pasta_uso.parent)
    return calcular_rateio(UsoSource().ler(pasta_uso), par, competencia)
