from __future__ import annotations
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from leitor_uso import Leitura, Reserva, Sessao
from ia_uso import detectar_anomalias, prever_uso_diario


def montar_sessao(i: int, kwh: float = 8.0, soc_ini: float = 40.0, soc_fim: float = 60.0, reserva=None) -> Sessao:
    inicio = datetime(2026, 9, 1) + timedelta(days=i, hours=10)
    leituras = [Leitura(inicio, 0.0, 7.0, soc_ini), Leitura(inicio + timedelta(hours=1), kwh, 7.0, soc_fim)]
    return Sessao(id=f"S{i:04}", usuario_id="U01", unidade_id="A-1", identificacao="app",
                  inicio=inicio, fim=inicio + timedelta(hours=1), fim_carga=inicio + timedelta(hours=1),
                  status="Concluida", motivo_parada="CarroCheio", reserva=reserva, leituras=leituras)


class TestIAUso(unittest.TestCase):
    def test_previsao_gera_dias_solicitados(self):
        resultado = prever_uso_diario([montar_sessao(i, 5 + i % 3) for i in range(15)], 5)
        self.assertEqual(len(resultado), 5)
        self.assertTrue((resultado["kwh_previsto"] >= 0).all())

    def test_historico_curto_usa_fallback(self):
        resultado = prever_uso_diario([montar_sessao(0), montar_sessao(1)], 3)
        self.assertEqual(len(resultado), 3)
        self.assertTrue((resultado["metodo"] == "media_movel_7_dias").all())

    def test_sessao_sem_identificacao_e_sinalizada(self):
        s = montar_sessao(0)
        s.usuario_id = ""
        s.identificacao = ""
        resultado = detectar_anomalias([s])
        self.assertEqual(len(resultado), 1)
        self.assertIn("sem identificação", resultado.iloc[0]["motivo"])

    def test_soc_acima_de_100_e_sinalizado(self):
        s = montar_sessao(0, soc_ini=92, soc_fim=105)
        resultado = detectar_anomalias([s])
        self.assertEqual(len(resultado), 1)
        self.assertIn("soc_fora_intervalo", resultado.iloc[0]["tipo"])
        self.assertIn("100%", resultado.iloc[0]["motivo"])

    def test_soc_negativo_e_sinalizado(self):
        s = montar_sessao(0, soc_ini=-1, soc_fim=10)
        resultado = detectar_anomalias([s])
        self.assertIn("soc_fora_intervalo", resultado.iloc[0]["tipo"])

    def test_soc_regredindo_com_medidor_crescente_e_sinalizado(self):
        s = montar_sessao(0, soc_ini=70, soc_fim=50)
        resultado = detectar_anomalias([s])
        self.assertIn("soc_incoerente", resultado.iloc[0]["tipo"])

    def test_sessao_sem_agendamento_e_sinalizada_para_revisao(self):
        s = montar_sessao(0)
        resultado = detectar_anomalias([s])
        self.assertIn("sem_agendamento", resultado.iloc[0]["tipo"])
        self.assertIn("autorizada", resultado.iloc[0]["motivo"])

    def test_reserva_criada_com_menos_de_uma_hora_e_sinalizada(self):
        inicio = datetime(2026, 9, 1, 10, 0)
        reserva = Reserva("AG0001", inicio, inicio + timedelta(hours=2), inicio - timedelta(minutes=20))
        s = montar_sessao(0, reserva=reserva)
        s.inicio = inicio + timedelta(minutes=5)
        resultado = detectar_anomalias([s])
        self.assertIn("antecedencia_reserva", resultado.iloc[0]["tipo"])

    def test_sessao_fora_da_janela_de_reserva_e_sinalizada(self):
        inicio = datetime(2026, 9, 1, 10, 0)
        reserva = Reserva("AG0001", inicio, inicio + timedelta(hours=1), inicio - timedelta(hours=2))
        s = montar_sessao(0, reserva=reserva)
        s.inicio = inicio + timedelta(hours=1)
        resultado = detectar_anomalias([s])
        self.assertIn("fora_agendamento", resultado.iloc[0]["tipo"])

    def test_sem_sessoes_nao_quebra(self):
        self.assertTrue(detectar_anomalias([]).empty)
        self.assertEqual(len(prever_uso_diario([], 1)), 1)


if __name__ == "__main__":
    unittest.main()
