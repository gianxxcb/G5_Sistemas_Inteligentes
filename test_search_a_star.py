"""Pruebas de búsqueda de aula alterna mediante A*."""

import unittest

from database import get_all_rooms
from search_a_star import AStarSearch


class AStarSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.search = AStarSearch(
            distancias_pabellones={
                ("A", "B"): 100,
                ("B", "C"): 80,
                ("A", "C"): 300,
            },
            penalizacion_por_asiento=20,
        )
        self.aulas = [
            {
                "id": "A101",
                "pabellon": "A",
                "tipo": "laboratorio",
                "aforo_max": 50,
                "tiene_computadoras": True,
            },
            {
                "id": "B201",
                "pabellon": "B",
                "tipo": "laboratorio",
                "aforo_max": 60,
                "tiene_computadoras": True,
            },
            {
                "id": "C301",
                "pabellon": "C",
                "tipo": "laboratorio",
                "aforo_max": 51,
                "tiene_computadoras": True,
            },
            {
                "id": "B101",
                "pabellon": "B",
                "tipo": "teoria",
                "aforo_max": 60,
                "tiene_computadoras": False,
            },
        ]

    def test_elige_mejor_costo_combinado_de_distancia_y_aforo(self) -> None:
        resultado = self.search.buscar(
            "A101",
            self.aulas,
            aforo_solicitado=50,
            requiere_laboratorio=True,
            excluir_ids=("A101",),
        )

        self.assertIsNotNone(resultado)
        self.assertEqual(resultado.aula_id, "C301")
        self.assertEqual(resultado.distancia_metros, 180)
        self.assertEqual(resultado.penalizacion_aforo, 20)
        self.assertEqual(resultado.costo_total, 200)
        self.assertEqual(resultado.ruta, ("A101", "B201", "C301"))

    def test_filtra_capacidad_tipo_equipo_y_disponibilidad(self) -> None:
        resultado = self.search.buscar(
            "A101",
            self.aulas,
            aforo_solicitado=51,
            requiere_laboratorio=True,
            disponibilidad=lambda aula_id: aula_id == "C301",
        )

        self.assertEqual(resultado.aula_id, "C301")

    def test_devuelve_none_si_no_hay_destino_factible(self) -> None:
        resultado = self.search.buscar(
            "A101",
            self.aulas,
            aforo_solicitado=70,
            requiere_laboratorio=True,
        )

        self.assertIsNone(resultado)

    def test_distancias_incluyen_triangulacion_por_pabellon_intermedio(self) -> None:
        search = AStarSearch(
            distancias_pabellones={
                ("A", "B"): 100,
                ("B", "C"): 80,
                ("A", "C"): 300,
            }
        )
        aulas = (
            {
                "id": "A101",
                "pabellon": "A",
                "tipo": "teoria",
                "aforo_max": 30,
            },
            {
                "id": "B101",
                "pabellon": "B",
                "tipo": "teoria",
                "aforo_max": 10,
            },
            {
                "id": "C101",
                "pabellon": "C",
                "tipo": "teoria",
                "aforo_max": 30,
            },
        )

        resultado = search.buscar("A101", aulas, 20)

        self.assertEqual(resultado.distancia_metros, 180)
        self.assertEqual(resultado.ruta, ("A101", "B101", "C101"))

    def test_usa_aulas_de_la_base_actual(self) -> None:
        resultado = AStarSearch().buscar(
            "B201",
            get_all_rooms(),
            aforo_solicitado=30,
            requiere_laboratorio=True,
            excluir_ids=("B201",),
        )

        self.assertIsNotNone(resultado)
        self.assertEqual(resultado.aula_id, "B203")

    def test_admite_aulas_tipadas_del_planificador(self) -> None:
        from schedule_models import Aula, TipoAula

        aulas = (
            Aula("A101", 30, TipoAula.TEORIA),
            Aula("B101", 35, TipoAula.TEORIA),
        )

        resultado = self.search.buscar(
            "A101",
            aulas,
            aforo_solicitado=25,
            pabellones={"A101": "A", "B101": "B"},
        )

        self.assertEqual(resultado.aula_id, "B101")


if __name__ == "__main__":
    unittest.main()
