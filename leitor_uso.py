"""
leitor_uso.py — leitor dos CSVs de uso do carregador (EV ChargeOps).

Corresponde ao item 1 do documento "Sistema de Leitura" (fonte de dados), agora
para os arquivos uso_*.csv do carregador (um por usuário). O leitor NÃO calcula
valores: só lê, normaliza e entrega objetos ao restante do sistema:

    UsoUsuario  ->  Sessao  ->  Leitura (ponto do medidor)
                    Reserva / EventoReserva

Cuidados do leitor (item 1 do documento, adaptados a este formato):
  * Colunas localizadas pelo NOME do cabeçalho (sem acento, maiúsculas ou ordem
    fixa); colunas extras são ignoradas, colunas opcionais ausentes viram vazio.
  * Valores chegam como texto: aceita vírgula ou ponto decimal, unidades
    ("6,5 kW"), vazios, "-" e "N/A".
  * Variações toleradas: delimitador (, ; tab |), encoding (UTF-8 com/sem BOM,
    UTF-16 com BOM, cp1252), formatos de data, linhas em branco, linhas fora de
    ordem e duplicadas.
  * Aceita UM arquivo ou uma PASTA (todos os uso_*.csv). Um arquivo ruim na
    pasta não derruba os demais.
  * Problemas fora do padrão viram AVISOS, não falhas. Só levanta ErroLeitura
    quando o arquivo é inutilizável (ilegível, sem colunas obrigatórias, vazio).
  * Os arquivos originais nunca são alterados.

Uso:
    python leitor_uso.py [arquivo.csv | pasta]      (padrão: ./uso_carregador ao lado do script)

Em código:
    from leitor_uso import UsoSource
    r = UsoSource().ler("uso_carregador")
    for u in r.usuarios.values(): print(u.nome, len(u.sessoes), u.kwh)
    r.avisos                    # lista de textos
"""
from __future__ import annotations

import csv
import io
import re
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# --------------------------------------------------------------- modelo
EVENTOS = {"inicio": "Inicio", "medicao": "Medicao", "carro_cheio": "CarroCheio", "carrocheio": "CarroCheio",
           "fim": "Fim", "reserva_nao_utilizada": "ReservaNaoUtilizada", "reservanaoutilizada": "ReservaNaoUtilizada",
           "reserva_cancelada": "ReservaCancelada", "reservacancelada": "ReservaCancelada"}

# nome canônico -> nomes aceitos no cabeçalho (já normalizados)
COLUNAS = {
    "timestamp": ("timestamp", "data_hora", "datahora", "datetime"),
    "usuario_id": ("usuario_id", "usuario", "id_usuario", "user_id"),
    "unidade_id": ("unidade_id", "unidade", "apartamento"),
    "evento": ("evento", "event", "tipo_evento"),
    "sessao_id": ("sessao_id", "sessao", "id_sessao", "transaction_id"),
    "identificacao": ("identificacao", "autenticacao"),
    "agendamento_id": ("agendamento_id", "reserva_id", "agendamento"),
    "reserva_inicio": ("reserva_inicio",),
    "reserva_fim": ("reserva_fim",),
    "reserva_criada_em": ("reserva_criada_em", "reserva_criada"),
    "energia_acumulada_kwh": ("energia_acumulada_kwh", "energia_kwh", "medidor_kwh", "registrador_kwh"),
    "potencia_kw": ("potencia_kw", "potencia"),
    "soc_pct": ("soc_pct", "soc"),
    "fila_espera": ("fila_espera", "fila"),
    "motivo_parada": ("motivo_parada", "motivo"),
}
OBRIGATORIAS = ("timestamp", "evento", "usuario_id", "sessao_id", "energia_acumulada_kwh")


class ErroLeitura(Exception):
    """Arquivo inutilizável (ilegível, sem colunas obrigatórias ou sem dados)."""


@dataclass
class Reserva:
    id: str
    inicio: Optional[datetime]
    fim: Optional[datetime]
    criada_em: Optional[datetime]


@dataclass
class Leitura:
    """Um ponto do medidor dentro de uma sessão."""
    t: datetime
    energia_kwh: float                      # registrador acumulado do medidor
    potencia_kw: Optional[float] = None
    soc_pct: Optional[float] = None
    fila_espera: bool = False               # outro usuário com reserva ativa neste instante


@dataclass
class Sessao:
    id: str
    usuario_id: str                         # "" = sessão não identificada
    unidade_id: str
    identificacao: str                      # reserva | rfid | app | ""
    inicio: datetime
    fim: datetime
    fim_carga: datetime                     # quando o carro parou de puxar energia
    status: str                             # Concluida | Interrompida | Incompleta
    motivo_parada: str
    reserva: Optional[Reserva]
    leituras: list[Leitura]
    arquivo: str = ""

    @property
    def identificada(self) -> bool:
        return bool(self.usuario_id and self.identificacao)

    @property
    def reg_ini(self) -> float:
        return self.leituras[0].energia_kwh if self.leituras else 0.0

    @property
    def reg_fim(self) -> float:
        return self.leituras[-1].energia_kwh if self.leituras else 0.0

    @property
    def kwh(self) -> float:
        return self.reg_fim - self.reg_ini

    @property
    def duracao_min(self) -> int:
        return int((self.fim - self.inicio).total_seconds() // 60)


@dataclass
class EventoReserva:
    tipo: str                               # nao_utilizada | cancelada
    timestamp: datetime
    usuario_id: str
    unidade_id: str
    reserva: Reserva


@dataclass
class UsoUsuario:
    usuario_id: str
    nome: str
    unidade_id: str
    arquivos: list[str] = field(default_factory=list)
    sessoes: list[Sessao] = field(default_factory=list)
    eventos_reserva: list[EventoReserva] = field(default_factory=list)

    @property
    def kwh(self) -> float:
        return sum(s.kwh for s in self.sessoes)


@dataclass
class ResultadoLeitura:
    usuarios: dict[str, UsoUsuario]
    sessoes: list[Sessao]                   # TODAS (inclui não identificadas), em ordem cronológica
    eventos_reserva: list[EventoReserva]
    reservas: dict[str, Reserva]            # reservas únicas vistas nos arquivos
    avisos: list[str]
    arquivos: list[str]

    @property
    def nao_identificadas(self) -> list[Sessao]:
        return [s for s in self.sessoes if not s.identificada]


# --------------------------------------------------------------- utilitários
def _norm(txt: str) -> str:
    t = unicodedata.normalize("NFKD", txt)
    t = "".join(c for c in t if not unicodedata.combining(c)).lower().strip()
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")


def _numero(txt: str) -> Optional[float]:
    """'' / '-' / 'N/A' -> None; '6,5' / '1.234,5' / '0.19 kW' -> float; lixo -> ValueError."""
    t = (txt or "").replace("\xa0", " ").strip()
    if t.lower() in ("", "-", "--", "n/a", "na", "nan", "none", "null"):
        return None
    t = re.sub(r"[^\d,.\-+]", "", t)
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".") if t.rfind(",") > t.rfind(".") else t.replace(",", "")
    elif "," in t:
        t = t.replace(",", ".")
    return float(t)


_FORMATOS_DATA = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M",
                  "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d-%m-%Y %H:%M:%S", "%d/%m/%y %H:%M")


def _data(txt: str) -> Optional[datetime]:
    t = (txt or "").strip()
    if not t:
        return None
    for fmt in _FORMATOS_DATA:
        try:
            return datetime.strptime(t, fmt)
        except ValueError:
            continue
    raise ValueError(f"data/hora ilegível '{txt}'")


def _decodificar(bruto: bytes) -> str:
    # UTF-16 só com BOM (sem BOM ele "decodifica" qualquer coisa e gera lixo)
    if bruto.startswith((b"\xff\xfe", b"\xfe\xff")):
        return bruto.decode("utf-16")
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return bruto.decode(enc)
        except UnicodeError:
            continue
    return bruto.decode("latin-1", errors="replace")


def _delimitador(cabecalho: str) -> str:
    return max(",;\t|", key=cabecalho.count)


def _booleano(txt: str) -> bool:
    return (txt or "").strip().lower() in ("1", "true", "sim", "s", "yes", "y")


def _nome_do_arquivo(stem: str, uid: str) -> str:
    partes = stem.split("_")
    if len(partes) > 2 and partes[0].lower() == "uso":
        return " ".join(partes[2:]).title()
    return uid


# --------------------------------------------------------------- leitor
class UsoSource:
    """Lê um arquivo .csv de uso ou uma pasta com vários uso_*.csv."""

    def ler(self, caminho: str | Path) -> ResultadoLeitura:
        p = Path(caminho)
        avisos: list[str] = []
        if p.is_dir():
            arquivos = sorted(f for f in p.iterdir() if f.is_file() and f.suffix.lower() == ".csv"
                              and f.name.lower().startswith("uso_"))
            if not arquivos:
                raise ErroLeitura(f"Nenhum uso_*.csv encontrado em {p}")
        elif p.is_file():
            arquivos = [p]
        else:
            raise ErroLeitura(f"Caminho não encontrado: {p}")

        linhas: list[dict] = []
        lidos: list[str] = []
        for arq in arquivos:
            try:
                linhas += self._ler_arquivo(arq, avisos)
                lidos.append(arq.name)
            except ErroLeitura as e:
                if len(arquivos) == 1:
                    raise
                avisos.append(f"{arq.name}: arquivo ignorado ({e})")
        if not lidos:
            raise ErroLeitura("Nenhum arquivo pôde ser lido")
        return self._montar(linhas, lidos, avisos)

    # --- um arquivo -> linhas normalizadas
    @staticmethod
    def _ler_arquivo(arq: Path, avisos: list[str]) -> list[dict]:
        try:
            texto = _decodificar(arq.read_bytes())
        except OSError as e:
            raise ErroLeitura(f"não foi possível abrir: {e}") from e
        linhas_txt = [l for l in texto.splitlines() if l.strip()]
        if len(linhas_txt) < 2:
            raise ErroLeitura("arquivo vazio ou só com cabeçalho")
        leitor = csv.reader(io.StringIO("\n".join(linhas_txt)), delimiter=_delimitador(linhas_txt[0]))
        cab = next(leitor)

        indice: dict[str, int] = {}
        for j, nome in enumerate(cab):
            n = _norm(nome)
            for canon, aceitos in COLUNAS.items():
                if n in aceitos and canon not in indice:
                    indice[canon] = j
        faltam = [c for c in OBRIGATORIAS if c not in indice]
        if faltam:
            raise ErroLeitura(f"colunas obrigatórias ausentes: {', '.join(faltam)}")
        ausentes_opc = [c for c in COLUNAS if c not in indice]
        if ausentes_opc:
            avisos.append(f"{arq.name}: colunas opcionais ausentes ({', '.join(ausentes_opc)}); tratadas como vazias")

        out, vistos, dup, ordenado, anterior = [], set(), 0, True, None
        for n_linha, cel in enumerate(leitor, start=2):
            def campo(nome: str) -> str:
                j = indice.get(nome)
                return cel[j].strip() if j is not None and j < len(cel) else ""
            try:
                ts = _data(campo("timestamp"))
            except ValueError as e:
                avisos.append(f"{arq.name} linha {n_linha}: {e}; linha ignorada")
                continue
            if ts is None:
                avisos.append(f"{arq.name} linha {n_linha}: sem timestamp; linha ignorada")
                continue
            ev = EVENTOS.get(_norm(campo("evento")))
            if ev is None:
                avisos.append(f"{arq.name} linha {n_linha}: evento desconhecido '{campo('evento')}'; ignorada")
                continue
            chave = (ts, ev, campo("sessao_id"), campo("usuario_id"), campo("agendamento_id"))
            if chave in vistos:
                dup += 1
                continue
            vistos.add(chave)
            if anterior and ts < anterior:
                ordenado = False
            anterior = ts

            def num(nome: str) -> Optional[float]:
                try:
                    return _numero(campo(nome))
                except ValueError:
                    avisos.append(f"{arq.name} linha {n_linha}: valor ilegível em {nome} ('{campo(nome)}')")
                    return None

            def dh(nome: str) -> Optional[datetime]:
                try:
                    return _data(campo(nome))
                except ValueError as e:
                    avisos.append(f"{arq.name} linha {n_linha} ({nome}): {e}")
                    return None

            out.append(dict(
                ts=ts, evento=ev, usuario=campo("usuario_id"), unidade=campo("unidade_id"),
                sessao=campo("sessao_id"), ident=campo("identificacao").lower(), ag=campo("agendamento_id"),
                res_ini=dh("reserva_inicio"), res_fim=dh("reserva_fim"), res_criada=dh("reserva_criada_em"),
                energia=num("energia_acumulada_kwh"), potencia=num("potencia_kw"), soc=num("soc_pct"),
                fila=_booleano(campo("fila_espera")), motivo=campo("motivo_parada"), arquivo=arq.name))
        if dup:
            avisos.append(f"{arq.name}: {dup} linha(s) duplicada(s) descartada(s)")
        if not ordenado:
            avisos.append(f"{arq.name}: linhas fora de ordem cronológica; reordenadas")
        if not out:
            raise ErroLeitura("nenhuma linha válida")
        return out

    # --- linhas de todos os arquivos -> objetos
    @staticmethod
    def _montar(linhas: list[dict], lidos: list[str], avisos: list[str]) -> ResultadoLeitura:
        reservas: dict[str, Reserva] = {}

        def reserva_de(l: dict) -> Optional[Reserva]:
            if not l["ag"]:
                return None
            r = reservas.get(l["ag"])
            if r is None:
                r = reservas[l["ag"]] = Reserva(l["ag"], l["res_ini"], l["res_fim"], l["res_criada"])
            else:                                  # completa dados que faltavam em outra linha
                r.inicio = r.inicio or l["res_ini"]
                r.fim = r.fim or l["res_fim"]
                r.criada_em = r.criada_em or l["res_criada"]
            if r.inicio and r.fim and r.fim <= r.inicio:
                avisos.append(f"{r.id}: reserva com fim antes do início")
            return r

        grupos: dict[str, list[dict]] = defaultdict(list)
        eventos: list[EventoReserva] = []
        for l in linhas:
            if l["evento"] in ("ReservaNaoUtilizada", "ReservaCancelada"):
                r = reserva_de(l)
                if r is None:
                    avisos.append(f"{l['ts']}: {l['evento']} sem agendamento_id; ignorado")
                    continue
                eventos.append(EventoReserva("nao_utilizada" if l["evento"] == "ReservaNaoUtilizada" else "cancelada",
                                             l["ts"], l["usuario"], l["unidade"], r))
            elif l["sessao"]:
                grupos[l["sessao"]].append(l)
            else:
                avisos.append(f"{l['ts']}: linha '{l['evento']}' sem sessao_id; ignorada")

        sessoes: list[Sessao] = []
        for sid, ls in grupos.items():
            ls.sort(key=lambda x: x["ts"])
            ini_l = next((x for x in ls if x["evento"] == "Inicio"), None)
            if ini_l is None:
                avisos.append(f"{sid}: sem evento Inicio; sessão ignorada")
                continue
            usuarios = {x["usuario"] for x in ls}
            if len(usuarios) > 1:
                avisos.append(f"{sid}: aparece com usuários diferentes ({', '.join(sorted(u or '(vazio)' for u in usuarios))})")
            fim_l = next((x for x in reversed(ls) if x["evento"] == "Fim"), None)
            ult = fim_l or ls[-1]
            cheio = next((x for x in ls if x["evento"] == "CarroCheio"), None)
            motivo = (fim_l or {}).get("motivo", "")
            if fim_l is None:
                avisos.append(f"{sid}: sem evento Fim; usada a última leitura (sessão incompleta)")
                status = "Incompleta"
            elif motivo == "PowerLoss":
                status = "Interrompida"
            else:
                status = "Concluida"
                if motivo not in ("", "EVDisconnected"):
                    avisos.append(f"{sid}: motivo_parada desconhecido '{motivo}'")
            if cheio:
                fim_carga = cheio["ts"]
            else:
                fim_carga = ult["ts"]
                if status == "Concluida":
                    avisos.append(f"{sid}: sem evento CarroCheio; fim da carga assumido no fim da sessão")
            pts = [Leitura(x["ts"], x["energia"], x["potencia"], x["soc"], x["fila"])
                   for x in ls if x["energia"] is not None]
            if len(pts) < 2:
                avisos.append(f"{sid}: menos de 2 leituras do medidor; kWh não confiável")
            for a, b in zip(pts, pts[1:]):
                if b.energia_kwh < a.energia_kwh - 1e-9:
                    avisos.append(f"{sid}: energia acumulada diminuiu entre {a.t:%H:%M} e {b.t:%H:%M}")
            sessoes.append(Sessao(
                id=sid, usuario_id=ini_l["usuario"], unidade_id=ini_l["unidade"], identificacao=ini_l["ident"],
                inicio=ini_l["ts"], fim=ult["ts"], fim_carga=fim_carga, status=status, motivo_parada=motivo,
                reserva=reserva_de(ini_l), leituras=pts, arquivo=ini_l["arquivo"]))
        sessoes.sort(key=lambda s: s.inicio)

        usuarios_obj: dict[str, UsoUsuario] = {}
        for l in linhas:
            uid = l["usuario"]
            if uid and uid not in usuarios_obj:
                usuarios_obj[uid] = UsoUsuario(uid, _nome_do_arquivo(Path(l["arquivo"]).stem, uid), l["unidade"])
            if uid and l["arquivo"] not in usuarios_obj[uid].arquivos:
                usuarios_obj[uid].arquivos.append(l["arquivo"])
        for s in sessoes:
            if s.usuario_id in usuarios_obj:
                usuarios_obj[s.usuario_id].sessoes.append(s)
        for e in sorted(eventos, key=lambda x: x.timestamp):
            if e.usuario_id in usuarios_obj:
                usuarios_obj[e.usuario_id].eventos_reserva.append(e)
        return ResultadoLeitura(dict(sorted(usuarios_obj.items())), sessoes, sorted(eventos, key=lambda x: x.timestamp),
                                reservas, avisos, lidos)


# --------------------------------------------------------------- CLI
def main(argv: list[str]) -> int:
    alvo = argv[1] if len(argv) > 1 else str(Path(__file__).resolve().parent / "uso_carregador")
    try:
        r = UsoSource().ler(alvo)
    except ErroLeitura as e:
        print(f"[ERRO] {e}")
        return 1
    print(f"{len(r.arquivos)} arquivo(s) lido(s): {', '.join(r.arquivos)}\n")
    print(f"{'usuário':8}{'nome':26}{'unid':7}{'sessões':>8}{'kWh':>9}{'reservas s/ uso':>17}  período")
    for u in r.usuarios.values():
        per = f"{u.sessoes[0].inicio:%d/%m %H:%M} → {u.sessoes[-1].fim:%d/%m %H:%M}" if u.sessoes else "—"
        print(f"{u.usuario_id:8}{u.nome[:25]:26}{u.unidade_id:7}{len(u.sessoes):>8}{u.kwh:9.2f}"
              f"{len(u.eventos_reserva):>17}  {per}")
    ni = r.nao_identificadas
    if ni:
        print(f"\nSessões NÃO identificadas: {len(ni)} ({sum(s.kwh for s in ni):.2f} kWh): {', '.join(s.id for s in ni)}")
    print(f"\n{len(r.sessoes)} sessões, {sum(s.kwh for s in r.sessoes):.2f} kWh no total, {len(r.avisos)} aviso(s)")
    for a in r.avisos[:15]:
        print("  aviso:", a)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
