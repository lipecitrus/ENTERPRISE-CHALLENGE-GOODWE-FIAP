"""
main.py — EV ChargeOps (versão simples, dados em Excel).

Cadastro com CPF, agendamento, liberação do carregador, painel do gestor e fatura mensal.
  * Dados do app (usuários, reservas, liberações): ev_chargeops.xlsx, lido/gravado com pandas.
  * Fatura: calculada pelo repositório (src/rateio) sobre a pasta uso_carregador.
  * Exportação do gestor: fatura_saida/fatura_mensal.xlsx.

Requisitos: pip install pandas openpyxl      Uso: python main.py
"""
import getpass
import hashlib
import secrets
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from src.rateio import ErroParametros, calcular_da_pasta, carregar_parametros  # noqa: E402
from src.rateio.contrato import ErroLeitura  # noqa: E402
from src.rateio.saida import brl, resumo  # noqa: E402

ARQ, PASTA_USO, PASTA_SAIDA = RAIZ / "ev_chargeops.xlsx", RAIZ / "uso_carregador", RAIZ / "fatura_saida"
FMT = "%Y-%m-%d %H:%M"
COLUNAS = {
    "usuarios": ["cpf", "usuario_id", "nome", "unidade_id", "senha"],
    "agendamentos": ["id", "usuario_id", "inicio", "fim", "status", "tardio"],
    "liberacoes": ["id", "usuario_id", "unidade_id", "identificacao", "agendamento_id", "inicio", "fim"],
    "config": ["chave", "valor"],
}
try:
    PAR = carregar_parametros()
except ErroParametros as e:
    sys.exit(f"[ERRO] {e}")
MIN_ANT = int(PAR.antecedencia.total_seconds() // 60)


# ---------------------------------------------------------------- dados (Excel)
def carregar():
    lido = pd.read_excel(ARQ, sheet_name=None, dtype=str, keep_default_na=False) if ARQ.exists() else {}
    return {aba: lido.get(aba, pd.DataFrame(columns=cols)) for aba, cols in COLUNAS.items()}


DB = carregar()


def salvar():
    with pd.ExcelWriter(ARQ) as w:
        for aba, df in DB.items():
            df.to_excel(w, sheet_name=aba, index=False)


def inserir(aba, **campos):
    DB[aba].loc[len(DB[aba])] = [str(campos.get(c, "")) for c in COLUNAS[aba]]
    salvar()


def atualizar(aba, mascara, **campos):
    df = DB[aba].copy()                      # copia: o DataFrame lido do Excel pode ser somente leitura
    for coluna, valor in campos.items():
        df.loc[mascara, coluna] = valor
    DB[aba] = df
    salvar()


# ---------------------------------------------------------------- utilitários
def ler(txt):
    try:
        return input(txt).strip()
    except (EOFError, KeyboardInterrupt):
        sys.exit("\nAté logo!")


def ler_senha(txt):
    try:
        return getpass.getpass(txt)
    except (EOFError, KeyboardInterrupt):
        sys.exit("\nAté logo!")


def agora():
    return datetime.now().replace(second=0, microsecond=0)


def menu(titulo, opcoes):
    print(f"\n=== {titulo} ===")
    for i, o in enumerate(opcoes, 1):
        print(f"  [{i}] {o}")
    print("  [0] Voltar/Sair")
    while True:
        t = ler("Opção: ")
        if t.isdigit() and int(t) <= len(opcoes):
            return int(t)


def cpf_valido(d):
    if len(d) == 11:
        return True
    


def mascara(cpf):
    return f"***.{cpf[3:6]}.{cpf[6:9]}-**"


def so_digitos(t):
    return "".join(c for c in t if c.isdigit())


def hash_senha(s):
    sal = secrets.token_hex(8)
    return sal + "$" + hashlib.pbkdf2_hmac("sha256", s.encode(), sal.encode(), 100_000).hex()


def senha_ok(s, guardada):
    sal, _, h = guardada.partition("$")
    return bool(h) and secrets.compare_digest(hashlib.pbkdf2_hmac("sha256", s.encode(), sal.encode(), 100_000).hex(), h)


def nova_senha(txt="Crie uma senha (mín. 6): "):
    s = ler_senha(txt)
    if len(s) < 6 or s != ler_senha("Repita: "):
        return print("Senha curta ou diferente.")
    return s


def marcar_nao_utilizadas():
    """Reserva ativa, 30 min após o início e sem liberação -> nao_utilizado (vira no-show)."""
    ag, lib = DB["agendamentos"], DB["liberacoes"]
    m = (ag.status == "ativo") & (ag.inicio <= (agora() - timedelta(minutes=30)).strftime(FMT)) \
        & ~ag.id.isin(lib.agendamento_id)
    if m.any():
        atualizar("agendamentos", m, status="nao_utilizado")


def calcular():
    """Leitor (frente 1) + rateio (frente 2) do repositório."""
    try:
        return calcular_da_pasta(PASTA_USO)
    except (ErroLeitura, ErroParametros) as e:
        print(f"[ERRO] {e}\nGere dados com: python gerar_uso_carregador.py --seed 5")


# ---------------------------------------------------------------- cadastro e login
def cadastrar():
    nome, cpf = ler("Nome: "), so_digitos(ler("CPF: "))
    unidade = ler("Unidade (ex.: B-21): ").upper()
    us = DB["usuarios"]
    if not (nome and unidade and cpf_valido(cpf)):
        return print("Dados inválidos (confira o CPF).")
    if (us.cpf == cpf).any() or (us.unidade_id == unidade).any():
        return print("CPF ou unidade já cadastrados.")
    senha = nova_senha()
    if not senha:
        return
    r = calcular()
    uid = next((f.usuario_id for f in r.faturas if f.unidade_id == unidade), None) if r else None
    uid = uid or f"U{len(us) + 10:02d}"                  # unidade sem uso nos arquivos: código novo
    inserir("usuarios", cpf=cpf, usuario_id=uid, nome=nome, unidade_id=unidade, senha=hash_senha(senha))
    print(f"Cadastro feito (CPF {mascara(cpf)}). Seu código: {uid}")


def entrar():
    cpf = so_digitos(ler("CPF: "))
    achou = DB["usuarios"][DB["usuarios"].cpf == cpf]
    if not achou.empty and senha_ok(ler_senha("Senha: "), achou.iloc[0].senha):
        return achou.iloc[0]
    print("CPF ou senha incorretos.")


# ---------------------------------------------------------------- agendamento
def agendar(u):
    try:
        ini = datetime.strptime(ler("Início (dd/mm/aaaa hh:mm): "), "%d/%m/%Y %H:%M")
        dur = int(ler("Duração em minutos (múltiplo de 30): "))
    except ValueError:
        return print("Valor inválido.")
    if ini.minute % 30 or dur <= 0 or dur % 30:
        return print("Use blocos de 30 minutos.")
    if dur > 120:
            return print(f"Duração máxima: 120 min.")
    
    if ini < agora() + PAR.antecedencia:
        return print(f"Reserva só com {MIN_ANT} min de antecedência.")
    fim = ini + timedelta(minutes=dur)
    ag = DB["agendamentos"]

    if ((ag.status == "ativo") & (ag.inicio < fim.strftime(FMT)) & (ag.fim > ini.strftime(FMT))).any():
        return print("Horário já reservado.")
    inserir("agendamentos", id=len(ag) + 1, usuario_id=u.usuario_id, inicio=ini.strftime(FMT),
            fim=fim.strftime(FMT), status="ativo", tardio=0)
    print(f"Reserva confirmada. No-show ou cancelamento com menos de {MIN_ANT} min: R$ {brl(PAR.taxa_no_show)}.")


def meus_agendamentos(u):
    ag = DB["agendamentos"]
    minhas = ag[ag.usuario_id == u.usuario_id].sort_values("inicio").tail(10)
    for _, a in minhas.iterrows():
        print(f"  #{a.id}  {a.inicio} → {a.fim[11:]}  {a.status}" + (" (cancelamento tardio)" if a.tardio == "1" else ""))
    num = ler("Número para cancelar (Enter volta): ")
    m = (ag.id == num) & (ag.usuario_id == u.usuario_id) & (ag.status == "ativo")
    if not num:
        return
    if not m.any():
        return print("Reserva não encontrada ou não está ativa.")
    tardio = agora() > datetime.strptime(ag[m].iloc[0].inicio, FMT) - PAR.antecedencia
    if tardio:
        print(f"ATENÇÃO: cancelar com menos de {MIN_ANT} min do início gera taxa de R$ {brl(PAR.taxa_no_show)}.")
        if ler("Confirmar? [s/N] ").lower() not in ("s", "sim"):
            return print("Cancelamento desfeito.")
    atualizar("agendamentos", m, status="cancelado", tardio="1" if tardio else "0")
    print("Reserva cancelada" + (" (com taxa)." if tardio else " sem custo."))


# ---------------------------------------------------------------- carregador
def iniciar(u):
    lib, ag = DB["liberacoes"], DB["agendamentos"]
    if (lib.fim == "").any():
        return print("O carregador está em uso.")
    t = agora().strftime(FMT)
    ativa = (ag.status == "ativo") & (ag.inicio <= (agora() + PAR.tolerancia_inicio).strftime(FMT)) & (ag.fim > t)
    minha = ag[ativa & (ag.usuario_id == u.usuario_id)]
    if not minha.empty:
        ident, ag_id = "reserva", minha.iloc[0].id
        atualizar("agendamentos", ag.id == ag_id, status="utilizado")
    else:
        if (ativa & (ag.inicio <= t)).any():
            return print("Há reserva de outro usuário em andamento.")
        ident, ag_id = ("rfid" if ler("[1] app  [2] rfid: ") == "2" else "app"), ""
        print(f"Uso avulso: taxa de R$ {brl(PAR.taxa_sem_reserva)}.")
    inserir("liberacoes", id=len(lib) + 1, usuario_id=u.usuario_id, unidade_id=u.unidade_id,
            identificacao=ident, agendamento_id=ag_id, inicio=t)
    print(f"Carregador liberado para {u.nome} ({u.unidade_id}) às {t[11:]}.")


def encerrar(u):
    lib = DB["liberacoes"]
    m = (lib.usuario_id == u.usuario_id) & (lib.fim == "")
    if not m.any():
        return print("Você não tem carregamento em andamento.")
    atualizar("liberacoes", m, fim=agora().strftime(FMT))
    print("Carregamento encerrado.")


# ---------------------------------------------------------------- fatura
def fatura(u):
    r = calcular()
    f = next((x for x in r.faturas if x.usuario_id == u.usuario_id), None) if r else None
    if r and not f:
        return print("Sem registros de uso para você nos arquivos.")
    if not f:
        return
    print(f"\nFATURA {f.competencia} — {f.nome} ({f.unidade_id}), CPF {mascara(u.cpf)}")
    print(f"{f.sessoes} sessões, {f.kwh:.2f} kWh")
    for nome, v in (("Energia", f.energia), ("Ociosidade", f.ociosidade), ("Sem reserva", f.taxa_sem_reserva),
                    ("No-show", f.no_show), ("Custo fixo", f.custo_fixo), ("TOTAL", f.total)):
        print(f"  {nome:<14} R$ {brl(v):>9}")


# ---------------------------------------------------------------- gestor
def exportar(r):
    PASTA_SAIDA.mkdir(exist_ok=True)
    arq = PASTA_SAIDA / "fatura_mensal.xlsx"
    faturas = pd.DataFrame([dict(competencia=f.competencia, unidade=f.unidade_id, usuario=f.usuario_id, nome=f.nome,
                                 sessoes=f.sessoes, kwh=round(f.kwh, 2), energia=f.energia, ociosidade=f.ociosidade,
                                 sem_reserva=f.taxa_sem_reserva, no_show=f.no_show, custo_fixo=f.custo_fixo,
                                 total=f.total) for f in r.faturas])
    detalhe = pd.DataFrame([dict(sessao=i.sessao_id, usuario=i.usuario_id, agendamento=i.agendamento_id,
                                 inicio=i.inicio, kwh=round(i.kwh, 3), energia=i.energia, ociosidade=i.ociosidade,
                                 sem_reserva=i.taxa_sem_reserva, no_show=i.no_show, total=i.total,
                                 observacao=i.observacao) for i in r.detalhe])
    with pd.ExcelWriter(arq) as w:
        faturas.to_excel(w, sheet_name="faturas", index=False)
        detalhe.to_excel(w, sheet_name="detalhe", index=False)
    print("Gravado:", arq)


def gestor():
    cfg = DB["config"]
    if cfg.empty:
        print("Primeiro acesso: defina a senha do gestor.")
        s = nova_senha("Senha do gestor (mín. 6): ")
        if not s:
            return
        inserir("config", chave="senha_gestor", valor=hash_senha(s))
    elif not senha_ok(ler_senha("Senha do gestor: "), cfg.iloc[0].valor):
        return print("Senha incorreta.")
    while True:
        marcar_nao_utilizadas()
        op = menu("GESTOR", ["Resumo do mês", "Liberações (quem iniciou)", "Agenda", "Exportar fatura (xlsx)"])
        if op == 0:
            return
        if op in (1, 4):
            r = calcular()
            if r:
                print(resumo(r, PASTA_SAIDA)) if op == 1 else exportar(r)
        elif op == 2:
            d = DB["liberacoes"].merge(DB["usuarios"][["usuario_id", "nome", "cpf"]], on="usuario_id")
            for _, l in d.sort_values("inicio").tail(20).iterrows():
                print(f"  {l.inicio} → {l.fim or 'em andamento'}  {l.nome} ({l.unidade_id}) CPF {mascara(l.cpf)}  "
                      f"{'reserva' if l.agendamento_id else 'AVULSO'}")
        else:
            d = DB["agendamentos"].merge(DB["usuarios"][["usuario_id", "nome"]], on="usuario_id")
            for _, a in d.sort_values("inicio").tail(20).iterrows():
                print(f"  #{a.id} {a.inicio} → {a.fim[11:]}  {a.nome}  {a.status}" + (" (cancel. tardio)" if a.tardio == "1" else ""))


# ---------------------------------------------------------------- principal
def area_morador(u):
    acoes = [agendar, meus_agendamentos, iniciar, encerrar, fatura]
    while True:
        marcar_nao_utilizadas()
        op = menu(f"Olá, {u.nome.split()[0]} — CPF {mascara(u.cpf)} — unidade {u.unidade_id}",
                  ["Novo agendamento", "Meus agendamentos", "Iniciar carregamento", "Encerrar carregamento",
                   "Fatura mensal"])
        if op == 0:
            return
        acoes[op - 1](u)


def main():
    while True:
        op = menu("EV ChargeOps", ["Entrar (CPF e senha)", "Cadastrar-se", "Painel do gestor"])
        if op == 0:
            return
        if op == 1:
            u = entrar()
            if u is not None:
                area_morador(u)
        elif op == 2:
            cadastrar()
        else:
            gestor()


if __name__ == "__main__":
    main()