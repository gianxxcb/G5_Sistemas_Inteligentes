"""Validación de restricciones obligatorias para horarios semanales."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from schedule_models import (
    Aula,
    Curso,
    DatosPlanificacion,
    Docente,
    GrupoLaboratorio,
    SesionFija,
    SesionProgramada,
    TipoAula,
)


@dataclass(frozen=True)
class IncidenciaHorario:
    codigo: str
    mensaje: str
    sesiones: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ResultadoValidacionHorario:
    valido: bool
    incidencias: Tuple[IncidenciaHorario, ...]


class ValidadorHorario:
    """Comprueba las reglas duras antes de puntuar o aceptar un horario."""

    def validar(
        self,
        datos: DatosPlanificacion,
        sesiones: Iterable[SesionProgramada],
    ) -> ResultadoValidacionHorario:
        """Valida el horario completo y devuelve todas las incidencias detectadas."""
        candidatas = tuple(sesiones)
        incidencias: List[IncidenciaHorario] = []

        cursos: Dict[str, Curso] = {curso.id: curso for curso in datos.cursos}
        docentes: Dict[str, Docente] = {
            docente.id: docente for docente in datos.docentes
        }
        aulas: Dict[str, Aula] = {aula.id: aula for aula in datos.aulas}
        grupos: Dict[str, GrupoLaboratorio] = {
            grupo.id: grupo for grupo in datos.grupos_laboratorio
        }
        grupos_por_cohorte: Dict[str, Tuple[GrupoLaboratorio, ...]] = {}
        for grupo in datos.grupos_laboratorio:
            grupos_por_cohorte.setdefault(grupo.cohorte_id, ())
            grupos_por_cohorte[grupo.cohorte_id] += (grupo,)

        vistos = set()
        for sesion in candidatas:
            if not isinstance(sesion, SesionProgramada):
                incidencias.append(
                    IncidenciaHorario(
                        "sesion_invalida",
                        "Todas las entradas deben ser instancias de SesionProgramada.",
                    )
                )
                continue
            if sesion.id in vistos:
                incidencias.append(
                    IncidenciaHorario(
                        "id_sesion_duplicado",
                        f"El identificador de sesión {sesion.id} está duplicado.",
                        (sesion.id,),
                    )
                )
            vistos.add(sesion.id)

        sesiones_validas = tuple(
            sesion for sesion in candidatas if isinstance(sesion, SesionProgramada)
        )
        por_grupo: Dict[str, List[SesionProgramada]] = {}
        cursos_presentes = set()

        for sesion in sesiones_validas:
            curso = cursos.get(sesion.curso_id)
            aula = aulas.get(sesion.aula_id)
            if curso is None:
                incidencias.append(
                    IncidenciaHorario(
                        "curso_inexistente",
                        f"La sesión {sesion.id} referencia el curso inexistente "
                        f"{sesion.curso_id}.",
                        (sesion.id,),
                    )
                )
                continue
            cursos_presentes.add(curso.id)
            if aula is None:
                incidencias.append(
                    IncidenciaHorario(
                        "aula_inexistente",
                        f"La sesión {sesion.id} referencia el aula inexistente "
                        f"{sesion.aula_id}.",
                        (sesion.id,),
                    )
                )

            if sesion.franja.dia not in datos.configuracion.dias_habiles:
                incidencias.append(
                    IncidenciaHorario(
                        "dia_no_habilitado",
                        f"La sesión {sesion.id} está programada en un día no habilitado.",
                        (sesion.id,),
                    )
                )

            if sesion.franja.duracion_minutos != curso.duracion_minutos:
                incidencias.append(
                    IncidenciaHorario(
                        "duracion_incorrecta",
                        f"La duración de la sesión {sesion.id} no coincide con la "
                        f"duración de {curso.id} ({curso.duracion_minutos} minutos).",
                        (sesion.id,),
                    )
                )

            docente = docentes.get(curso.docente_id)
            if docente is not None and not _esta_disponible(docente, sesion):
                incidencias.append(
                    IncidenciaHorario(
                        "docente_fuera_de_disponibilidad",
                        f"El docente {docente.id} no está disponible durante la "
                        f"sesión {sesion.id}.",
                        (sesion.id,),
                    )
                )

            grupo = None
            if sesion.grupo_laboratorio_id is not None:
                grupo = grupos.get(sesion.grupo_laboratorio_id)
                if grupo is None:
                    incidencias.append(
                        IncidenciaHorario(
                            "grupo_inexistente",
                            f"La sesión {sesion.id} referencia el grupo inexistente "
                            f"{sesion.grupo_laboratorio_id}.",
                            (sesion.id,),
                        )
                    )
                elif grupo.curso_id != curso.id:
                    incidencias.append(
                        IncidenciaHorario(
                            "grupo_curso_incompatible",
                            f"El grupo {grupo.id} pertenece al curso {grupo.curso_id}, "
                            f"no a {curso.id}.",
                            (sesion.id,),
                        )
                    )
                else:
                    por_grupo.setdefault(grupo.id, []).append(sesion)

            if curso.requiere_laboratorio and grupo is None:
                incidencias.append(
                    IncidenciaHorario(
                        "falta_grupo_laboratorio",
                        f"La sesión {sesion.id} debe identificar su grupo de laboratorio.",
                        (sesion.id,),
                    )
                )
            elif not curso.requiere_laboratorio and grupo is not None:
                incidencias.append(
                    IncidenciaHorario(
                        "grupo_en_curso_no_laboratorio",
                        f"El curso {curso.id} no requiere grupos de laboratorio.",
                        (sesion.id,),
                    )
                )

            if curso.requiere_laboratorio and aula is not None:
                if aula.tipo != TipoAula.LABORATORIO or not aula.tiene_computadoras:
                    incidencias.append(
                        IncidenciaHorario(
                            "aula_no_apta_para_laboratorio",
                            f"El aula {aula.id} no es un laboratorio equipado.",
                            (sesion.id,),
                        )
                    )
                if grupo is not None and aula.capacidad < grupo.cantidad_estudiantes:
                    incidencias.append(
                        IncidenciaHorario(
                            "capacidad_insuficiente",
                            f"El aula {aula.id} no tiene capacidad para el grupo {grupo.id}.",
                            (sesion.id,),
                        )
                    )
            elif not curso.requiere_laboratorio and aula is not None:
                if aula.tipo != TipoAula.TEORIA:
                    incidencias.append(
                        IncidenciaHorario(
                            "aula_no_apta_para_teoria",
                            f"El aula {aula.id} no es un aula de teoría.",
                            (sesion.id,),
                        )
                    )

        for curso in datos.cursos:
            if curso.id not in cursos_presentes:
                incidencias.append(
                    IncidenciaHorario(
                        "curso_sin_programar",
                        f"El curso {curso.id} no tiene sesiones programadas.",
                    )
                )

        for grupo in datos.grupos_laboratorio:
            sesiones_grupo = por_grupo.get(grupo.id, [])
            if len(sesiones_grupo) != 1:
                incidencias.append(
                    IncidenciaHorario(
                        "cantidad_sesiones_grupo_incorrecta",
                        f"El grupo {grupo.id} debe tener exactamente una sesión; "
                        f"tiene {len(sesiones_grupo)}.",
                        tuple(sesion.id for sesion in sesiones_grupo),
                    )
                )

        self._validar_sesiones_fijas(
            datos.sesiones_fijas, sesiones_validas, incidencias
        )
        self._validar_choques(
            sesiones_validas, cursos, grupos, grupos_por_cohorte, incidencias
        )
        self._validar_laboratorios_contra_fijos(
            datos.sesiones_fijas,
            sesiones_validas,
            cursos,
            grupos,
            incidencias,
        )

        return ResultadoValidacionHorario(
            valido=not incidencias,
            incidencias=tuple(incidencias),
        )

    @staticmethod
    def _validar_sesiones_fijas(
        fijas: Tuple[SesionFija, ...],
        sesiones: Tuple[SesionProgramada, ...],
        incidencias: List[IncidenciaHorario],
    ) -> None:
        for fija in fijas:
            coincide = any(
                sesion.curso_id == fija.curso_id
                and sesion.franja == fija.franja
                and (fija.aula_id is None or sesion.aula_id == fija.aula_id)
                and sesion.grupo_laboratorio_id == fija.grupo_laboratorio_id
                for sesion in sesiones
            )
            if not coincide:
                incidencias.append(
                    IncidenciaHorario(
                        "sesion_fija_ausente_o_modificada",
                        f"La sesión fija de {fija.curso_id} debe conservar su día y "
                        "horario, y su aula si fue especificada.",
                    )
                )

    @staticmethod
    def _validar_choques(
        sesiones: Tuple[SesionProgramada, ...],
        cursos: Dict[str, Curso],
        grupos: Dict[str, GrupoLaboratorio],
        grupos_por_cohorte: Dict[str, Tuple[GrupoLaboratorio, ...]],
        incidencias: List[IncidenciaHorario],
    ) -> None:
        for indice, primera in enumerate(sesiones):
            curso_primero = cursos.get(primera.curso_id)
            for segunda in sesiones[indice + 1 :]:
                if not primera.franja.se_superpone(segunda.franja):
                    continue
                curso_segundo = cursos.get(segunda.curso_id)
                if primera.aula_id == segunda.aula_id:
                    incidencias.append(
                        IncidenciaHorario(
                            "choque_de_aula",
                            f"Las sesiones {primera.id} y {segunda.id} se superponen "
                            f"en el aula {primera.aula_id}.",
                            (primera.id, segunda.id),
                        )
                    )
                if (
                    curso_primero is not None
                    and curso_segundo is not None
                    and curso_primero.docente_id == curso_segundo.docente_id
                ):
                    incidencias.append(
                        IncidenciaHorario(
                            "choque_de_docente",
                            f"El docente {curso_primero.docente_id} tiene sesiones "
                            f"superpuestas {primera.id} y {segunda.id}.",
                            (primera.id, segunda.id),
                        )
                    )
                if (
                    curso_primero is not None
                    and curso_segundo is not None
                    and _audiencia_sesion(
                        primera, curso_primero, grupos, grupos_por_cohorte
                    )
                    & _audiencia_sesion(
                        segunda, curso_segundo, grupos, grupos_por_cohorte
                    )
                ):
                    incidencias.append(
                        IncidenciaHorario(
                            "choque_de_cohorte",
                            "Los mismos estudiantes tienen sesiones "
                            f"superpuestas {primera.id} y {segunda.id}.",
                            (primera.id, segunda.id),
                        )
                    )

    @staticmethod
    def _validar_laboratorios_contra_fijos(
        fijas: Tuple[SesionFija, ...],
        sesiones: Tuple[SesionProgramada, ...],
        cursos: Dict[str, Curso],
        grupos: Dict[str, GrupoLaboratorio],
        incidencias: List[IncidenciaHorario],
    ) -> None:
        for sesion in sesiones:
            if sesion.grupo_laboratorio_id is None:
                continue
            curso_laboratorio = cursos.get(sesion.curso_id)
            if curso_laboratorio is None:
                continue
            for fija in fijas:
                if (
                    sesion.curso_id == fija.curso_id
                    and sesion.grupo_laboratorio_id == fija.grupo_laboratorio_id
                    and sesion.franja == fija.franja
                ):
                    continue
                curso_fijo = cursos.get(fija.curso_id)
                grupo_laboratorio = grupos.get(sesion.grupo_laboratorio_id)
                grupo_fijo = grupos.get(fija.grupo_laboratorio_id or "")
                mismo_estudiante = (
                    curso_fijo is not None
                    and curso_fijo.cohorte_id == curso_laboratorio.cohorte_id
                    and (
                        fija.grupo_laboratorio_id is None
                        or (
                            grupo_laboratorio is not None
                            and grupo_fijo is not None
                            and grupo_laboratorio.subcohorte_id
                            == grupo_fijo.subcohorte_id
                        )
                    )
                )
                if mismo_estudiante and sesion.franja.se_superpone(fija.franja):
                    incidencias.append(
                        IncidenciaHorario(
                            "laboratorio_choca_con_curso_fijo",
                            f"El laboratorio {sesion.id} se cruza con el curso fijo "
                            f"{fija.curso_id}.",
                            (sesion.id,),
                        )
                    )


def _audiencia_sesion(
    sesion: SesionProgramada,
    curso: Curso,
    grupos: Dict[str, GrupoLaboratorio],
    grupos_por_cohorte: Dict[str, Tuple[GrupoLaboratorio, ...]],
) -> set[Tuple[str, Optional[str]]]:
    if sesion.grupo_laboratorio_id is not None:
        grupo = grupos.get(sesion.grupo_laboratorio_id)
        if grupo is not None and grupo.curso_id == curso.id:
            return {(curso.cohorte_id, grupo.subcohorte_id)}

    subcohortes = {
        grupo.subcohorte_id
        for grupo in grupos_por_cohorte.get(curso.cohorte_id, ())
    }
    if subcohortes:
        return {(curso.cohorte_id, subcohorte_id) for subcohorte_id in subcohortes}
    return {(curso.cohorte_id, None)}


def _esta_disponible(docente: Docente, sesion: SesionProgramada) -> bool:
    return any(
        disponibilidad.dia == sesion.franja.dia
        and disponibilidad.hora_inicio <= sesion.franja.hora_inicio
        and sesion.franja.hora_fin <= disponibilidad.hora_fin
        for disponibilidad in docente.disponibilidad
    )
