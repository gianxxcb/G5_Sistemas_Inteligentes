"""Carga validada de datos de planificación desde JSON.

El documento raíz acepta ``docentes``, ``cursos`` y ``aulas``. También puede
incluir ``grupos_laboratorio``, ``sesiones_fijas`` y ``configuracion``. Las
franjas usan los campos ``dia``, ``hora_inicio`` y ``hora_fin``.
"""

from __future__ import annotations

import json
from pathlib import Path
from enum import Enum
from typing import Any, Mapping, Optional, Tuple, Type, TypeVar

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


class ErrorEntradaPlanificacion(ValueError):
    """Documento de entrada mal formado o incompatible con el modelo."""


TipoEnum = TypeVar("TipoEnum", bound=Enum)


def cargar_datos_planificacion(ruta: str | Path) -> DatosPlanificacion:
    """Lee un archivo JSON UTF-8 y devuelve los datos de planificación validados."""
    ruta = Path(ruta)
    try:
        with ruta.open("r", encoding="utf-8") as archivo:
            documento = json.load(archivo)
    except OSError as error:
        raise ErrorEntradaPlanificacion(
            f"No se pudo leer el archivo de planificación '{ruta}': {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise ErrorEntradaPlanificacion(
            f"JSON inválido en '{ruta}', línea {error.lineno}, columna "
            f"{error.colno}: {error.msg}"
        ) from error
    return datos_planificacion_desde_dict(documento)


def datos_planificacion_desde_dict(documento: Any) -> DatosPlanificacion:
    """Convierte un objeto decodificado de JSON en modelos validados."""
    raiz = _objeto(documento, "$")
    _claves(
        raiz,
        "$",
        requeridas=("docentes", "cursos", "aulas"),
        opcionales=("grupos_laboratorio", "sesiones_fijas", "configuracion"),
    )

    configuracion = _crear_configuracion(raiz.get("configuracion", {}))
    docentes = tuple(
        _crear_docente(elemento, f"$.docentes[{indice}]")
        for indice, elemento in enumerate(_lista(raiz["docentes"], "$.docentes"))
    )
    cursos = tuple(
        _crear_curso(elemento, f"$.cursos[{indice}]")
        for indice, elemento in enumerate(_lista(raiz["cursos"], "$.cursos"))
    )
    aulas = tuple(
        _crear_aula(elemento, f"$.aulas[{indice}]")
        for indice, elemento in enumerate(_lista(raiz["aulas"], "$.aulas"))
    )
    grupos = tuple(
        _crear_grupo(elemento, f"$.grupos_laboratorio[{indice}]")
        for indice, elemento in enumerate(
            _lista(raiz.get("grupos_laboratorio", []), "$.grupos_laboratorio")
        )
    )
    sesiones_fijas = tuple(
        _crear_sesion_fija(elemento, f"$.sesiones_fijas[{indice}]")
        for indice, elemento in enumerate(
            _lista(raiz.get("sesiones_fijas", []), "$.sesiones_fijas")
        )
    )

    try:
        return DatosPlanificacion(
            docentes=docentes,
            cursos=cursos,
            aulas=aulas,
            grupos_laboratorio=grupos,
            sesiones_fijas=sesiones_fijas,
            configuracion=configuracion,
        )
    except ErrorModeloPlanificacion as error:
        raise ErrorEntradaPlanificacion(f"Datos de planificación inválidos: {error}") from error


def _crear_configuracion(valor: Any) -> ConfiguracionPlanificacion:
    ruta = "$.configuracion"
    objeto = _objeto(valor, ruta)
    campos = (
        "cursos_por_semestre",
        "cursos_con_laboratorio",
        "grupos_por_curso_laboratorio",
        "cantidad_aulas_laboratorio",
        "tamano_grupo_objetivo",
        "tolerancia_tamano_grupo",
        "max_horarios",
        "dias_activos_objetivo",
        "dias_habiles",
    )
    _claves(objeto, ruta, opcionales=campos)
    argumentos = dict(objeto)
    if "dias_habiles" in argumentos:
        argumentos["dias_habiles"] = tuple(
            _enum(DiaSemana, dia, f"{ruta}.dias_habiles[{indice}]")
            for indice, dia in enumerate(
                _lista(argumentos["dias_habiles"], f"{ruta}.dias_habiles")
            )
        )
    try:
        return ConfiguracionPlanificacion(**argumentos)
    except (ErrorModeloPlanificacion, TypeError) as error:
        raise ErrorEntradaPlanificacion(f"{ruta}: {error}") from error


def _crear_docente(valor: Any, ruta: str) -> Docente:
    objeto = _objeto(valor, ruta)
    _claves(objeto, ruta, requeridas=("id", "nombre", "disponibilidad"))
    franjas = tuple(
        _crear_franja(franja, f"{ruta}.disponibilidad[{indice}]")
        for indice, franja in enumerate(
            _lista(objeto["disponibilidad"], f"{ruta}.disponibilidad")
        )
    )
    try:
        return Docente(
            id=_texto(objeto["id"], f"{ruta}.id"),
            nombre=_texto(objeto["nombre"], f"{ruta}.nombre"),
            disponibilidad=franjas,
        )
    except ErrorModeloPlanificacion as error:
        raise ErrorEntradaPlanificacion(f"{ruta}: {error}") from error


def _crear_curso(valor: Any, ruta: str) -> Curso:
    objeto = _objeto(valor, ruta)
    _claves(
        objeto,
        ruta,
        requeridas=(
            "id",
            "nombre",
            "docente_id",
            "cohorte_id",
            "duracion_minutos",
        ),
        opcionales=("requiere_laboratorio", "duracion_laboratorio_minutos"),
    )
    try:
        return Curso(
            id=_texto(objeto["id"], f"{ruta}.id"),
            nombre=_texto(objeto["nombre"], f"{ruta}.nombre"),
            docente_id=_texto(objeto["docente_id"], f"{ruta}.docente_id"),
            cohorte_id=_texto(objeto["cohorte_id"], f"{ruta}.cohorte_id"),
            duracion_minutos=objeto["duracion_minutos"],
            requiere_laboratorio=objeto.get("requiere_laboratorio", False),
            duracion_laboratorio_minutos=objeto.get("duracion_laboratorio_minutos"),
        )
    except ErrorModeloPlanificacion as error:
        raise ErrorEntradaPlanificacion(f"{ruta}: {error}") from error


def _crear_grupo(valor: Any, ruta: str) -> GrupoLaboratorio:
    objeto = _objeto(valor, ruta)
    _claves(
        objeto,
        ruta,
        requeridas=("id", "curso_id", "cohorte_id", "cantidad_estudiantes"),
        opcionales=("subcohorte_id",),
    )
    try:
        return GrupoLaboratorio(
            id=_texto(objeto["id"], f"{ruta}.id"),
            curso_id=_texto(objeto["curso_id"], f"{ruta}.curso_id"),
            cohorte_id=_texto(objeto["cohorte_id"], f"{ruta}.cohorte_id"),
            cantidad_estudiantes=objeto["cantidad_estudiantes"],
            subcohorte_id=objeto.get("subcohorte_id"),
        )
    except ErrorModeloPlanificacion as error:
        raise ErrorEntradaPlanificacion(f"{ruta}: {error}") from error


def _crear_aula(valor: Any, ruta: str) -> Aula:
    objeto = _objeto(valor, ruta)
    _claves(
        objeto,
        ruta,
        requeridas=("id", "capacidad", "tipo"),
        opcionales=("tiene_computadoras", "tiene_proyector_integrado"),
    )
    tipo = _enum(TipoAula, objeto["tipo"], f"{ruta}.tipo")
    try:
        return Aula(
            id=_texto(objeto["id"], f"{ruta}.id"),
            capacidad=objeto["capacidad"],
            tipo=tipo,
            tiene_computadoras=objeto.get("tiene_computadoras", False),
            tiene_proyector_integrado=objeto.get("tiene_proyector_integrado", False),
        )
    except ErrorModeloPlanificacion as error:
        raise ErrorEntradaPlanificacion(f"{ruta}: {error}") from error


def _crear_sesion_fija(valor: Any, ruta: str) -> SesionFija:
    objeto = _objeto(valor, ruta)
    _claves(
        objeto,
        ruta,
        requeridas=("curso_id", "franja"),
        opcionales=("aula_id", "grupo_laboratorio_id"),
    )
    try:
        return SesionFija(
            curso_id=_texto(objeto["curso_id"], f"{ruta}.curso_id"),
            franja=_crear_franja(objeto["franja"], f"{ruta}.franja"),
            aula_id=_opcional_texto(objeto.get("aula_id"), f"{ruta}.aula_id"),
            grupo_laboratorio_id=_opcional_texto(
                objeto.get("grupo_laboratorio_id"),
                f"{ruta}.grupo_laboratorio_id",
            ),
        )
    except ErrorModeloPlanificacion as error:
        raise ErrorEntradaPlanificacion(f"{ruta}: {error}") from error


def _crear_franja(valor: Any, ruta: str) -> FranjaSemanal:
    objeto = _objeto(valor, ruta)
    _claves(objeto, ruta, requeridas=("dia", "hora_inicio", "hora_fin"))
    dia = _enum(DiaSemana, objeto["dia"], f"{ruta}.dia")
    try:
        return FranjaSemanal(
            dia=dia,
            hora_inicio=_texto(objeto["hora_inicio"], f"{ruta}.hora_inicio"),
            hora_fin=_texto(objeto["hora_fin"], f"{ruta}.hora_fin"),
        )
    except ErrorModeloPlanificacion as error:
        raise ErrorEntradaPlanificacion(f"{ruta}: {error}") from error


def _objeto(valor: Any, ruta: str) -> Mapping[str, Any]:
    if not isinstance(valor, dict):
        raise ErrorEntradaPlanificacion(f"{ruta} debe ser un objeto JSON.")
    return valor


def _lista(valor: Any, ruta: str) -> Tuple[Any, ...]:
    if not isinstance(valor, list):
        raise ErrorEntradaPlanificacion(f"{ruta} debe ser una lista JSON.")
    return tuple(valor)


def _claves(
    objeto: Mapping[str, Any],
    ruta: str,
    requeridas: Tuple[str, ...] = (),
    opcionales: Tuple[str, ...] = (),
) -> None:
    faltantes = [clave for clave in requeridas if clave not in objeto]
    desconocidas = sorted(set(objeto) - set(requeridas) - set(opcionales))
    if faltantes:
        raise ErrorEntradaPlanificacion(
            f"{ruta} no contiene los campos requeridos: {', '.join(faltantes)}."
        )
    if desconocidas:
        raise ErrorEntradaPlanificacion(
            f"{ruta} contiene campos desconocidos: {', '.join(desconocidas)}."
        )


def _texto(valor: Any, ruta: str) -> str:
    if not isinstance(valor, str):
        raise ErrorEntradaPlanificacion(f"{ruta} debe ser un texto.")
    return valor


def _opcional_texto(valor: Any, ruta: str) -> Optional[str]:
    if valor is not None and not isinstance(valor, str):
        raise ErrorEntradaPlanificacion(f"{ruta} debe ser un texto o null.")
    return valor


def _enum(tipo: Type[TipoEnum], valor: Any, ruta: str) -> TipoEnum:
    if not isinstance(valor, str):
        raise ErrorEntradaPlanificacion(f"{ruta} debe ser un texto válido.")
    try:
        return tipo(valor.strip().lower())
    except ValueError as error:
        opciones = ", ".join(miembro.value for miembro in tipo)
        raise ErrorEntradaPlanificacion(
            f"{ruta} debe ser uno de: {opciones}."
        ) from error
