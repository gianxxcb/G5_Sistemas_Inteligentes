"""Búsqueda A* de aulas alternas por distancia y ajuste de capacidad."""

from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass
from math import inf
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Tuple

from schedule_models import Aula, TipoAula


# Distancias demostrativas en metros. Deben sustituirse por mediciones del campus.
DISTANCIAS_PABELLONES_METROS: Dict[Tuple[str, str], float] = {
    ("A", "B"): 120.0,
    ("A", "C"): 250.0,
    ("B", "C"): 150.0,
}


@dataclass(frozen=True)
class ResultadoAStar:
    aula_id: str
    ruta: Tuple[str, ...]
    distancia_metros: float
    penalizacion_aforo: float
    costo_total: float


class AStarSearch:
    """Encuentra un aula factible minimizando reubicación y sobrecapacidad."""

    def __init__(
        self,
        distancias_pabellones: Optional[Mapping[Tuple[str, str], float]] = None,
        penalizacion_por_asiento: float = 5.0,
    ) -> None:
        if (
            isinstance(penalizacion_por_asiento, bool)
            or not isinstance(penalizacion_por_asiento, (int, float))
            or penalizacion_por_asiento < 0
        ):
            raise ValueError("penalizacion_por_asiento debe ser no negativa.")
        self.penalizacion_por_asiento = float(penalizacion_por_asiento)
        distancias = (
            DISTANCIAS_PABELLONES_METROS
            if distancias_pabellones is None
            else distancias_pabellones
        )
        self._distancias_directas = _validar_distancias(distancias)
        self._distancias_cortas = _calcular_distancias_cortas(
            self._distancias_directas
        )

    def buscar(
        self,
        aula_origen_id: str,
        aulas: Iterable[Any],
        aforo_solicitado: int,
        requiere_laboratorio: bool = False,
        requiere_computadoras: Optional[bool] = None,
        excluir_ids: Iterable[str] = (),
        disponibilidad: Optional[Callable[[str], bool]] = None,
        pabellones: Optional[Mapping[str, str]] = None,
    ) -> Optional[ResultadoAStar]:
        """Busca la alternativa factible de menor costo desde el aula primaria.

        Los nodos son aulas. El costo de una transición es la distancia mínima
        entre pabellones; el costo por aforo se aplica una sola vez al destino.
        """
        if not isinstance(aula_origen_id, str) or not aula_origen_id.strip():
            raise ValueError("aula_origen_id debe ser un texto no vacío.")
        if (
            isinstance(aforo_solicitado, bool)
            or not isinstance(aforo_solicitado, int)
            or aforo_solicitado <= 0
        ):
            raise ValueError("aforo_solicitado debe ser un entero positivo.")
        if not isinstance(requiere_laboratorio, bool):
            raise ValueError("requiere_laboratorio debe ser booleano.")
        if requiere_computadoras is not None and not isinstance(
            requiere_computadoras, bool
        ):
            raise ValueError("requiere_computadoras debe ser booleano o None.")

        origen_id = aula_origen_id.strip()
        pabellon_por_aula = dict(pabellones or {})
        nodos: Dict[str, _NodoAula] = {}
        for aula in aulas:
            nodo = _normalizar_aula(aula, pabellon_por_aula)
            if nodo.identificador in nodos:
                raise ValueError(f"Identificador de aula duplicado: {nodo.identificador}.")
            nodos[nodo.identificador] = nodo

        if origen_id not in nodos:
            nodo_origen = _NodoAula(
                identificador=origen_id,
                pabellon=pabellon_por_aula.get(origen_id)
                or _inferir_pabellon(origen_id),
                capacidad=aforo_solicitado,
                tipo="",
                tiene_computadoras=False,
            )
            nodos[origen_id] = nodo_origen
        else:
            nodo_origen = nodos[origen_id]

        excluidos = set(excluir_ids)
        destinos = {
            identificador
            for identificador, nodo in nodos.items()
            if identificador != origen_id
            and identificador not in excluidos
            and _es_compatible(
                nodo,
                aforo_solicitado,
                requiere_laboratorio,
                requiere_computadoras,
            )
            and (disponibilidad is None or disponibilidad(identificador))
        }
        if not destinos:
            return None

        nodos_por_pabellon: Dict[str, Tuple[str, ...]] = {}
        for identificador, nodo in nodos.items():
            if nodo.pabellon:
                nodos_por_pabellon.setdefault(nodo.pabellon, ())
                nodos_por_pabellon[nodo.pabellon] += (identificador,)

        secuencia = itertools.count()
        cola = [(0.0, next(secuencia), 0.0, origen_id, (origen_id,))]
        mejores_costos = {origen_id: 0.0}
        mejor_destino: Optional[ResultadoAStar] = None

        while cola:
            estimado, _, costo_recorrido, actual_id, ruta = heapq.heappop(cola)
            if mejor_destino is not None and estimado >= mejor_destino.costo_total:
                break
            if costo_recorrido > mejores_costos.get(actual_id, inf):
                continue

            actual = nodos[actual_id]
            if actual_id in destinos:
                penalizacion = (
                    max(0, actual.capacidad - aforo_solicitado)
                    * self.penalizacion_por_asiento
                )
                costo_total = costo_recorrido + penalizacion
                if mejor_destino is None or (
                    costo_total,
                    actual_id,
                ) < (mejor_destino.costo_total, mejor_destino.aula_id):
                    mejor_destino = ResultadoAStar(
                        aula_id=actual_id,
                        ruta=ruta,
                        distancia_metros=costo_recorrido,
                        penalizacion_aforo=penalizacion,
                        costo_total=costo_total,
                    )

            for vecino_id, vecino in nodos.items():
                if vecino_id == actual_id:
                    continue
                distancia = self._distancia_directa(
                    actual.pabellon,
                    vecino.pabellon,
                )
                if distancia is None:
                    continue
                nuevo_costo = costo_recorrido + distancia
                if nuevo_costo >= mejores_costos.get(vecino_id, inf):
                    continue
                mejores_costos[vecino_id] = nuevo_costo
                heuristica = self._heuristica(vecino.pabellon, destinos, nodos)
                heapq.heappush(
                    cola,
                    (
                        nuevo_costo + heuristica,
                        next(secuencia),
                        nuevo_costo,
                        vecino_id,
                        ruta + (vecino_id,),
                    ),
                )

        return mejor_destino

    def _distancia(
        self,
        pabellon_origen: Optional[str],
        pabellon_destino: Optional[str],
    ) -> Optional[float]:
        if not pabellon_origen or not pabellon_destino:
            return 0.0 if pabellon_origen == pabellon_destino else None
        if pabellon_origen == pabellon_destino:
            return 0.0
        return self._distancias_cortas.get(
            _par_pabellones(pabellon_origen, pabellon_destino)
        )

    def _distancia_directa(
        self,
        pabellon_origen: Optional[str],
        pabellon_destino: Optional[str],
    ) -> Optional[float]:
        if not pabellon_origen or not pabellon_destino:
            return 0.0 if pabellon_origen == pabellon_destino else None
        if pabellon_origen == pabellon_destino:
            return 0.0
        return self._distancias_directas.get(
            _par_pabellones(pabellon_origen, pabellon_destino)
        )

    def _heuristica(
        self,
        pabellon_actual: Optional[str],
        destinos: set[str],
        nodos: Mapping[str, _NodoAula],
    ) -> float:
        if not pabellon_actual:
            return 0.0
        distancias = [
            self._distancia(pabellon_actual, nodos[destino].pabellon)
            for destino in destinos
        ]
        conocidas = [distancia for distancia in distancias if distancia is not None]
        return min(conocidas, default=0.0)


@dataclass(frozen=True)
class _NodoAula:
    identificador: str
    pabellon: Optional[str]
    capacidad: int
    tipo: str
    tiene_computadoras: bool


def _normalizar_aula(
    aula: Any,
    pabellones: Mapping[str, str],
) -> _NodoAula:
    if isinstance(aula, Mapping):
        identificador = aula.get("id")
        pabellon = aula.get("pabellon")
        capacidad = aula.get("aforo_max", aula.get("capacidad"))
        tipo = aula.get("tipo")
        computadoras = aula.get("tiene_computadoras", False)
    elif isinstance(aula, Aula):
        identificador = aula.id
        pabellon = getattr(aula, "pabellon", None)
        capacidad = aula.capacidad
        tipo = aula.tipo.value if isinstance(aula.tipo, TipoAula) else aula.tipo
        computadoras = aula.tiene_computadoras
    else:
        raise TypeError("Cada aula debe ser un modelo Aula o un mapeo de aula.")

    if not isinstance(identificador, str) or not identificador.strip():
        raise ValueError("Cada aula debe incluir un id no vacío.")
    identificador = identificador.strip()
    pabellon = pabellones.get(identificador, pabellon)
    if pabellon is None:
        pabellon = _inferir_pabellon(identificador)
    if pabellon is not None and (
        not isinstance(pabellon, str) or not pabellon.strip()
    ):
        raise ValueError(f"El pabellón del aula {identificador} no es válido.")
    if isinstance(capacidad, bool) or not isinstance(capacidad, int) or capacidad <= 0:
        raise ValueError(f"La capacidad del aula {identificador} no es válida.")
    if not isinstance(tipo, (str, TipoAula)):
        raise ValueError(f"El tipo del aula {identificador} no es válido.")
    if not isinstance(computadoras, bool):
        raise ValueError(
            f"El campo tiene_computadoras del aula {identificador} debe ser booleano."
        )
    tipo_texto = tipo.value if isinstance(tipo, TipoAula) else tipo.strip().lower()
    return _NodoAula(
        identificador=identificador,
        pabellon=pabellon.strip().upper() if pabellon else None,
        capacidad=capacidad,
        tipo=tipo_texto,
        tiene_computadoras=computadoras,
    )


def _es_compatible(
    aula: _NodoAula,
    aforo: int,
    requiere_laboratorio: bool,
    requiere_computadoras: Optional[bool],
) -> bool:
    tipo_requerido = (
        TipoAula.LABORATORIO.value
        if requiere_laboratorio
        else TipoAula.TEORIA.value
    )
    if aula.capacidad < aforo or aula.tipo != tipo_requerido:
        return False
    if requiere_laboratorio and not aula.tiene_computadoras:
        return False
    return requiere_computadoras is None or (
        aula.tiene_computadoras == requiere_computadoras
    )


def _validar_distancias(
    distancias: Mapping[Tuple[str, str], float],
) -> Dict[Tuple[str, str], float]:
    normalizadas: Dict[Tuple[str, str], float] = {}
    for clave, distancia in distancias.items():
        if (
            not isinstance(clave, tuple)
            or len(clave) != 2
            or not all(isinstance(parte, str) and parte.strip() for parte in clave)
        ):
            raise ValueError("Cada distancia debe usar un par de pabellones válido.")
        if (
            isinstance(distancia, bool)
            or not isinstance(distancia, (int, float))
            or distancia < 0
        ):
            raise ValueError("Las distancias entre pabellones deben ser no negativas.")
        origen, destino = (parte.strip().upper() for parte in clave)
        if origen == destino:
            if distancia != 0:
                raise ValueError("La distancia de un pabellón a sí mismo debe ser cero.")
        else:
            normalizadas[(origen, destino)] = float(distancia)
            normalizadas[(destino, origen)] = float(distancia)
    return normalizadas


def _calcular_distancias_cortas(
    directas: Mapping[Tuple[str, str], float],
) -> Dict[Tuple[str, str], float]:
    pabellones = {pabellon for par in directas for pabellon in par}
    distancias = {
        (origen, destino): (0.0 if origen == destino else inf)
        for origen in pabellones
        for destino in pabellones
    }
    distancias.update(directas)
    for intermedio in pabellones:
        for origen in pabellones:
            for destino in pabellones:
                via_intermedio = (
                    distancias[(origen, intermedio)]
                    + distancias[(intermedio, destino)]
                )
                if via_intermedio < distancias[(origen, destino)]:
                    distancias[(origen, destino)] = via_intermedio
    return {
        par: distancia
        for par, distancia in distancias.items()
        if distancia != inf
    }


def _par_pabellones(origen: str, destino: str) -> Tuple[str, str]:
    return origen.strip().upper(), destino.strip().upper()


def _inferir_pabellon(identificador: str) -> Optional[str]:
    prefijo = identificador[:1].upper()
    return prefijo if prefijo.isalpha() else None
