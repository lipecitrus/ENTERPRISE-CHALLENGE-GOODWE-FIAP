from __future__ import annotations
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from main import cpf_valido


class TestCpf(unittest.TestCase):
    def test_cpfs_validos(self):
        for cpf in ("52998224725", "11144477735", "12345678909"):
            self.assertTrue(cpf_valido(cpf), cpf)

    def test_digito_verificador_errado(self):
        self.assertFalse(cpf_valido("52998224724"))   # 2º dígito errado
        self.assertFalse(cpf_valido("52998224715"))   # 1º dígito errado

    def test_tamanho_e_repetidos(self):
        for cpf in ("", "5299822472", "529982247250", "11111111111", "00000000000"):
            self.assertFalse(cpf_valido(cpf), cpf)


if __name__ == "__main__":
    unittest.main()


class TestAgendamento(unittest.TestCase):
    """Regras de reserva do menu, com Excel temporário e entradas simuladas."""

    def setUp(self):
        import tempfile
        import main
        self.main = main
        self.tmp = tempfile.TemporaryDirectory()
        main.ARQ = Path(self.tmp.name) / "app.xlsx"
        main.DB = main.carregar()
        self.u = type("U", (), {"usuario_id": "U01"})()

    def tearDown(self):
        self.tmp.cleanup()

    def reservar(self, inicio, minutos):
        respostas = iter([inicio.strftime("%d/%m/%Y %H:%M"), str(minutos)])
        self.main.ler = lambda texto: next(respostas)
        self.main.agendar(self.u)
        return len(self.main.DB["agendamentos"])

    def test_reserva_valida_e_sobreposta(self):
        from datetime import datetime, timedelta
        amanha = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        self.assertEqual(self.reservar(amanha, 60), 1)
        self.assertEqual(self.reservar(amanha, 30), 1)          # mesmo horário: recusada

    def test_reserva_com_menos_de_uma_hora_e_recusada(self):
        from datetime import datetime, timedelta
        em_breve = datetime.now() + timedelta(minutes=20)
        em_breve = em_breve.replace(minute=0 if em_breve.minute < 30 else 30, second=0, microsecond=0)
        self.assertEqual(self.reservar(em_breve, 30), 0)

    def test_duracao_maxima_120_min(self):
        from datetime import datetime, timedelta
        amanha = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        self.assertEqual(self.reservar(amanha, 150), 0)
