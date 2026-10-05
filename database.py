from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4
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

def _fecha_coincide(fecha_reserva, fecha_consulta) -> bool:
    return (
        fecha_reserva is None
        or fecha_consulta is None
        or str(fecha_reserva) == str(fecha_consulta)
    )


def is_room_available(
    room_id: str,
    start_time: str,
    end_time: str,
    fecha=None,
    exclude_reservation_id: Optional[str] = None,
) -> bool:
    aula = _AULAS.get(room_id.upper())
    if aula is None: return False
    for reserva in aula["reservas"]:
        if reserva.get("id") == exclude_reservation_id:
            continue
        if not _fecha_coincide(reserva.get("fecha"), fecha):
            continue
        if _horarios_se_superponen(start_time, end_time, reserva["horario_inicio"], reserva["horario_fin"]):
            return False
    return True


def get_available_rooms(
    start_time: str,
    end_time: str,
    fecha=None,
    exclude_reservation_id: Optional[str] = None,
    aforo_minimo: int = 0,
    requiere_laboratorio: Optional[bool] = None,
) -> List[DatosAula]:
    aulas = [
        aula for aula in get_all_rooms()
        if aula["aforo_max"] >= aforo_minimo
        and (
            requiere_laboratorio is None
            or (aula["tipo"] == "laboratorio" and aula["tiene_computadoras"])
            if requiere_laboratorio
            else requiere_laboratorio is None or aula["tipo"] == "teoria"
        )
        and is_room_available(
            aula["id"], start_time, end_time, fecha, exclude_reservation_id
        )
    ]
    return sorted(aulas, key=lambda aula: (aula["aforo_max"], aula["id"]))


def add_reservation(
    room_id: str,
    start_time: str,
    end_time: str,
    materia: str,
    fecha=None,
    correo_docente: str = "",
    aforo: int = 0,
    facultad: str = "",
    requiere_laboratorio: bool = False,
) -> bool:
    aula = _AULAS.get(room_id.upper())
    if aula is None or not is_room_available(room_id, start_time, end_time, fecha):
        return False
    aula["reservas"].append({
        "id": uuid4().hex,
        "fecha": str(fecha) if fecha else None,
        "horario_inicio": start_time,
        "horario_fin": end_time,
        "materia": materia.strip(),
        "correo_docente": correo_docente.strip().lower(),
        "aforo": int(aforo or 0),
        "facultad": facultad.strip(),
        "requiere_laboratorio": bool(requiere_laboratorio),
        "estado": "Confirmada",
    })
    return True


def get_reservations_by_email(correo_docente: str) -> List[Dict[str, Any]]:
    correo = correo_docente.strip().lower()
    if not correo:
        return []
    reservas = []
    for aula in _AULAS.values():
        for reserva in aula["reservas"]:
            if reserva.get("correo_docente", "").strip().lower() == correo:
                reservas.append({**deepcopy(reserva), "aula": aula["id"]})
    return sorted(
        reservas,
        key=lambda reserva: (
            reserva.get("fecha") or "",
            reserva.get("horario_inicio", ""),
        ),
    )


def update_reservation(
    reservation_id: str,
    room_id: str,
    start_time: str,
    end_time: str,
    fecha,
) -> bool:
    aula_destino = _AULAS.get(room_id.upper())
    if aula_destino is None:
        return False

    reserva_actual = None
    aula_actual = None
    for aula in _AULAS.values():
        for reserva in aula["reservas"]:
            if reserva.get("id") == reservation_id:
                reserva_actual = reserva
                aula_actual = aula
                break
        if reserva_actual is not None:
            break

    if reserva_actual is None or aula_actual is None:
        return False
    if not is_room_available(
        room_id, start_time, end_time, fecha, exclude_reservation_id=reservation_id
    ):
        return False

    actualizada = {
        **reserva_actual,
        "fecha": str(fecha) if fecha else None,
        "horario_inicio": start_time,
        "horario_fin": end_time,
        "estado": "Confirmada",
    }
    aula_actual["reservas"].remove(reserva_actual)
    aula_destino["reservas"].append(actualizada)
    return True
