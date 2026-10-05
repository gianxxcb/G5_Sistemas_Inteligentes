"""
agent_expert.py
================
Proyecto Universitario:
"Sistema Inteligente para la Gestión y Asignación de Aulas y Horarios Académicos"

Módulo: AgenteExperto
Responsabilidad: Evaluar hechos normalizados por AgenteMonitor, consultar database.py
y aplicar reglas de negocio deterministas para la toma de decisiones de asignación de aulas.

Autor: JUAN JOSE JORGE PUENTE
"""

import logging
from typing import Dict, Any, Iterable, List, Optional, Tuple

from schedule_models import DatosPlanificacion, SesionProgramada
from schedule_optimizer import GeneradorHorarios, ResultadoGeneracion
from schedule_validator import ResultadoValidacionHorario, ValidadorHorario
from search_a_star import AStarSearch, ResultadoAStar

# Configuración de logger para trazabilidad del motor de inferencia
logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger("AgenteExperto")

# ==============================================================================
# IMPORTACIÓN DE LA BASE DE DATOS
# ==============================================================================
# Se consumen exclusivamente las funciones públicas expuestas por database.py.
# Los nombres se mantienen en inglés porque forman parte del contrato público
# definido para ese módulo.
try:
    from database import (
        get_all_rooms,
        get_room_by_id,
        is_room_available,
    )
except ImportError:
    # Fallback/Mock para ejecución de pruebas aisladas si database.py aún no está disponible
    logger.warning("Módulo 'database.py' no detectado. Se utilizará mock interno de respaldo para pruebas unitarias.")
    
    MOCK_AULAS = {
        "B201": {"id": "B201", "aforo_max": 40, "tipo": "laboratorio", "tiene_computadoras": True, "tiene_proyector_integrado": True},
        "B101": {"id": "B101", "aforo_max": 30, "tipo": "laboratorio", "tiene_computadoras": True, "tiene_proyector_integrado": True},
        "A101": {"id": "A101", "aforo_max": 35, "tipo": "teoria", "tiene_computadoras": False, "tiene_proyector_integrado": True},
        "A102": {"id": "A102", "aforo_max": 25, "tipo": "teoria", "tiene_computadoras": False, "tiene_proyector_integrado": False},
    }

    def get_room_by_id(aula_id: str) -> Optional[Dict[str, Any]]:
        return MOCK_AULAS.get(aula_id)

    def get_all_rooms() -> List[Dict[str, Any]]:
        return list(MOCK_AULAS.values())

    def is_room_available(room_id: str, start_time: str, end_time: str, fecha=None, exclude_reservation_id=None) -> bool:
        """Mock de disponibilidad para pruebas aisladas."""
        return True


class AgenteExperto:
    """
    Motor de Inferencia Determinista para la gestión de asignación de aulas.
    """

    # Identificadores unívocos de Reglas de Negocio
    REGLA_LAB_AFORO_PICO = "LAB_AFORO_PICO"
    REGLA_LAB_ESTANDAR = "LAB_ESTANDAR"
    REGLA_AULA_TEORIA = "AULA_TEORIA_ESTANDAR"
    REGLA_RECHAZO_AFORO = "RECHAZO_CAPACIDAD_INSUFICIENTE"
    REGLA_RECHAZO_TIPO = "RECHAZO_INCOMPATIBILIDAD_TIPO"

    def __init__(self):
        self._validador_horario = ValidadorHorario()
        self._generador_horarios = GeneradorHorarios()
        self._busqueda_a_star = AStarSearch()
        logger.info("AgenteExperto inicializado correctamente.")

    def validar_horario(
        self,
        datos: DatosPlanificacion,
        sesiones: Iterable[SesionProgramada],
    ) -> ResultadoValidacionHorario:
        """Valida restricciones obligatorias de un horario semanal candidato."""
        return self._validador_horario.validar(datos, sesiones)

    def generar_horarios(self, datos: DatosPlanificacion) -> ResultadoGeneracion:
        """Genera y ordena alternativas de horario semanal."""
        return self._generador_horarios.generar(datos)

    def evaluar(self, hechos: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evalúa los hechos recibidos y determina la asignación del aula o rechazo de la solicitud.

        Args:
            hechos (dict): Estructura de hechos normalizados enviada por AgenteMonitor.

        Returns:
            dict: Respuesta JSON-compatible con la decisión del Agente Experto.
        """
        aforo_solicitado = hechos.get("aforo", 0)
        requiere_lab = hechos.get("requiere_laboratorio", False)
        franja = hechos.get("franja", "normal")
        # Estos nombres coinciden exactamente con los hechos entregados por
        # AgenteMonitor.procesar_solicitud.
        hora_inicio = hechos.get("horario_inicio", "")
        hora_fin = hechos.get("horario_fin", "")
        fecha = hechos.get("fecha")

        # ----------------------------------------------------------------------
        # 1. PASO 1: Validación Física y de Capacidad en Base de Datos
        # ----------------------------------------------------------------------
        todas_las_aulas = get_all_rooms()
        
        # Filtrar por tipo. Un laboratorio debe ser de tipo laboratorio y
        # tener computadoras; una solicitud teórica requiere aula de teoría.
        aulas_compatibles_tipo = [
            aula for aula in todas_las_aulas
            if (
                aula.get("tipo") == "laboratorio" and aula.get("tiene_computadoras", False)
                if requiere_lab
                else aula.get("tipo") == "teoria"
            )
        ]

        if not aulas_compatibles_tipo:
            return self._generar_respuesta_rechazo(
                regla=self.REGLA_RECHAZO_TIPO,
                motivo=f"No existen aulas de tipo {'laboratorio' if requiere_lab else 'teoría'} en la infraestructura."
            )

        # Filtrar si existe AL MENOS un aula compatible en la infraestructura que soporte el aforo
        aulas_capacidad_suficiente = [
            aula for aula in aulas_compatibles_tipo
            if aula.get("aforo_max", 0) >= aforo_solicitado
        ]

        if not aulas_capacidad_suficiente:
            return self._generar_respuesta_rechazo(
                regla=self.REGLA_RECHAZO_AFORO,
                motivo=f"No existe ningún {'laboratorio' if requiere_lab else 'aula'} con aforo suficiente para {aforo_solicitado} alumnos."
            )

        # ----------------------------------------------------------------------
        # 2. PASO 2: Inferencia de Reglas Deterministas
        # ----------------------------------------------------------------------
        regla_aplicada, aula_objetivo_id = self._inferir_regla_y_objetivo(
            requiere_lab=requiere_lab,
            aforo=aforo_solicitado,
            franja=franja
        )

        # ----------------------------------------------------------------------
        # 3. PASO 3: Validación del Aula Objetivo y Disponibilidad Horaria
        # ----------------------------------------------------------------------
        info_aula = get_room_by_id(aula_objetivo_id)

        # Si el aula dictaminada por la regla no cubre el aforo (pero sí existen otras en el sistema),
        # se activa la bandera para que el Integrante 3 aplique A*
        if not info_aula or info_aula.get("aforo_max", 0) < aforo_solicitado:
            requiere_alternativa = True
            disponible = False
        else:
            # Consultar disponibilidad usando los horarios normalizados por
            # AgenteMonitor y la función pública de database.py.
            disponible = is_room_available(
                room_id=aula_objetivo_id,
                start_time=hora_inicio,
                end_time=hora_fin,
                fecha=fecha,
            )
            requiere_alternativa = not disponible

        alternativa = None
        if requiere_alternativa:
            alternativa = self.buscar_aula_alternativa(
                aula_objetivo_id=aula_objetivo_id,
                aforo_solicitado=aforo_solicitado,
                requiere_laboratorio=requiere_lab,
                horario_inicio=hora_inicio,
                horario_fin=hora_fin,
                fecha=fecha,
            )

        # ----------------------------------------------------------------------
        # 4. PASO 4: Evaluación de Restricciones Secundarias
        # ----------------------------------------------------------------------
        aula_asignada = (
            get_room_by_id(alternativa.aula_id)
            if alternativa is not None
            else (info_aula if disponible else None)
        )
        restricciones = self._evaluar_restricciones(aula_asignada)

        # ----------------------------------------------------------------------
        # 5. PASO 5: Generación del Dictamen Final
        # ----------------------------------------------------------------------
        if requiere_alternativa:
            if not disponible and (info_aula and info_aula.get("aforo_max", 0) >= aforo_solicitado):
                motivo = "El aula objetivo cumple la regla, pero está ocupada en el horario solicitado."
            else:
                motivo = "El aula asignada por la regla no cumple los requisitos físicos completos para la solicitud."
        else:
            motivo = f"Solicitud aprobada y asignada exitosamente al aula objetivo {aula_objetivo_id}."
        if alternativa is not None:
            motivo += (
                f" Se recomienda el aula alterna {alternativa.aula_id} "
                f"(costo de reubicación: {alternativa.costo_total:.2f})."
            )
        elif requiere_alternativa:
            motivo += " No se encontró un aula alterna factible."

        return {
            "aprobado": True,
            "aula_objetivo": aula_objetivo_id,
            "aula_asignada": (
                alternativa.aula_id
                if alternativa is not None
                else aula_objetivo_id if disponible else None
            ),
            "requiere_alternativa": requiere_alternativa,
            "alternativa_encontrada": alternativa is not None,
            "aula_alternativa": alternativa.aula_id if alternativa else None,
            "costo_reubicacion": alternativa.costo_total if alternativa else None,
            "distancia_reubicacion_metros": (
                alternativa.distancia_metros if alternativa else None
            ),
            "penalizacion_aforo": (
                alternativa.penalizacion_aforo if alternativa else None
            ),
            "ruta_reubicacion": list(alternativa.ruta) if alternativa else [],
            "regla_aplicada": regla_aplicada,
            "restricciones": restricciones,
            "motivo": motivo
        }

    def buscar_aula_alternativa(
        self,
        aula_objetivo_id: str,
        aforo_solicitado: int,
        requiere_laboratorio: bool,
        horario_inicio: str,
        horario_fin: str,
        fecha=None,
    ) -> Optional[ResultadoAStar]:
        """Busca la alternativa factible de menor costo mediante A*."""
        return self._busqueda_a_star.buscar(
            aula_origen_id=aula_objetivo_id,
            aulas=get_all_rooms(),
            aforo_solicitado=aforo_solicitado,
            requiere_laboratorio=requiere_laboratorio,
            disponibilidad=lambda aula_id: is_room_available(
                room_id=aula_id,
                start_time=horario_inicio,
                end_time=horario_fin,
                fecha=fecha,
            ),
            excluir_ids=(aula_objetivo_id,),
        )

    # ==========================================================================
    # MÉTODOS PRIVADOS DEL MOTOR DE INFERENCIA DE REGLAS
    # ==========================================================================

    def _inferir_regla_y_objetivo(self, requiere_lab: bool, aforo: int, franja: str) -> Tuple[str, str]:
        """Aplica la jerarquía de reglas de negocio para determinar el aula objetivo."""
        
        # Regla Principal
        if self._regla_lab_aforo_pico(requiere_lab, aforo, franja):
            return self.REGLA_LAB_AFORO_PICO, "B201"

        # Regla Secundaria para Laboratorios
        if requiere_lab:
            return self.REGLA_LAB_ESTANDAR, "B101"

        # Regla Secundaria para Aulas Teóricas
        return self.REGLA_AULA_TEORIA, "A101"

    def _regla_lab_aforo_pico(self, requiere_lab: bool, aforo: int, franja: str) -> bool:
        """
        REGLA PRINCIPAL:
        SI requiere_laboratorio == True Y aforo > 30 Y franja == "pico"
        ENTONCES aula_objetivo = "B201"
        """
        return requiere_lab is True and aforo > 30 and franja == "pico"

    def _evaluar_restricciones(self, info_aula: Optional[Dict[str, Any]]) -> List[str]:
        """Evalúa si se debe bloquear la asignación de proyector adicional."""
        restricciones = []
        if info_aula and info_aula.get("tiene_proyector_integrado", False):
            restricciones.append("proyector_adicional_bloqueado")
        return restricciones

    def _generar_respuesta_rechazo(self, regla: str, motivo: str) -> Dict[str, Any]:
        """Estructura de respuesta estandarizada cuando la solicitud no es ejecutable."""
        return {
            "aprobado": False,
            "aula_objetivo": None,
            "aula_asignada": None,
            "requiere_alternativa": False,
            "alternativa_encontrada": False,
            "aula_alternativa": None,
            "costo_reubicacion": None,
            "distancia_reubicacion_metros": None,
            "penalizacion_aforo": None,
            "ruta_reubicacion": [],
            "regla_aplicada": regla,
            "restricciones": [],
            "motivo": motivo
        }


# ==============================================================================
# SUITE DE PRUEBAS UNITARIAS DE DEMOSTRACIÓN
# ==============================================================================
if __name__ == "__main__":
    import json

    print("=" * 70)
    print("EJECUTANDO CASOS DE PRUEBA DEL AGENTE EXPERTO")
    print("=" * 70)

    experto = AgenteExperto()

    # Caso 1: 38 alumnos + laboratorio + hora pico (09:00-11:00)
    # Resultado esperado: B201, LAB_AFORO_PICO
    caso_1 = {
        "aforo": 38,
        "requiere_laboratorio": True,
        "franja": "pico",
        "dia": "Lunes",
        "hora_inicio": "09:00",
        "hora_fin": "11:00"
    }
    print("\n--- CASO 1: Laboratorio Alta Demanda en hora pico ---")
    res_1 = experto.evaluar(caso_1)
    print(json.dumps(res_1, indent=2, ensure_ascii=False))

    # Caso 2: 20 alumnos + no laboratorio + hora normal (14:00-16:00)
    # Resultado esperado: No activar regla de laboratorio, asignar aula de teoría (A101)
    caso_2 = {
        "aforo": 20,
        "requiere_laboratorio": False,
        "franja": "normal",
        "dia": "Martes",
        "hora_inicio": "14:00",
        "hora_fin": "16:00"
    }
    print("\n--- CASO 2: Solicitud Teórica Estándar ---")
    res_2 = experto.evaluar(caso_2)
    print(json.dumps(res_2, indent=2, ensure_ascii=False))

    # Caso 3: 38 alumnos + laboratorio + hora pico + B201 ocupado
    # Se fuerza mock para ocupar B201
    def aula_ocupada(room_id, start_time, end_time):
        if room_id == "B201":
            return False
        return True
    
    # Inyectar mock de ocupación temporalmente
    import sys
    current_module = sys.modules[__name__]
    setattr(current_module, "is_room_available", aula_ocupada)

    caso_3 = {
        "aforo": 38,
        "requiere_laboratorio": True,
        "franja": "pico",
        "dia": "Lunes",
        "hora_inicio": "09:00",
        "hora_fin": "11:00"
    }
    print("\n--- CASO 3: Laboratorio Pico con Aula Objetivo Ocupada ---")
    res_3 = experto.evaluar(caso_3)
    print(json.dumps(res_3, indent=2, ensure_ascii=False))

    # Caso 4: 45 alumnos + laboratorio + hora pico (Supera aforo máximo de todo laboratorio)
    # Resultado esperado: Rechazo (aprobado: false)
    caso_4 = {
        "aforo": 45,
        "requiere_laboratorio": True,
        "franja": "pico",
        "dia": "Miércoles",
        "hora_inicio": "10:00",
        "hora_fin": "12:00"
    }
    print("\n--- CASO 4: Exceso de Aforo sobre Infraestructura ---")
    res_4 = experto.evaluar(caso_4)
    print(json.dumps(res_4, indent=2, ensure_ascii=False))
