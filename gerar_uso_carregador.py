"""
gerar_uso_carregador.py — simula os DADOS DE USO de um carregador compartilhado
(HCA G2, estilo OCPP/MODBUS): 5 arquivos CSV, um por usuário, todos com a MESMA
estrutura, cobrindo o mês inteiro.

Cada arquivo é um log de eventos/leituras do carregador para aquele usuário:

    timestamp, usuario_id, unidade_id, evento, sessao_id, identificacao,
    agendamento_id, reserva_inicio, reserva_fim, reserva_criada_em,
    energia_acumulada_kwh, potencia_kw, soc_pct, fila_espera, motivo_parada

Eventos:
    Inicio      começa a sessão (carrega dados da reserva, se houver)
    Medicao     leitura do medidor a cada 15 min (kWh acumulado do medidor, kW)
    CarroCheio  o carro parou de puxar energia (como o SuspendedEV do OCPP)
    Fim         sessão encerrada (EVDisconnected ou PowerLoss)
    ReservaNaoUtilizada / ReservaCancelada   eventos de reserva sem sessão

O arquivo NÃO traz kWh por sessão, duração nem valores: quem deriva isso e
calcula o que cada um paga é o calcular_fatura.py. O que o carregador/app
"sabe" e registra: identificação, reserva, medidor, SOC informado pelo carro e
`fila_espera` (1 = outro usuário tinha reserva ativa naquele momento).

Regras do domínio: só libera com identificação (reserva reconhecida pelo
horário, ou RFID/app no equipamento); reserva só até 1 h antes; um ponto de
recarga, sem sobreposição; medidor acumulado contínuo entre usuários.

Gera SOMENTE os arquivos de uso (nada de cadastro nem tarifas: isso fica no
calcular_fatura.py). Dados 100% fictícios.

Uso:
    python gerar_uso_carregador.py                      # setembro/2026 em ./uso_carregador
    python gerar_uso_carregador.py --mes 2026-10 --seed 7      # reproduzível
    python gerar_uso_carregador.py --anomalias          # injeta 3 problemas para testar validações
"""
from __future__ import annotations

import argparse
import csv
import heapq
import random
import unicodedata
from dataclasses import dataclass, field, replace
from datetime import datetime, time, timedelta
from pathlib import Path

# --------------------------------------------------------------- premissas
CARREGADOR_KW = 7.0            # wallbox 7 kW em 220 V
ETA_AC = 0.90                  # energia na bateria / energia na tomada
REGISTRO_INICIAL_KWH = 1284.350
PASSO_LEITURA_MIN = 15

FERIADOS_2026 = ["2026-01-01", "2026-04-03", "2026-04-21", "2026-05-01", "2026-06-04",
                 "2026-09-07", "2026-10-12", "2026-11-02", "2026-11-15", "2026-12-25"]

CABECALHO = ["timestamp", "usuario_id", "unidade_id", "evento", "sessao_id", "identificacao",
             "agendamento_id", "reserva_inicio", "reserva_fim", "reserva_criada_em",
             "energia_acumulada_kwh", "potencia_kw", "soc_pct", "fila_espera", "motivo_parada"]


@dataclass
class Perfil:
    nome: str
    unidade: str
    modelo: str
    bateria_kwh: float
    obc_kw: float
    km_dia: float
    consumo: float           # kWh/100 km
    janela: str              # noturna | madrugada | diurna | flex
    p_reserva: float
    p_esquece: float         # chance de deixar o carro plugado por horas
    alvo_soc: int
    gatilho_soc: int
    uid: str = ""
    placa: str = ""


# Baterias do Dolphin Mini (38 kWh, AC 6,6 kW) e Dolphin (44,9 kWh): fichas técnicas
# públicas. Dolphin Plus e híbrido: hipóteses.
PERFIS = [
    Perfil("Ana Beatriz Souza", "A-11", "BYD Dolphin Mini", 38.0, 6.6, 40, 11.0, "noturna", 0.85, 0.10, 90, 40),
    Perfil("Ricardo Mendes", "B-14", "BYD Dolphin Plus", 60.5, 6.6, 60, 15.0, "madrugada", 0.60, 0.25, 100, 35),
    Perfil("Juliana Castro", "B-21", "Híbrido plug-in", 18.0, 3.3, 35, 16.0, "noturna", 0.40, 0.30, 100, 55),
    Perfil("Marcos Vinícius Rocha", "B-33", "BYD Dolphin Mini", 38.0, 6.6, 45, 11.0, "flex", 0.50, 0.15, 80, 40),
    Perfil("Patrícia Nogueira", "B-42", "BYD Dolphin", 44.9, 6.6, 25, 13.0, "diurna", 0.95, 0.05, 80, 35),
]


# --------------------------------------------------------------- simulação
for _i, _p in enumerate(PERFIS, start=1):
    _p.uid = f"U{_i:02d}"

# Faixas consideradas NORMAIS para um carregador residencial/condominial compartilhado.
# Cada execução sorteia dados diferentes, mas só é aceita se ficar dentro destas faixas.
FAIXAS = {
    "sessoes_por_usuario": (2, 20),        # recargas no mês
    "kwh_por_usuario": (40.0, 380.0),      # energia mensal por morador
    "kwh_total": (400.0, 1300.0),          # energia mensal do ponto de recarga
    "kwh_sessao_min": 2.0,                 # abaixo disso seria só "pingar" o carro
    "duracao_carga_max_min": 14 * 60,      # carga efetiva (potência > 0) por sessão
    "ociosidade_max_min": 600,             # carro plugado já carregado
    "soc_inicio": (10.0, 75.0),            # bateria ao plugar
}


def jitter_perfil(p: Perfil, rnd: random.Random) -> Perfil:
    """Variação pequena do hábito de cada morador de uma execução para outra."""
    return replace(
        p,
        km_dia=p.km_dia * rnd.uniform(0.93, 1.07),
        consumo=p.consumo * rnd.uniform(0.95, 1.05),
        gatilho_soc=p.gatilho_soc + rnd.randint(-2, 2),
        p_reserva=min(0.98, max(0.2, p.p_reserva + rnd.uniform(-0.05, 0.05))),
        p_esquece=min(0.40, max(0.02, p.p_esquece + rnd.uniform(-0.03, 0.03))),
    )


def simular_carga(soc0: float, alvo: float, p: Perfil, rnd: random.Random) -> list[float]:
    """kW na tomada, minuto a minuto: constante até 90% e depois cai linearmente
    até 35% da nominal em 100% (hipótese de curva AC)."""
    p_max = min(CARREGADOR_KW, p.obc_kw)
    soc, minutos = soc0, []
    while soc < alvo - 1e-9 and len(minutos) < 20 * 60:
        fator = 1.0 if soc < 90 else max(0.35, 1 - (soc - 90) * 0.065)
        kw = p_max * fator * rnd.uniform(0.985, 1.0)
        soc += kw * ETA_AC / 60 / p.bateria_kwh * 100
        minutos.append(kw)
    return minutos


def eh_util(d, feriados: set[str]) -> bool:
    return d.weekday() < 5 and d.isoformat() not in feriados


@dataclass
class Pedido:
    perfil: Perfil
    desejado: datetime
    soc0: float
    minutos: list[float]
    tipo: str                      # reserva | avulsa
    tentativas: int = 0
    ag: dict = field(default_factory=dict)


def gerar_pedidos(rnd, p: Perfil, ini: datetime, fim: datetime) -> list[Pedido]:
    feriados = set(FERIADOS_2026)
    pedidos: list[Pedido] = []
    soc = rnd.uniform(45, 80)
    d = ini.date()
    while datetime.combine(d, time()) < fim:
        fds = not eh_util(d, feriados)
        km = p.km_dia * (0.6 if fds else 1.0) * rnd.uniform(0.75, 1.25)
        if rnd.random() < 0.05:
            km *= 2.2                                      # viagem ocasional
        queda = km * p.consumo / 100 / p.bateria_kwh * 100
        janela = p.janela if p.janela != "flex" else ("noturna" if rnd.random() < 0.55 else "diurna")
        noturno = janela in ("noturna", "madrugada")
        soc_plug = max(10.0, soc - (queda if noturno else 0))
        if soc_plug <= p.gatilho_soc + rnd.uniform(-3, 3):
            h = {"noturna": rnd.uniform(18.0, 22.5), "madrugada": rnd.uniform(22.0, 25.0),
                 "diurna": rnd.uniform(8.5, 15.5)}[janela]
            minutos = simular_carga(soc_plug, p.alvo_soc, p, rnd)
            if minutos:
                desejado = datetime.combine(d, time()) + timedelta(minutes=int(h * 60))
                tipo = "reserva" if rnd.random() < p.p_reserva else "avulsa"
                pedidos.append(Pedido(p, desejado, soc_plug, minutos, tipo))
            soc = float(p.alvo_soc) if noturno else float(p.alvo_soc) - queda
        else:
            soc = max(10.0, soc - queda)
        d += timedelta(days=1)
    return pedidos


def ceil30(t: datetime) -> datetime:
    t = t.replace(second=0, microsecond=0)
    return t if t.minute % 30 == 0 else t + timedelta(minutes=30 - t.minute % 30)


def reservar(janelas, desejado: datetime, dur_min: int, limite: datetime):
    t = ceil30(desejado)
    for _ in range(12):
        a, b = t, t + timedelta(minutes=dur_min)
        if b <= limite and all(b <= x or a >= y for x, y in janelas):
            return a, b
        t += timedelta(minutes=30)
    return None


def ociosidade_min(p: Perfil, noturno: bool, rnd: random.Random) -> int:
    if rnd.random() < p.p_esquece:
        return rnd.randint(90, 540) if noturno else rnd.randint(60, 240)
    return max(0, int(rnd.gauss(8, 6)))


def fmt(t: datetime | None) -> str:
    return t.strftime("%Y-%m-%d %H:%M:%S") if t else ""


def slug(txt: str) -> str:
    t = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode()
    return "".join(c if c.isalnum() else "_" for c in t.lower()).strip("_")


# --------------------------------------------------------------- geração
def gerar(ano: int, mes: int, seed: int, anomalias: bool):
    rnd = random.Random(seed)
    ini = datetime(ano, mes, 1)
    fim_mes = datetime(ano + (mes == 12), mes % 12 + 1, 1)
    perfis = [jitter_perfil(p, rnd) for p in PERFIS]

    pedidos: list[Pedido] = []
    for p in perfis:
        pedidos += gerar_pedidos(rnd, p, ini, fim_mes)
    pedidos.sort(key=lambda x: x.desejado)

    # --- fase 1: reservas
    janelas, agendamentos, avulsas, reservados = [], [], [], []
    for ped in pedidos:
        if ped.tipo == "avulsa":
            avulsas.append(ped)
            continue
        dur = -(-(len(ped.minutos) + 30) // 30) * 30
        slot = reservar(janelas, ped.desejado, dur, fim_mes)
        if slot is None:
            ped.tipo = "avulsa"
            avulsas.append(ped)
            continue
        a, b = slot
        r = rnd.random()
        status = "cancelado" if r < 0.05 else "nao_compareceu" if r < 0.08 else "utilizado"
        criado = a - timedelta(minutes=rnd.randint(65, 30 * 60))
        cancelado = (a - timedelta(minutes=rnd.randint(70, 360))) if status == "cancelado" else None
        if status != "cancelado":
            janelas.append((a, b))
        ped.ag = dict(usuario_id=ped.perfil.uid, inicio=a, fim=b, status=status,
                      criado_em=criado, cancelado_em=cancelado)
        agendamentos.append(ped.ag)
        if status == "utilizado":
            reservados.append(ped)
    agendamentos.sort(key=lambda a: a["inicio"])
    for k, a in enumerate(agendamentos, start=1):
        a["id"] = f"AG{k:04d}"

    # anomalia 1: reserva criada em cima da hora (viola a regra de 1 h)
    inj = []
    if anomalias and reservados:
        alvo = reservados[len(reservados) // 3].ag
        alvo["criado_em"] = alvo["inicio"] - timedelta(minutes=20)
        inj.append(f"{alvo['id']} ({alvo['usuario_id']}) criada com 20 min de antecedência (regra: 60 min)")

    # --- fase 2: sessões em ordem cronológica no único ponto de recarga
    heap, seq = [], 0
    for ped in reservados:
        heapq.heappush(heap, (ped.ag["inicio"] + timedelta(minutes=rnd.randint(0, 20)), seq, ped)); seq += 1
    for ped in avulsas:
        heapq.heappush(heap, (ped.desejado, seq, ped)); seq += 1

    sessoes: list[dict] = []
    ultimo_fim = ini - timedelta(days=1)
    troca = timedelta(minutes=3)
    while heap:
        t, _, ped = heapq.heappop(heap)
        p = ped.perfil
        if ped.tipo == "reserva":
            inicio = max(t, ultimo_fim + troca)
        else:
            if t < ultimo_fim + troca:
                ped.tentativas += 1
                if ped.tentativas <= 3:
                    heapq.heappush(heap, (ultimo_fim + troca, seq, ped)); seq += 1
                continue
            dur = timedelta(minutes=len(ped.minutos) + 10)
            conflito = next((b for a, b in sorted(janelas) if a < t + dur and b > t), None)
            if conflito:
                ped.tentativas += 1
                if ped.tentativas <= 3:
                    heapq.heappush(heap, (conflito, seq, ped)); seq += 1
                continue
            inicio = t
        minutos, motivo, status = ped.minutos, "EVDisconnected", "Concluida"
        if rnd.random() < 0.03:                              # queda de energia no meio da carga
            minutos = minutos[: max(5, int(len(minutos) * rnd.uniform(0.3, 0.8)))]
            motivo, status = "PowerLoss", "Interrompida"
        fim_carga = inicio + timedelta(minutes=len(minutos))
        noturno = inicio.hour >= 18 or inicio.hour < 6
        ocio = 0 if status == "Interrompida" else ociosidade_min(p, noturno, rnd)
        fim = fim_carga + timedelta(minutes=ocio)
        if fim >= fim_mes:
            continue
        ultimo_fim = fim
        sessoes.append(dict(ped=ped, inicio=inicio, fim_carga=fim_carga, fim=fim, minutos=minutos,
                            motivo=motivo, status=status,
                            ident="reserva" if ped.tipo == "reserva" else rnd.choice(["rfid", "rfid", "app"])))
    sessoes.sort(key=lambda s: s["inicio"])

    # janelas de quem realmente estava na fila (reservas utilizadas)
    reservas_uso = [(a["usuario_id"], a["inicio"], a["fim"]) for a in agendamentos if a["status"] == "utilizado"]

    def fila(uid: str, t: datetime) -> int:
        return int(any(u != uid and a <= t < b for u, a, b in reservas_uso))

    # --- linhas por sessão (eventos + leituras de 15 min)
    por_usuario = {p.uid: [] for p in perfis}
    reg = REGISTRO_INICIAL_KWH
    salto_em = len(sessoes) // 2 if anomalias else -1
    sem_id_k = next((i for i, s in enumerate(sessoes) if s["ident"] != "reserva"), 0) if anomalias else -1
    nao_ident = []
    for i, s in enumerate(sessoes):
        if i == salto_em:
            reg += 3.2                                       # anomalia 2: kWh sem sessão
            inj.append(f"medidor saltou +3,2 kWh antes da sessão S{i + 1:04d} (consumo fora de sessão)")
        ped, mins = s["ped"], s["minutos"]
        p = ped.perfil
        sid = f"S{i + 1:04d}"
        n = len(mins)
        ag = ped.ag if ped.tipo == "reserva" else {}
        uid, uni, ident = p.uid, p.unidade, s["ident"]
        if i == sem_id_k:                                    # anomalia 3: sessão sem identificação
            inj.append(f"{sid} sem usuário/identificação (arquivo uso_NAO_IDENTIFICADO.csv)")
            uid = uni = ident = ""
        linhas = []

        def linha(t, evento, acum=None, pot=None, soc=None, motivo="", inicio_ev=False):
            linhas.append([
                fmt(t), uid, uni, evento, sid, ident, ag.get("id", "") if inicio_ev else "",
                fmt(ag.get("inicio")) if inicio_ev and ag else "", fmt(ag.get("fim")) if inicio_ev and ag else "",
                fmt(ag.get("criado_em")) if inicio_ev and ag else "",
                "" if acum is None else f"{acum:.3f}", "" if pot is None else f"{pot:.2f}",
                "" if soc is None else f"{soc:.0f}", fila(p.uid, t) if uid else fila("", t), motivo])

        def estado(t):
            m = int((t - s["inicio"]).total_seconds() // 60)
            e = sum(mins[: min(m, n)]) / 60
            return reg + e, (mins[m] if m < n else 0.0), min(100.0, ped.soc0 + e * ETA_AC / p.bateria_kwh * 100)

        a0, _, soc0 = estado(s["inicio"])
        linha(s["inicio"], "Inicio", a0, 0.0, soc0, inicio_ev=True)
        t = s["inicio"] + timedelta(minutes=PASSO_LEITURA_MIN)
        while t < s["fim"]:
            if t != s["fim_carga"]:
                a, pot, sc = estado(t)
                linha(t, "Medicao", a, pot, sc)
            t += timedelta(minutes=PASSO_LEITURA_MIN)
        if s["status"] == "Concluida":                        # carro parou de puxar energia
            a, _, sc = estado(s["fim_carga"])
            linha(s["fim_carga"], "CarroCheio", a, 0.0, sc)
        a, _, sc = estado(s["fim"])
        linha(s["fim"], "Fim", a, 0.0, sc, motivo=s["motivo"])
        linhas.sort(key=lambda x: x[0])
        (nao_ident if i == sem_id_k else por_usuario[p.uid]).extend(linhas)
        reg += sum(mins) / 60

    # --- eventos de reserva sem sessão (no-show e cancelamentos)
    uid_de = {p.uid: p for p in perfis}
    for a in agendamentos:
        if a["status"] in ("nao_compareceu", "cancelado"):
            p = uid_de[a["usuario_id"]]
            cancel = a["status"] == "cancelado"
            t = a["cancelado_em"] if cancel else a["inicio"] + timedelta(minutes=30)
            por_usuario[p.uid].append([
                fmt(t), p.uid, p.unidade, "ReservaCancelada" if cancel else "ReservaNaoUtilizada", "", "",
                a["id"], fmt(a["inicio"]), fmt(a["fim"]), fmt(a["criado_em"]), "", "", "", "", ""])
    for linhas in por_usuario.values():
        linhas.sort(key=lambda x: x[0])
    resumo = [dict(uid=x["ped"].perfil.uid, kwh=sum(x["minutos"]) / 60, pmax=max(x["minutos"]),
                   carga_min=len(x["minutos"]), ocio_min=(x["fim"] - x["fim_carga"]).total_seconds() / 60,
                   soc0=x["ped"].soc0, bateria=x["ped"].perfil.bateria_kwh, obc=x["ped"].perfil.obc_kw)
              for x in sessoes]
    return por_usuario, nao_ident, inj, resumo


def checar_faixas(resumo: list[dict]) -> list[str]:
    """Devolve os problemas encontrados (lista vazia = tudo dentro do normal)."""
    f, pb = FAIXAS, []
    por = {p.uid: [r for r in resumo if r["uid"] == p.uid] for p in PERFIS}
    total = sum(r["kwh"] for r in resumo)
    if not f["kwh_total"][0] <= total <= f["kwh_total"][1]:
        pb.append(f"energia total {total:.0f} kWh fora de {f['kwh_total']}")
    for p in PERFIS:
        rs = por[p.uid]
        kwh = sum(r["kwh"] for r in rs)
        if not f["sessoes_por_usuario"][0] <= len(rs) <= f["sessoes_por_usuario"][1]:
            pb.append(f"{p.uid}: {len(rs)} sessões fora de {f['sessoes_por_usuario']}")
        if not f["kwh_por_usuario"][0] <= kwh <= f["kwh_por_usuario"][1]:
            pb.append(f"{p.uid}: {kwh:.0f} kWh no mês fora de {f['kwh_por_usuario']}")
    for r in resumo:
        if r["kwh"] < f["kwh_sessao_min"] or r["kwh"] > r["bateria"] / ETA_AC * 1.02:
            pb.append(f"{r['uid']}: sessão de {r['kwh']:.1f} kWh incompatível com bateria de {r['bateria']} kWh")
        if r["pmax"] > min(CARREGADOR_KW, r["obc"]) * 1.01:
            pb.append(f"{r['uid']}: potência {r['pmax']:.2f} kW acima do limite")
        if r["carga_min"] > f["duracao_carga_max_min"] or r["ocio_min"] > f["ociosidade_max_min"]:
            pb.append(f"{r['uid']}: duração fora do normal ({r['carga_min']} min carga, {r['ocio_min']:.0f} min ocioso)")
        if not f["soc_inicio"][0] <= r["soc0"] <= f["soc_inicio"][1]:
            pb.append(f"{r['uid']}: SOC inicial {r['soc0']:.0f}% fora de {f['soc_inicio']}")
    return pb


def escrever(caminho: Path, cab: list[str], linhas: list[list], delim: str = ",") -> None:
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=delim)
        w.writerow(cab)
        w.writerows(linhas)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mes", default="2026-09", help="AAAA-MM (padrão 2026-09)")
    ap.add_argument("--seed", type=int, default=None,
                    help="semente; sem ela cada execução gera dados diferentes (a usada é mostrada no final)")
    ap.add_argument("--saida", default=str(Path(__file__).resolve().parent / "uso_carregador"),
                    help="pasta de saída (padrão: subpasta uso_carregador ao lado deste script; use . para a pasta atual)")
    ap.add_argument("--anomalias", action="store_true", help="injeta 3 problemas de dados")
    a = ap.parse_args()
    ano, mes = map(int, a.mes.split("-"))
    fixa = a.seed is not None
    for tentativa in range(1, 31):
        seed = a.seed if fixa else random.randrange(1, 10**6)
        por_usuario, nao_ident, inj, resumo = gerar(ano, mes, seed, a.anomalias)
        problemas = checar_faixas(resumo)
        if not problemas or fixa:
            break                      # sem semente: sorteia de novo até ficar nas faixas normais

    pasta = Path(a.saida)
    pasta.mkdir(parents=True, exist_ok=True)
    for p in PERFIS:
        escrever(pasta / f"uso_{p.uid}_{slug(p.nome)}.csv", CABECALHO, por_usuario[p.uid])
    if nao_ident:
        escrever(pasta / "uso_NAO_IDENTIFICADO.csv", CABECALHO, nao_ident)

    print(f"Arquivos gravados em: {pasta.resolve()}")
    for p in PERFIS:
        ls = por_usuario[p.uid]
        n_ses = sum(1 for l in ls if l[3] == "Inicio")
        print(f"  uso_{p.uid}_{slug(p.nome)}.csv  {len(ls):4d} linhas, {n_ses:2d} sessões, {p.nome} ({p.modelo})")
    for m in inj:
        print("  anomalia injetada:", m)
    total = sum(r["kwh"] for r in resumo)
    print(f"  total: {len(resumo)} sessões, {total:.0f} kWh | semente {seed} (repita com --seed {seed})")
    if problemas:
        print("  AVISO: dados fora das faixas normais com esta semente:")
        for m in problemas:
            print("   -", m)
    else:
        print("  faixas normais de uso: OK")


if __name__ == "__main__":
    main()
