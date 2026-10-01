"""Pruebas de restricciones duras del validador de horarios."""

import unittest
from unittest.mock import patch

from agent_expert import AgenteExperto
from schedule_models import (
    Aula,
    ConfiguracionPlanificacion,
    Curso,
    DatosPlanificacion,
    DiaSemana,
    Docente,
    FranjaSemanal,
    GrupoLaboratorio,
    SesionFija,
    SesionProgramada,
    TipoAula,
)
from schedule_validator import ValidadorHorario


def crear_escenario():
    franja_libre = (
        FranjaSemanal(DiaSemana.LUNES, "07:00", "22:00"),
        FranjaSemanal(DiaSemana.MARTES, "07:00", "22:00"),
    )
    docentes = (
        Docente("doc-lab", "Docente laboratorio", franja_libre),
        Docente("doc-teoria", "Docente teoría", franja_libre),
    )
    cursos = (
        Curso("lab", "Curso laboratorio", "doc-lab", "cohorte", 120, True),
        Curso("teoria", "Curso teórico fijo", "doc-teoria", "cohorte", 120),
    )
    aulas = tuple(
        Aula(f"lab-{indice}", 55, TipoAula.LABORATORIO, True)
        for indice in range(1, 6)
    ) + (Aula("aula-teoria", 60, TipoAula.TEORIA),)
    grupos = tuple(
        GrupoLaboratorio(f"grupo-{indice}", "lab", "cohorte", 50)
        for indice in range(1, 4)
    )
    fija = SesionFija(
        "teoria", FranjaSemanal(DiaSemana.LUNES, "09:00", "11:00")
    )
    configuracion = ConfiguracionPlanificacion(
        cursos_por_semestre=2,
        cursos_con_laboratorio=1,
    )
    datos = DatosPlanificacion(
        docentes=docentes,
        cursos=cursos,
        aulas=aulas,
        grupos_laboratorio=grupos,
        sesiones_fijas=(fija,),
        configuracion=configuracion,
    )
    sesiones = (
        SesionProgramada(
            "teoria-lun",
            "teoria",
            fija.franja,
            "aula-teoria",
        ),
        SesionProgramada(
            "lab-g1",
            "lab",
            FranjaSemanal(DiaSemana.LUNES, "07:00", "09:00"),
            "lab-1",
            "grupo-1",
        ),
        SesionProgramada(
            "lab-g2",
            "lab",
            FranjaSemanal(DiaSemana.LUNES, "11:00", "13:00"),
            "lab-2",
            "grupo-2",
        ),
        SesionProgramada(
            "lab-g3",
            "lab",
            FranjaSemanal(DiaSemana.MARTES, "09:00", "11:00"),
            "lab-3",
            "grupo-3",
        ),
    )
    return datos, sesiones


class ValidadorHorarioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validador = ValidadorHorario()
        self.datos, self.sesiones = crear_escenario()

    def test_acepta_horario_que_cumple_restricciones(self) -> None:
        resultado = self.validador.validar(self.datos, self.sesiones)

        self.assertTrue(resultado.valido)
        self.assertEqual(resultado.incidencias, ())

    def test_rechaza_laboratorio_que_choca_con_curso_fijo(self) -> None:
        lab = SesionProgramada(
            "lab-conflicto",
            "lab",
            FranjaSemanal(DiaSemana.LUNES, "09:30", "11:30"),
            "lab-1",
            "grupo-1",
        )
        sesiones = (self.sesiones[0], lab, self.sesiones[2], self.sesiones[3])

        resultado = self.validador.validar(self.datos, sesiones)
        codigos = {incidencia.codigo for incidencia in resultado.incidencias}

        self.assertFalse(resultado.valido)
        self.assertIn("laboratorio_choca_con_curso_fijo", codigos)
        self.assertIn("choque_de_cohorte", codigos)

    def test_rechaza_disponibilidad_docente_fuera_de_franja(self) -> None:
        docente_restringido = Docente(
            "doc-lab",
            "Docente externo",
            (FranjaSemanal(DiaSemana.MARTES, "13:00", "17:00"),),
        )
        datos = DatosPlanificacion(
            docentes=(docente_restringido, self.datos.docentes[1]),
            cursos=self.datos.cursos,
            aulas=self.datos.aulas,
            grupos_laboratorio=self.datos.grupos_laboratorio,
            sesiones_fijas=self.datos.sesiones_fijas,
            configuracion=self.datos.configuracion,
        )

        resultado = self.validador.validar(datos, self.sesiones)
        self.assertIn(
            "docente_fuera_de_disponibilidad",
            {incidencia.codigo for incidencia in resultado.incidencias},
        )

    def test_rechaza_grupo_omitido_y_sesion_doble(self) -> None:
        sesiones = self.sesiones[:-1] + (self.sesiones[2],)

        resultado = self.validador.validar(self.datos, sesiones)
        codigos = {incidencia.codigo for incidencia in resultado.incidencias}

        self.assertIn("cantidad_sesiones_grupo_incorrecta", codigos)
        self.assertIn("id_sesion_duplicado", codigos)

    def test_rechaza_dos_sesiones_en_la_misma_aula(self) -> None:
        lab_doble = SesionProgramada(
            "lab-otra-aula-misma",
            "lab",
            FranjaSemanal(DiaSemana.LUNES, "07:30", "09:30"),
            "lab-1",
            "grupo-2",
        )
        sesiones = self.sesiones[:2] + (lab_doble,) + self.sesiones[3:]

        resultado = self.validador.validar(self.datos, sesiones)
        self.assertIn(
            "choque_de_aula",
            {incidencia.codigo for incidencia in resultado.incidencias},
        )

    def test_permite_solapamiento_de_grupos_distintos_de_una_cohorte(self) -> None:
        disponibilidad = (
            FranjaSemanal(DiaSemana.LUNES, "07:00", "13:00"),
        )
        docentes = (
            Docente("doc-1", "Docente 1", disponibilidad),
            Docente("doc-2", "Docente 2", disponibilidad),
        )
        cursos = (
            Curso("lab-1", "Laboratorio 1", "doc-1", "cohorte", 120, True),
            Curso("lab-2", "Laboratorio 2", "doc-2", "cohorte", 120, True),
        )
        grupos = tuple(
            GrupoLaboratorio(
                f"{curso_id}-{subgrupo}",
                curso_id,
                "cohorte",
                50,
                subgrupo,
            )
            for curso_id in ("lab-1", "lab-2")
            for subgrupo in ("A", "B", "C")
        )
        aulas = tuple(
            Aula(f"aula-{indice}", 55, TipoAula.LABORATORIO, True)
            for indice in range(1, 6)
        )
        datos = DatosPlanificacion(
            docentes=docentes,
            cursos=cursos,
            aulas=aulas,
            grupos_laboratorio=grupos,
            configuracion=ConfiguracionPlanificacion(
                cursos_por_semestre=2,
                cursos_con_laboratorio=2,
            ),
        )
        sesiones = tuple(
            SesionProgramada(
                f"{curso_id}-{subgrupo}",
                curso_id,
                FranjaSemanal(DiaSemana.LUNES, inicio, fin),
                aula_id,
                f"{curso_id}-{subgrupo}",
            )
            for curso_id, subgrupo, inicio, fin, aula_id in (
                ("lab-1", "A", "07:00", "09:00", "aula-1"),
                ("lab-1", "B", "09:00", "11:00", "aula-1"),
                ("lab-1", "C", "11:00", "13:00", "aula-1"),
                ("lab-2", "C", "07:00", "09:00", "aula-2"),
                ("lab-2", "A", "09:00", "11:00", "aula-2"),
                ("lab-2", "B", "11:00", "13:00", "aula-2"),
            )
        )

        resultado = self.validador.validar(datos, sesiones)

        self.assertNotIn(
            "choque_de_cohorte",
            {incidencia.codigo for incidencia in resultado.incidencias},
        )
        self.assertTrue(resultado.valido, resultado.incidencias)

    def test_agente_experto_expone_el_validador_semanal(self) -> None:
        resultado = AgenteExperto().validar_horario(self.datos, self.sesiones)

        self.assertTrue(resultado.valido)

    def test_agente_experto_asigna_alternativa_a_star_si_aula_primaria_ocupada(
        self,
    ) -> None:
        experto = AgenteExperto()
        hechos = {
            "aforo": 35,
            "requiere_laboratorio": True,
            "franja": "pico",
            "horario_inicio": "09:00",
            "horario_fin": "11:00",
        }
        with patch(
            "agent_expert.is_room_available",
            side_effect=lambda room_id, start_time, end_time: room_id != "B201",
        ):
            resultado = experto.evaluar(hechos)

        self.assertTrue(resultado["requiere_alternativa"])
        self.assertTrue(resultado["alternativa_encontrada"])
        self.assertEqual(resultado["aula_objetivo"], "B201")
        self.assertEqual(resultado["aula_alternativa"], "B203")
        self.assertEqual(resultado["aula_asignada"], "B203")
        self.assertEqual(resultado["costo_reubicacion"], 0)

    def test_agente_experto_indica_si_no_hay_alternativa_disponible(self) -> None:
        experto = AgenteExperto()
        hechos = {
            "aforo": 35,
            "requiere_laboratorio": True,
            "franja": "pico",
            "horario_inicio": "09:00",
            "horario_fin": "11:00",
        }
        with patch("agent_expert.is_room_available", return_value=False):
            resultado = experto.evaluar(hechos)

        self.assertTrue(resultado["requiere_alternativa"])
        self.assertFalse(resultado["alternativa_encontrada"])
        self.assertIsNone(resultado["aula_asignada"])
        self.assertIsNone(resultado["aula_alternativa"])

    def test_agente_experto_reubica_aula_primaria_inexistente(self) -> None:
        resultado = AgenteExperto().evaluar(
            {
                "aforo": 20,
                "requiere_laboratorio": True,
                "franja": "regular",
                "horario_inicio": "14:00",
                "horario_fin": "16:00",
            }
        )

        self.assertEqual(resultado["aula_objetivo"], "B101")
        self.assertTrue(resultado["alternativa_encontrada"])
        self.assertEqual(resultado["aula_asignada"], "B202")


if __name__ == "__main__":
    unittest.main()
