# --- MÓDULO INTERFAZ SIAH-UNT ---
import sys
from copy import deepcopy
from pathlib import Path
import ipywidgets as widgets
from IPython.display import display, clear_output
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import requests
from datetime import date, datetime
import json
import base64
import html
import uuid

carpeta_proyecto = Path.cwd() / "G5_Sistemas_Inteligentes"
if carpeta_proyecto.exists() and str(carpeta_proyecto) not in sys.path:
    sys.path.append(str(carpeta_proyecto))
elif str(Path.cwd()) not in sys.path:
    sys.path.append(str(Path.cwd()))

try:
    from database import (
        get_all_rooms, get_available_rooms, is_room_available, add_reservation,
        get_reservations_by_email, update_reservation,
    )
    from config import COORDENADAS_FACULTADES
    from agent_expert import AgenteExperto
    from schedule_models import (
        DatosPlanificacion, ConfiguracionPlanificacion, Curso, 
        Docente, Aula, TipoAula, FranjaSemanal, DiaSemana, GrupoLaboratorio
    )
    from schedule_optimizer import GeneradorHorarios
    from schedule_input import cargar_datos_planificacion, datos_planificacion_desde_dict
    BACKEND_DISPONIBLE = True
except ImportError as e:
    BACKEND_DISPONIBLE = False

WEBHOOK_N8N_URL = "https://acorn-pushiness-authentic.ngrok-free.dev/webhook/40e725c6-cc5d-4dbb-81e4-0f9cb91277c3"

aulas_registradas = get_all_rooms() if BACKEND_DISPONIBLE else []
aforos_registrados_db = sorted(list(set(aula["aforo_max"] for aula in aulas_registradas))) if aulas_registradas else [30, 35, 40, 45, 50, 55, 60]
facultades_registradas = [f.capitalize() for f in list(COORDENADAS_FACULTADES.keys())] if BACKEND_DISPONIBLE else ["Ingeniería"]

def cargar_catalogo_json():
    ruta_j = carpeta_proyecto / "datos_prueba_ingreso.json"
    if not ruta_j.exists():
        ruta_j = Path.cwd() / "datos_prueba_ingreso.json"
    cat = []
    if ruta_j.exists():
        with open(ruta_j, "r", encoding="utf-8") as f:
            d = json.load(f)
            for c in d.get("cursos", []):
                cat.append({
                    "id": c["id"],
                    "nombre": c["nombre"],
                    "docente_id": c.get("docente_id", ""),
                    "horas_teoria": int(c.get("duracion_minutos", 120) / 60),
                    "requiere_lab": c.get("requiere_laboratorio", False),
                    "horas_lab": 2 if c.get("requiere_laboratorio", False) else 0
                })
    return cat


def cargar_docentes_json():
    ruta_j = _ruta_archivo_proyecto("datos_prueba_ingreso.json")
    if not ruta_j.exists():
        return []
    try:
        with open(ruta_j, "r", encoding="utf-8") as f:
            return json.load(f).get("docentes", [])
    except (OSError, json.JSONDecodeError):
        return []


catalogo_cursos = cargar_catalogo_json()
materias_nombres = [c["nombre"] for c in catalogo_cursos]
ciclos_academicos = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]


def _ruta_archivo_proyecto(nombre):
    directorio = carpeta_proyecto if carpeta_proyecto.exists() else Path.cwd()
    return directorio / nombre


def _cargar_horarios_guardados():
    ruta = _ruta_archivo_proyecto("horarios_generados.json")
    if not ruta.exists():
        return {ciclo: [] for ciclo in ciclos_academicos}
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        if not isinstance(datos, dict):
            return {ciclo: [] for ciclo in ciclos_academicos}
        return {
            ciclo: datos.get(ciclo, [])
            for ciclo in ciclos_academicos
        }
    except (OSError, json.JSONDecodeError):
        return {ciclo: [] for ciclo in ciclos_academicos}


def _guardar_horarios_guardados(horarios):
    ruta = _ruta_archivo_proyecto("horarios_generados.json")
    ruta.write_text(
        json.dumps(horarios, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

style = {'description_width': '170px'}
layout_campo = widgets.Layout(width='620px', margin='6px 0px')

def exportar_excel_matricial(resultado_horarios, max_alternativas, ruta_salida="HORARIO_2026_II_GENERADO.xlsx"):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    
    franjas_horas = [
        ("07:00", "08:00"), ("08:00", "09:00"), ("09:00", "10:00"),
        ("10:00", "11:00"), ("11:00", "12:00"), ("12:00", "13:00"),
        ("13:00", "14:00"), ("14:00", "15:00"), ("15:00", "16:00"),
        ("16:00", "17:00"), ("17:00", "18:00"), ("18:00", "19:00"),
        ("19:00", "20:00"), ("20:00", "21:00")
    ]
    
    dias_semana = ["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES"]

    border_thin = Border(left=Side(style='thin', color='D9D9D9'),
                         right=Side(style='thin', color='D9D9D9'),
                         top=Side(style='thin', color='D9D9D9'),
                         bottom=Side(style='thin', color='D9D9D9'))
    
    fill_header = PatternFill(start_color="1D4ED8", end_color="1D4ED8", fill_type="solid")
    font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    
    fill_hora = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    font_hora = Font(name="Calibri", size=10, bold=True, color="334155")
    
    fill_curso = PatternFill(start_color="E0F2FE", end_color="E0F2FE", fill_type="solid")
    font_curso = Font(name="Calibri", size=9, bold=True, color="0369A1")

    for idx, h in enumerate(resultado_horarios[:max_alternativas], 1):
        ws = wb.create_sheet(title=f"Opcion {idx}")
        
        ws.cell(row=1, column=1, value="HORA").fill = fill_header
        ws.cell(row=1, column=1).font = font_header
        ws.cell(row=1, column=1).alignment = Alignment(horizontal="center", vertical="center")
        
        for col_idx, dia in enumerate(dias_semana, start=2):
            cell = ws.cell(row=1, column=col_idx, value=dia)
            cell.fill = fill_header
            cell.font = font_header
            cell.alignment = Alignment(horizontal="center", vertical="center")

        for row_idx, (h_i, h_f) in enumerate(franjas_horas, start=2):
            cell_h = ws.cell(row=row_idx, column=1, value=f"{h_i} - {h_f}")
            cell_h.fill = fill_hora
            cell_h.font = font_hora
            cell_h.alignment = Alignment(horizontal="center", vertical="center")
            
            for col_idx in range(2, 7):
                c = ws.cell(row=row_idx, column=col_idx)
                c.border = border_thin

        for sesion in h.sesiones:
            dia_str = sesion.franja.dia.value.upper()
            if dia_str in dias_semana:
                col_i = dias_semana.index(dia_str) + 2
                h_inicio_s = sesion.franja.hora_inicio
                
                for r_i, (h_i, h_f) in enumerate(franjas_horas, start=2):
                    if h_i == h_inicio_s or (h_i <= h_inicio_s < h_f):
                        cell_target = ws.cell(row=r_i, column=col_i)
                        
                        tipo_txt = "LAB" if "grupo" in str(sesion.grupo_laboratorio_id or "").lower() else "Teoria"
                        val_actual = cell_target.value
                        nuevo_val = f"{sesion.curso_id.replace('p2022-', '').upper()}\n{tipo_txt} - ({sesion.aula_id})"
                        
                        cell_target.value = f"{val_actual}\n---\n{nuevo_val}" if val_actual else nuevo_val
                        cell_target.fill = fill_curso
                        cell_target.font = font_curso
                        cell_target.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        ws.column_dimensions['A'].width = 16
        for col_letter in ['B', 'C', 'D', 'E', 'F']:
            ws.column_dimensions[col_letter].width = 28

    wb.save(ruta_salida)
    return ruta_salida

def generar_link_descarga(ruta_archivo, nombre_mostrado, bg_color="#16a34a"):
    with open(ruta_archivo, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()
    href = f'data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}'
    return f'<a href="{href}" download="{ruta_archivo}" target="_blank" style="display: inline-block; background-color: {bg_color}; color: white; padding: 10px 18px; text-decoration: none; font-weight: bold; border-radius: 6px; font-family: sans-serif; font-size: 13px; margin-top: 8px; margin-right: 8px;">📥 Descargar {nombre_mostrado} (.xlsx)</a>'

def generar_link_descarga_csv(df, nombre_archivo="HORARIO_2026_II_GENERADO.csv"):
    csv_str = df.to_csv(index=False, encoding="utf-8-sig")
    b64 = base64.b64encode(csv_str.encode()).decode()
    href = f'data:text/csv;charset=utf-8;base64,{b64}'
    return f'<a href="{href}" download="{nombre_archivo}" target="_blank" style="display: inline-block; background-color: #0284c7; color: white; padding: 10px 18px; text-decoration: none; font-weight: bold; border-radius: 6px; font-family: sans-serif; font-size: 13px; margin-top: 8px;">📊 Descargar Formato CSV (.csv)</a>'

def iniciar_interfaz():
    logo_path = Path("/content/G5_Sistemas_Inteligentes/img/logo.png")
    if logo_path.exists():
        logo_widget = widgets.Image(value=logo_path.read_bytes(), format='png', width=180)
    else:
        logo_widget = widgets.HTML("""
        <div style="border: 2px dashed #94a3b8; border-radius: 12px; padding: 15px; text-align: center; width: 180px; background: #f8fafc;">
            <span style="font-size: 26px;">🏫</span>
            <p style="margin: 4px 0 0 0; font-size: 11px; color: #334155; font-weight: bold;">Logo no hallado</p>
        </div>
        """)

    bienvenida_html = widgets.HTML("""
    <div style="font-family: sans-serif; color: #111827; line-height: 1.5; max-width: 550px;">
        <h3 style="color: #1d4ed8; margin-top: 0;">Panel de Control Académico Institucional</h3>
        <p>Sistema inteligente con descarga directa de archivos Excel y CSV a tu computadora.</p>
    </div>
    """)

    inicio_box = widgets.VBox([
        widgets.HTML("<h3 style='color: #111827; border-bottom: 2px solid #eab308; padding-bottom: 8px;'>🏠 Inicio y Bienvenida</h3>"),
        widgets.HTML("<br>"),
        widgets.HBox([logo_widget, widgets.HTML("<div style='width: 20px;'></div>"), bienvenida_html], layout=widgets.Layout(align_items='center')),
    ], layout=widgets.Layout(padding='15px', background_color='#ffffff'))

    lbl_p1 = widgets.HTML("<h4 style='color: #111827; margin-bottom: 5px;'>Formulario de Solicitud de Reserva Espontánea</h4>")
    fecha_reserva_picker = widgets.DatePicker(value=date.today(), description='📅 Fecha de Reserva:', style=style, layout=layout_campo)
    
    materia_reserva_select = widgets.Dropdown(options=[''] + materias_nombres, value='', description='📚 Materia:', style=style, layout=layout_campo)
    aforo_reserva_select = widgets.Dropdown(options=[''] + aforos_registrados_db, value='', description='👥 Aforo Requerido:', style=style, layout=layout_campo)
    
    opciones_ampm = ['']
    for h in [7, 8, 9, 10, 11]:
        opciones_ampm.append(f"{h:02d}:00 AM")
        opciones_ampm.append(f"{h:02d}:30 AM")
    opciones_ampm.append("12:00 PM")
    opciones_ampm.append("12:30 PM")
    for h in range(1, 10):
        opciones_ampm.append(f"{h:02d}:00 PM")
        opciones_ampm.append(f"{h:02d}:30 PM")

    h_ini_reserva = widgets.Dropdown(options=opciones_ampm, value='', description='⏰ Hora Inicio (AM/PM):', style=style, layout=layout_campo)
    h_fin_reserva = widgets.Dropdown(options=opciones_ampm, value='', description='⏰ Hora Fin (AM/PM):', style=style, layout=layout_campo)
    
    facultad_reserva_select = widgets.Dropdown(options=[''] + facultades_registradas, value='', description='🏛 Facultad de Origen:', style=style, layout=layout_campo)
    correo_docente_input = widgets.Text(value='', placeholder='docente@unitru.edu.pe', description='✉️ Correo Docente UNT:', style=style, layout=layout_campo)

    btn_consultar_disponibilidad = widgets.Button(
        description='🔍 Evaluar con Agente Experto y Enviar a n8n', 
        button_style='primary', 
        layout=widgets.Layout(width='620px', height='40px', margin='12px 0px 5px 0px')
    )

    output_reserva = widgets.Output()
    btn_buscar_reservas = widgets.Button(
        description='Buscar reservas del docente', icon='search',
        button_style='info', layout=widgets.Layout(width='620px', height='38px', margin='8px 0')
    )
    output_reservas_docente = widgets.Output()
    output_opciones_cambio = widgets.Output()
    reserva_seleccionada = {"reserva": None, "opciones": []}
    fecha_cambio_picker = widgets.DatePicker(
        value=date.today(), description='Nueva fecha:', style=style, layout=layout_campo
    )
    hora_inicio_cambio = widgets.Dropdown(
        options=opciones_ampm, value='', description='Nueva hora inicio:',
        style=style, layout=layout_campo
    )
    hora_fin_cambio = widgets.Dropdown(
        options=opciones_ampm, value='', description='Nueva hora fin:',
        style=style, layout=layout_campo
    )
    opcion_cambio_select = widgets.Dropdown(
        options=[('', '')], value='', description='Opción:',
        style=style, layout=layout_campo
    )
    btn_consultar_opciones = widgets.Button(
        description='Buscar aulas y horarios libres', icon='calendar',
        button_style='primary', layout=widgets.Layout(width='620px', height='38px', margin='8px 0')
    )
    btn_enviar_propuesta = widgets.Button(
        description='Enviar propuesta al docente', icon='envelope',
        button_style='warning', layout=widgets.Layout(width='300px', height='38px', margin='5px')
    )
    btn_confirmar_cambio = widgets.Button(
        description='Registrar aceptación y cambiar reserva', icon='check',
        button_style='success', layout=widgets.Layout(width='310px', height='38px', margin='5px')
    )
    cambio_box = widgets.VBox([
        widgets.HTML("<h4>Proponer reprogramación</h4><p>La reserva vigente se conserva hasta confirmar que el docente aceptó una opción.</p>"),
        fecha_cambio_picker, hora_inicio_cambio, hora_fin_cambio,
        btn_consultar_opciones, output_opciones_cambio, opcion_cambio_select,
        widgets.HBox([btn_enviar_propuesta, btn_confirmar_cambio]),
    ], layout=widgets.Layout(padding='12px', border='1px solid #dbe4ea', border_radius='6px'))
    cambio_box.layout.display = 'none'

    def _hora_24(hora_ampm):
        return datetime.strptime(hora_ampm.strip(), "%I:%M %p").strftime("%H:%M")

    def _hora_ampm(hora_24):
        return datetime.strptime(hora_24, "%H:%M").strftime("%I:%M %p")

    def mostrar_reservas_docente(b):
        with output_reservas_docente:
            output_reservas_docente.clear_output(wait=True)
            correo = correo_docente_input.value.strip()
            if not correo:
                print("Escribe el correo del docente para consultar sus reservas.")
                return
            reservas = get_reservations_by_email(correo)
            if not reservas:
                display(widgets.HTML(
                    "<p style='color:#64748b'>No se encontraron reservas para este correo en la sesión actual.</p>"
                ))
                return
            filas = []
            for reserva in reservas:
                detalle = widgets.HTML(
                    f"<div style='padding:8px 4px'><b>{html.escape(reserva.get('materia', ''))}</b>"
                    f" · {html.escape(reserva.get('fecha') or 'Sin fecha')}"
                    f" · {html.escape(reserva.get('horario_inicio', ''))}–{html.escape(reserva.get('horario_fin', ''))}"
                    f" · Aula {html.escape(reserva.get('aula', ''))}</div>"
                )
                btn_cambiar = widgets.Button(
                    description='Proponer cambio', icon='calendar',
                    layout=widgets.Layout(width='160px', height='32px')
                )

                def elegir_reserva(button, reserva_actual=deepcopy(reserva)):
                    reserva_seleccionada["reserva"] = reserva_actual
                    reserva_seleccionada["opciones"] = []
                    opcion_cambio_select.options = [('', '')]
                    opcion_cambio_select.value = ''
                    if reserva_actual.get("fecha"):
                        try:
                            fecha_cambio_picker.value = date.fromisoformat(reserva_actual["fecha"])
                        except ValueError:
                            fecha_cambio_picker.value = date.today()
                    hora_inicio_cambio.value = _hora_ampm(reserva_actual["horario_inicio"])
                    hora_fin_cambio.value = _hora_ampm(reserva_actual["horario_fin"])
                    output_opciones_cambio.clear_output(wait=True)
                    cambio_box.layout.display = 'flex'
                    with output_opciones_cambio:
                        display(widgets.HTML(
                            f"<p>Reserva actual seleccionada: <b>{html.escape(reserva_actual.get('materia', ''))}</b> "
                            f"en {html.escape(reserva_actual.get('aula', ''))}, "
                            f"{html.escape(reserva_actual.get('fecha') or 'sin fecha')} "
                            f"{html.escape(reserva_actual.get('horario_inicio', ''))}–{html.escape(reserva_actual.get('horario_fin', ''))}.</p>"
                        ))

                btn_cambiar.on_click(elegir_reserva)
                filas.append(widgets.HBox([detalle, btn_cambiar], layout=widgets.Layout(align_items='center')))
            display(widgets.VBox(filas, layout=widgets.Layout(width='100%')))

    btn_buscar_reservas.on_click(mostrar_reservas_docente)

    def buscar_reservas_al_escribir(change):
        correo = change.get('new', '').strip()
        dominio = correo.rsplit('@', 1)[-1] if '@' in correo else ''
        if '@' in correo and '.' in dominio and ' ' not in correo:
            mostrar_reservas_docente(None)
        elif not correo:
            output_reservas_docente.clear_output(wait=True)

    correo_docente_input.observe(buscar_reservas_al_escribir, names='value')

    def consultar_opciones_cambio(b):
        with output_opciones_cambio:
            output_opciones_cambio.clear_output(wait=True)
            reserva = reserva_seleccionada["reserva"]
            if reserva is None:
                print("Primero selecciona una reserva del docente.")
                return
            if not fecha_cambio_picker.value or not hora_inicio_cambio.value or not hora_fin_cambio.value:
                print("Selecciona la fecha y el intervalo horario propuesto.")
                return
            inicio = _hora_24(hora_inicio_cambio.value)
            fin = _hora_24(hora_fin_cambio.value)
            minutos_inicio = datetime.strptime(inicio, "%H:%M")
            minutos_fin = datetime.strptime(fin, "%H:%M")
            duracion_minutos = int((minutos_fin - minutos_inicio).total_seconds() / 60)
            if duracion_minutos <= 0:
                print("La hora final debe ser posterior a la hora de inicio.")
                return

            fecha_nueva = str(fecha_cambio_picker.value)
            opciones = []

            def agregar_opciones(hora_inicio, hora_fin):
                aulas = get_available_rooms(
                    hora_inicio, hora_fin, fecha=fecha_nueva,
                    exclude_reservation_id=reserva["id"],
                    aforo_minimo=reserva.get("aforo", 0),
                    requiere_laboratorio=reserva.get("requiere_laboratorio", False),
                )
                for aula in aulas:
                    misma_reserva = (
                        fecha_nueva == reserva.get("fecha")
                        and hora_inicio == reserva.get("horario_inicio")
                        and hora_fin == reserva.get("horario_fin")
                        and aula["id"] == reserva.get("aula")
                    )
                    if not misma_reserva:
                        opciones.append({
                            "fecha": fecha_nueva,
                            "hora_inicio": hora_inicio,
                            "hora_fin": hora_fin,
                            "aula": aula["id"],
                        })

            agregar_opciones(inicio, fin)
            if not opciones:
                for inicio_minutos in range(7 * 60, 22 * 60 - duracion_minutos + 1, 30):
                    fin_minutos = inicio_minutos + duracion_minutos
                    hora_inicio = f"{inicio_minutos // 60:02d}:{inicio_minutos % 60:02d}"
                    hora_fin = f"{fin_minutos // 60:02d}:{fin_minutos % 60:02d}"
                    agregar_opciones(hora_inicio, hora_fin)
                    if len(opciones) >= 8:
                        break

            reserva_seleccionada["opciones"] = opciones[:8]
            if not reserva_seleccionada["opciones"]:
                opcion_cambio_select.options = [('', '')]
                opcion_cambio_select.value = ''
                print("No hay aulas y franjas disponibles para esa fecha y duración.")
                return

            opcion_cambio_select.options = [('', '')] + [
                (
                    f"{opcion['fecha']} · {opcion['hora_inicio']}–{opcion['hora_fin']} · Aula {opcion['aula']}",
                    str(indice),
                )
                for indice, opcion in enumerate(reserva_seleccionada["opciones"])
            ]
            opcion_cambio_select.value = ''
            display(widgets.HTML(
                f"<p style='color:#0f766e'>Se encontraron {len(reserva_seleccionada['opciones'])} opción(es). "
                "La primera búsqueda respeta el horario solicitado; si está ocupado, se muestran otras franjas "
                "del mismo día. La reserva actual todavía no se modificó.</p>"
            ))

    btn_consultar_opciones.on_click(consultar_opciones_cambio)

    def enviar_propuesta_cambio(b):
        reserva = reserva_seleccionada["reserva"]
        opciones = reserva_seleccionada["opciones"]
        if reserva is None or not opciones:
            with output_opciones_cambio:
                print("Busca primero opciones disponibles para una reserva seleccionada.")
            return
        payload = {
            "estado": "Propuesta pendiente de aceptación",
            "materia": reserva.get("materia", ""),
            "aforo": reserva.get("aforo", 0),
            "horario": f"{reserva.get('horario_inicio', '')} - {reserva.get('horario_fin', '')}",
            "facultad": reserva.get("facultad", ""),
            "correo_docente": reserva.get("correo_docente", ""),
            "detalle": "Se solicita confirmar si acepta una de las opciones de reprogramación. La reserva actual permanece activa hasta su aceptación.",
            "fecha": reserva.get("fecha"),
            "aula_actual": reserva.get("aula"),
            "reserva_id": reserva.get("id"),
            "opciones_disponibles": opciones,
            "requiere_confirmacion_docente": True,
        }
        try:
            respuesta = requests.post(WEBHOOK_N8N_URL, json=payload, timeout=15)
            respuesta.raise_for_status()
            with output_opciones_cambio:
                display(widgets.HTML(
                    "<p style='color:#0f766e'><b>Propuesta enviada.</b> No se cambió la reserva; "
                    "espera la respuesta del docente antes de registrar su aceptación.</p>"
                ))
        except Exception as error:
            with output_opciones_cambio:
                print(f"No se pudo enviar la propuesta a n8n: {error}")

    btn_enviar_propuesta.on_click(enviar_propuesta_cambio)

    def confirmar_cambio_aceptado(b):
        reserva = reserva_seleccionada["reserva"]
        indice = opcion_cambio_select.value
        if reserva is None or indice == '':
            with output_opciones_cambio:
                print("Selecciona la opción que el docente aceptó.")
            return
        opcion = reserva_seleccionada["opciones"][int(indice)]
        if not update_reservation(
            reserva["id"], opcion["aula"], opcion["hora_inicio"],
            opcion["hora_fin"], opcion["fecha"],
        ):
            with output_opciones_cambio:
                print("No se aplicó el cambio: la opción dejó de estar disponible.")
            return
        payload = {
            "estado": "Cambio confirmado",
            "materia": reserva.get("materia", ""),
            "aforo": reserva.get("aforo", 0),
            "horario": f"{opcion['hora_inicio']} - {opcion['hora_fin']}",
            "facultad": reserva.get("facultad", ""),
            "correo_docente": reserva.get("correo_docente", ""),
            "detalle": f"Cambio aceptado por el docente. Nueva aula: {opcion['aula']}",
            "fecha": opcion["fecha"],
            "aula_asignada": opcion["aula"],
            "reserva_id": reserva["id"],
            "reserva_anterior": {
                "fecha": reserva.get("fecha"), "aula": reserva.get("aula"),
                "horario_inicio": reserva.get("horario_inicio"),
                "horario_fin": reserva.get("horario_fin"),
            },
        }
        try:
            respuesta = requests.post(WEBHOOK_N8N_URL, json=payload, timeout=15)
            respuesta.raise_for_status()
        except Exception as error:
            print(f"El cambio se guardó, pero no se pudo notificar a n8n: {error}")
        mostrar_reservas_docente(None)
        with output_opciones_cambio:
            display(widgets.HTML(
                "<p style='color:#15803d'><b>Cambio registrado.</b> Se notificó al docente con la nueva fecha, "
                "horario y aula.</p>"
            ))

    btn_confirmar_cambio.on_click(confirmar_cambio_aceptado)

    def on_consultar_clicked(b):
        with output_reserva:
            output_reserva.clear_output(wait=True)
            if not BACKEND_DISPONIBLE:
                print("Backend no disponible.")
                return
            if (
                not materia_reserva_select.value
                or not aforo_reserva_select.value
                or not h_ini_reserva.value
                or not h_fin_reserva.value
                or not fecha_reserva_picker.value
                or not correo_docente_input.value.strip()
            ):
                print("Por favor completa todos los campos obligatorios.")
                return

            experto = AgenteExperto()
            aforo_solicitado = int(aforo_reserva_select.value)
            h_ini = h_ini_reserva.value.strip()
            h_fin = h_fin_reserva.value.strip()
            correo_docente = correo_docente_input.value.strip()
            fecha_reserva = str(fecha_reserva_picker.value)
            curso_reserva = next(
                (curso for curso in catalogo_cursos if curso["nombre"] == materia_reserva_select.value),
                {},
            )
            requiere_lab = bool(curso_reserva.get("requiere_lab", False))
            facultad = facultad_reserva_select.value or "Ingeniería"

            hechos = {
                "materia": materia_reserva_select.value, "aforo": aforo_solicitado,
                "requiere_laboratorio": requiere_lab, "franja": "pico" if ("09" in h_ini or "10" in h_ini) else "normal",
                "horario_inicio": h_ini, "horario_fin": h_fin,
                "facultad_origen": facultad, "fecha": fecha_reserva,
            }
            
            evaluacion = experto.evaluar(hechos)
            regla_id = evaluacion.get('regla_aplicada', 'N/A')
            aula_preferida = evaluacion.get('aula_asignada', None)
            aprobado_experto = evaluacion.get('aprobado', False)
            
            r_pico_cumplida = (hechos["franja"] == "pico" and aforo_solicitado > 30)
            aula_final = None
            estrategia_asignacion = ""
            r_disponibilidad_cumplida = False

            if aprobado_experto and aula_preferida and is_room_available(
                aula_preferida, h_ini, h_fin, fecha=fecha_reserva
            ):
                aula_final = aula_preferida
                r_disponibilidad_cumplida = True
                estrategia_asignacion = f"Aula asignada por regla experta ({regla_id})."
            elif aprobado_experto:
                candidatas = get_available_rooms(
                    h_ini, h_fin, fecha=fecha_reserva,
                    aforo_minimo=aforo_solicitado,
                    requiere_laboratorio=requiere_lab,
                )
                if candidatas:
                    aula_final = candidatas[0]["id"]
                    r_disponibilidad_cumplida = True
                    estrategia_asignacion = f"Aula preferida ocupada. Reasignado a: <b>{aula_final}</b>."
                else:
                    estrategia_asignacion = "Sin aulas disponibles con suficiente capacidad."
            else:
                estrategia_asignacion = f"Rechazado: {evaluacion.get('motivo')}."

            aprobado_final = False
            if aula_final and r_disponibilidad_cumplida:
                if add_reservation(
                    aula_final, h_ini, h_fin, materia_reserva_select.value,
                    fecha=fecha_reserva, correo_docente=correo_docente,
                    aforo=aforo_solicitado, facultad=facultad,
                    requiere_laboratorio=requiere_lab,
                ):
                    aprobado_final = True

            estado_color = "#16a34a" if aprobado_final else "#dc2626"
            display(widgets.HTML(f"""
            <div style="background: #fffbeb; border-left: 5px solid {'#16a34a' if aprobado_final else '#eab308'}; padding: 14px; border-radius: 6px; margin-top: 12px; font-family: sans-serif;">
                <h4 style="margin: 0 0 8px 0; color: #111827;">Auditoría de Reglas Aplicadas (Reserva):</h4>
                <p style="margin: 4px 0;"><b>1. Regla Experta Evaluada:</b> <code style="background: #fef08a; padding: 2px 6px; border-radius: 4px; font-weight: bold;">{regla_id}</code> - <span style="color: {'#16a34a' if aprobado_experto else '#dc2626'}; font-weight: bold;">{'Cumplida' if aprobado_experto else 'Rechazada'}</span></p>
                <p style="margin: 4px 0;"><b>2. Regla de Franja Pico (>30 alumnos):</b> <span style="color: {'#16a34a' if r_pico_cumplida else '#e65100'}; font-weight: bold;">{'Cumplida' if r_pico_cumplida else 'Franja regular / No aplica'}</span></p>
                <p style="margin: 4px 0;"><b>3. Disponibilidad sin Solapamiento (AM/PM):</b> <span style="color: {'#16a34a' if r_disponibilidad_cumplida else '#dc2626'}; font-weight: bold;">{'Libre en Base de Datos' if r_disponibilidad_cumplida else 'Horario Ocupado'}</span></p>
                <hr style="border: 0; border-top: 1px solid #fef08a; margin: 8px 0;">
                <p style="margin: 4px 0;"><b>• Dictamen Final:</b> <span style="color: {estado_color}; font-weight: bold;">{'APROBADO' if aprobado_final else 'RECHAZADO'} ({aula_final if aprobado_final else 'Sin Asignación'})</span></p>
                <p style="margin: 4px 0; font-size: 12px; color: #4b5563;"><b>• Fundamento:</b> {estrategia_asignacion}</p>
                <p style="margin: 4px 0; color: #1d4ed8; font-size: 12px;"><b>• Correo Destino:</b> {correo_docente}</p>
            </div>
            """))

            try:
                respuesta = requests.post(WEBHOOK_N8N_URL, json={
                    "estado": "Reserva confirmada" if aprobado_final else "Solicitud rechazada",
                    "materia": materia_reserva_select.value,
                    "aforo": aforo_solicitado,
                    "horario": f"{h_ini} - {h_fin}",
                    "facultad": facultad,
                    "correo_docente": correo_docente,
                    "detalle": estrategia_asignacion,
                    "fecha": fecha_reserva,
                    "aula_asignada": aula_final,
                    "regla_experta": regla_id,
                }, timeout=15)
                respuesta.raise_for_status()
                print(f"[n8n]: Notificación enviada para {correo_docente}.")
            except Exception as e:
                print(f"Error al conectar con n8n: {e}")

    btn_consultar_disponibilidad.on_click(on_consultar_clicked)

    reserva_box = widgets.VBox([
        lbl_p1, fecha_reserva_picker, materia_reserva_select, aforo_reserva_select,
        h_ini_reserva, h_fin_reserva, facultad_reserva_select, correo_docente_input,
        btn_consultar_disponibilidad, output_reserva,
        widgets.HTML("<hr><h4>Reservas existentes del docente</h4>"),
        btn_buscar_reservas, output_reservas_docente, cambio_box,
    ], layout=widgets.Layout(padding='15px', background_color='#ffffff'))

    lbl_p2 = widgets.HTML("<h3 style='color: #111827; margin-bottom: 5px;'>Generar horario por ciclo</h3><p style='color:#64748b;margin-top:0'>Selecciona el ciclo, los cursos y las condiciones de generación.</p>")
    horarios_guardados = _cargar_horarios_guardados()
    cursos_box = widgets.VBox()

    def actualizar_checkboxes_cursos():
        global checkbox_list, catalogo_cursos
        catalogo_cursos = cargar_catalogo_json()
        materia_reserva_select.options = [''] + [curso['nombre'] for curso in catalogo_cursos]
        nombres_docentes = {d['id']: d['nombre'] for d in cargar_docentes_json()}
        checkbox_list = [
            widgets.Checkbox(
                value=False,
                description=(
                    f"{c['nombre']} · {nombres_docentes.get(c.get('docente_id'), 'Docente sin asignar')} "
                    f"· Teoría {c['horas_teoria']}h · Lab {c['horas_lab'] if c['requiere_lab'] else 0}h"
                ),
                indent=False,
                layout=widgets.Layout(width='100%', margin='3px 0'),
            )
            for c in catalogo_cursos
        ]
        cursos_box.children = checkbox_list

    actualizar_checkboxes_cursos()

    nuevo_nombre_input = widgets.Text(value='', placeholder='Ej. Inteligencia Artificial', description='📖 Nombre Curso:', style=style, layout=layout_campo)
    nuevo_horas_teoria = widgets.Dropdown(options=['', 1, 2, 3, 4], value='', description='📚 Horas Teoría:', style=style, layout=layout_campo)
    nuevo_req_lab_select = widgets.Dropdown(options=['', 'No', 'Sí'], value='', description='🔬 ¿Requiere Lab?:', style=style, layout=layout_campo)
    nuevo_horas_lab = widgets.Dropdown(options=['', 1, 2, 3], value='', description='⏱️ Horas Laboratorio:', style=style, layout=layout_campo)
    nuevo_docente_select = widgets.Dropdown(
        options=[('', '')] + [(d['nombre'], d['id']) for d in cargar_docentes_json()],
        value='', description='👨‍🏫 Docente existente:', style=style, layout=layout_campo
    )
    nuevo_docente_nombre = widgets.Text(
        value='', placeholder='O registra un docente nuevo',
        description='👨‍🏫 Nuevo docente:', style=style, layout=layout_campo
    )
    
    horas_lab_box = widgets.VBox([nuevo_horas_lab])
    horas_lab_box.layout.display = 'none'

    def on_req_lab_change(change):
        if change['new'] == 'Sí':
            horas_lab_box.layout.display = 'flex'
        else:
            horas_lab_box.layout.display = 'none'
            nuevo_horas_lab.value = ''
    nuevo_req_lab_select.observe(on_req_lab_change, names='value')

    btn_add_curso = widgets.Button(description='💾 Guardar Curso en el Catálogo y JSON', button_style='info', layout=widgets.Layout(width='620px', height='32px', margin='4px 0px 8px 0px'))
    output_add = widgets.Output()

    form_nuevo_curso_box = widgets.VBox([
        widgets.HTML("<b>➕ Registrar nuevo curso:</b>"),
        nuevo_nombre_input, nuevo_docente_select, nuevo_docente_nombre,
        nuevo_horas_teoria, nuevo_req_lab_select, horas_lab_box,
        btn_add_curso, output_add, widgets.HTML("<hr>")
    ])
    form_nuevo_curso_box.layout.display = 'none'

    curso_modificar_select = widgets.Dropdown(
        options=[('', '')], value='', description='Curso:',
        style=style, layout=layout_campo
    )
    selector_modificar_box = widgets.VBox([curso_modificar_select])
    selector_modificar_box.layout.display = 'none'
    modo_formulario_curso = {"curso_id": None, "modo": "nuevo"}

    def actualizar_opciones_cursos_modificar():
        curso_modificar_select.options = [('', '')] + [
            (curso['nombre'], curso['id']) for curso in cargar_catalogo_json()
        ]

    def limpiar_formulario_curso():
        modo_formulario_curso["curso_id"] = None
        modo_formulario_curso["modo"] = "nuevo"
        nuevo_nombre_input.value = ''
        nuevo_docente_select.value = ''
        nuevo_docente_nombre.value = ''
        nuevo_horas_teoria.value = ''
        nuevo_req_lab_select.value = ''
        nuevo_horas_lab.value = ''
        btn_add_curso.description = 'Guardar curso'

    def cargar_curso_en_formulario(curso_id):
        ruta_json = _ruta_archivo_proyecto("datos_prueba_ingreso.json")
        if not curso_id or not ruta_json.exists():
            return
        documento = json.loads(ruta_json.read_text(encoding="utf-8"))
        curso = next(
            (item for item in documento.get("cursos", []) if item["id"] == curso_id),
            None,
        )
        if curso is None:
            return
        modo_formulario_curso["curso_id"] = curso_id
        modo_formulario_curso["modo"] = "modificar"
        nuevo_nombre_input.value = curso.get("nombre", "")
        nuevo_docente_select.options = [('', '')] + [
            (docente["nombre"], docente["id"])
            for docente in documento.get("docentes", [])
        ]
        nuevo_docente_select.value = curso.get("docente_id", "")
        nuevo_docente_nombre.value = ''
        nuevo_horas_teoria.value = int(curso.get("duracion_minutos", 120) / 60)
        nuevo_req_lab_select.value = 'Sí' if curso.get("requiere_laboratorio") else 'No'
        nuevo_horas_lab.value = 2 if curso.get("requiere_laboratorio") else ''
        btn_add_curso.description = 'Guardar cambios'

    def on_curso_modificar_change(change):
        if change.get('name') == 'value' and change.get('new'):
            cargar_curso_en_formulario(change['new'])

    curso_modificar_select.observe(on_curso_modificar_change, names='value')
    actualizar_opciones_cursos_modificar()

    btn_toggle_form = widgets.Button(description='Añadir', icon='plus', button_style='warning', layout=widgets.Layout(width='295px', height='36px', margin='6px 5px 6px 0px'))
    btn_toggle_modificar = widgets.Button(description='Modificar', icon='edit', button_style='info', layout=widgets.Layout(width='295px', height='36px', margin='6px 0px'))

    def toggle_form_visibility(b):
        selector_modificar_box.layout.display = 'none'
        curso_modificar_select.value = ''
        limpiar_formulario_curso()
        form_nuevo_curso_box.layout.display = 'flex'
        form_nuevo_curso_box.children = (
            widgets.HTML("<b>Registrar curso nuevo:</b>"),
            nuevo_nombre_input, nuevo_docente_select, nuevo_docente_nombre,
            nuevo_horas_teoria, nuevo_req_lab_select, horas_lab_box,
            btn_add_curso, output_add, widgets.HTML("<hr>"),
        )

    def mostrar_formulario_modificar(b):
        limpiar_formulario_curso()
        modo_formulario_curso["modo"] = "modificar"
        output_add.clear_output(wait=True)
        selector_modificar_box.layout.display = 'flex'
        form_nuevo_curso_box.children = (
            widgets.HTML("<b>Modificar curso existente:</b>"),
            selector_modificar_box, nuevo_nombre_input, nuevo_docente_select,
            nuevo_docente_nombre, nuevo_horas_teoria, nuevo_req_lab_select,
            horas_lab_box, btn_add_curso, output_add, widgets.HTML("<hr>"),
        )
        form_nuevo_curso_box.layout.display = 'flex'

    btn_toggle_form.on_click(toggle_form_visibility)
    btn_toggle_modificar.on_click(mostrar_formulario_modificar)

    def ocultar_formulario_curso():
            form_nuevo_curso_box.layout.display = 'none'

    def on_add_curso_clicked(b):
        with output_add:
            output_add.clear_output(wait=True)
            nombre = nuevo_nombre_input.value.strip()
            if not nombre or nuevo_horas_teoria.value == '' or nuevo_req_lab_select.value == '':
                print("Completa los campos obligatorios del curso.")
                return
            if modo_formulario_curso["modo"] == "modificar" and not modo_formulario_curso["curso_id"]:
                print("Selecciona el curso que deseas modificar.")
                return
            nombre_docente = nuevo_docente_nombre.value.strip()
            if not nombre_docente and not nuevo_docente_select.value:
                print("Selecciona un docente existente o registra uno nuevo.")
                return
            req_l = (nuevo_req_lab_select.value == 'Sí')
            
            ruta_j = carpeta_proyecto / "datos_prueba_ingreso.json"
            if not ruta_j.exists():
                ruta_j = Path.cwd() / "datos_prueba_ingreso.json"
            if ruta_j.exists():
                with open(ruta_j, "r", encoding="utf-8") as f:
                    d_json = json.load(f)

                if nombre_docente:
                    docente_existente = next(
                        (d for d in d_json.get('docentes', [])
                         if d['nombre'].strip().casefold() == nombre_docente.casefold()),
                        None,
                    )
                    if docente_existente:
                        docente_id = docente_existente['id']
                    else:
                        docente_id = f"doc-{uuid.uuid4().hex[:8]}"
                        d_json.setdefault('docentes', []).append({
                            "id": docente_id,
                            "nombre": nombre_docente,
                            "disponibilidad": [
                                {"dia": dia, "hora_inicio": "07:00", "hora_fin": "22:00"}
                                for dia in ("lunes", "martes", "miercoles", "jueves", "viernes")
                            ],
                        })
                else:
                    docente_id = nuevo_docente_select.value

                curso_id = modo_formulario_curso["curso_id"]
                if curso_id:
                    curso_guardado = next(
                        (curso for curso in d_json["cursos"] if curso["id"] == curso_id),
                        None,
                    )
                    if curso_guardado is None:
                        print("El curso seleccionado ya no existe en el catálogo.")
                        return
                    curso_guardado.update({
                        "nombre": nombre,
                        "docente_id": docente_id,
                        "duracion_minutos": int(nuevo_horas_teoria.value) * 60,
                        "requiere_laboratorio": req_l,
                    })
                    d_json["grupos_laboratorio"] = [
                        grupo for grupo in d_json.get("grupos_laboratorio", [])
                        if grupo["curso_id"] != curso_id
                    ]
                    nuevo_id = curso_id
                else:
                    nuevo_id = f"p2022-curso-{uuid.uuid4().hex[:8]}"
                    d_json["cursos"].append({
                        "id": nuevo_id, "nombre": nombre, "docente_id": docente_id,
                        "cohorte_id": "cohorte-1",
                        "duracion_minutos": int(nuevo_horas_teoria.value) * 60,
                        "requiere_laboratorio": req_l,
                    })
                if req_l:
                    grupos_existentes = d_json.setdefault("grupos_laboratorio", [])
                    for s in range(1, 4):
                        grupos_existentes.append({
                            "id": f"grupo-{nuevo_id}-s{s}", "curso_id": nuevo_id,
                            "cohorte_id": "cohorte-1", "cantidad_estudiantes": 15,
                            "subcohorte_id": f"seccion-{s}",
                        })
                with open(ruta_j, "w", encoding="utf-8") as f:
                    json.dump(d_json, f, indent=2, ensure_ascii=False)
                nuevo_docente_select.options = [('', '')] + [
                    (d['nombre'], d['id']) for d in d_json.get('docentes', [])
                ]
                nuevo_docente_select.value = ''
            
            actualizar_checkboxes_cursos()
            actualizar_opciones_cursos_modificar()
            print(
                f"Curso '{nombre}' actualizado."
                if modo_formulario_curso["curso_id"]
                else f"Curso '{nombre}' guardado con el docente asignado."
            )
            limpiar_formulario_curso()
            curso_modificar_select.value = ''
            ocultar_formulario_curso()
    btn_add_curso.on_click(on_add_curso_clicked)

    ciclo_generacion_select = widgets.Dropdown(
        options=ciclos_academicos, value='I', description='Ciclo:',
        style=style, layout=layout_campo
    )
    estudiantes_ciclo_select = widgets.Dropdown(options=['', 16, 20, 25, 30, 34, 40, 50], value='', description='👥 Estudiantes (mín. 16):', style=style, layout=layout_campo)
    max_alternativas_gen = widgets.Dropdown(options=[('', ''), ('1 alternativa', 1), ('2 alternativas', 2), ('3 alternativas', 3)], value='', description='Alternativas:', style=style, layout=layout_campo)
    
    btn_generar_horarios = widgets.Button(description='Generar horario', button_style='success', layout=widgets.Layout(width='620px', height='42px', margin='12px 0px 5px 0px'))
    output_generacion = widgets.Output()

    def on_generar_horarios_clicked(b):
        with output_generacion:
            output_generacion.clear_output(wait=True)
            if not BACKEND_DISPONIBLE:
                print("Backend no disponible.")
                return
            
            cursos_sel = [catalogo_cursos[i] for i, chk in enumerate(checkbox_list) if chk.value]
            ciclo = ciclo_generacion_select.value
            
            r_6_cursos = (len(cursos_sel) >= 6)
            if not r_6_cursos:
                display(widgets.HTML(f"""
                <div style="background: #fef2f2; border-left: 5px solid #dc2626; padding: 14px; border-radius: 6px; margin: 12px 0; font-family: sans-serif;">
                    <h4 style="margin: 0 0 8px 0; color: #991b1b;">Error de Validación de Regla:</h4>
                    <p style="margin: 4px 0; color: #991b1b;"><b>Regla: mínimo 6 cursos por ciclo.</b> No cumplida; seleccionaste {len(cursos_sel)} para el ciclo {ciclo}.</p>
                </div>
                """))
                return

            if estudiantes_ciclo_select.value == '' or max_alternativas_gen.value == '':
                print("Selecciona el ciclo, el total de estudiantes y cuántas alternativas generar.")
                return

            total_est = int(estudiantes_ciclo_select.value)
            if total_est < 16:
                print("El número total de estudiantes debe ser al menos 16.")
                return

            try:
                ruta_j = _ruta_archivo_proyecto("datos_prueba_ingreso.json")
                with open(ruta_j, "r", encoding="utf-8") as f:
                    d_json = json.load(f)
                
                ids_sel = [c["id"] for c in cursos_sel]
                cursos_filtrados = [c for c in d_json["cursos"] if c["id"] in ids_sel]
                grupos_filtrados = [g for g in d_json["grupos_laboratorio"] if g["curso_id"] in [c["id"] for c in cursos_filtrados]]
                cohorte_ciclo = f"ciclo-{ciclo}"
                for curso in cursos_filtrados:
                    curso["cohorte_id"] = cohorte_ciclo
                for grupo in grupos_filtrados:
                    grupo["cohorte_id"] = cohorte_ciclo
                
                d_json["cursos"] = cursos_filtrados
                d_json["grupos_laboratorio"] = grupos_filtrados
                d_json["configuracion"]["cursos_por_semestre"] = len(cursos_filtrados)
                d_json["configuracion"]["cursos_con_laboratorio"] = sum(1 for c in cursos_filtrados if c.get("requiere_laboratorio", False))
                d_json["configuracion"]["max_horarios"] = int(max_alternativas_gen.value)

                datos_plan = datos_planificacion_desde_dict(d_json)
                agente = AgenteExperto()
                resultado = agente.generar_horarios(datos_plan)
                validaciones = [
                    agente.validar_horario(datos_plan, horario.sesiones)
                    for horario in resultado.horarios
                ]
                codigos_incidencias = {
                    incidencia.codigo
                    for validacion in validaciones
                    for incidencia in validacion.incidencias
                }
                r_docentes = bool(validaciones) and all(
                    not any(i.codigo == "choque_de_docente" for i in validacion.incidencias)
                    for validacion in validaciones
                )
                r_disponibilidad_docente = bool(validaciones) and all(
                    not any(i.codigo == "docente_fuera_de_disponibilidad" for i in validacion.incidencias)
                    for validacion in validaciones
                )
                r_aulas = bool(validaciones) and all(
                    not any(i.codigo == "choque_de_aula" for i in validacion.incidencias)
                    for validacion in validaciones
                )
                r_aulas_aptas = bool(validaciones) and not bool(
                    codigos_incidencias.intersection({
                        "aula_inexistente", "aula_no_apta_para_teoria",
                        "aula_no_apta_para_laboratorio", "capacidad_insuficiente",
                    })
                )
                r_cohorte = bool(validaciones) and not bool(
                    codigos_incidencias.intersection({
                        "choque_de_cohorte", "laboratorio_choca_con_curso_fijo",
                    })
                )
                r_experto = bool(validaciones) and all(v.valido for v in validaciones)

                registros = []
                offset_alternativa = len(horarios_guardados[ciclo])
                nombre_cursos = {c["id"]: c["nombre"] for c in cursos_filtrados}
                nombre_docentes = {d["id"]: d["nombre"] for d in d_json["docentes"]}
                if resultado.horarios:
                    ruta_excel = _ruta_archivo_proyecto(
                        f"HORARIO_CICLO_{ciclo}_GENERADO.xlsx"
                    )
                    exportar_excel_matricial(
                        resultado.horarios,
                        int(max_alternativas_gen.value),
                        str(ruta_excel),
                    )
                    for indice, horario in enumerate(resultado.horarios, 1):
                        sesiones_guardadas = []
                        for sesion in horario.sesiones:
                            curso = next(c for c in cursos_filtrados if c["id"] == sesion.curso_id)
                            sesiones_guardadas.append({
                                "curso": nombre_cursos.get(sesion.curso_id, sesion.curso_id),
                                "docente": nombre_docentes.get(curso["docente_id"], curso["docente_id"]),
                                "dia": sesion.franja.dia.value.upper(),
                                "hora_inicio": sesion.franja.hora_inicio,
                                "hora_fin": sesion.franja.hora_fin,
                                "aula": sesion.aula_id,
                                "tipo": "Laboratorio" if sesion.grupo_laboratorio_id else "Teoría",
                                "grupo": sesion.grupo_laboratorio_id or "",
                            })
                        registros.append({
                            "id": uuid.uuid4().hex,
                            "nombre": f"Alternativa {offset_alternativa + indice}",
                            "creado": date.today().isoformat(),
                            "puntaje": round(horario.puntaje.penalizacion_total, 2),
                            "archivo_excel": str(ruta_excel),
                            "sesiones": sesiones_guardadas,
                        })
                    horarios_guardados[ciclo].extend(registros)
                    _guardar_horarios_guardados(horarios_guardados)
                    actualizar_vista_horarios()

                display(widgets.HTML(f"""
                <div style="background:#f8fafc;border:1px solid #dbe4ea;border-left:5px solid #0f766e;padding:16px;border-radius:8px;margin:12px 0;font-family:sans-serif">
                    <h4 style="margin:0 0 10px;color:#102a43">Auditoría del agente experto · Ciclo {ciclo}</h4>
                    <p style="margin:5px 0"><b>Cursos (mínimo 6):</b> <span style="color:{'#15803d' if r_6_cursos else '#b91c1c'}">{'Cumplida' if r_6_cursos else 'No cumplida'} · {len(cursos_filtrados)}</span></p>
                    <p style="margin:5px 0"><b>Estudiantes (mínimo 16):</b> <span style="color:{'#15803d' if total_est >= 16 else '#b91c1c'}">{'Cumplida' if total_est >= 16 else 'No cumplida'} · {total_est}</span></p>
                    <p style="margin:5px 0"><b>Sin cruce de docente:</b> <span style="color:{'#15803d' if r_docentes else '#b91c1c'}">{'Cumplida' if r_docentes else 'No validada / sin alternativas'}</span></p>
                    <p style="margin:5px 0"><b>Disponibilidad docente:</b> <span style="color:{'#15803d' if r_disponibilidad_docente else '#b91c1c'}">{'Cumplida' if r_disponibilidad_docente else 'No validada / sin alternativas'}</span></p>
                    <p style="margin:5px 0"><b>Sin cruce de aula:</b> <span style="color:{'#15803d' if r_aulas else '#b91c1c'}">{'Cumplida' if r_aulas else 'No validada / sin alternativas'}</span></p>
                    <p style="margin:5px 0"><b>Tipo y capacidad de aula:</b> <span style="color:{'#15803d' if r_aulas_aptas else '#b91c1c'}">{'Cumplida' if r_aulas_aptas else 'No validada / sin alternativas'}</span></p>
                    <p style="margin:5px 0"><b>Sin cruce de cohorte ni laboratorio fijo:</b> <span style="color:{'#15803d' if r_cohorte else '#b91c1c'}">{'Cumplida' if r_cohorte else 'No validada / sin alternativas'}</span></p>
                    <p style="margin:5px 0"><b>Validación completa del agente experto:</b> <span style="color:{'#15803d' if r_experto else '#b91c1c'}">{'Cumplida' if r_experto else 'No hay horario válido'}</span></p>
                    <hr style="border:0;border-top:1px solid #dbe4ea;margin:10px 0">
                    <p style="margin:5px 0"><b>Resultado:</b> {html.escape(resultado.mensaje)} · {len(resultado.horarios)} alternativa(s).</p>
                    <p style="margin:5px 0;color:#475569">Las alternativas se guardaron en “Ver horario”. El catálogo original no fue modificado.</p>
                </div>
                """))

                requests.post(WEBHOOK_N8N_URL, json={
                    "evento": "generacion_semestral", "ciclo": ciclo,
                    "opciones": len(resultado.horarios),
                }, timeout=10)
            except Exception as e:
                print(f"Error al procesar: {e}")

    btn_generar_horarios.on_click(on_generar_horarios_clicked)

    ciclo_ver_select = widgets.Dropdown(
        options=ciclos_academicos, value='I', description='Ciclo:',
        style=style, layout=layout_campo
    )
    output_ver_horario = widgets.Output()

    def actualizar_vista_horarios(change=None):
        ciclo = ciclo_ver_select.value
        with output_ver_horario:
            output_ver_horario.clear_output(wait=True)
            registros = horarios_guardados.get(ciclo, [])
            if not registros:
                display(widgets.HTML(
                    f"<p style='color:#64748b;padding:16px 0'>Aún no hay horarios guardados para el ciclo {ciclo}.</p>"
                ))
                return

            tarjetas = []
            for registro in registros:
                filas = "".join(
                    "<tr>"
                    f"<td>{html.escape(str(sesion.get('curso', '')))}</td>"
                    f"<td>{html.escape(str(sesion.get('docente', '')))}</td>"
                    f"<td>{html.escape(str(sesion.get('dia', '')))}</td>"
                    f"<td>{html.escape(str(sesion.get('hora_inicio', '')))}–{html.escape(str(sesion.get('hora_fin', '')))}</td>"
                    f"<td>{html.escape(str(sesion.get('aula', '')))}</td>"
                    f"<td>{html.escape(str(sesion.get('tipo', '')))}</td>"
                    "</tr>"
                    for sesion in registro.get('sesiones', [])
                )
                tabla = f"""
                <div style="overflow-x:auto;margin:10px 0 12px">
                  <table style="border-collapse:collapse;width:100%;font:13px sans-serif;text-align:left">
                    <thead><tr style="background:#123b45;color:white">
                      <th style="padding:8px">Curso</th><th style="padding:8px">Docente</th>
                      <th style="padding:8px">Día</th><th style="padding:8px">Hora</th>
                      <th style="padding:8px">Aula</th><th style="padding:8px">Tipo</th>
                    </tr></thead>
                    <tbody>{filas}</tbody>
                  </table>
                </div>
                """
                archivo_excel = registro.get('archivo_excel', '')
                descarga = (
                    generar_link_descarga(archivo_excel, 'Descargar Excel', '#0f766e')
                    if archivo_excel and Path(archivo_excel).exists()
                    else ""
                )
                encabezado = widgets.HTML(
                    f"<div style='border-top:1px solid #dbe4ea;padding-top:14px;margin-top:12px'>"
                    f"<b style='color:#123b45'>{html.escape(str(registro.get('nombre', 'Horario')))}</b>"
                    f"<span style='color:#64748b'> · {html.escape(str(registro.get('creado', '')))}"
                    f" · puntaje {html.escape(str(registro.get('puntaje', '')))}</span></div>"
                    f"{tabla}{descarga}"
                )
                btn_eliminar = widgets.Button(
                    description='Eliminar', icon='trash', button_style='danger',
                    layout=widgets.Layout(width='115px', height='32px')
                )

                def eliminar_horario(b, ciclo_actual=ciclo, id_actual=registro.get('id')):
                    horarios_guardados[ciclo_actual] = [
                        item for item in horarios_guardados.get(ciclo_actual, [])
                        if item.get('id') != id_actual
                    ]
                    _guardar_horarios_guardados(horarios_guardados)
                    actualizar_vista_horarios()

                btn_eliminar.on_click(eliminar_horario)
                tarjetas.append(widgets.VBox(
                    [encabezado, btn_eliminar],
                    layout=widgets.Layout(
                        padding='0 0 12px 0', margin='0 0 10px 0',
                        border_bottom='1px solid #dbe4ea',
                    ),
                ))
            display(widgets.VBox(tarjetas, layout=widgets.Layout(width='100%')))

    ciclo_ver_select.observe(actualizar_vista_horarios, names='value')
    actualizar_vista_horarios()

    ver_horario_box = widgets.VBox([
        widgets.HTML("<h3 style='color:#111827;margin-bottom:4px'>Horarios guardados</h3><p style='color:#64748b;margin-top:0'>Consulta y elimina alternativas por ciclo.</p>"),
        ciclo_ver_select, output_ver_horario,
    ], layout=widgets.Layout(padding='18px', background_color='#ffffff'))

    generar_box = widgets.VBox([
        lbl_p2, ciclo_generacion_select, cursos_box, widgets.HTML("<hr>"),
        widgets.HBox([btn_toggle_form, btn_toggle_modificar]), form_nuevo_curso_box,
        estudiantes_ciclo_select, max_alternativas_gen,
        btn_generar_horarios, output_generacion
    ], layout=widgets.Layout(padding='15px', background_color='#ffffff'))

    sidebar_titulo = widgets.HTML("""
    <div style="font-family: sans-serif; padding: 5px 0 15px 0; border-bottom: 2px solid #eab308;">
        <h3 style="margin: 0; font-size: 15px; color: #1d4ed8;">🏛️ SIAH-UNT</h3>
        <p style="margin: 3px 0 0 0; font-size: 11px; color: #4b5563;">Gestión Inteligente</p>
    </div>
    """)

    btn_nav_inicio = widgets.Button(description='🏠 Inicio', layout=widgets.Layout(width='180px', height='38px', margin='4px 0px'))
    btn_nav_reserva = widgets.Button(description='📅 Reservar', layout=widgets.Layout(width='180px', height='38px', margin='4px 0px'))
    btn_nav_generar = widgets.Button(description='Generar horario', layout=widgets.Layout(width='180px', height='38px', margin='4px 0px'))
    btn_nav_ver_horario = widgets.Button(description='Ver horario', layout=widgets.Layout(width='180px', height='38px', margin='4px 0px'))

    content_panel = widgets.Box([inicio_box], layout=widgets.Layout(width='860px', min_height='560px', border='1px solid #dbe4ea', border_radius='8px', background_color='#ffffff'))

    def actualizar_indicadores(activo):
        btn_nav_inicio.description = '🏠 Inicio' + ('  ◀' if activo == 'inicio' else '')
        btn_nav_reserva.description = '📅 Reservar' + ('  ◀' if activo == 'reserva' else '')
        btn_nav_generar.description = 'Generar horario' + ('  ◀' if activo == 'generar' else '')
        btn_nav_ver_horario.description = 'Ver horario' + ('  ◀' if activo == 'ver_horario' else '')
        btn_nav_inicio.style.button_color = '#0f766e' if activo == 'inicio' else '#f1f5f9'
        btn_nav_reserva.style.button_color = '#0f766e' if activo == 'reserva' else '#f1f5f9'
        btn_nav_generar.style.button_color = '#0f766e' if activo == 'generar' else '#f1f5f9'
        btn_nav_ver_horario.style.button_color = '#0f766e' if activo == 'ver_horario' else '#f1f5f9'

    actualizar_indicadores('inicio')

    btn_nav_inicio.on_click(lambda b: (setattr(content_panel, 'children', [inicio_box]), actualizar_indicadores('inicio')))
    btn_nav_reserva.on_click(lambda b: (setattr(content_panel, 'children', [reserva_box]), actualizar_indicadores('reserva')))
    btn_nav_generar.on_click(lambda b: (setattr(content_panel, 'children', [generar_box]), actualizar_indicadores('generar')))
    btn_nav_ver_horario.on_click(lambda b: (setattr(content_panel, 'children', [ver_horario_box]), actualizar_indicadores('ver_horario')))

    sidebar_box = widgets.VBox([
        sidebar_titulo, widgets.HTML("<div style='height: 10px;'></div>"),
        btn_nav_inicio, btn_nav_reserva, btn_nav_generar, btn_nav_ver_horario,
        widgets.HTML("<div style='flex-grow: 1;'></div>"),
        widgets.HTML("<p style='font-size: 10px; color: #9ca3af; text-align: center; margin: 0;'>SIAH v2.6 • UNT</p>")
    ], layout=widgets.Layout(width='215px', padding='10px', background_color='#f1f5f4', border_right='3px solid #d97706', min_height='580px'))

    dashboard_principal = widgets.HBox([sidebar_box, widgets.HTML("<div style='width: 15px;'></div>"), content_panel], layout=widgets.Layout(align_items='flex-start'))
    header_principal = widgets.HTML("""
    <div style="background: #ffffff; color: #111827; padding: 14px 20px; border-radius: 8px; font-family: sans-serif; border: 1px solid #e5e7eb; margin-bottom: 12px;">
        <h2 style="margin: 0; font-size: 18px; color: #1d4ed8;">🎓 Universidad Nacional de Trujillo (UNT)</h2>
        <p style="margin: 3px 0 0 0; font-size: 12px; color: #4b5563;">SIAH-UNT: Sistema Inteligente de Asignación y Horarios Académicos</p>
    </div>
    """)
    display(header_principal, dashboard_principal)
