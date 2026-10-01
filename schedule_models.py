"""Modelos y validaciones de datos para la planificación semanal de cursos."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import ceil, floor
from typing import Optional, Tuple


FORMATO_HORA = "%H:%M"


class ErrorModeloPlanificacion(ValueError):
    """Indica que los datos de planificación no cumplen el modelo."""


class DiaSemana(str, Enum):
    LUNES = "lunes"
    MARTES = "martes"
    MIERCOLES = "miercoles"
    JUEVES = "jueves"
    VIERNES = "viernes"
    SABADO = "sabado"
    DOMINGO = "domingo"


class TipoAula(str, Enum):
    TEORIA = "teoria"
    LABORATORIO = "laboratorio"


def _texto_requerido(valor: str, campo: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ErrorModeloPlanificacion(f"{campo} debe ser un texto no vacío.")
    return valor.strip()


def _normalizar_hora(valor: str, campo: str) -> str:
    if not isinstance(valor, str):
        raise ErrorModeloPlanificacion(f"{campo} debe tener formato HH:MM.")
    try:
        return datetime.strptime(valor.strip(), FORMATO_HORA).strftime(FORMATO_HORA)
    except ValueError as error:
        raise ErrorModeloPlanificacion(
            f"{campo} debe tener formato HH:MM válido."
        ) from error


@dataclass(frozen=True)
class FranjaSemanal:
    """Intervalo de clase o disponibilidad en un día de la semana."""

    dia: DiaSemana
    hora_inicio: str
    hora_fin: str

    def __post_init__(self) -> None:
        try:
            dia = self.dia if isinstance(self.dia, DiaSemana) else DiaSemana(self.dia)
        except (TypeError, ValueError) as error:
            raise ErrorModeloPlanificacion(
                "dia debe ser un día válido de la semana."
            ) from error
        inicio = _normalizar_hora(self.hora_inicio, "hora_inicio")
        fin = _normalizar_hora(self.hora_fin, "hora_fin")
        if inicio >= fin:
            raise ErrorModeloPlanificacion(
                "hora_inicio debe ser anterior a hora_fin."
            )

        object.__setattr__(self, "dia", dia)
        object.__setattr__(self, "hora_inicio", inicio)
        object.__setattr__(self, "hora_fin", fin)

    @property
    def duracion_minutos(self) -> int:
        inicio = datetime.strptime(self.hora_inicio, FORMATO_HORA)
        fin = datetime.strptime(self.hora_fin, FORMATO_HORA)
        return (fin.hour * 60 + fin.minute) - (inicio.hour * 60 + inicio.minute)

    def se_superpone(self, otra: FranjaSemanal) -> bool:
        """Indica si dos intervalos del mismo día tienen minutos en común."""
        if self.dia != otra.dia:
            return False
        return (
            self.hora_inicio < otra.hora_fin
            and otra.hora_inicio < self.hora_fin
        )


@dataclass(frozen=True)
class Docente:
    id: str
    nombre: str
    disponibilidad: Tuple[FranjaSemanal, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _texto_requerido(self.id, "id"))
        object.__setattr__(self, "nombre", _texto_requerido(self.nombre, "nombre"))
        object.__setattr__(self, "disponibilidad", tuple(self.disponibilidad))
        if not all(isinstance(item, FranjaSemanal) for item in self.disponibilidad):
            raise ErrorModeloPlanificacion(
                "disponibilidad debe contener franjas semanales."
            )


@dataclass(frozen=True)
class Curso:
    id: str
    nombre: str
    docente_id: str
    cohorte_id: str
    duracion_minutos: int
    requiere_laboratorio: bool = False

    def __post_init__(self) -> None:
        for campo in ("id", "nombre", "docente_id", "cohorte_id"):
            object.__setattr__(self, campo, _texto_requerido(getattr(self, campo), campo))
        if (
            isinstance(self.duracion_minutos, bool)
            or not isinstance(self.duracion_minutos, int)
            or self.duracion_minutos <= 0
        ):
            raise ErrorModeloPlanificacion(
                "duracion_minutos debe ser un entero positivo."
            )
        if not isinstance(self.requiere_laboratorio, bool):
            raise ErrorModeloPlanificacion("requiere_laboratorio debe ser booleano.")


@dataclass(frozen=True)
class GrupoLaboratorio:
    """Grupo de una sección; reutilizar subcohorte_id entre cursos correlaciona alumnos."""

    id: str
    curso_id: str
    cohorte_id: str
    cantidad_estudiantes: int
    subcohorte_id: Optional[str] = None

    def __post_init__(self) -> None:
        for campo in ("id", "curso_id", "cohorte_id"):
            object.__setattr__(self, campo, _texto_requerido(getattr(self, campo), campo))
        subcohorte_id = self.subcohorte_id
        if subcohorte_id is None:
            subcohorte_id = f"{self.cohorte_id}:{self.id}"
        object.__setattr__(
            self,
            "subcohorte_id",
            _texto_requerido(subcohorte_id, "subcohorte_id"),
        )
        if (
            isinstance(self.cantidad_estudiantes, bool)
            or not isinstance(self.cantidad_estudiantes, int)
            or self.cantidad_estudiantes <= 0
        ):
            raise ErrorModeloPlanificacion(
                "cantidad_estudiantes debe ser un entero positivo."
            )


@dataclass(frozen=True)
class Aula:
    id: str
    capacidad: int
    tipo: TipoAula
    tiene_computadoras: bool = False
    tiene_proyector_integrado: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _texto_requerido(self.id, "id"))
        try:
            tipo = self.tipo if isinstance(self.tipo, TipoAula) else TipoAula(self.tipo)
        except (TypeError, ValueError) as error:
            raise ErrorModeloPlanificacion(
                "tipo debe ser 'teoria' o 'laboratorio'."
            ) from error
        object.__setattr__(self, "tipo", tipo)
        if (
            isinstance(self.capacidad, bool)
            or not isinstance(self.capacidad, int)
            or self.capacidad <= 0
        ):
            raise ErrorModeloPlanificacion("capacidad debe ser un entero positivo.")
        if not isinstance(self.tiene_computadoras, bool):
            raise ErrorModeloPlanificacion("tiene_computadoras debe ser booleano.")
        if not isinstance(self.tiene_proyector_integrado, bool):
            raise ErrorModeloPlanificacion(
                "tiene_proyector_integrado debe ser booleano."
            )


@dataclass(frozen=True)
class SesionFija:
    """Curso que ya ocupa una franja y no puede ser desplazado."""

    curso_id: str
    franja: FranjaSemanal
    aula_id: Optional[str] = None
    grupo_laboratorio_id: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "curso_id", _texto_requerido(self.curso_id, "curso_id"))
        if not isinstance(self.franja, FranjaSemanal):
            raise ErrorModeloPlanificacion("franja debe ser una FranjaSemanal.")
        if self.aula_id is not None:
            object.__setattr__(self, "aula_id", _texto_requerido(self.aula_id, "aula_id"))
        if self.grupo_laboratorio_id is not None:
            object.__setattr__(
                self,
                "grupo_laboratorio_id",
                _texto_requerido(self.grupo_laboratorio_id, "grupo_laboratorio_id"),
            )


@dataclass(frozen=True)
class SesionProgramada:
    """Instancia de un curso o grupo colocada en el horario candidato."""

    id: str
    curso_id: str
    franja: FranjaSemanal
    aula_id: str
    grupo_laboratorio_id: Optional[str] = None

    def __post_init__(self) -> None:
        for campo in ("id", "curso_id", "aula_id"):
            object.__setattr__(self, campo, _texto_requerido(getattr(self, campo), campo))
        if not isinstance(self.franja, FranjaSemanal):
            raise ErrorModeloPlanificacion("franja debe ser una FranjaSemanal.")
        if self.grupo_laboratorio_id is not None:
            object.__setattr__(
                self,
                "grupo_laboratorio_id",
                _texto_requerido(self.grupo_laboratorio_id, "grupo_laboratorio_id"),
            )


@dataclass(frozen=True)
class ConfiguracionPlanificacion:
    """Supuestos configurables para construir horarios y sus alternativas."""

    cursos_por_semestre: int = 7
    cursos_con_laboratorio: int = 3
    grupos_por_curso_laboratorio: int = 3
    cantidad_aulas_laboratorio: int = 5
    tamano_grupo_objetivo: int = 50
    tolerancia_tamano_grupo: float = 0.10
    max_horarios: int = 5
    dias_activos_objetivo: Optional[int] = 4
    dias_habiles: Tuple[DiaSemana, ...] = (
        DiaSemana.LUNES,
        DiaSemana.MARTES,
        DiaSemana.MIERCOLES,
        DiaSemana.JUEVES,
        DiaSemana.VIERNES,
    )

    def __post_init__(self) -> None:
        limites_positivos = (
            "cursos_por_semestre",
            "grupos_por_curso_laboratorio",
            "cantidad_aulas_laboratorio",
            "tamano_grupo_objetivo",
            "max_horarios",
        )
        for campo in limites_positivos:
            valor = getattr(self, campo)
            if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
                raise ErrorModeloPlanificacion(f"{campo} debe ser un entero positivo.")

        if (
            isinstance(self.cursos_con_laboratorio, bool)
            or not isinstance(self.cursos_con_laboratorio, int)
            or not 0 <= self.cursos_con_laboratorio <= self.cursos_por_semestre
        ):
            raise ErrorModeloPlanificacion(
                "cursos_con_laboratorio debe estar entre cero y cursos_por_semestre."
            )
        if (
            isinstance(self.tolerancia_tamano_grupo, bool)
            or not isinstance(self.tolerancia_tamano_grupo, (float, int))
            or not 0 <= self.tolerancia_tamano_grupo < 1
        ):
            raise ErrorModeloPlanificacion(
                "tolerancia_tamano_grupo debe estar entre cero y uno."
            )
        if self.dias_activos_objetivo is not None and (
            isinstance(self.dias_activos_objetivo, bool)
            or not isinstance(self.dias_activos_objetivo, int)
            or not 1 <= self.dias_activos_objetivo <= len(self.dias_habiles)
        ):
            raise ErrorModeloPlanificacion(
                "dias_activos_objetivo debe estar entre uno y la cantidad de días hábiles."
            )

        try:
            dias = tuple(
                dia if isinstance(dia, DiaSemana) else DiaSemana(dia)
                for dia in self.dias_habiles
            )
        except (TypeError, ValueError) as error:
            raise ErrorModeloPlanificacion(
                "dias_habiles debe contener días válidos de la semana."
            ) from error
        if not dias or len(set(dias)) != len(dias):
            raise ErrorModeloPlanificacion(
                "dias_habiles debe tener al menos un día y no repetirlos."
            )
        object.__setattr__(self, "dias_habiles", dias)

    @property
    def tamano_grupo_minimo(self) -> int:
        return 16  # Mínimo requerido de estudiantes para habilitar el curso

    @property
    def tamano_grupo_maximo(self) -> int:
        return 200


@dataclass(frozen=True)
class DatosPlanificacion:
    """Conjunto validado de recursos, cursos y compromisos semanales."""

    docentes: Tuple[Docente, ...]
    cursos: Tuple[Curso, ...]
    aulas: Tuple[Aula, ...]
    grupos_laboratorio: Tuple[GrupoLaboratorio, ...] = ()
    sesiones_fijas: Tuple[SesionFija, ...] = ()
    configuracion: ConfiguracionPlanificacion = ConfiguracionPlanificacion()

    def __post_init__(self) -> None:
        for campo in (
            "docentes",
            "cursos",
            "aulas",
            "grupos_laboratorio",
            "sesiones_fijas",
        ):
            object.__setattr__(self, campo, tuple(getattr(self, campo)))
        self._validar_referencias()

    def _validar_referencias(self) -> None:
        if len(self.cursos) != self.configuracion.cursos_por_semestre:
            raise ErrorModeloPlanificacion(
                f"Se esperaban {self.configuracion.cursos_por_semestre} cursos y "
                f"se recibieron {len(self.cursos)}."
            )
        _validar_ids_unicos(self.docentes, "docente")
        _validar_ids_unicos(self.cursos, "curso")
        _validar_ids_unicos(self.aulas, "aula")
        _validar_ids_unicos(self.grupos_laboratorio, "grupo de laboratorio")

        docentes = {docente.id for docente in self.docentes}
        cursos = {curso.id: curso for curso in self.cursos}
        aulas = {aula.id for aula in self.aulas}
        grupos_por_curso: dict[str, list[GrupoLaboratorio]] = {}

        for curso in self.cursos:
            if curso.docente_id not in docentes:
                raise ErrorModeloPlanificacion(
                    f"El curso {curso.id} referencia al docente inexistente "
                    f"{curso.docente_id}."
                )
        cantidad_cursos_laboratorio = sum(
            curso.requiere_laboratorio for curso in self.cursos
        )
        if (
            cantidad_cursos_laboratorio
            != self.configuracion.cursos_con_laboratorio
        ):
            raise ErrorModeloPlanificacion(
                f"Se esperaban {self.configuracion.cursos_con_laboratorio} cursos "
                f"con laboratorio y se recibieron {cantidad_cursos_laboratorio}."
            )

        for grupo in self.grupos_laboratorio:
            curso = cursos.get(grupo.curso_id)
            if curso is None:
                raise ErrorModeloPlanificacion(
                    f"El grupo {grupo.id} referencia al curso inexistente {grupo.curso_id}."
                )
            if not curso.requiere_laboratorio:
                raise ErrorModeloPlanificacion(
                    f"El curso {curso.id} no requiere laboratorio."
                )
            if grupo.cohorte_id != curso.cohorte_id:
                raise ErrorModeloPlanificacion(
                    f"El grupo {grupo.id} debe pertenecer a la cohorte {curso.cohorte_id}."
                )
            
            # Validación flexible: permite subgrupos dinámicos (ej. 15, 16, 4) sin rangos fijos estrictos
            if grupo.cantidad_estudiantes <= 0:
                raise ErrorModeloPlanificacion(
                    f"El grupo {grupo.id} debe tener una cantidad positiva de estudiantes."
                )

            # Validar que exista un laboratorio con capacidad para este subgrupo
            if not any(
                aula.tipo == TipoAula.LABORATORIO
                and aula.capacidad >= grupo.cantidad_estudiantes
                for aula in self.aulas
            ):
                raise ErrorModeloPlanificacion(
                    f"No hay un laboratorio con capacidad suficiente para el subgrupo "
                    f"{grupo.id} ({grupo.cantidad_estudiantes} estudiantes)."
                )

            grupos_por_curso.setdefault(curso.id, []).append(grupo)

        # Validación flexible de cantidad de grupos (permite subgrupos dinámicos sin exigir un número fijo estricto)
        for curso in self.cursos:
            if curso.requiere_laboratorio:
                grupos = grupos_por_curso.get(curso.id, [])
                if len(grupos) < 1:
                    raise ErrorModeloPlanificacion(
                        f"El curso {curso.id} requiere al menos un grupo de laboratorio."
                    )

        cantidad_laboratorios = sum(
            aula.tipo == TipoAula.LABORATORIO for aula in self.aulas
        )
        if cantidad_laboratorios != self.configuracion.cantidad_aulas_laboratorio:
            raise ErrorModeloPlanificacion(
                f"Se esperaban {self.configuracion.cantidad_aulas_laboratorio} aulas "
                f"de laboratorio y se recibieron {cantidad_laboratorios}."
            )

        for sesion in self.sesiones_fijas:
            curso = cursos.get(sesion.curso_id)
            if curso is None:
                raise ErrorModeloPlanificacion(
                    f"La sesión fija referencia al curso inexistente {sesion.curso_id}."
                )
            if sesion.aula_id is not None and sesion.aula_id not in aulas:
                raise ErrorModeloPlanificacion(
                    f"La sesión fija referencia al aula inexistente {sesion.aula_id}."
                )
            if curso.requiere_laboratorio and sesion.grupo_laboratorio_id is None:
                raise ErrorModeloPlanificacion(
                    f"La sesión fija del curso de laboratorio {curso.id} debe indicar "
                    "su grupo."
                )
            if not curso.requiere_laboratorio and sesion.grupo_laboratorio_id is not None:
                raise ErrorModeloPlanificacion(
                    f"La sesión fija del curso {curso.id} no puede indicar un grupo "
                    "de laboratorio."
                )
            if sesion.grupo_laboratorio_id is not None:
                grupo = next(
                    (
                        item
                        for item in self.grupos_laboratorio
                        if item.id == sesion.grupo_laboratorio_id
                    ),
                    None,
                )
                if grupo is None or grupo.curso_id != curso.id:
                    raise ErrorModeloPlanificacion(
                        f"La sesión fija referencia un grupo de laboratorio inválido: "
                        f"{sesion.grupo_laboratorio_id}."
                    )


def _validar_ids_unicos(elementos: tuple, nombre: str) -> None:
    ids = [elemento.id for elemento in elementos]
    if len(ids) != len(set(ids)):
        raise ErrorModeloPlanificacion(f"Hay identificadores de {nombre} duplicados.")