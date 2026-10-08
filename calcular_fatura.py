"""
calcular_fatura.py — fatura mensal do EV ChargeOps a partir dos DADOS DE USO do
carregador (arquivos uso_*.csv gerados por gerar_uso_carregador.py).

Os arquivos trazem só eventos e leituras do medidor. Este programa:
  1. junta os arquivos de todos os usuários e reconstrói as SESSÕES
     (início, fim da carga, fim, kWh medidos);
  2. valida os dados (gera AVISOS, não interrompe);
  3. calcula o que cada usuário paga no mês.

Modelo de rateio (valores em parametros_rateio.csv):
  Energia     kWh de cada intervalo do medidor x tarifa da faixa horária
              (fora de ponta / intermediária / ponta; fim de semana e feriado
              = fora de ponta).
  Ociosidade  após o carro terminar de carregar há uma carência; passada ela,
              cobra-se por bloco apenas o tempo em que OUTRO usuário tinha
              reserva ativa (fila_espera = 1), com teto por sessão.
  Sem reserva taxa simples por sessão avulsa.
  No-show     reserva não utilizada, ou cancelada com menos de 1 h de antecedência.
  Custo fixo  por unidade cadastrada, usando ou não o carregador.

Sessão sem usuário/identificação vai para NAO_IDENTIFICADO: energia na tarifa
normal, sem taxas, não atribuída a ninguém, pendente para o gestor.

Entrada: apenas os arquivos uso_*.csv. Usuário e unidade vêm das linhas; o nome, do
nome do arquivo. As tarifas ficam em PARAMETROS_PADRAO (abaixo) e podem ser
sobrescritas por um parametros_rateio.csv opcional na pasta de uso.

Uso:
    python calcular_fatura.py [pasta_uso] [pasta_saida]
    (padrões: uso_carregador e fatura_saida, ao lado deste script)
Saídas: fatura_mensal.csv, detalhe_sessoes.csv, avisos.txt (separador ';', decimal ',')
"""
from __future__ import annotations

import csv
import math
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from leitor_uso import UsoSource, ErroLeitura

FMT = "%Y-%m-%d %H:%M:%S"
TOL_KWH = 0.05


def dt(s: str) -> datetime:
    return datetime.strptime(s, FMT)


def ler(caminho: Path) -> list[dict]:
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def brl(v: float) -> str:
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def num(v: float, casas: int = 2) -> str:
    return f"{v:.{casas}f}".replace(".", ",")


# Regras de cobrança. Valores ARBITRÁRIOS (plano da Sprint 2): ajuste aqui, ou crie um
# parametros_rateio.csv (colunas: parametro,valor) na pasta de uso para sobrescrever.
PARAMETROS_PADRAO = {
    "preco_fora_ponta": "0.85",             # R$/kWh
    "preco_intermediaria": "1.20",          # R$/kWh
    "preco_ponta": "1.70",                  # R$/kWh
    "horas_ponta": "18;19;20",              # horas cheias, dias úteis
    "horas_intermediaria": "17;21",
    "feriados": "2026-01-01;2026-04-03;2026-04-21;2026-05-01;2026-06-04;2026-09-07;"
                "2026-10-12;2026-11-02;2026-11-15;2026-12-25",
    "antecedencia_min_agendamento_min": "60",   # reserva só até 1 h antes
    "carencia_ociosidade_min": "15",            # grátis após terminar de carregar
    "bloco_ociosidade_min": "30",
    "taxa_bloco_ociosidade": "2.00",            # R$/bloco, só com outro usuário na fila
    "teto_ociosidade_sessao": "20.00",          # R$ por sessão
    "taxa_sem_agendamento": "1.50",             # R$ por sessão sem reserva
    "taxa_no_show": "5.00",                     # R$ por reserva não utilizada / cancelada tarde
    "custo_fixo_unidade": "15.00",              # R$/mês por unidade
}


class Parametros:
    def __init__(self, sobrescrever: list[dict] | None = None):
        p = dict(PARAMETROS_PADRAO)
        p.update({l["parametro"]: l["valor"] for l in (sobrescrever or [])})
        self.preco = {"fora_ponta": float(p["preco_fora_ponta"]),
                      "intermediaria": float(p["preco_intermediaria"]),
                      "ponta": float(p["preco_ponta"])}
        self.h_ponta = {int(x) for x in p["horas_ponta"].split(";") if x}
        self.h_inter = {int(x) for x in p["horas_intermediaria"].split(";") if x}
        self.feriados = {x for x in p["feriados"].split(";") if x}
        self.antec = timedelta(minutes=int(p["antecedencia_min_agendamento_min"]))
        self.carencia = timedelta(minutes=int(p["carencia_ociosidade_min"]))
        self.bloco = timedelta(minutes=int(p["bloco_ociosidade_min"]))
        self.taxa_bloco = float(p["taxa_bloco_ociosidade"])
        self.teto_ocio = float(p["teto_ociosidade_sessao"])
        self.taxa_sem_ag = float(p["taxa_sem_agendamento"])
        self.taxa_no_show = float(p["taxa_no_show"])
        self.custo_fixo = float(p["custo_fixo_unidade"])

    def faixa(self, t: datetime) -> str:
        if t.weekday() >= 5 or t.date().isoformat() in self.feriados:
            return "fora_ponta"
        if t.hour in self.h_ponta:
            return "ponta"
        if t.hour in self.h_inter:
            return "intermediaria"
        return "fora_ponta"


def calcular(pasta: Path):
    arq_par = pasta / "parametros_rateio.csv"
    par = Parametros(ler(arq_par) if arq_par.exists() else None)
    # leitura (item 01 do sistema de leitura): toda a interpretação do CSV fica em leitor_uso.py
    lido = UsoSource().ler(pasta)
    avisos: list[str] = list(lido.avisos)
    arquivos = [pasta / a for a in lido.arquivos]
    cadastro = {u.usuario_id: {"usuario_id": u.usuario_id, "nome": u.nome, "unidade_id": u.unidade_id}
                for u in lido.usuarios.values()}
    sessoes, ev_reserva = lido.sessoes, lido.eventos_reserva

    # validação da regra de antecedência (uma vez por reserva)
    for r in lido.reservas.values():
        if r.criada_em and r.inicio and r.criada_em > r.inicio - par.antec:
            avisos.append(f"{r.id}: criada com menos de {int(par.antec.total_seconds() // 60)} min de antecedência")

    detalhe, nao_ident = [], []
    cobr = defaultdict(lambda: defaultdict(float))
    kwh_cobrado, anterior = 0.0, None

    for s in sessoes:
        sid, uid = s.id, s.usuario_id
        e_kwh = s.reg_fim - s.reg_ini
        dur = int((s.fim - s.inicio).total_seconds() // 60)

        # continuidade do medidor e sobreposição (com todos os arquivos carregados)
        if anterior:
            salto = s.reg_ini - anterior.reg_fim
            if salto > TOL_KWH:
                avisos.append(f"{sid}: medidor avançou {salto:.3f} kWh desde a sessão "
                              f"{anterior.id} (consumo fora de sessão)")
            elif salto < -TOL_KWH:
                avisos.append(f"{sid}: medidor voltou {-salto:.3f} kWh em relação à sessão {anterior.id}")
            if s.inicio < anterior.fim:
                avisos.append(f"{sid}: sobreposta à sessão {anterior.id}")
        anterior = s

        # energia por faixa horária (intervalos entre leituras; faixa pelo ponto médio)
        kwh_f = defaultdict(float)
        pts = [(x.t, x.energia_kwh, x.fila_espera) for x in s.leituras]
        if len(pts) >= 2:
            for (t0, e0, _), (t1, e1, _) in zip(pts, pts[1:]):
                if e1 < e0 - 1e-9:
                    avisos.append(f"{sid}: energia acumulada diminuiu entre {t0:%H:%M} e {t1:%H:%M}")
                kwh_f[par.faixa(t0 + (t1 - t0) / 2)] += max(0.0, e1 - e0)
        else:
            avisos.append(f"{sid}: leituras insuficientes; energia na faixa do horário de início")
            kwh_f[par.faixa(s.inicio)] += e_kwh
        custo_energia = sum(k * par.preco[f] for f, k in kwh_f.items())

        # identificação
        if not uid or uid not in cadastro or not s.identificacao:
            motivo = "sem usuário" if not uid else ("usuário não cadastrado" if uid not in cadastro else "sem identificação")
            avisos.append(f"{sid}: {motivo}; energia ({e_kwh:.2f} kWh) vai para NAO_IDENTIFICADO")
            nao_ident.append((sid, e_kwh, custo_energia))
            detalhe.append([sid, "NAO_IDENTIFICADO", "", f"{s.inicio:%Y-%m-%d %H:%M}", f"{s.fim:%Y-%m-%d %H:%M}",
                            dur, num(e_kwh, 3), num(custo_energia), "0,00", "0,00", "0,00", num(custo_energia), ""])
            continue

        if s.reserva and s.reserva.inicio and s.inicio < s.reserva.inicio - timedelta(minutes=30):
            avisos.append(f"{sid}: iniciada mais de 30 min antes da reserva {s.reserva.id}")

        # ociosidade: só o tempo com outro usuário na fila, após a carência
        ocio_ini = s.fim_carga + par.carencia
        espera = timedelta()
        for (t0, _, _), (t1, _, fila1) in zip(pts, pts[1:]):
            a, b = max(t0, ocio_ini), min(t1, s.fim)
            if b > a and fila1 and s.motivo_parada != "PowerLoss":
                espera += b - a
        blocos = math.ceil(espera / par.bloco) if espera > timedelta() else 0
        ocio_c = min(blocos * par.taxa_bloco, par.teto_ocio)
        obs = f"{int(espera.total_seconds() // 60)} min parado com fila" if blocos else ""
        taxa_sem = par.taxa_sem_ag if not s.reserva else 0.0

        total = custo_energia + ocio_c + taxa_sem
        c = cobr[uid]
        c["sessoes"] += 1
        c["kwh"] += e_kwh
        for f, k in kwh_f.items():
            c["kwh_" + f] += k
        c["energia"] += custo_energia
        c["ociosidade"] += ocio_c
        c["sem_agendamento"] += taxa_sem
        kwh_cobrado += e_kwh
        detalhe.append([sid, uid, s.reserva.id if s.reserva else "", f"{s.inicio:%Y-%m-%d %H:%M}", f"{s.fim:%Y-%m-%d %H:%M}", dur,
                        num(e_kwh, 3), num(custo_energia), num(ocio_c), num(taxa_sem), "0,00", num(total), obs])

    # no-show e cancelamento tardio
    for e in ev_reserva:
        uid = e.usuario_id
        tardio = e.tipo == "cancelada" and e.timestamp > e.reserva.inicio - par.antec
        if e.tipo == "nao_utilizada" or tardio:
            cobr[uid]["no_show"] += par.taxa_no_show
            detalhe.append(["", uid, e.reserva.id, f"{e.reserva.inicio:%Y-%m-%d %H:%M}", "", "", "0,000", "0,00", "0,00",
                            "0,00", num(par.taxa_no_show), num(par.taxa_no_show),
                            "reserva não utilizada" if e.tipo == "nao_utilizada" else "cancelamento tardio"])

    # fatura por usuário/unidade
    fatura = []
    for uid, u in sorted(cadastro.items()):
        c = cobr[uid]
        total = c["energia"] + c["ociosidade"] + c["sem_agendamento"] + c["no_show"] + par.custo_fixo
        fatura.append(dict(unidade=u["unidade_id"], uid=uid, nome=u["nome"], sessoes=int(c["sessoes"]),
                           kwh=c["kwh"], fp=c["kwh_fora_ponta"], it=c["kwh_intermediaria"], pt=c["kwh_ponta"],
                           energia=c["energia"], ocio=c["ociosidade"], sem=c["sem_agendamento"],
                           no_show=c["no_show"], fixo=par.custo_fixo, total=total))

    # conciliação com o medidor
    if sessoes:
        medido = sessoes[-1].reg_fim - sessoes[0].reg_ini
        explicado = kwh_cobrado + sum(x[1] for x in nao_ident)
        if abs(medido - explicado) > TOL_KWH:
            avisos.append(f"Conciliação: o medidor avançou {medido:.2f} kWh; as sessões explicam "
                          f"{explicado:.2f} kWh; diferença {medido - explicado:.2f} kWh")
    return fatura, detalhe, avisos, nao_ident, len(sessoes), arquivos


CAB_FATURA = ["unidade_id", "usuario_id", "nome", "sessoes", "kwh_total", "kwh_fora_ponta", "kwh_intermediaria",
              "kwh_ponta", "custo_energia", "ociosidade", "taxa_sem_agendamento", "no_show", "custo_fixo", "total"]
CAB_DET = ["sessao_id", "usuario_id", "agendamento_id", "inicio", "fim", "duracao_min", "kwh", "custo_energia",
           "ociosidade", "taxa_sem_agendamento", "no_show", "total", "observacao"]


def main(argv: list[str]) -> int:
    aqui = Path(__file__).resolve().parent
    base = Path(argv[1]) if len(argv) > 1 else aqui / "uso_carregador"
    saida = Path(argv[2]) if len(argv) > 2 else aqui / "fatura_saida"
    if not base.is_dir():
        print(f"[ERRO] pasta não encontrada: {base}  (rode antes: python gerar_uso_carregador.py)")
        return 1
    try:
        fatura, detalhe, avisos, nao_ident, n_sess, arquivos = calcular(base)
    except (FileNotFoundError, KeyError, ErroLeitura) as e:
        print(f"[ERRO] {e}")
        return 1
    saida.mkdir(parents=True, exist_ok=True)
    with open(saida / "fatura_mensal.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(CAB_FATURA)
        for l in fatura:
            w.writerow([l["unidade"], l["uid"], l["nome"], l["sessoes"], num(l["kwh"]), num(l["fp"]), num(l["it"]),
                        num(l["pt"]), num(l["energia"]), num(l["ocio"]), num(l["sem"]), num(l["no_show"]),
                        num(l["fixo"]), num(l["total"])])
    with open(saida / "detalhe_sessoes.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(CAB_DET)
        w.writerows(detalhe)
    (saida / "avisos.txt").write_text("\n".join(avisos) + ("\n" if avisos else ""), encoding="utf-8")

    print(f"{len(arquivos)} arquivo(s) de uso lidos, {n_sess} sessões reconstruídas\n")
    print(f"{'unid':6}{'usuário':24}{'sess':>5}{'kWh':>8}{'energia':>10}{'ocios.':>8}{'s/res':>7}{'no-show':>8}{'fixo':>7}{'TOTAL':>10}")
    soma = 0.0
    for l in fatura:
        print(f"{l['unidade']:6}{l['nome'][:23]:24}{l['sessoes']:>5}{l['kwh']:8.1f}{brl(l['energia']):>10}"
              f"{brl(l['ocio']):>8}{brl(l['sem']):>7}{brl(l['no_show']):>8}{brl(l['fixo']):>7}{brl(l['total']):>10}")
        soma += l["total"]
    print(f"{'':58}{'TOTAL A ARRECADAR':>25}  R$ {brl(soma)}")
    if nao_ident:
        print(f"NAO_IDENTIFICADO: {len(nao_ident)} sessão(ões), {sum(x[1] for x in nao_ident):.2f} kWh, "
              f"R$ {brl(sum(x[2] for x in nao_ident))} pendentes")
    print(f"{len(avisos)} aviso(s)" + (f" — ver {saida / 'avisos.txt'}" if avisos else ""))
    for a in avisos[:10]:
        print("  aviso:", a)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
