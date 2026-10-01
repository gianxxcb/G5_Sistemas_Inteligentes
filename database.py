"""Base de conocimiento en memoria para aulas y reservas.

Este módulo solo almacena y consulta información. No decide prioridades ni
aplica reglas del sistema experto.
"""

from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional

from config import FORMATO_HORA, PABELLON_A, PABELLON_B, PABELLON_C

DatosAula = Dict[str, Any]


def _crear_aula(
    identificador: str,
    pabellon: str,
    nombre: str,
    tipo: str,
    aforo_maximo: int,
    tiene_computadoras: bool,
    tiene_proyector_integrado: bool,
    coordenada_x: int,
    coordenada_y: int,
) -> DatosAula:
    """Construye una estructura de aula uniforme para la base en memoria."""
    return {
        "id": identificador,
        "pabellon": pabellon,
        "nombre": nombre,
        "tipo": tipo,
        "aforo_max": aforo_maximo,
        "tiene_computadoras": tiene_computadoras,
        "tiene_proyector_integrado": tiene_proyector_integrado,
        "coordenada_x": coordenada_x,
        "coordenada_y": coordenada_y,
        "reservas": [],
    }


# Base de conocimiento inicial. Las reservas pueden añadirse mediante
# add_reservation para probar conflictos de horario.
_AULAS: Dict[str, DatosAula] = {
    "A101": _crear_aula(
        "A101", PABELLON_A, "Aula 101", "teoria", 45, False, True, 0, 10
    ),
    "A102": _crear_aula(
        "A102", PABELLON_A, "Aula 102", "teoria", 25, False, False, 0, 14
    ),
    "B201": _crear_aula(
        "B201", PABELLON_B, "Laboratorio 201", "laboratorio", 40, True, True, 5, 12
    ),
    "B202": _crear_aula(
        "B202", PABELLON_B, "Laboratorio 202", "laboratorio", 25, True, False, 5, 16
    ),
    "B203": _crear_aula(
        "B203", PABELLON_B, "Laboratorio 203", "laboratorio", 35, True, True, 7, 12
    ),
    "C101": _crear_aula(
        "C101", PABELLON_C, "Aula 101", "teoria", 60, False, True, 11, 8
    ),
    "C102": _crear_aula(
        "C102", PABELLON_C, "Aula 102", "teoria", 35, False, False, 11, 12
    ),
}


def _convertir_hora_a_minutos(hora: str) -> int:
    """Convierte una hora HH:MM a minutos desde medianoche."""
    return datetime.strptime(hora, FORMATO_HORA).hour * 60 + datetime.strptime(
        hora, FORMATO_HORA
    ).minute


def _horarios_se_superponen(
    inicio_1: str, fin_1: str, inicio_2: str, fin_2: str
) -> bool:
    """Indica si dos intervalos horarios se superponen."""
    inicio_1_minutos = _convertir_hora_a_minutos(inicio_1)
    fin_1_minutos = _convertir_hora_a_minutos(fin_1)
    inicio_2_minutos = _convertir_hora_a_minutos(inicio_2)
    fin_2_minutos = _convertir_hora_a_minutos(fin_2)
    return inicio_1_minutos < fin_2_minutos and inicio_2_minutos < fin_1_minutos


def get_all_rooms() -> List[DatosAula]:
    """Devuelve copias de todas las aulas para evitar mutaciones accidentales."""
    return deepcopy(list(_AULAS.values()))


def get_room_by_id(room_id: str) -> Optional[DatosAula]:
    """Busca un aula por identificador y devuelve una copia, o None si no existe."""
    aula = _AULAS.get(room_id.upper())
    return deepcopy(aula) if aula is not None else None


def is_room_available(room_id: str, start_time: str, end_time: str) -> bool:
    """Verifica que un aula exista y no tenga reservas que se superpongan."""
    aula = _AULAS.get(room_id.upper())
    if aula is None:
        return False

    for reserva in aula["reservas"]:
        if _horarios_se_superponen(
            start_time, end_time, reserva["horario_inicio"], reserva["horario_fin"]
        ):
            return False
    return True


def get_available_rooms(start_time: str, end_time: str) -> List[DatosAula]:
    """Devuelve todas las aulas libres para el intervalo solicitado."""
    return [
        aula
        for aula in get_all_rooms()
        if is_room_available(aula["id"], start_time, end_time)
    ]


def add_reservation(room_id: str, start_time: str, end_time: str, materia: str) -> bool:
    """Registra una reserva si el aula existe y está libre; devuelve si tuvo éxito."""
    aula = _AULAS.get(room_id.upper())
    if aula is None or not is_room_available(room_id, start_time, end_time):
        return False

    aula["reservas"].append(
        {
            "horario_inicio": start_time,
            "horario_fin": end_time,
            "materia": materia.strip(),
        }
    )
    return True


def get_room_distance(room_id_1: str, room_id_2: str) -> Optional[float]:
    """Calcula distancia euclídea entre dos aulas, útil para el módulo A*."""
    aula_1 = _AULAS.get(room_id_1.upper())
    aula_2 = _AULAS.get(room_id_2.upper())
    if aula_1 is None or aula_2 is None:
        return None

    diferencia_x = aula_1["coordenada_x"] - aula_2["coordenada_x"]
    diferencia_y = aula_1["coordenada_y"] - aula_2["coordenada_y"]
    return (diferencia_x**2 + diferencia_y**2) ** 0.5


if __name__ == "__main__":
    print("Aulas disponibles entre 09:00 y 11:00:")
    for aula in get_available_rooms("09:00", "11:00"):
        print(f"- {aula['id']}: {aula['nombre']}")
