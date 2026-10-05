"""Pruebas del generador y puntuador de horarios."""

import unittest

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
from agent_expert import AgenteExperto
from schedule_optimizer import (
    GeneradorHorarios,
    PreferenciasHorario,
    PuntuadorHorario,
)
from schedule_validator import ValidadorHorario


def crear_datos_planificables() -> DatosPlanificacion:
    disponibilidad_lab = (
        FranjaSemanal(DiaSemana.LUNES, "07:00", "17:00"),
        FranjaSemanal(DiaSemana.MARTES, "07:00", "17:00"),
    )
    disponibilidad_teoria = (
        FranjaSemanal(DiaSemana.LUNES, "09:00", "11:00"),
    )
    docentes = (
        Docente("doc-lab", "Docente laboratorio", disponibilidad_lab),
        Docente("doc-teoria", "Docente teoría", disponibilidad_teoria),
    )
    cursos = (
        Curso("lab", "Laboratorio", "doc-lab", "cohorte", 120, True),
        Curso("teoria", "Teoría fija", "doc-teoria", "cohorte", 120),
    )
    aulas = tuple(
        Aula(f"lab-{indice}", 55, TipoAula.LABORATORIO, True)
        for indice in range(1, 6)
    ) + (Aula("aula-teoria", 60, TipoAula.TEORIA),)
    grupos = tuple(
        GrupoLaboratorio(f"grupo-{indice}", "lab", "cohorte", 50)
        for indice in range(1, 4)
    )
    sesion_fija = SesionFija(
        "teoria",
        FranjaSemanal(DiaSemana.LUNES, "09:00", "11:00"),
        "aula-teoria",
    )
    configuracion = ConfiguracionPlanificacion(
        cursos_por_semestre=2,
        cursos_con_laboratorio=1,
        max_horarios=5,
    )
    return DatosPlanificacion(
        docentes=docentes,
        cursos=cursos,
        aulas=aulas,
        grupos_laboratorio=grupos,
        sesiones_fijas=(sesion_fija,),
        configuracion=configuracion,
    )


def crear_carga_semestral_completa() -> DatosPlanificacion:
    disponibilidad = tuple(
        FranjaSemanal(dia, "07:00", "22:00")
        for dia in (
            DiaSemana.LUNES,
            DiaSemana.MARTES,
            DiaSemana.MIERCOLES,
            DiaSemana.JUEVES,
            DiaSemana.VIERNES,
        )
    )
    docente = Docente("docente", "Docente", disponibilidad)
    cursos = tuple(
        Curso(
            f"curso-{indice}",
            f"Curso {indice}",
            docente.id,
            "cohorte",
            120,
            indice <= 3,
        )
        for indice in range(1, 8)
    )
    grupos = tuple(
        GrupoLaboratorio(
            f"grupo-{curso_indice}-{grupo_indice}",
            f"curso-{curso_indice}",
            "cohorte",
            tamano,
            f"subcohorte-{grupo_indice}",
        )
        for curso_indice in range(1, 4)
        for grupo_indice, tamano in enumerate((45, 50, 55), start=1)
    )
    aulas = tuple(
        Aula(f"lab-{indice}", 55, TipoAula.LABORATORIO, True)
        for indice in range(1, 6)
    ) + tuple(
        Aula(f"teoria-{indice}", 60, TipoAula.TEORIA)
        for indice in range(1, 5)
    )
    return DatosPlanificacion(
        docentes=(docente,),
        cursos=cursos,
        aulas=aulas,
        grupos_laboratorio=grupos,
    )


class GeneradorHorariosTests(unittest.TestCase):
    def test_distribuye_cursos_en_cinco_dias_y_varia_las_alternativas(self) -> None:
        disponibilidad = tuple(
            FranjaSemanal(dia, "07:00", "22:00")
            for dia in (
                DiaSemana.LUNES,
                DiaSemana.MARTES,
                DiaSemana.MIERCOLES,
                DiaSemana.JUEVES,
                DiaSemana.VIERNES,
            )
        )
        docente = Docente("docente", "Docente", disponibilidad)
        cursos = tuple(
            Curso(f"curso-{indice}", f"Curso {indice}", docente.id, "ciclo-I", 120)
            for indice in range(1, 7)
        )
        aulas = tuple(
            Aula(f"teoria-{indice}", 60, TipoAula.TEORIA)
            for indice in range(1, 8)
        ) + tuple(
            Aula(f"lab-{indice}", 60, TipoAula.LABORATORIO, True)
            for indice in range(1, 6)
        )
        configuracion = ConfiguracionPlanificacion(
            cursos_por_semestre=6,
            cursos_con_laboratorio=0,
            max_horarios=3,
            dias_activos_objetivo=5,
            tamano_grupo_objetivo=34,
        )
        datos = DatosPlanificacion(
            docentes=(docente,),
            cursos=cursos,
            aulas=aulas,
            configuracion=configuracion,
        )

        resultado = GeneradorHorarios(max_estados=5000).generar(datos)

        self.assertEqual(len(resultado.horarios), 3)
        distribuciones = []
        for horario in resultado.horarios:
            carga_diaria = {}
            for sesion in horario.sesiones:
                carga_diaria[sesion.franja.dia] = (
                    carga_diaria.get(sesion.franja.dia, 0)
                    + sesion.franja.duracion_minutos // 60
                )
            self.assertEqual(set(carga_diaria), set(configuracion.dias_habiles))
            self.assertLessEqual(max(carga_diaria.values()), 4)
            distribuciones.append(
                tuple(sorted((sesion.id, sesion.franja.dia) for sesion in horario.sesiones))
            )
            self.assertTrue(ValidadorHorario().validar(datos, horario.sesiones).valido)
        self.assertEqual(len(set(distribuciones)), len(resultado.horarios))

    def test_genera_hasta_cinco_horarios_validos_y_ordenados(self) -> None:
        datos = crear_datos_planificables()
        resultado = GeneradorHorarios(max_estados=3000).generar(datos)

        self.assertGreaterEqual(len(resultado.horarios), 1)
        self.assertLessEqual(len(resultado.horarios), 5)
        self.assertGreater(resultado.estados_explorados, 0)
        puntajes = [
            horario.puntaje.penalizacion_total for horario in resultado.horarios
        ]
        self.assertEqual(puntajes, sorted(puntajes))
        firmas = {
            tuple(
                sorted(
                    (sesion.id, sesion.franja.dia, sesion.franja.hora_inicio)
                    for sesion in horario.sesiones
                )
            )
            for horario in resultado.horarios
        }
        self.assertEqual(len(firmas), len(resultado.horarios))

        validador = ValidadorHorario()
        for horario in resultado.horarios:
            self.assertTrue(validador.validar(datos, horario.sesiones).valido)

    def test_respeta_disponibilidad_restringida_del_docente_externo(self) -> None:
        datos = crear_datos_planificables()
        resultado = GeneradorHorarios(max_estados=3000).generar(datos)

        for horario in resultado.horarios:
            for sesion in horario.sesiones:
                if sesion.curso_id == "teoria":
                    self.assertEqual(sesion.franja.dia, DiaSemana.LUNES)
                    self.assertEqual(sesion.franja.hora_inicio, "09:00")

    def test_curso_con_practica_programa_teoria_y_todos_los_grupos(self) -> None:
        datos_base = crear_datos_planificables()
        curso_laboratorio = Curso(
            "lab",
            "Laboratorio",
            "doc-lab",
            "cohorte",
            120,
            True,
            duracion_laboratorio_minutos=60,
        )
        aulas = datos_base.aulas + (Aula("teoria-pequena", 40, TipoAula.TEORIA),)
        datos = DatosPlanificacion(
            docentes=datos_base.docentes,
            cursos=(curso_laboratorio, datos_base.cursos[1]),
            aulas=aulas,
            grupos_laboratorio=datos_base.grupos_laboratorio,
            sesiones_fijas=datos_base.sesiones_fijas,
            configuracion=datos_base.configuracion,
        )

        resultado = GeneradorHorarios(max_estados=5000).generar(datos)

        self.assertGreaterEqual(len(resultado.horarios), 1)
        for horario in resultado.horarios:
            sesiones_curso = [
                sesion for sesion in horario.sesiones if sesion.curso_id == "lab"
            ]
            sesiones_teoria = [
                sesion for sesion in sesiones_curso
                if sesion.grupo_laboratorio_id is None
            ]
            sesiones_practica = [
                sesion for sesion in sesiones_curso
                if sesion.grupo_laboratorio_id is not None
            ]
            self.assertEqual(len(sesiones_teoria), 1)
            self.assertEqual(len(sesiones_practica), 3)
            self.assertGreaterEqual(
                next(aula.capacidad for aula in datos.aulas if aula.id == sesiones_teoria[0].aula_id),
                datos.configuracion.tamano_grupo_objetivo,
            )
            self.assertNotEqual(sesiones_teoria[0].aula_id, "teoria-pequena")
            self.assertTrue(ValidadorHorario().validar(datos, horario.sesiones).valido)

    def test_puntuador_resta_huecos_y_aplica_objetivo_de_dias(self) -> None:
        datos = crear_datos_planificables()
        resultado = GeneradorHorarios(max_estados=3000).generar(datos)
        puntajes = [
            PuntuadorHorario().puntuar(
                datos,
                horario.sesiones,
                PreferenciasHorario(dias_activos_objetivo=2),
            )
            for horario in resultado.horarios
        ]

        self.assertTrue(all(puntaje.penalizacion_total >= 0 for puntaje in puntajes))
        self.assertTrue(all(puntaje.dias_activos >= 1 for puntaje in puntajes))

    def test_retorna_sin_horario_si_profesor_no_tiene_disponibilidad(self) -> None:
        datos = crear_datos_planificables()
        docente_lab = Docente("doc-lab", "Sin horas", ())
        datos_sin_horas = DatosPlanificacion(
            docentes=(docente_lab, datos.docentes[1]),
            cursos=datos.cursos,
            aulas=datos.aulas,
            grupos_laboratorio=datos.grupos_laboratorio,
            sesiones_fijas=datos.sesiones_fijas,
            configuracion=datos.configuracion,
        )

        resultado = GeneradorHorarios().generar(datos_sin_horas)

        self.assertEqual(resultado.horarios, ())
        self.assertTrue(resultado.busqueda_completa)
        self.assertIn("No hay combinaciones", resultado.mensaje)

    def test_agente_experto_exhibe_generador_semanal(self) -> None:
        datos = crear_datos_planificables()

        resultado = AgenteExperto().generar_horarios(datos)

        self.assertLessEqual(len(resultado.horarios), datos.configuracion.max_horarios)

    def test_genera_alternativas_para_carga_semestral_base(self) -> None:
        datos = crear_carga_semestral_completa()
        resultado = GeneradorHorarios(max_estados=5000).generar(datos)

        self.assertEqual(len(resultado.horarios), 5)
        self.assertEqual(len(resultado.horarios[0].sesiones), 13)
        self.assertLessEqual(len(resultado.horarios), 5)
        self.assertTrue(
            ValidadorHorario().validar(datos, resultado.horarios[0].sesiones).valido
        )

    def test_puntua_huecos_segun_el_grupo_que_asiste_al_laboratorio(self) -> None:
        disponibilidad = (
            FranjaSemanal(DiaSemana.LUNES, "07:00", "19:00"),
        )
        docentes = (
            Docente("doc-lab", "Docente laboratorio", disponibilidad),
            Docente("doc-teoria", "Docente teoría", disponibilidad),
        )
        cursos = (
            Curso("lab", "Laboratorio", "doc-lab", "cohorte", 120, True),
            Curso("teoria", "Teoría", "doc-teoria", "cohorte", 120),
        )
        aulas = tuple(
            Aula(f"lab-{indice}", 55, TipoAula.LABORATORIO, True)
            for indice in range(1, 6)
        ) + (Aula("teoria-1", 60, TipoAula.TEORIA),)
        grupos = tuple(
            GrupoLaboratorio(
                f"grupo-{indice}",
                "lab",
                "cohorte",
                tamano,
                f"subcohorte-{indice}",
            )
            for indice, tamano in enumerate((45, 50, 55), start=1)
        )
        datos = DatosPlanificacion(
            docentes=docentes,
            cursos=cursos,
            aulas=aulas,
            grupos_laboratorio=grupos,
            configuracion=ConfiguracionPlanificacion(
                cursos_por_semestre=2,
                cursos_con_laboratorio=1,
            ),
        )
        sesiones = (
            SesionProgramada(
                "lab-1",
                "lab",
                FranjaSemanal(DiaSemana.LUNES, "07:00", "09:00"),
                "lab-1",
                "grupo-1",
            ),
            SesionProgramada(
                "lab-2",
                "lab",
                FranjaSemanal(DiaSemana.LUNES, "09:00", "11:00"),
                "lab-2",
                "grupo-2",
            ),
            SesionProgramada(
                "lab-3",
                "lab",
                FranjaSemanal(DiaSemana.LUNES, "13:00", "15:00"),
                "lab-3",
                "grupo-3",
            ),
            SesionProgramada(
                "teoria",
                "teoria",
                FranjaSemanal(DiaSemana.LUNES, "17:00", "19:00"),
                "teoria-1",
            ),
        )

        puntaje = PuntuadorHorario().puntuar(datos, sesiones)

        self.assertEqual(puntaje.minutos_huecos, 308)

    def test_generador_conserva_sesion_fija_de_un_grupo_de_laboratorio(self) -> None:
        datos_base = crear_datos_planificables()
        fija = SesionFija(
            "lab",
            FranjaSemanal(DiaSemana.LUNES, "07:00", "09:00"),
            "lab-1",
            "grupo-1",
        )
        datos = DatosPlanificacion(
            docentes=datos_base.docentes,
            cursos=datos_base.cursos,
            aulas=datos_base.aulas,
            grupos_laboratorio=datos_base.grupos_laboratorio,
            sesiones_fijas=(fija,),
            configuracion=datos_base.configuracion,
        )

        resultado = GeneradorHorarios(max_estados=3000).generar(datos)

        self.assertGreaterEqual(len(resultado.horarios), 1)
        self.assertTrue(
            any(
                sesion.grupo_laboratorio_id == "grupo-1"
                and sesion.franja == fija.franja
                and sesion.aula_id == fija.aula_id
                for sesion in resultado.horarios[0].sesiones
            )
        )
        self.assertTrue(
            ValidadorHorario().validar(datos, resultado.horarios[0].sesiones).valido
        )


if __name__ == "__main__":
    unittest.main()
