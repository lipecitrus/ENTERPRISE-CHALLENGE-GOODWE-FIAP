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
