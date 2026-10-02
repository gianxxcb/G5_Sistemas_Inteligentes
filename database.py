from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional
from config import FORMATO_HORA, PABELLON_A, PABELLON_B, PABELLON_C

DatosAula = Dict[str, Any]

def _crear_aula(identificador, pabellon, nombre, tipo, aforo_maximo, tiene_computadoras, proyector, x, y):
    return {
        "id": identificador, "pabellon": pabellon, "nombre": nombre, "tipo": tipo,
        "aforo_max": aforo_maximo, "tiene_computadoras": tiene_computadoras,
        "tiene_proyector_integrado": proyector, "coordenada_x": x, "coordenada_y": y, "reservas": [],
    }

_AULAS: Dict[str, DatosAula] = {}

# Carga de A101 a A107
for idx, i in enumerate(range(101, 108)):
    _AULAS[f"A{i}"] = _crear_aula(f"A{i}", PABELLON_A, f"Aula A{i}", "teoria", 30 + (idx * 5), False, True, 0, idx)

# Carga de B201 a B207 (B201 a B205 son Laboratorios equipados)
for idx, i in enumerate(range(201, 208)):
    es_lab = (i <= 205)
    _AULAS[f"B{i}"] = _crear_aula(
        f"B{i}", PABELLON_B, f"Laboratorio B{i}" if es_lab else f"Aula B{i}",
        "laboratorio" if es_lab else "teoria", 35 + (idx * 5), es_lab, True, 5, idx
    )

# Carga de C101 a C107
for idx, i in enumerate(range(101, 108)):
    _AULAS[f"C{i}"] = _crear_aula(f"C{i}", PABELLON_C, f"Aula C{i}", "teoria", 30 + (idx * 5), False, True, 10, idx)

def _convertir_hora_a_minutos(hora: str) -> int:
    h_str = hora.upper().strip().replace(".", "")
    if "PM" in h_str or "AM" in h_str:
        es_pm = "PM" in h_str
        h_limpia = h_str.replace("PM", "").replace("AM", "").strip()
        partes = h_limpia.split(":")
        h = int(partes[0])
        m = int(partes[1]) if len(partes) > 1 else 0
        if es_pm and h < 12: h += 12
        if not es_pm and h == 12: h = 0
        return h * 60 + m
    partes = h_str.split(":")
    return int(partes[0]) * 60 + (int(partes[1]) if len(partes) > 1 else 0)

def _horarios_se_superponen(inicio_1, fin_1, inicio_2, fin_2) -> bool:
    return _convertir_hora_a_minutos(inicio_1) < _convertir_hora_a_minutos(fin_2) and _convertir_hora_a_minutos(inicio_2) < _convertir_hora_a_minutos(fin_1)

def get_all_rooms() -> List[DatosAula]:
    return deepcopy(list(_AULAS.values()))

def get_room_by_id(room_id: str) -> Optional[DatosAula]:
    aula = _AULAS.get(room_id.upper())
    return deepcopy(aula) if aula is not None else None

def is_room_available(room_id: str, start_time: str, end_time: str) -> bool:
    aula = _AULAS.get(room_id.upper())
    if aula is None: return False
    for reserva in aula["reservas"]:
        if _horarios_se_superponen(start_time, end_time, reserva["horario_inicio"], reserva["horario_fin"]):
            return False
    return True

def get_available_rooms(start_time: str, end_time: str) -> List[DatosAula]:
    return [aula for aula in get_all_rooms() if is_room_available(aula["id"], start_time, end_time)]

def add_reservation(room_id: str, start_time: str, end_time: str, materia: str) -> bool:
    aula = _AULAS.get(room_id.upper())
    if aula is None or not is_room_available(room_id, start_time, end_time):
        return False
    aula["reservas"].append({"horario_inicio": start_time, "horario_fin": end_time, "materia": materia.strip()})
    return True
