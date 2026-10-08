"""
parametros.py — tarifas e taxas do rateio (seção 3.1 do Sistema de Leitura).

Os valores NÃO ficam no código: vêm de config/parametros_rateio.csv
(colunas parametro,valor[,descricao]). Um parametros_rateio.csv na pasta de uso,
se existir, sobrescreve só os parâmetros que trouxer.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ARQUIVO_PADRAO = RAIZ / "config" / "parametros_rateio.csv"

OBRIGATORIOS = (
    "preco_fora_ponta", "preco_intermediaria", "preco_ponta", "horas_ponta", "horas_intermediaria", "feriados",
    "antecedencia_min_agendamento_min", "carencia_ociosidade_min", "bloco_ociosidade_min", "taxa_bloco_ociosidade",
    "teto_ociosidade_sessao", "taxa_sem_agendamento", "taxa_no_show", "custo_fixo_unidade",
)
OPCIONAIS = {"tolerancia_inicio_antes_reserva_min": "30"}

FAIXAS = ("fora_ponta", "intermediaria", "ponta")


class ErroParametros(Exception):
    """Arquivo de parâmetros ausente, incompleto ou com valor ilegível."""


def _ler_csv(caminho: Path) -> dict[str, str]:
    try:
        with open(caminho, newline="", encoding="utf-8-sig") as f:
            linhas = list(csv.DictReader(f))
    except OSError as e:
        raise ErroParametros(f"não foi possível abrir {caminho}: {e}") from e
    if linhas and not {"parametro", "valor"} <= set(linhas[0]):
        raise ErroParametros(f"{caminho}: colunas esperadas 'parametro,valor'")
    return {l["parametro"].strip(): (l["valor"] or "").strip() for l in linhas if (l.get("parametro") or "").strip()}


def _num(nome: str, txt: str) -> float:
    try:
        return float(txt.replace(",", "."))
    except ValueError:
        raise ErroParametros(f"parâmetro '{nome}' com valor ilegível: '{txt}'") from None


def _lista(txt: str) -> list[str]:
    return [x.strip() for x in txt.split(";") if x.strip()]


@dataclass(frozen=True)
class Parametros:
    preco: dict[str, float]                 # R$/kWh por faixa
    horas_ponta: frozenset[int]
    horas_intermediaria: frozenset[int]
    feriados: frozenset[str]                # AAAA-MM-DD
    antecedencia: timedelta
    tolerancia_inicio: timedelta
    carencia: timedelta
    bloco: timedelta
    taxa_bloco: float
    teto_ociosidade: float
    taxa_sem_reserva: float
    taxa_no_show: float
    custo_fixo: float
    origem: tuple[str, ...] = ()            # arquivos usados, para rastrear a fatura

    @classmethod
    def de_dict(cls, p: dict[str, str], origem: tuple[str, ...] = ()) -> "Parametros":
        p = {**OPCIONAIS, **p}
        faltam = [n for n in OBRIGATORIOS if n not in p]
        if faltam:
            raise ErroParametros(f"parâmetros ausentes: {', '.join(faltam)}")

        def minutos(nome: str) -> timedelta:
            return timedelta(minutes=_num(nome, p[nome]))

        try:
            horas = lambda nome: frozenset(int(h) for h in _lista(p[nome]))
            h_ponta, h_inter = horas("horas_ponta"), horas("horas_intermediaria")
        except ValueError:
            raise ErroParametros("horas_ponta/horas_intermediaria devem ser inteiros separados por ';'") from None
        if h_ponta & h_inter:
            raise ErroParametros(f"horas em ponta e intermediária ao mesmo tempo: {sorted(h_ponta & h_inter)}")
        feriados = frozenset(_lista(p["feriados"]))
        for d in feriados:
            try:
                datetime.strptime(d, "%Y-%m-%d")
            except ValueError:
                raise ErroParametros(f"feriado com data inválida: '{d}' (use AAAA-MM-DD)") from None

        par = cls(
            preco={"fora_ponta": _num("preco_fora_ponta", p["preco_fora_ponta"]),
                   "intermediaria": _num("preco_intermediaria", p["preco_intermediaria"]),
                   "ponta": _num("preco_ponta", p["preco_ponta"])},
            horas_ponta=h_ponta, horas_intermediaria=h_inter, feriados=feriados,
            antecedencia=minutos("antecedencia_min_agendamento_min"),
            tolerancia_inicio=minutos("tolerancia_inicio_antes_reserva_min"),
            carencia=minutos("carencia_ociosidade_min"),
            bloco=minutos("bloco_ociosidade_min"),
            taxa_bloco=_num("taxa_bloco_ociosidade", p["taxa_bloco_ociosidade"]),
            teto_ociosidade=_num("teto_ociosidade_sessao", p["teto_ociosidade_sessao"]),
            taxa_sem_reserva=_num("taxa_sem_agendamento", p["taxa_sem_agendamento"]),
            taxa_no_show=_num("taxa_no_show", p["taxa_no_show"]),
            custo_fixo=_num("custo_fixo_unidade", p["custo_fixo_unidade"]),
            origem=origem,
        )
        if par.bloco <= timedelta():
            raise ErroParametros("bloco_ociosidade_min deve ser maior que zero")
        negativos = [f for f, v in par.preco.items() if v < 0]
        if negativos:
            raise ErroParametros(f"tarifa negativa: {', '.join(negativos)}")
        return par


def carregar_parametros(pasta_uso: str | Path | None = None,
                        arquivo_base: str | Path = ARQUIVO_PADRAO) -> Parametros:
    """Lê config/parametros_rateio.csv e aplica o parametros_rateio.csv da pasta de uso, se houver."""
    base = Path(arquivo_base)
    if not base.is_file():
        raise ErroParametros(f"arquivo de parâmetros não encontrado: {base}")
    valores = _ler_csv(base)
    origem = [str(base)]
    if pasta_uso is not None:
        extra = Path(pasta_uso) / "parametros_rateio.csv"
        if extra.is_file():
            valores.update(_ler_csv(extra))
            origem.append(str(extra))
    return Parametros.de_dict(valores, tuple(origem))
