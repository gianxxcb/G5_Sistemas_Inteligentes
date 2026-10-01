"""Pruebas del modelo de datos para planificación semanal."""

import unittest

from schedule_models import (
    Aula,
    ConfiguracionPlanificacion,
    Curso,
    DatosPlanificacion,
    DiaSemana,
    Docente,
    ErrorModeloPlanificacion,
    FranjaSemanal,
    GrupoLaboratorio,
    SesionFija,
    TipoAula,
)


def crear_datos_planificacion() -> DatosPlanificacion:
    disponibilidad = (
        FranjaSemanal(DiaSemana.LUNES, "07:00", "22:00"),
        FranjaSemanal(DiaSemana.MARTES, "07:00", "22:00"),
    )
    docente = Docente("doc-1", "Docente externo", disponibilidad)
    cursos = (
        Curso("curso-lab", "Laboratorio", "doc-1", "cohorte-1", 120, True),
        Curso("curso-fijo", "Curso fijo", "doc-1", "cohorte-1", 120),
    )
    aulas = tuple(
        Aula(f"lab-{indice}", 55, TipoAula.LABORATORIO, True)
        for indice in range(1, 6)
    )
    grupos = tuple(
        GrupoLaboratorio(f"grupo-{indice}", "curso-lab", "cohorte-1", cantidad)
        for indice, cantidad in enumerate((45, 50, 55), start=1)
    )
    sesion_fija = SesionFija(
        "curso-fijo", FranjaSemanal(DiaSemana.LUNES, "09:00", "11:00")
    )
    configuracion = ConfiguracionPlanificacion(
        cursos_por_semestre=2,
        cursos_con_laboratorio=1,
    )
    return DatosPlanificacion(
        docentes=(docente,),
        cursos=cursos,
        aulas=aulas,
        grupos_laboratorio=grupos,
        sesiones_fijas=(sesion_fija,),
        configuracion=configuracion,
    )


class FranjaSemanalTests(unittest.TestCase):
    def test_normaliza_horas_y_calcula_duracion(self) -> None:
        franja = FranjaSemanal("lunes", "9:00", "11:30")

        self.assertEqual(franja.dia, DiaSemana.LUNES)
        self.assertEqual(franja.hora_inicio, "09:00")
        self.assertEqual(franja.duracion_minutos, 150)

    def test_intervalos_contiguos_no_se_superponen(self) -> None:
        primera = FranjaSemanal(DiaSemana.LUNES, "07:00", "09:00")
        segunda = FranjaSemanal(DiaSemana.LUNES, "09:00", "11:00")

        self.assertFalse(primera.se_superpone(segunda))

    def test_rechaza_hora_invertida(self) -> None:
        with self.assertRaises(ErrorModeloPlanificacion):
            FranjaSemanal(DiaSemana.LUNES, "11:00", "09:00")


class DatosPlanificacionTests(unittest.TestCase):
    def test_acepta_grupos_entre_45_y_55_y_cinco_laboratorios(self) -> None:
        datos = crear_datos_planificacion()

        self.assertEqual(len(datos.grupos_laboratorio), 3)
        self.assertEqual(
            sum(aula.tipo == TipoAula.LABORATORIO for aula in datos.aulas), 5
        )
        self.assertEqual(datos.configuracion.max_horarios, 5)
        self.assertEqual(datos.configuracion.dias_activos_objetivo, 4)

    def test_rechaza_grupo_fuera_de_tolerancia(self) -> None:
        datos = crear_datos_planificacion()
        grupos = (
            datos.grupos_laboratorio[0],
            datos.grupos_laboratorio[1],
            GrupoLaboratorio("grupo-3", "curso-lab", "cohorte-1", 56),
        )

        with self.assertRaisesRegex(ErrorModeloPlanificacion, "entre 45 y 55"):
            DatosPlanificacion(
                docentes=datos.docentes,
                cursos=datos.cursos,
                aulas=datos.aulas,
                grupos_laboratorio=grupos,
                sesiones_fijas=datos.sesiones_fijas,
                configuracion=datos.configuracion,
            )

    def test_rechaza_grupo_de_laboratorio_para_curso_teorico(self) -> None:
        datos = crear_datos_planificacion()
        grupos = datos.grupos_laboratorio + (
            GrupoLaboratorio("grupo-extra", "curso-fijo", "cohorte-1", 50),
        )

        with self.assertRaisesRegex(ErrorModeloPlanificacion, "no requiere laboratorio"):
            DatosPlanificacion(
                docentes=datos.docentes,
                cursos=datos.cursos,
                aulas=datos.aulas,
                grupos_laboratorio=grupos,
                sesiones_fijas=datos.sesiones_fijas,
                configuracion=datos.configuracion,
            )

    def test_permite_configurar_cantidad_de_cursos_y_grupos(self) -> None:
        configuracion = ConfiguracionPlanificacion(
            cursos_por_semestre=8,
            cursos_con_laboratorio=2,
            grupos_por_curso_laboratorio=2,
            cantidad_aulas_laboratorio=5,
            max_horarios=4,
        )

        self.assertEqual(configuracion.cursos_por_semestre, 8)
        self.assertEqual(configuracion.max_horarios, 4)


if __name__ == "__main__":
    unittest.main()
