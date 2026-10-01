"""Agente Monitor de solicitudes de reserva de aulas.

Recibe una solicitud, valida sus campos, normaliza los valores y determina si
la reserva pertenece a una franja pico o regular. No asigna aulas ni aplica
reglas del AgenteExperto.
"""

from datetime import datetime
from typing import Any, Dict, List, Union

from config import (
    AFORO_MAXIMO_SOLICITUD,
    AFORO_MINIMO_SOLICITUD,
    FORMATO_HORA,
    FRANJAS_PICO,
    FRANJAS_REGULARES,
)

RespuestaMonitor = Dict[str, Union[bool, List[str], Dict[str, Any]]]


class AgenteMonitor:
    """Valida y normaliza solicitudes antes de enviarlas al AgenteExperto."""

    CAMPOS_OBLIGATORIOS = (
        "materia",
        "aforo",
        "requiere_laboratorio",
        "horario_inicio",
        "horario_fin",
        "facultad_origen",
    )

    def procesar_solicitud(self, solicitud: dict) -> dict:
        """Procesa una solicitud y devuelve hechos limpios o errores estructurados."""
        errores = self._validar_solicitud(solicitud)
        if errores:
            return {"valido": False, "errores": errores}

        horario_inicio = self._normalizar_hora(solicitud["horario_inicio"])
        horario_fin = self._normalizar_hora(solicitud["horario_fin"])

        hechos = {
            "materia": solicitud["materia"].strip(),
            "aforo": int(solicitud["aforo"]),
            "requiere_laboratorio": solicitud["requiere_laboratorio"],
            "horario_inicio": horario_inicio,
            "horario_fin": horario_fin,
            "facultad_origen": solicitud["facultad_origen"].strip(),
            "franja": self._determinar_franja(horario_inicio, horario_fin),
        }
        return {"valido": True, "hechos": hechos}

    def _validar_solicitud(self, solicitud: dict) -> List[str]:
        """Valida presencia, tipos básicos y coherencia de los campos de entrada."""
        errores: List[str] = []
        if not isinstance(solicitud, dict):
            return ["La solicitud debe ser un objeto JSON."]

        for campo in self.CAMPOS_OBLIGATORIOS:
            if campo not in solicitud:
                errores.append(f"Falta el campo obligatorio: {campo}.")

        if errores:
            return errores

        if not isinstance(solicitud["materia"], str) or not solicitud["materia"].strip():
            errores.append("materia debe ser un texto no vacío.")

        aforo = solicitud["aforo"]
        if isinstance(aforo, bool) or not isinstance(aforo, int):
            errores.append("aforo debe ser un número entero.")
        elif not AFORO_MINIMO_SOLICITUD <= aforo <= AFORO_MAXIMO_SOLICITUD:
            errores.append(
                f"aforo debe estar entre {AFORO_MINIMO_SOLICITUD} y {AFORO_MAXIMO_SOLICITUD}."
            )

        if not isinstance(solicitud["requiere_laboratorio"], bool):
            errores.append("requiere_laboratorio debe ser true o false.")

        if not isinstance(solicitud["facultad_origen"], str) or not solicitud["facultad_origen"].strip():
            errores.append("facultad_origen debe ser un texto no vacío.")

        inicio_valido = self._hora_valida(solicitud["horario_inicio"])
        fin_valido = self._hora_valida(solicitud["horario_fin"])
        if not inicio_valido:
            errores.append("horario_inicio debe tener formato HH:MM válido.")
        if not fin_valido:
            errores.append("horario_fin debe tener formato HH:MM válido.")

        if inicio_valido and fin_valido:
            inicio = self._convertir_hora_a_minutos(solicitud["horario_inicio"])
            fin = self._convertir_hora_a_minutos(solicitud["horario_fin"])
            if inicio >= fin:
                errores.append("horario_inicio debe ser anterior a horario_fin.")

        return errores

    @staticmethod
    def _hora_valida(hora: Any) -> bool:
        """Comprueba que un valor sea una hora válida en formato HH:MM."""
        if not isinstance(hora, str):
            return False
        try:
            datetime.strptime(hora.strip(), FORMATO_HORA)
        except ValueError:
            return False
        return True

    @staticmethod
    def _normalizar_hora(hora: str) -> str:
        """Devuelve una hora en el formato de dos dígitos HH:MM."""
        return datetime.strptime(hora.strip(), FORMATO_HORA).strftime(FORMATO_HORA)

    @staticmethod
    def _convertir_hora_a_minutos(hora: str) -> int:
        """Convierte una hora HH:MM a minutos desde medianoche."""
        hora_normalizada = datetime.strptime(hora.strip(), FORMATO_HORA)
        return hora_normalizada.hour * 60 + hora_normalizada.minute

    def _determinar_franja(self, horario_inicio: str, horario_fin: str) -> str:
        """Clasifica como pico si se cruza con una franja pico; en otro caso regular."""
        inicio = self._convertir_hora_a_minutos(horario_inicio)
        fin = self._convertir_hora_a_minutos(horario_fin)

        for inicio_pico, fin_pico in FRANJAS_PICO:
            inicio_pico_minutos = self._convertir_hora_a_minutos(inicio_pico)
            fin_pico_minutos = self._convertir_hora_a_minutos(fin_pico)
            if inicio < fin_pico_minutos and inicio_pico_minutos < fin:
                return "pico"

        # Las franjas regulares se mantienen configuradas para poder ampliarlas.
        # Cualquier horario válido no pico se clasifica como regular.
        _ = FRANJAS_REGULARES
        return "regular"


if __name__ == "__main__":
    agente_monitor = AgenteMonitor()
    solicitud_prueba = {
        "materia": "Taller de Programación",
        "aforo": 35,
        "requiere_laboratorio": True,
        "horario_inicio": "09:00",
        "horario_fin": "11:00",
        "facultad_origen": "Ingeniería",
    }
    print(agente_monitor.procesar_solicitud(solicitud_prueba))
