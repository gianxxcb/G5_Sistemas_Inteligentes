"""Generación acotada y puntuación de horarios semanales."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from math import sqrt
from typing import Dict, Iterable, List, Optional, Tuple

from schedule_models import (
    Aula,
    Curso,
    DatosPlanificacion,
    Docente,
    DiaSemana,
    FranjaSemanal,
    GrupoLaboratorio,
    SesionFija,
    SesionProgramada,
    TipoAula,
)
from schedule_validator import (
    ValidadorHorario,
)


FORMATO_HORA = "%H:%M"
_ORDEN_DIAS = {dia: indice for indice, dia in enumerate(DiaSemana)}


@dataclass(frozen=True)
class PreferenciasHorario:
    """Pesos de calidad; los horarios inválidos siempre se descartan."""

    peso_huecos: float = 1.0
    peso_desbalance_semanal: float = 0.25
    dias_activos_objetivo: Optional[int] = None
    peso_dias_fuera_objetivo: float = 120.0

    def __post_init__(self) -> None:
        for nombre in (
            "peso_huecos",
            "peso_desbalance_semanal",
            "peso_dias_fuera_objetivo",
        ):
            valor = getattr(self, nombre)
            if isinstance(valor, bool) or not isinstance(valor, (int, float)) or valor < 0:
                raise ValueError(f"{nombre} debe ser un número no negativo.")
        if self.dias_activos_objetivo is not None and (
            isinstance(self.dias_activos_objetivo, bool)
            or not isinstance(self.dias_activos_objetivo, int)
            or self.dias_activos_objetivo <= 0
        ):
            raise ValueError("dias_activos_objetivo debe ser un entero positivo.")


@dataclass(frozen=True)
class PuntajeHorario:
    penalizacion_total: float
    penalizacion_huecos: float
    penalizacion_desbalance: float
    penalizacion_dias_activos: float
    dias_activos: float
    minutos_huecos: float


@dataclass(frozen=True)
class HorarioPropuesto:
    sesiones: Tuple[SesionProgramada, ...]
    puntaje: PuntajeHorario


@dataclass(frozen=True)
class ResultadoGeneracion:
    horarios: Tuple[HorarioPropuesto, ...]
    estados_explorados: int
    busqueda_completa: bool
    mensaje: str


@dataclass(frozen=True)
class _Tarea:
    id: str
    curso: Curso
    grupo: Optional[GrupoLaboratorio]
    franja_fija: Optional[FranjaSemanal] = None
    aula_fija: Optional[str] = None


class PuntuadorHorario:
    """Calcula penalizaciones descriptivas para horarios ya factibles."""

    def puntuar(
        self,
        datos: DatosPlanificacion,
        sesiones: Iterable[SesionProgramada],
        preferencias: PreferenciasHorario = PreferenciasHorario(),
    ) -> PuntajeHorario:
        sesiones = tuple(sesiones)
        resultado = ValidadorHorario().validar(datos, sesiones)
        if not resultado.valido:
            detalles = "; ".join(
                f"{incidencia.codigo}: {incidencia.mensaje}"
                for incidencia in resultado.incidencias
            )
            raise ValueError(f"No se puede puntuar un horario inválido: {detalles}")
        return _puntuar_sesiones(
            sesiones,
            {curso.id: curso.cohorte_id for curso in datos.cursos},
            datos.grupos_laboratorio,
            datos.configuracion.dias_habiles,
            _preferencias_efectivas(preferencias, datos),
        )


class GeneradorHorarios:
    """Busca hasta el máximo configurado de horarios válidos y diferenciados."""

    def __init__(
        self,
        intervalo_inicio_minutos: int = 30,
        max_estados: int = 5000,
        preferencias: PreferenciasHorario = PreferenciasHorario(),
    ) -> None:
        if (
            isinstance(intervalo_inicio_minutos, bool)
            or not isinstance(intervalo_inicio_minutos, int)
            or intervalo_inicio_minutos <= 0
        ):
            raise ValueError("intervalo_inicio_minutos debe ser un entero positivo.")
        if (
            isinstance(max_estados, bool)
            or not isinstance(max_estados, int)
            or max_estados <= 0
        ):
            raise ValueError("max_estados debe ser un entero positivo.")
        self.intervalo_inicio_minutos = intervalo_inicio_minutos
        self.max_estados = max_estados
        self.preferencias = preferencias
        self._validador = ValidadorHorario()

    def generar(self, datos: DatosPlanificacion) -> ResultadoGeneracion:
        tareas = self._crear_tareas(datos)
        aulas = {aula.id: aula for aula in datos.aulas}
        cursos = {curso.id: curso for curso in datos.cursos}
        grupos = {grupo.id: grupo for grupo in datos.grupos_laboratorio}
        docentes = {docente.id: docente for docente in datos.docentes}
        candidatos = {
            tarea.id: self._crear_candidatos(
                tarea,
                aulas,
                docentes,
                datos.configuracion.tamano_grupo_objetivo,
            )
            for tarea in tareas
        }
        tareas = tuple(
            sorted(tareas, key=lambda tarea: (len(candidatos[tarea.id]), tarea.id))
        )

        if any(not candidatos[tarea.id] for tarea in tareas):
            sin_candidatos = [
                tarea.id for tarea in tareas if not candidatos[tarea.id]
            ]
            return ResultadoGeneracion(
                horarios=(),
                estados_explorados=0,
                busqueda_completa=True,
                mensaje=(
                    "No hay combinaciones de horario y aula para: "
                    + ", ".join(sin_candidatos)
                    + "."
                ),
            )

        hallados: Dict[Tuple[Tuple[str, str, str], ...], HorarioPropuesto] = {}
        estados = 0
        limitado = False

        def explorar(
            indice: int,
            sesiones: Tuple[SesionProgramada, ...],
        ) -> None:
            nonlocal estados, limitado
            if estados >= self.max_estados:
                limitado = True
                return
            estados += 1

            if indice == len(tareas):
                validacion = self._validador.validar(datos, sesiones)
                if not validacion.valido:
                    return
                propuesta = HorarioPropuesto(
                    sesiones=tuple(sorted(sesiones, key=_orden_sesion)),
                    puntaje=_puntuar_sesiones(
                        sesiones,
                        {curso.id: curso.cohorte_id for curso in datos.cursos},
                        datos.grupos_laboratorio,
                        datos.configuracion.dias_habiles,
                        _preferencias_efectivas(self.preferencias, datos),
                    ),
                )
                firma = _firma_horario(propuesta.sesiones)
                anterior = hallados.get(firma)
                if anterior is None or propuesta.puntaje.penalizacion_total < (
                    anterior.puntaje.penalizacion_total
                ):
                    hallados[firma] = propuesta
                return

            tarea = tareas[indice]
            for candidato in candidatos[tarea.id]:
                if not _es_compatible(
                    candidato, sesiones, tarea.curso, cursos, grupos
                ):
                    continue
                explorar(indice + 1, sesiones + (candidato,))
                if estados >= self.max_estados:
                    limitado = indice + 1 < len(tareas) or limitado
                    return

        explorar(0, ())
        mejores = tuple(
            sorted(
                hallados.values(),
                key=lambda horario: (
                    horario.puntaje.penalizacion_total,
                    _firma_horario(horario.sesiones),
                ),
            )[: datos.configuracion.max_horarios]
        )
        completo = not limitado
        if mejores:
            mensaje = (
                f"Se encontraron {len(mejores)} horarios válidos"
                + (
                    " dentro del límite de búsqueda."
                    if limitado
                    else "."
                )
            )
        elif limitado:
            mensaje = (
                "No se encontró un horario válido antes de alcanzar el límite de "
                "búsqueda; esto no demuestra que el problema sea infactible."
            )
        else:
            mensaje = "No existe un horario válido con las restricciones y datos indicados."

        return ResultadoGeneracion(
            horarios=mejores,
            estados_explorados=estados,
            busqueda_completa=completo,
            mensaje=mensaje,
        )

    @staticmethod
    def _crear_tareas(datos: DatosPlanificacion) -> Tuple[_Tarea, ...]:
        cursos = {curso.id: curso for curso in datos.cursos}
        grupos = {grupo.id: grupo for grupo in datos.grupos_laboratorio}
        fijas_por_curso: Dict[str, List[SesionFija]] = {}
        grupos_fijos = set()
        tareas: List[_Tarea] = []

        for indice, fija in enumerate(datos.sesiones_fijas):
            curso = cursos[fija.curso_id]
            fijas_por_curso.setdefault(curso.id, []).append(fija)
            grupo = (
                grupos[fija.grupo_laboratorio_id]
                if fija.grupo_laboratorio_id is not None
                else None
            )
            if grupo is not None:
                grupos_fijos.add(grupo.id)
            tareas.append(
                _Tarea(
                    id=f"fija:{indice}:{curso.id}",
                    curso=curso,
                    grupo=grupo,
                    franja_fija=fija.franja,
                    aula_fija=fija.aula_id,
                )
            )

        for curso in datos.cursos:
            if curso.requiere_laboratorio:
                if curso.duracion_laboratorio_minutos is not None:
                    tareas.append(
                        _Tarea(
                            id=f"teoria:{curso.id}",
                            curso=curso,
                            grupo=None,
                        )
                    )
                for grupo in datos.grupos_laboratorio:
                    if grupo.curso_id == curso.id and grupo.id not in grupos_fijos:
                        tareas.append(
                            _Tarea(
                                id=f"grupo:{grupo.id}",
                                curso=curso,
                                grupo=grupo,
                            )
                        )
            elif curso.id not in fijas_por_curso:
                tareas.append(
                    _Tarea(id=f"curso:{curso.id}", curso=curso, grupo=None)
                )

        return tuple(tareas)

    def _crear_candidatos(
        self,
        tarea: _Tarea,
        aulas: Dict[str, Aula],
        docentes: Dict[str, Docente],
        estudiantes_totales: int = 0,
    ) -> Tuple[SesionProgramada, ...]:
        docente = docentes[tarea.curso.docente_id]
        if (
            tarea.franja_fija is not None
            and not _franja_dentro_de_disponibilidad(
                docente.disponibilidad, tarea.franja_fija
            )
        ):
            return ()
        franjas = (
            (tarea.franja_fija,)
            if tarea.franja_fija is not None
            else _generar_franjas(
                docente.disponibilidad,
                (
                    tarea.curso.duracion_laboratorio_minutos
                    if tarea.grupo is not None
                    and tarea.curso.duracion_laboratorio_minutos is not None
                    else tarea.curso.duracion_minutos
                ),
                self.intervalo_inicio_minutos,
            )
        )
        if tarea.grupo is not None:
            aulas_compatibles = tuple(
                aula
                for aula in aulas.values()
                if aula.tipo == TipoAula.LABORATORIO
                and aula.tiene_computadoras
                and aula.capacidad >= tarea.grupo.cantidad_estudiantes
            )
        else:
            aulas_compatibles = tuple(
                aula
                for aula in aulas.values()
                if aula.tipo == TipoAula.TEORIA
                and aula.capacidad >= estudiantes_totales
            )

        if tarea.aula_fija is not None:
            aulas_compatibles = tuple(
                aula for aula in aulas_compatibles if aula.id == tarea.aula_fija
            )

        return tuple(
            SesionProgramada(
                id=tarea.id,
                curso_id=tarea.curso.id,
                franja=franja,
                aula_id=aula.id,
                grupo_laboratorio_id=(
                    tarea.grupo.id if tarea.grupo is not None else None
                ),
            )
            for franja in franjas
            for aula in sorted(aulas_compatibles, key=lambda item: item.id)
        )


def _generar_franjas(
    disponibilidad: Tuple[FranjaSemanal, ...],
    duracion_minutos: int,
    paso_minutos: int,
) -> Tuple[FranjaSemanal, ...]:
    candidatas = set()
    for ventana in disponibilidad:
        inicio = _a_minutos(ventana.hora_inicio)
        fin = _a_minutos(ventana.hora_fin)
        ultimo_inicio = fin - duracion_minutos
        while inicio <= ultimo_inicio:
            candidatas.add(
                FranjaSemanal(
                    ventana.dia,
                    _desde_minutos(inicio),
                    _desde_minutos(inicio + duracion_minutos),
                )
            )
            inicio += paso_minutos
    return tuple(sorted(candidatas, key=_orden_franja))


def _franja_dentro_de_disponibilidad(
    disponibilidad: Tuple[FranjaSemanal, ...],
    franja: FranjaSemanal,
) -> bool:
    return any(
        ventana.dia == franja.dia
        and ventana.hora_inicio <= franja.hora_inicio
        and franja.hora_fin <= ventana.hora_fin
        for ventana in disponibilidad
    )


def _es_compatible(
    candidata: SesionProgramada,
    existentes: Tuple[SesionProgramada, ...],
    curso: Curso,
    cursos: Dict[str, Curso],
    grupos: Dict[str, GrupoLaboratorio],
) -> bool:
    for existente in existentes:
        if not candidata.franja.se_superpone(existente.franja):
            continue
        curso_existente = cursos[existente.curso_id]
        if (
            candidata.aula_id == existente.aula_id
            or curso.docente_id == curso_existente.docente_id
            or _audiencias_comparten_estudiantes(
                candidata, curso, existente, curso_existente, grupos
            )
        ):
            return False
    return True


def _puntuar_sesiones(
    sesiones: Tuple[SesionProgramada, ...],
    cohorte_por_curso: Dict[str, str],
    grupos: Tuple[GrupoLaboratorio, ...],
    dias_habiles: Tuple[DiaSemana, ...],
    preferencias: PreferenciasHorario,
) -> PuntajeHorario:
    grupos_por_id = {grupo.id: grupo for grupo in grupos}
    subcohortes: Dict[str, Dict[str, int]] = {}
    for grupo in grupos:
        subcohortes.setdefault(grupo.cohorte_id, {})[grupo.subcohorte_id] = (
            grupo.cantidad_estudiantes
        )

    agendas: Dict[
        Tuple[str, Optional[str]], List[SesionProgramada]
    ] = {}
    pesos: Dict[Tuple[str, Optional[str]], int] = {}
    for cohorte in set(cohorte_por_curso.values()):
        if subcohortes.get(cohorte):
            for subcohorte_id, cantidad in subcohortes[cohorte].items():
                clave = (cohorte, subcohorte_id)
                agendas[clave] = []
                pesos[clave] = cantidad
        else:
            clave = (cohorte, None)
            agendas[clave] = []
            pesos[clave] = 1

    for sesion in sesiones:
        cohorte = cohorte_por_curso[sesion.curso_id]
        if sesion.grupo_laboratorio_id is not None:
            grupo = grupos_por_id.get(sesion.grupo_laboratorio_id)
            if grupo is not None:
                agendas[(cohorte, grupo.subcohorte_id)].append(sesion)
                continue
        for clave in agendas:
            if clave[0] == cohorte:
                agendas[clave].append(sesion)

    peso_total = sum(pesos.values())
    minutos_huecos = 0.0
    desbalance = 0.0
    dias_activos = 0.0
    if peso_total:
        for clave, agenda in agendas.items():
            agenda.sort(key=lambda sesion: _a_minutos(sesion.franja.hora_inicio))
            huecos_agenda = sum(
                max(
                    0,
                    _a_minutos(siguiente.franja.hora_inicio)
                    - _a_minutos(anterior.franja.hora_fin),
                )
                for anterior, siguiente in zip(agenda, agenda[1:])
            )
            carga_diaria = {dia: 0 for dia in dias_habiles}
            dias_agenda = set()
            for sesion in agenda:
                carga_diaria[sesion.franja.dia] += sesion.franja.duracion_minutos
                dias_agenda.add(sesion.franja.dia)
            cargas = [carga_diaria[dia] for dia in dias_habiles]
            promedio = sum(cargas) / len(cargas) if cargas else 0
            desbalance_agenda = (
                sqrt(
                    sum((carga - promedio) ** 2 for carga in cargas) / len(cargas)
                )
                if cargas
                else 0
            )
            proporcion = pesos[clave] / peso_total
            minutos_huecos += huecos_agenda * proporcion
            desbalance += desbalance_agenda * proporcion
            dias_activos += len(dias_agenda) * proporcion

    exceso_dias = (
        abs(dias_activos - preferencias.dias_activos_objetivo)
        if preferencias.dias_activos_objetivo is not None
        else 0
    )
    huecos = minutos_huecos * preferencias.peso_huecos
    desbalance_ponderado = desbalance * preferencias.peso_desbalance_semanal
    dias_ponderados = exceso_dias * preferencias.peso_dias_fuera_objetivo

    return PuntajeHorario(
        penalizacion_total=huecos + desbalance_ponderado + dias_ponderados,
        penalizacion_huecos=huecos,
        penalizacion_desbalance=desbalance_ponderado,
        penalizacion_dias_activos=dias_ponderados,
        dias_activos=dias_activos,
        minutos_huecos=minutos_huecos,
    )


def _audiencias_comparten_estudiantes(
    primera: SesionProgramada,
    curso_primero: Curso,
    segunda: SesionProgramada,
    curso_segundo: Curso,
    grupos: Dict[str, GrupoLaboratorio],
) -> bool:
    if curso_primero.cohorte_id != curso_segundo.cohorte_id:
        return False

    subcohortes = {
        grupo.subcohorte_id
        for grupo in grupos.values()
        if grupo.cohorte_id == curso_primero.cohorte_id
    }
    return bool(
        _audiencia(primera, curso_primero, grupos, subcohortes)
        & _audiencia(segunda, curso_segundo, grupos, subcohortes)
    )


def _audiencia(
    sesion: SesionProgramada,
    curso: Curso,
    grupos: Dict[str, GrupoLaboratorio],
    subcohortes: set[str],
) -> set[Optional[str]]:
    if sesion.grupo_laboratorio_id is not None:
        grupo = grupos.get(sesion.grupo_laboratorio_id)
        if grupo is not None and grupo.curso_id == curso.id:
            return {grupo.subcohorte_id}
    return subcohortes or {None}


def _preferencias_efectivas(
    preferencias: PreferenciasHorario,
    datos: DatosPlanificacion,
) -> PreferenciasHorario:
    if preferencias.dias_activos_objetivo is not None:
        return preferencias
    return PreferenciasHorario(
        peso_huecos=preferencias.peso_huecos,
        peso_desbalance_semanal=preferencias.peso_desbalance_semanal,
        dias_activos_objetivo=datos.configuracion.dias_activos_objetivo,
        peso_dias_fuera_objetivo=preferencias.peso_dias_fuera_objetivo,
    )


def _firma_horario(
    sesiones: Tuple[SesionProgramada, ...],
) -> Tuple[Tuple[str, str, str], ...]:
    return tuple(
        sorted(
            (
                sesion.id,
                sesion.franja.dia.value,
                sesion.franja.hora_inicio,
            )
            for sesion in sesiones
        )
    )


def _orden_sesion(sesion: SesionProgramada) -> Tuple[int, str, str, str]:
    return (
        _ORDEN_DIAS[sesion.franja.dia],
        sesion.franja.hora_inicio,
        sesion.aula_id,
        sesion.id,
    )


def _orden_franja(franja: FranjaSemanal) -> Tuple[int, str, str]:
    return (_ORDEN_DIAS[franja.dia], franja.hora_inicio, franja.hora_fin)


def _a_minutos(hora: str) -> int:
    valor = datetime.strptime(hora, FORMATO_HORA)
    return valor.hour * 60 + valor.minute


def _desde_minutos(minutos: int) -> str:
    valor = datetime(2000, 1, 1) + timedelta(minutes=minutos)
    return valor.strftime(FORMATO_HORA)
