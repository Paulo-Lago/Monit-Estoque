import unittest
from datetime import date, timedelta

from modulo_pinteiro import calcular_aves_vivas, status_exibicao_vacina


class PinteiroRulesTests(unittest.TestCase):
    def test_calcula_aves_vivas_com_mortalidade(self):
        self.assertEqual(calcular_aves_vivas(100, 12), 88)

    def test_calcula_aves_vivas_considera_transferencia(self):
        self.assertEqual(calcular_aves_vivas(100, 12, 88), 0)

    def test_aves_vivas_nunca_ficam_negativas(self):
        self.assertEqual(calcular_aves_vivas(10, 12), 0)

    def test_vacina_prevista_vira_atrasada_apos_o_prazo(self):
        hoje = date(2026, 7, 28)
        self.assertEqual(
            status_exibicao_vacina("prevista", hoje - timedelta(days=1), hoje),
            "atrasada",
        )

    def test_vacina_aplicada_permanece_aplicada(self):
        hoje = date(2026, 7, 28)
        self.assertEqual(
            status_exibicao_vacina("aplicada", hoje - timedelta(days=10), hoje),
            "aplicada",
        )


if __name__ == "__main__":
    unittest.main()
