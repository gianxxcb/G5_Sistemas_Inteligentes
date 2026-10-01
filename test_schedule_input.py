"""Pruebas del cargador JSON de datos de planificación."""

import json
import tempfile
import unittest
from pathlib import Path

from schedule_input import (
    ErrorEntradaPlanificacion,
    cargar_datos_planificacion,
    datos_planificacion_desde_dict,
)
from schedule_models import DiaSemana, TipoAula


def documento_planificacion() -> dict:
    return {
        "configuracion": {
            "cursos_por_semestre": 2,
            "cursos_con_laboratorio": 1,
            "grupos_por_curso_laboratorio": 3,
            "cantidad_aulas_laboratorio": 5,
            "max_horarios": 5,
        },
        "docentes": [
            {
                "id": "doc-1",
                "nombre": "Docente externo",
                "disponibilidad": [
                    {
                        "dia": "lunes",
                        "hora_inicio": "07:00",
                        "hora_fin": "17:00",
                    }
                ],
            }
        ],
        "cursos": [
            {
                "id": "lab",
                "nombre": "Laboratorio",
                "docente_id": "doc-1",
                "cohorte_id": "cohorte-1",
                "duracion_minutos": 120,
                "requiere_laboratorio": True,
            },
            {
                "id": "teoria",
                "nombre": "Teoría",
                "docente_id": "doc-1",
                "cohorte_id": "cohorte-1",
                "duracion_minutos": 120,
            },
        ],
        "grupos_laboratorio": [
            {
                "id": f"grupo-{indice}",
                "curso_id": "lab",
                "cohorte_id": "cohorte-1",
                "cantidad_estudiantes": cantidad,
                "subcohorte_id": f"seccion-{indice}",
            }
            for indice, cantidad in enumerate((45, 50, 55), start=1)
        ],
        "aulas": [
            {
                "id": f"lab-{indice}",
                "capacidad": 55,
                "tipo": "laboratorio",
                "tiene_computadoras": True,
            }
            for indice in range(1, 6)
        ]
        + [
            {
                "id": "aula-teoria",
                "capacidad": 60,
                "tipo": "teoria",
            }
        ],
        "sesiones_fijas": [
            {
                "curso_id": "lab",
                "franja": {
                    "dia": "lunes",
                    "hora_inicio": "07:00",
                    "hora_fin": "09:00",
                },
                "aula_id": "lab-1",
                "grupo_laboratorio_id": "grupo-1",
            }
        ],
    }


class DatosPlanificacionDesdeDictTests(unittest.TestCase):
    def test_construye_datos_de_todos_los_componentes(self) -> None:
        datos = datos_planificacion_desde_dict(documento_planificacion())

        self.assertEqual(len(datos.cursos), 2)
        self.assertEqual(len(datos.grupos_laboratorio), 3)
        self.assertEqual(datos.grupos_laboratorio[0].subcohorte_id, "seccion-1")
        self.assertEqual(datos.sesiones_fijas[0].grupo_laboratorio_id, "grupo-1")
        self.assertEqual(datos.docentes[0].disponibilidad[0].dia, DiaSemana.LUNES)
        self.assertEqual(datos.aulas[0].tipo, TipoAula.LABORATORIO)

    def test_usa_configuracion_predeterminada_si_se_omite(self) -> None:
        documento = documento_planificacion()
        documento.pop("configuracion")

        with self.assertRaisesRegex(ErrorEntradaPlanificacion, "Se esperaban 7 cursos"):
            datos_planificacion_desde_dict(documento)

    def test_rechaza_campos_desconocidos_para_detectar_errores_tipograficos(self) -> None:
        documento = documento_planificacion()
        documento["cursos"][0]["duracion_minuto"] = 120

        with self.assertRaisesRegex(
            ErrorEntradaPlanificacion, "campos desconocidos: duracion_minuto"
        ):
            datos_planificacion_desde_dict(documento)

    def test_rechaza_booleano_como_capacidad_numerica(self) -> None:
        documento = documento_planificacion()
        documento["aulas"][0]["capacidad"] = True

        with self.assertRaisesRegex(ErrorEntradaPlanificacion, "capacidad debe"):
            datos_planificacion_desde_dict(documento)

    def test_rechaza_referencia_a_docente_inexistente(self) -> None:
        documento = documento_planificacion()
        documento["cursos"][0]["docente_id"] = "desconocido"

        with self.assertRaisesRegex(
            ErrorEntradaPlanificacion, "docente inexistente desconocido"
        ):
            datos_planificacion_desde_dict(documento)

    def test_rechaza_documento_raiz_que_no_es_objeto(self) -> None:
        with self.assertRaisesRegex(ErrorEntradaPlanificacion, r"\$ debe ser"):
            datos_planificacion_desde_dict([])

    def test_datos_cargados_se_conectan_al_generador_del_agente(self) -> None:
        from agent_expert import AgenteExperto

        datos = datos_planificacion_desde_dict(documento_planificacion())
        resultado = AgenteExperto().generar_horarios(datos)

        self.assertGreaterEqual(len(resultado.horarios), 1, resultado.mensaje)


class CargarDatosPlanificacionTests(unittest.TestCase):
    def test_carga_archivo_json_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as directorio:
            ruta = Path(directorio) / "plan.json"
            ruta.write_text(
                json.dumps(documento_planificacion(), ensure_ascii=False),
                encoding="utf-8",
            )

            datos = cargar_datos_planificacion(ruta)

        self.assertEqual(datos.cursos[0].nombre, "Laboratorio")

    def test_reporta_json_mal_formado_con_ubicacion(self) -> None:
        with tempfile.TemporaryDirectory() as directorio:
            ruta = Path(directorio) / "roto.json"
            ruta.write_text('{"cursos": [}', encoding="utf-8")

            with self.assertRaisesRegex(
                ErrorEntradaPlanificacion, "JSON inválido.*línea 1"
            ):
                cargar_datos_planificacion(ruta)

    def test_reporta_archivo_inexistente(self) -> None:
        with tempfile.TemporaryDirectory() as directorio:
            ruta = Path(directorio) / "no-existe.json"

            with self.assertRaisesRegex(
                ErrorEntradaPlanificacion, "No se pudo leer el archivo"
            ):
                cargar_datos_planificacion(ruta)


if __name__ == "__main__":
    unittest.main()
