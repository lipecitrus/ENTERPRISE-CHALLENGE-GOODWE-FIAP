"""
gerar_sessao_terminal.py — grava uma sessão real do main.py em sessao_terminal.txt.

Copia o projeto para uma pasta temporária (para não criar ev_chargeops.xlsx nem
uso_carregador/ no repositório), gera os CSVs com --seed 5 e conduz o menu do
main.py como um usuário faria: cadastro, login, reservas, fatura, liberação do
carregador e painel do gestor. As senhas não aparecem porque o main.py usa getpass.

Requer pexpect (Linux/macOS):  pip install pexpect
Uso, a partir da raiz do repositório:  python evidencias/gerar_sessao_terminal.py
"""
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pexpect

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = Path(__file__).resolve().parent / "sessao_terminal.txt"
ARQUIVOS = ["main.py", "leitor_uso.py", "gerar_uso_carregador.py", "ia_uso.py", "config", "src"]

CPF, SENHA, SENHA_GESTOR = "52998224725", "morador123", "gestor123"


def main():
    with tempfile.TemporaryDirectory() as tmp:
        for nome in ARQUIVOS:
            origem, destino = RAIZ / nome, Path(tmp) / nome
            if origem.is_dir():
                shutil.copytree(origem, destino, ignore=shutil.ignore_patterns("__pycache__"))
            else:
                shutil.copy2(origem, destino)
        subprocess.run([sys.executable, "gerar_uso_carregador.py", "--seed", "5"], cwd=tmp, check=True,
                       capture_output=True)

        # reserva para amanhã às 10h: respeita a antecedência mínima de 60 min
        reserva = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y") + " 10:00"
        log = []
        p = pexpect.spawn(sys.executable, ["main.py"], cwd=tmp, encoding="utf-8", timeout=60,
                          dimensions=(50, 200))
        p.logfile_read = type("Log", (), {"write": lambda _, t: log.append(t), "flush": lambda _: None})()

        def passo(espera, resposta):
            p.expect(re.escape(espera))
            p.sendline(resposta)

        # cadastro do morador da unidade B-21
        passo("Opção: ", "2")
        passo("Nome: ", "Juliana Castro")
        passo("CPF: ", "529.982.247-25")
        passo("Unidade (ex.: B-21): ", "B-21")
        passo("Crie uma senha (mín. 6): ", SENHA)
        passo("Repita: ", SENHA)
        # login
        passo("Opção: ", "1")
        passo("CPF: ", CPF)
        passo("Senha: ", SENHA)
        # duas reservas no mesmo horário: a segunda é recusada
        for _ in range(2):
            passo("Opção: ", "1")
            passo("Início (dd/mm/aaaa hh:mm): ", reserva)
            passo("Duração em minutos (múltiplo de 30): ", "60")
        passo("Opção: ", "2")                      # meus agendamentos
        passo("Número para cancelar (Enter volta): ", "")
        passo("Opção: ", "5")                      # fatura mensal
        passo("Opção: ", "3")                      # iniciar carregamento (avulso)
        passo("[1] app  [2] rfid: ", "2")
        passo("Opção: ", "4")                      # encerrar carregamento
        passo("Opção: ", "0")
        # painel do gestor (primeiro acesso define a senha)
        passo("Opção: ", "3")
        passo("Senha do gestor (mín. 6): ", SENHA_GESTOR)
        passo("Repita: ", SENHA_GESTOR)
        for op in ("1", "2", "3", "4", "5"):
            passo("Opção: ", op)
        passo("Opção: ", "0")
        passo("Opção: ", "0")
        p.expect(pexpect.EOF)

    texto = "".join(log).replace("\r\n", "\n").replace("\r", "")
    texto = texto.replace(tmp + "/", "")
    cabecalho = (f"# Sessão gravada em {datetime.now():%d/%m/%Y %H:%M} com evidencias/gerar_sessao_terminal.py\n"
                 "# Dados de uso: python gerar_uso_carregador.py --seed 5. As senhas não são exibidas (getpass).\n\n")
    SAIDA.write_text(cabecalho + "$ python main.py\n" + texto, encoding="utf-8")
    print("Gravado:", SAIDA)


if __name__ == "__main__":
    main()
