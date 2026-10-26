"""Testes do leitor de BU contra o BU real de AC/Rio Branco, zona 9, seção 267 (2º turno 2026)."""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bu_parser as bp  # noqa: E402

FIXTURE = HERE / "fixtures" / "01392-0009-0267-bu.dat"


class TestBER(unittest.TestCase):
    def test_short_and_long_lengths(self):
        n = bp.decode(bytes([0x30, 0x03, 0x02, 0x01, 0x05]))
        self.assertTrue(n.is_seq)
        self.assertEqual(n.children[0].int(), 5)
        long = bytes([0x04, 0x81, 0x80]) + b"x" * 128
        self.assertEqual(len(bp.decode(long).value), 128)

    def test_negative_integer_and_truncation(self):
        self.assertEqual(bp.decode(bytes([0x02, 0x01, 0xFF])).int(), -1)
        with self.assertRaises(ValueError):
            bp.decode(bytes([0x30, 0x05, 0x02, 0x01]))

    def test_garbage_is_rejected(self):
        with self.assertRaises(ValueError):
            bp.parse_bu(b'<?xml version="1.0"?><Error><Code>NoSuchKey</Code></Error>')


class TestFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bu = bp.parse_bu(FIXTURE.read_bytes())

    def test_identificacao(self):
        self.assertEqual((self.bu.municipio, self.bu.zona, self.bu.secao), (1392, 9, 267))
        self.assertEqual(self.bu.emissao, "20261025T150136")

    def test_presidente(self):
        p = self.bu.presidente()
        self.assertEqual(p.id_eleicao, 6258)
        self.assertEqual(p.codigo_cargo, 1)
        self.assertEqual(p.aptos, 226)
        self.assertEqual(p.comparecimento, 184)
        self.assertEqual(p.votos, {13: 61, 22: 118})
        self.assertEqual((p.brancos, p.nulos, p.legenda), (3, 2, 0))
        self.assertEqual(p.total, p.comparecimento)

    def test_governador_tambem_lido(self):
        g = [r for r in self.bu.resultados if r.codigo_cargo == 3]
        self.assertEqual(len(g), 1)
        self.assertEqual(g[0].id_eleicao, 6260)
        self.assertEqual(g[0].votos, {10: 44, 11: 122})
        self.assertEqual(g[0].total, 184)


if __name__ == "__main__":
    unittest.main(verbosity=2)
