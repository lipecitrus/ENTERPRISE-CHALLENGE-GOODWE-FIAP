"""
Testes da frente 2 (rateio e fatura). Só biblioteca padrão:

    python -m unittest discover -s tests -v        (a partir da raiz do repositório)

1. Regras isoladas, com sessões montadas à mão (sem depender do gerador).
2. Aceitação com a semente 5 (seção 3.3 do Sistema de Leitura), com cada cobrança
   arredondada a centavos antes de somar: R$ 884,20 (o documento traz R$ 884,19,
   calculado sem arredondar por sessão), S0009, S0020 e o no-show da AG0004.
3. Dados com --anomalias (validações da seção 5.1).
4. Propriedades que valem para qualquer mês gerado e a linha de comando (calcular_fatura.py).
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.rateio import (NAO_IDENTIFICADO, ErroParametros, Parametros, calcular_da_pasta,  # noqa: E402
                        calcular_rateio, carregar_parametros)
from src.rateio import regras  # noqa: E402
from src.rateio.regras import centavos  # noqa: E402
from src.rateio.contrato import EventoReserva, Leitura, Reserva, ResultadoLeitura, Sessao, UsoSource  # noqa: E402
from src.rateio.parametros import ARQUIVO_PADRAO, FAIXAS, _ler_csv  # noqa: E402
from src.rateio.saida import gravar  # noqa: E402

PAR = carregar_parametros()


def gerar(pasta: Path, *args: str) -> Path:
    subprocess.run([sys.executable, str(RAIZ / "gerar_uso_carregador.py"), "--saida", str(pasta), *args],
                   check=True, capture_output=True)
    return pasta


def dt(txt: str) -> datetime:
    return datetime.strptime(txt, "%Y-%m-%d %H:%M")


def sessao(leituras: list[tuple[str, float, bool]], fim_carga: str | None = None, reserva: Reserva | None = None,
           motivo: str = "EVDisconnected", usuario: str = "U01", ident: str = "app") -> Sessao:
    pts = [Leitura(dt(t), e, fila_espera=f) for t, e, f in leituras]
    return Sessao(id="S9999", usuario_id=usuario, unidade_id="A-11", identificacao=ident, inicio=pts[0].t,
                  fim=pts[-1].t, fim_carga=dt(fim_carga) if fim_carga else pts[-1].t,
                  status="Concluida", motivo_parada=motivo, reserva=reserva, leituras=pts)


# ------------------------------------------------------------------ 1. regras
class TestParametros(unittest.TestCase):
    def test_valores_padrao_da_secao_3_1(self):
        self.assertEqual(PAR.preco, {"fora_ponta": 0.85, "intermediaria": 1.20, "ponta": 1.70})
        self.assertEqual(PAR.horas_ponta, {18, 19, 20})
        self.assertEqual(PAR.horas_intermediaria, {17, 21})
        self.assertEqual((PAR.carencia, PAR.bloco), (timedelta(minutes=15), timedelta(minutes=30)))
        self.assertEqual((PAR.taxa_bloco, PAR.teto_ociosidade), (2.0, 20.0))
        self.assertEqual((PAR.taxa_sem_reserva, PAR.taxa_no_show, PAR.custo_fixo), (1.5, 5.0, 15.0))
        self.assertEqual(PAR.antecedencia, timedelta(minutes=60))

    def test_sobrescrita_pela_pasta_de_uso(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "parametros_rateio.csv").write_text("parametro,valor\npreco_ponta,\"2,10\"\n", encoding="utf-8")
            p = carregar_parametros(d)
        self.assertEqual(p.preco["ponta"], 2.10)
        self.assertEqual(p.preco["fora_ponta"], 0.85)
        self.assertEqual(len(p.origem), 2)

    def test_parametro_ausente_ou_ilegivel(self):
        base = _ler_csv(ARQUIVO_PADRAO)
        with self.assertRaises(ErroParametros):
            Parametros.de_dict({k: v for k, v in base.items() if k != "taxa_no_show"})
        with self.assertRaises(ErroParametros):
            Parametros.de_dict({**base, "preco_ponta": "abc"})
        with self.assertRaises(ErroParametros):
            Parametros.de_dict({**base, "horas_intermediaria": "17;18"})
        with self.assertRaises(ErroParametros):
            carregar_parametros(arquivo_base=RAIZ / "nao_existe.csv")


class TestRegras(unittest.TestCase):
    def test_faixa_horaria(self):
        self.assertEqual(regras.faixa(dt("2026-09-09 18:30"), PAR), "ponta")          # quarta
        self.assertEqual(regras.faixa(dt("2026-09-09 21:59"), PAR), "intermediaria")
        self.assertEqual(regras.faixa(dt("2026-09-09 17:00"), PAR), "intermediaria")
        self.assertEqual(regras.faixa(dt("2026-09-09 22:00"), PAR), "fora_ponta")
        self.assertEqual(regras.faixa(dt("2026-09-12 19:00"), PAR), "fora_ponta")     # sábado
        self.assertEqual(regras.faixa(dt("2026-09-07 19:00"), PAR), "fora_ponta")     # feriado

    def test_energia_pelo_ponto_medio(self):
        # pontos médios: 20:57:30 (ponta), 21:12:30 (intermediária), 22:20 (fora de ponta)
        s = sessao([("2026-09-09 20:50", 100.0, False), ("2026-09-09 21:05", 101.5, False),
                    ("2026-09-09 21:20", 103.0, False), ("2026-09-09 23:20", 107.0, False)])
        kwh = regras.kwh_por_faixa(s, PAR)
        self.assertAlmostEqual(kwh["ponta"], 1.5)
        self.assertAlmostEqual(kwh["intermediaria"], 1.5)
        self.assertAlmostEqual(kwh["fora_ponta"], 4.0)
        self.assertAlmostEqual(regras.custo_energia(kwh, PAR), 1.5 * 1.70 + 1.5 * 1.20 + 4.0 * 0.85)

    def test_energia_com_uma_leitura_vai_para_faixa_do_inicio(self):
        s = sessao([("2026-09-09 19:00", 100.0, False)])
        self.assertEqual(regras.kwh_por_faixa(s, PAR), {"fora_ponta": 0.0, "intermediaria": 0.0, "ponta": 0.0})

    def test_ociosidade_so_com_fila_apos_carencia_por_bloco_iniciado(self):
        # carga acaba 01:00 -> ociosidade a partir de 01:15; fila nas leituras de 01:30 e 02:00
        s = sessao([("2026-09-10 00:00", 100.0, False), ("2026-09-10 01:00", 107.0, False),
                    ("2026-09-10 01:30", 107.0, True), ("2026-09-10 02:00", 107.0, True),
                    ("2026-09-10 03:00", 107.0, False)], fim_carga="2026-09-10 01:00")
        espera = regras.tempo_ocioso_com_fila(s, PAR)
        self.assertEqual(espera, timedelta(minutes=45))                 # 01:15-01:30 + 01:30-02:00
        self.assertEqual(regras.blocos_ociosidade(espera, PAR), 2)      # 45 min = 2 blocos iniciados
        self.assertEqual(regras.custo_ociosidade(2, PAR), 4.0)

    def test_ociosidade_sem_fila_e_gratis(self):
        s = sessao([("2026-09-10 00:00", 100.0, False), ("2026-09-10 05:00", 110.0, False)],
                   fim_carga="2026-09-10 01:00")
        self.assertEqual(regras.tempo_ocioso_com_fila(s, PAR), timedelta())

    def test_ociosidade_tem_teto_e_nao_vale_para_power_loss(self):
        self.assertEqual(regras.custo_ociosidade(50, PAR), 20.0)
        s = sessao([("2026-09-10 00:00", 100.0, False), ("2026-09-10 05:00", 107.0, True)],
                   fim_carga="2026-09-10 01:00", motivo="PowerLoss")
        self.assertEqual(regras.tempo_ocioso_com_fila(s, PAR), timedelta())

    def test_taxa_sem_reserva(self):
        r = Reserva("AG1", dt("2026-09-10 00:00"), dt("2026-09-10 02:00"), dt("2026-09-09 10:00"))
        self.assertEqual(regras.taxa_sem_reserva(sessao([("2026-09-10 00:00", 1.0, False)]), PAR), 1.5)
        self.assertEqual(regras.taxa_sem_reserva(sessao([("2026-09-10 00:00", 1.0, False)], reserva=r), PAR), 0.0)

    def test_no_show_e_cancelamento(self):
        r = Reserva("AG1", dt("2026-09-10 20:00"), dt("2026-09-10 22:00"), dt("2026-09-09 10:00"))
        ev = lambda tipo, t: EventoReserva(tipo, dt(t), "U01", "A-11", r)
        self.assertEqual(regras.motivo_cobranca_reserva(ev("nao_utilizada", "2026-09-10 22:00"), PAR),
                         "reserva não utilizada")
        self.assertEqual(regras.motivo_cobranca_reserva(ev("cancelada", "2026-09-10 19:30"), PAR),
                         "cancelamento tardio")
        self.assertIsNone(regras.motivo_cobranca_reserva(ev("cancelada", "2026-09-10 18:59"), PAR))
        sem_inicio = EventoReserva("cancelada", dt("2026-09-10 19:30"), "U01", "A-11", Reserva("AG2", None, None, None))
        self.assertIsNone(regras.motivo_cobranca_reserva(sem_inicio, PAR))

    def test_centavos_meio_para_cima(self):
        self.assertEqual(centavos(2.955), 2.96)
        self.assertEqual(centavos(2.945), 2.95)
        self.assertEqual(centavos(1.005), 1.01)             # round(1.005, 2) daria 1.0
        self.assertEqual(centavos(0.1 + 0.2), 0.30)
        self.assertEqual(centavos(10.004999), 10.0)

    def test_sessao_nao_identificada(self):
        conhecidos = {"U01"}
        self.assertEqual(regras.motivo_nao_identificada(sessao([("2026-09-10 00:00", 1, False)], usuario=""),
                                                        conhecidos), "sem usuário")
        self.assertEqual(regras.motivo_nao_identificada(sessao([("2026-09-10 00:00", 1, False)], usuario="U77"),
                                                        conhecidos), "usuário não cadastrado")
        self.assertEqual(regras.motivo_nao_identificada(sessao([("2026-09-10 00:00", 1, False)], ident=""),
                                                        conhecidos), "sem identificação")
        self.assertIsNone(regras.motivo_nao_identificada(sessao([("2026-09-10 00:00", 1, False)]), conhecidos))


class TestCompetencia(unittest.TestCase):
    def _lido(self, inicios: list[str]) -> ResultadoLeitura:
        ss = [sessao([(t, 1.0, False), (t, 2.0, False)]) for t in inicios]
        for i, s in enumerate(ss):
            s.id = f"S{i:04d}"
        return ResultadoLeitura({}, ss, [], {}, [], [])

    def test_mes_do_inicio_da_sessao(self):
        # sessão que começa em 30/09 e termina em 01/10 é de setembro
        r = calcular_rateio(self._lido(["2026-09-02 10:00", "2026-09-30 23:30"]), PAR)
        self.assertEqual(r.competencia, "2026-09")
        self.assertFalse(any("mais de um mês" in a for a in r.avisos))

    def test_meses_misturados_geram_aviso(self):
        r = calcular_rateio(self._lido(["2026-09-02 10:00", "2026-09-03 10:00", "2026-10-01 08:00"]), PAR)
        self.assertEqual(r.competencia, "2026-09")
        self.assertTrue(any("mais de um mês" in a and "2026-10 (1)" in a for a in r.avisos))

    def test_competencia_informada_prevalece(self):
        self.assertEqual(calcular_rateio(self._lido(["2026-09-02 10:00"]), PAR, "2026-08").competencia, "2026-08")

    def test_sem_dados(self):
        self.assertEqual(calcular_rateio(self._lido([]), PAR).competencia, "")


# ------------------------------------------------------------------ 2. aceitação (semente 5)
class TestAceitacaoSemente5(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.pasta = gerar(Path(cls.tmp.name) / "ref5", "--seed", "5")
        cls.r = calcular_da_pasta(cls.pasta)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_totais_gerais(self):
        self.assertEqual(self.r.n_sessoes, 34)
        self.assertEqual(round(self.r.kwh_total), 774)
        self.assertEqual(self.r.avisos, [])
        self.assertEqual(self.r.nao_identificadas, [])
        self.assertEqual(self.r.total_arrecadar, 884.20)
        self.assertEqual(self.r.competencia, "2026-09")

    def test_tabela_por_usuario(self):
        esperado = {  # unidade, sessões, kWh, energia, ociosidade, sem reserva, no-show, total
            "U01": ("A-11", 7, 154.47, 159.07, 0.00, 1.50, 0.00, 175.57),
            "U02": ("B-14", 6, 277.66, 269.56, 0.00, 6.00, 0.00, 290.56),
            "U03": ("B-21", 11, 129.99, 140.10, 22.00, 10.50, 0.00, 187.60),
            "U04": ("B-33", 6, 110.36, 101.67, 0.00, 6.00, 5.00, 127.67),
            "U05": ("B-42", 4, 101.54, 86.30, 0.00, 1.50, 0.00, 102.80),
        }
        self.assertEqual([f.usuario_id for f in self.r.faturas], list(esperado))
        for uid, (unid, n, kwh, ener, ocio, sem, ns, total) in esperado.items():
            with self.subTest(uid=uid):
                f = self.r.fatura(uid)
                self.assertEqual((f.unidade_id, f.sessoes), (unid, n))
                for obtido, valor in ((f.kwh, kwh), (f.energia, ener), (f.ociosidade, ocio),
                                      (f.taxa_sem_reserva, sem), (f.no_show, ns), (f.total, total)):
                    self.assertAlmostEqual(round(obtido, 2), valor, places=2)
                self.assertEqual(f.custo_fixo, 15.0)
                self.assertEqual(f.competencia, "2026-09")

    def test_caso_S0009(self):
        c = self.r.cobranca("S0009")
        self.assertEqual((c.usuario_id, c.agendamento_id), ("U03", "AG0009"))
        self.assertAlmostEqual(c.kwh, 12.873, places=3)
        self.assertAlmostEqual(c.kwh_faixa["intermediaria"], 2.457, places=3)
        self.assertAlmostEqual(c.kwh_faixa["fora_ponta"], 10.416, places=3)
        self.assertAlmostEqual(c.kwh_faixa["ponta"], 0.0, places=3)
        self.assertAlmostEqual(c.energia, 11.80, places=2)
        self.assertEqual((c.minutos_ociosos, c.blocos_ociosidade, c.ociosidade), (237, 8, 16.0))
        self.assertEqual(c.taxa_sem_reserva, 0.0)
        self.assertEqual(c.total, 27.80)

    def test_caso_S0020(self):
        c = self.r.cobranca("S0020")
        self.assertEqual((c.minutos_ociosos, c.blocos_ociosidade, c.ociosidade), (85, 3, 6.0))

    def test_no_show_AG0004(self):
        ns = [i for i in self.r.fatura("U04").itens if i.tipo == "no_show"]
        self.assertEqual(len(ns), 1)
        self.assertEqual((ns[0].agendamento_id, ns[0].no_show, ns[0].observacao),
                         ("AG0004", 5.0, "reserva não utilizada"))

    def test_detalhe_soma_a_fatura(self):
        for f in self.r.faturas:
            with self.subTest(uid=f.usuario_id):
                self.assertEqual(centavos(sum(i.total for i in f.itens) + f.custo_fixo), f.total)

    def test_arquivos_de_saida(self):
        with tempfile.TemporaryDirectory() as d:
            arqs = gravar(self.r, d)
            linhas = arqs[0].read_text(encoding="utf-8-sig").splitlines()
            self.assertEqual(len(linhas), 6)
            self.assertTrue(linhas[0].lstrip("﻿").startswith("competencia;unidade_id;"))
            self.assertTrue(linhas[3].startswith("2026-09;B-21;U03;Juliana Castro;11;129,99;"))
            self.assertTrue(linhas[3].endswith(";187,60"))
            detalhe = arqs[1].read_text(encoding="utf-8-sig").splitlines()
            self.assertEqual(len(detalhe), 1 + 34 + 1)                   # cabeçalho + sessões + no-show
            self.assertEqual(arqs[2].read_text(encoding="utf-8"), "")


# ------------------------------------------------------------------ 3. anomalias
class TestAnomalias(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.r = calcular_da_pasta(gerar(Path(cls.tmp.name) / "anom", "--seed", "5", "--anomalias"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_validacoes_disparam(self):
        avisos = "\n".join(self.r.avisos)
        self.assertIn("criada com menos de 60 min de antecedência", avisos)
        self.assertIn("sem usuário; energia", avisos)
        self.assertIn("medidor avançou 3.200 kWh", avisos)
        self.assertIn("Conciliação", avisos)

    def test_sessao_sem_usuario_nao_e_cobrada(self):
        self.assertEqual(len(self.r.nao_identificadas), 1)
        ni = self.r.nao_identificadas[0]
        self.assertEqual(ni.usuario_id, NAO_IDENTIFICADO)
        self.assertEqual((ni.ociosidade, ni.taxa_sem_reserva, ni.no_show), (0.0, 0.0, 0.0))
        self.assertGreater(ni.energia, 0)
        cobradas = {i.sessao_id for f in self.r.faturas for i in f.itens}
        self.assertNotIn(ni.sessao_id, cobradas)
        self.assertEqual(self.r.total_arrecadar, 870.71)


# ------------------------------------------------------------------ 4. propriedades e linha de comando
class TestPropriedades(unittest.TestCase):
    """Regras que valem para qualquer mês gerado (sem depender de valores esperados fixos)."""

    def test_varias_sementes(self):
        casos = [("1",), ("7",), ("42",), ("3", "--anomalias"), ("5", "--mes", "2026-10")]
        with tempfile.TemporaryDirectory() as d:
            for i, args in enumerate(casos):
                with self.subTest(args=args):
                    lido = UsoSource().ler(gerar(Path(d) / f"c{i}", "--seed", *args))
                    r = calcular_rateio(lido, PAR)
                    # toda sessão vai para exatamente um lugar: uma fatura ou NAO_IDENTIFICADO
                    ids = [i.sessao_id for i in r.detalhe if i.tipo == "sessao"]
                    self.assertEqual(sorted(ids), sorted(s.id for s in lido.sessoes))
                    self.assertAlmostEqual(r.kwh_total, sum(s.kwh for s in lido.sessoes), places=6)
                    self.assertEqual(r.competencia, args[args.index("--mes") + 1] if "--mes" in args else "2026-09")
                    self.assertEqual(r.total_arrecadar, centavos(sum(f.total for f in r.faturas)))
                    for f in r.faturas:
                        self.assertEqual(f.custo_fixo, PAR.custo_fixo)
                        self.assertEqual(f.competencia, r.competencia)
                        # o que o morador vê no detalhe fecha exatamente com o total da fatura
                        self.assertEqual(centavos(sum(i.total for i in f.itens) + f.custo_fixo), f.total)
                        self.assertEqual(f.total, centavos(f.energia + f.ociosidade + f.taxa_sem_reserva
                                                           + f.no_show + f.custo_fixo))
                        self.assertAlmostEqual(f.kwh, sum(f.kwh_na_faixa(x) for x in FAIXAS), places=6)
                        for item in f.itens:
                            self.assertEqual(item.energia, centavos(item.energia))
                            self.assertLessEqual(item.ociosidade, PAR.teto_ociosidade)
                            self.assertEqual(item.taxa_sem_reserva > 0, item.tipo == "sessao" and not item.agendamento_id)
                    for ni in r.nao_identificadas:
                        self.assertEqual(ni.total, ni.energia)


class TestLinhaDeComando(unittest.TestCase):
    def test_calcular_fatura_py(self):
        with tempfile.TemporaryDirectory() as d:
            pasta, saida = gerar(Path(d) / "ref5", "--seed", "5"), Path(d) / "saida"
            p = subprocess.run([sys.executable, str(RAIZ / "calcular_fatura.py"), str(pasta), str(saida)],
                               capture_output=True, text=True, encoding="utf-8", env={**os.environ,
                                                                                       "PYTHONIOENCODING": "utf-8"})
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertIn("R$ 884,20", p.stdout)
            self.assertIn("Competência 2026-09", p.stdout)
            for nome in ("fatura_mensal.csv", "detalhe_sessoes.csv", "avisos.txt"):
                self.assertTrue((saida / nome).is_file(), nome)

    def test_pasta_inexistente(self):
        p = subprocess.run([sys.executable, str(RAIZ / "calcular_fatura.py"), str(RAIZ / "nao_existe")],
                           capture_output=True, text=True, encoding="utf-8",
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        self.assertEqual(p.returncode, 1)
        self.assertIn("[ERRO]", p.stdout)


if __name__ == "__main__":
    unittest.main()
