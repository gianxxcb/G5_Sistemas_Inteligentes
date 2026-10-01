"""Configuración central del Sistema Inteligente de Asignación de Aulas.

Este módulo reúne parámetros de negocio y evita valores mágicos en los demás
componentes. No contiene lógica de decisión ni datos de reservas.
"""

from typing import Final, Tuple

# Formato de hora esperado: HH:MM en reloj de 24 horas.
FORMATO_HORA: Final[str] = "%H:%M"

# Una franja se representa como (hora_inicio_inclusiva, hora_fin_exclusiva).
# Por ejemplo, una reserva de 09:00 a 11:00 pertenece a la franja pico.
FRANJAS_PICO: Final[Tuple[Tuple[str, str], ...]] = (
    ("09:00", "11:00"),
)

FRANJAS_REGULARES: Final[Tuple[Tuple[str, str], ...]] = (
    ("07:00", "09:00"),
    ("11:00", "18:00"),
    ("18:00", "22:00"),
)

# Límites académicos y de infraestructura.
AFORO_LABORATORIO_PRIORITARIO: Final[int] = 30
AFORO_MINIMO_SOLICITUD: Final[int] = 1
AFORO_MAXIMO_SOLICITUD: Final[int] = 200

# Identificadores de pabellones disponibles en el entorno simulado.
PABELLON_A: Final[str] = "A"
PABELLON_B: Final[str] = "B"
PABELLON_C: Final[str] = "C"
PABELLONES: Final[Tuple[str, ...]] = (
    PABELLON_A,
    PABELLON_B,
    PABELLON_C,
)

# Tipos de aula admitidos por la base de conocimiento.
TIPO_AULA_TEORIA: Final[str] = "teoria"
TIPO_AULA_LABORATORIO: Final[str] = "laboratorio"

# Aula utilizada como referencia por la regla prioritaria del AgenteExperto.
AULA_PRIORITARIA: Final[str] = "B201"

# Coordenadas de referencia de facultades para módulos que calculen rutas.
COORDENADAS_FACULTADES: Final[dict[str, tuple[int, int]]] = {
    "ingenieria": (0, 0),
    "ciencias": (4, 4),
    "humanidades": (10, 2),
}
