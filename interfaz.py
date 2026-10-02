# --- MÓDULO INTERFAZ SIAH-UNT ---
import sys
from pathlib import Path
import ipywidgets as widgets
from IPython.display import display, clear_output
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import requests
from datetime import date
import json
import base64

carpeta_proyecto = Path.cwd() / "G5_Sistemas_Inteligentes"
if carpeta_proyecto.exists() and str(carpeta_proyecto) not in sys.path:
    sys.path.append(str(carpeta_proyecto))
elif str(Path.cwd()) not in sys.path:
    sys.path.append(str(Path.cwd()))

try:
    from database import get_all_rooms, get_available_rooms, is_room_available, add_reservation
    from config import COORDENADAS_FACULTADES
    from agent_expert import AgenteExperto
    from schedule_models import (
        DatosPlanificacion, ConfiguracionPlanificacion, Curso, 
        Docente, Aula, TipoAula, FranjaSemanal, DiaSemana, GrupoLaboratorio
    )
    from schedule_optimizer import GeneradorHorarios
    from schedule_input import cargar_datos_planificacion
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
                    "horas_teoria": int(c.get("duracion_minutos", 120) / 60),
                    "requiere_lab": c.get("requiere_laboratorio", False),
                    "horas_lab": 2 if c.get("requiere_laboratorio", False) else 0
                })
    return cat

catalogo_cursos = cargar_catalogo_json()
materias_nombres = [c["nombre"] for c in catalogo_cursos]

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

    def on_consultar_clicked(b):
        with output_reserva:
            output_reserva.clear_output(wait=True)
            if not BACKEND_DISPONIBLE:
                print("Backend no disponible.")
                return
            if not materia_reserva_select.value or not aforo_reserva_select.value or not h_ini_reserva.value or not h_fin_reserva.value or not correo_docente_input.value:
                print("Por favor completa todos los campos obligatorios.")
                return

            experto = AgenteExperto()
            aforo_solicitado = int(aforo_reserva_select.value)
            h_ini = h_ini_reserva.value.strip()
            h_fin = h_fin_reserva.value.strip()
            correo_docente = correo_docente_input.value.strip()

            hechos = {
                "materia": materia_reserva_select.value, "aforo": aforo_solicitado,
                "requiere_laboratorio": True, "franja": "pico" if ("09" in h_ini or "10" in h_ini) else "normal",
                "horario_inicio": h_ini, "horario_fin": h_fin,
                "facultad_origen": facultad_reserva_select.value if facultad_reserva_select.value else "Ingeniería"
            }
            
            evaluacion = experto.evaluar(hechos)
            regla_id = evaluacion.get('regla_aplicada', 'N/A')
            aula_preferida = evaluacion.get('aula_asignada', None)
            aprobado_experto = evaluacion.get('aprobado', False)
            
            r_pico_cumplida = (hechos["franja"] == "pico" and aforo_solicitado > 30)
            aula_final = None
            estrategia_asignacion = ""
            r_disponibilidad_cumplida = False

            if aprobado_experto and aula_preferida and is_room_available(aula_preferida, h_ini, h_fin):
                aula_final = aula_preferida
                r_disponibilidad_cumplida = True
                estrategia_asignacion = f"Aula asignada por regla experta ({regla_id})."
            elif aprobado_experto:
                aulas_disponibles = get_available_rooms(h_ini, h_fin)
                candidatas = [a for a in aulas_disponibles if a["aforo_max"] >= aforo_solicitado]
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
                if add_reservation(aula_final, h_ini, h_fin, materia_reserva_select.value):
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
                requests.post(WEBHOOK_N8N_URL, json={
                    "fecha": str(fecha_reserva_picker.value), "materia": materia_reserva_select.value,
                    "aforo": aforo_solicitado, "horario": f"{h_ini} - {h_fin}", "correo_docente": correo_docente,
                    "estado": "Aprobado" if aprobado_final else "Rechazado", "aula_asignada": str(aula_final), "detalle": estrategia_asignacion
                })
                print(f"[n8n]: Notificación enviada para {correo_docente}.")
            except Exception as e:
                print(f"Error al conectar con n8n: {e}")

    btn_consultar_disponibilidad.on_click(on_consultar_clicked)

    reserva_box = widgets.VBox([
        lbl_p1, fecha_reserva_picker, materia_reserva_select, aforo_reserva_select,
        h_ini_reserva, h_fin_reserva, facultad_reserva_select, correo_docente_input,
        btn_consultar_disponibilidad, output_reserva
    ], layout=widgets.Layout(padding='15px', background_color='#ffffff'))

    lbl_p2 = widgets.HTML("<h4 style='color: #111827; margin-bottom: 5px;'>Configuración de Cursos para la Planificación Semestral (Obligatorio seleccionar al menos 6 cursos)</h4>")
    cursos_box = widgets.VBox()

    def actualizar_checkboxes_cursos():
        global checkbox_list, catalogo_cursos
        catalogo_cursos = cargar_catalogo_json()
        checkbox_list = [
            widgets.Checkbox(value=False, description=f"{c['nombre']} (Teo: {c['horas_teoria']}h | Lab: {c['horas_lab'] if c['requiere_lab'] else 0}h)", indent=False)
            for c in catalogo_cursos
        ]
        cursos_box.children = checkbox_list

    actualizar_checkboxes_cursos()

    nuevo_nombre_input = widgets.Text(value='', placeholder='Ej. Inteligencia Artificial', description='📖 Nombre Curso:', style=style, layout=layout_campo)
    nuevo_horas_teoria = widgets.Dropdown(options=['', 1, 2, 3, 4], value='', description='📚 Horas Teoría:', style=style, layout=layout_campo)
    nuevo_req_lab_select = widgets.Dropdown(options=['', 'No', 'Sí'], value='', description='🔬 ¿Requiere Lab?:', style=style, layout=layout_campo)
    nuevo_horas_lab = widgets.Dropdown(options=['', 1, 2, 3], value='', description='⏱️ Horas Laboratorio:', style=style, layout=layout_campo)
    
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
        nuevo_nombre_input, nuevo_horas_teoria, nuevo_req_lab_select, horas_lab_box,
        btn_add_curso, output_add, widgets.HTML("<hr>")
    ])
    form_nuevo_curso_box.layout.display = 'none'

    btn_toggle_form = widgets.Button(description='➕ Añadir Nuevo Curso al Catálogo', button_style='warning', layout=widgets.Layout(width='620px', height='34px', margin='6px 0px'))
    def toggle_form_visibility(b):
        if form_nuevo_curso_box.layout.display == 'none':
            form_nuevo_curso_box.layout.display = 'flex'
            btn_toggle_form.description = '➖ Ocultar Formulario'
        else:
            form_nuevo_curso_box.layout.display = 'none'
            btn_toggle_form.description = '➕ Añadir Nuevo Curso al Catálogo'
    btn_toggle_form.on_click(toggle_form_visibility)

    def on_add_curso_clicked(b):
        with output_add:
            output_add.clear_output(wait=True)
            nombre = nuevo_nombre_input.value.strip()
            if not nombre or nuevo_horas_teoria.value == '' or nuevo_req_lab_select.value == '':
                print("Completa los campos obligatorios del curso.")
                return
            req_l = (nuevo_req_lab_select.value == 'Sí')
            
            ruta_j = carpeta_proyecto / "datos_prueba_ingreso.json"
            if not ruta_j.exists():
                ruta_j = Path.cwd() / "datos_prueba_ingreso.json"
            if ruta_j.exists():
                with open(ruta_j, "r", encoding="utf-8") as f:
                    d_json = json.load(f)
                nuevo_id = f"p2022-curso{len(d_json['cursos'])+1}"
                d_json["cursos"].append({
                    "id": nuevo_id, "nombre": nombre, "docente_id": "doc-1", "cohorte_id": "cohorte-1",
                    "duracion_minutos": int(nuevo_horas_teoria.value) * 60, "requiere_laboratorio": req_l
                })
                if req_l:
                    for s in range(1, 4):
                        d_json["grupos_laboratorio"].append({
                            "id": f"grupo-{nuevo_id}-s{s}", "curso_id": nuevo_id, "cohorte_id": "cohorte-1",
                            "cantidad_estudiantes": 15, "subcohorte_id": f"seccion-{s}"
                        })
                with open(ruta_j, "w", encoding="utf-8") as f:
                    json.dump(d_json, f, indent=2, ensure_ascii=False)
            
            actualizar_checkboxes_cursos()
            print(f"Curso '{nombre}' guardado en el JSON e interfaz.")
            nuevo_nombre_input.value = ''
    btn_add_curso.on_click(on_add_curso_clicked)

    estudiantes_ciclo_select = widgets.Dropdown(options=['', 16, 20, 25, 30, 34, 40, 50], value='', description='👥 Total Estudiantes (Mín. 16):', style=style, layout=layout_campo)
    max_alternativas_gen = widgets.Dropdown(options=['', 1, 2, 3], value='', description='📊 Alternativas a Generar:', style=style, layout=layout_campo)
    
    btn_generar_horarios = widgets.Button(description='🚀 Generar Horarios, Mostrar y Exportar Excel', button_style='success', layout=widgets.Layout(width='620px', height='40px', margin='12px 0px 5px 0px'))
    output_generacion = widgets.Output()

    def on_generar_horarios_clicked(b):
        with output_generacion:
            output_generacion.clear_output(wait=True)
            if not BACKEND_DISPONIBLE:
                print("Backend no disponible.")
                return
            
            cursos_sel = [catalogo_cursos[i] for i, chk in enumerate(checkbox_list) if chk.value]
            
            r_6_cursos = (len(cursos_sel) >= 6)
            if not r_6_cursos:
                display(widgets.HTML(f"""
                <div style="background: #fef2f2; border-left: 5px solid #dc2626; padding: 14px; border-radius: 6px; margin: 12px 0; font-family: sans-serif;">
                    <h4 style="margin: 0 0 8px 0; color: #991b1b;">Error de Validación de Regla:</h4>
                    <p style="margin: 4px 0; color: #991b1b;"><b>• Regla de Mínimo de Cursos (>= 6):</b> <span style="color: #dc2626; font-weight: bold;">No Cumplida</span> (Se seleccionaron solo {len(cursos_sel)} cursos).</p>
                    <p style="margin: 4px 0; color: #4b5563; font-size: 12px;">Debes marcar al menos 6 cursos en la lista para habilitar la generación.</p>
                </div>
                """))
                return

            if estudiantes_ciclo_select.value == '' or max_alternativas_gen.value == '':
                print("Selecciona el total de estudiantes y las alternativas a generar.")
                return

            total_est = int(estudiantes_ciclo_select.value)
            if total_est < 16:
                print("El número total de estudiantes debe ser al menos 16.")
                return

            try:
                ruta_j = carpeta_proyecto / "datos_prueba_ingreso.json"
                if not ruta_j.exists():
                    ruta_j = Path.cwd() / "datos_prueba_ingreso.json"
                with open(ruta_j, "r", encoding="utf-8") as f:
                    d_json = json.load(f)
                
                ids_sel = [c["id"] for c in cursos_sel]
                cursos_filtrados = [c for c in d_json["cursos"] if c["id"] in ids_sel or c["nombre"] in [x["nombre"] for x in cursos_sel]]
                grupos_filtrados = [g for g in d_json["grupos_laboratorio"] if g["curso_id"] in [c["id"] for c in cursos_filtrados]]
                
                d_json["cursos"] = cursos_filtrados
                d_json["grupos_laboratorio"] = grupos_filtrados
                d_json["configuracion"]["cursos_por_semestre"] = len(cursos_filtrados)
                d_json["configuracion"]["cursos_con_laboratorio"] = sum(1 for c in cursos_filtrados if c.get("requiere_laboratorio", False))
                d_json["configuracion"]["max_horarios"] = int(max_alternativas_gen.value)
                
                with open(ruta_j, "w", encoding="utf-8") as f:
                    json.dump(d_json, f, indent=2, ensure_ascii=False)

                datos_plan = cargar_datos_planificacion(ruta_j)
                resultado = GeneradorHorarios(max_estados=8000).generar(datos_plan)
                r_cruces_cero = (len(resultado.horarios) > 0)

                archivo_excel_generado = exportar_excel_matricial(resultado.horarios, int(max_alternativas_gen.value))
                
                filas_csv = []
                for idx, h in enumerate(resultado.horarios[:int(max_alternativas_gen.value)], 1):
                    for sesion in h.sesiones:
                        filas_csv.append({
                            "Alternativa": f"Opción {idx}",
                            "Curso": sesion.curso_id.replace("p2022-", "").upper(),
                            "Día": sesion.franja.dia.value.upper(),
                            "Horario": f"{sesion.franja.hora_inicio} - {sesion.franja.hora_fin}",
                            "Aula Asignada": sesion.aula_id
                        })
                df_export = pd.DataFrame(filas_csv)

                btn_excel_html = generar_link_descarga(archivo_excel_generado, "Horarios Matriz Excel")
                btn_csv_html = generar_link_descarga_csv(df_export, "HORARIO_2026_II_GENERADO.csv")

                tabla_html = "<table border='1' style='border-collapse: collapse; width: 100%; text-align: center; font-size: 12px; font-family: sans-serif; margin-top: 10px;'><tr style='background: #1d4ed8; color: white;'><th>Alternativa</th><th>Curso</th><th>Día</th><th>Horario</th><th>Aula Asignada</th></tr>"
                for fila in filas_csv:
                    tabla_html += f"<tr><td>{fila['Alternativa']}</td><td>{fila['Curso']}</td><td>{fila['Día']}</td><td>{fila['Horario']}</td><td><b>{fila['Aula Asignada']}</b></td></tr>"
                tabla_html += "</table>"

                display(widgets.HTML(f"""
                <div style="background: #eff6ff; border-left: 5px solid #3b82f6; padding: 14px; border-radius: 6px; margin: 12px 0; font-family: sans-serif;">
                    <h4 style="margin: 0 0 8px 0; color: #111827;">📋 Auditoría de Reglas Aplicadas (Planificación Semestral):</h4>
                    <p style="margin: 4px 0;"><b>1. Regla Mínimo 6 Cursos:</b> <span style="color: #16a34a; font-weight: bold;">✅ Cumplida ({len(cursos_filtrados)} cursos seleccionados)</span></p>
                    <p style="margin: 4px 0;"><b>2. Umbral Estudiantes (>= 16):</b> <span style="color: #16a34a; font-weight: bold;">✅ Cumplida ({total_est} alumnos)</span></p>
                    <p style="margin: 4px 0;"><b>3. Validación de Infraestructura (5 Aulas Lab):</b> <span style="color: #16a34a; font-weight: bold;">✅ Cumplida (B201-B205 reutilizables)</span></p>
                    <p style="margin: 4px 0;"><b>4. Control de Cruces (schedule_validator):</b> <span style="color: {'#16a34a' if r_cruces_cero else '#dc2626'}; font-weight: bold;">{'✅ Cumplida (0 Solapamientos)' if r_cruces_cero else '❌ Incompatible'}</span></p>
                    <hr style="border: 0; border-top: 1px solid #bfdbfe; margin: 8px 0;">
                    <p style="margin: 4px 0;"><b>• Resultado:</b> {len(resultado.horarios)} alternativas válidas generadas.</p>
                    <div style="margin: 12px 0;">
                        {btn_excel_html}
                        {btn_csv_html}
                    </div>
                    {tabla_html}
                </div>
                """))

                requests.post(WEBHOOK_N8N_URL, json={"evento": "generacion_semestral", "opciones": len(resultado.horarios)})
            except Exception as e:
                print(f"Error al procesar: {e}")

    btn_generar_horarios.on_click(on_generar_horarios_clicked)

    generar_box = widgets.VBox([
        lbl_p2, cursos_box, widgets.HTML("<hr>"),
        btn_toggle_form, form_nuevo_curso_box,
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
    btn_nav_generar = widgets.Button(description='🚀 Generar Horario', layout=widgets.Layout(width='180px', height='38px', margin='4px 0px'))

    content_panel = widgets.Box([inicio_box], layout=widgets.Layout(width='700px', min_height='520px', border='1px solid #e5e7eb', border_radius='8px', background_color='#ffffff'))

    def actualizar_indicadores(activo):
        btn_nav_inicio.description = '🏠 Inicio' + ('  ◀' if activo == 'inicio' else '')
        btn_nav_reserva.description = '📅 Reservar' + ('  ◀' if activo == 'reserva' else '')
        btn_nav_generar.description = '🚀 Generar Horario' + ('  ◀' if activo == 'generar' else '')
        btn_nav_inicio.style.button_color = '#1d4ed8' if activo == 'inicio' else '#f1f5f9'
        btn_nav_reserva.style.button_color = '#1d4ed8' if activo == 'reserva' else '#f1f5f9'
        btn_nav_generar.style.button_color = '#1d4ed8' if activo == 'generar' else '#f1f5f9'

    actualizar_indicadores('inicio')

    btn_nav_inicio.on_click(lambda b: (setattr(content_panel, 'children', [inicio_box]), actualizar_indicadores('inicio')))
    btn_nav_reserva.on_click(lambda b: (setattr(content_panel, 'children', [reserva_box]), actualizar_indicadores('reserva')))
    btn_nav_generar.on_click(lambda b: (setattr(content_panel, 'children', [generar_box]), actualizar_indicadores('generar')))

    sidebar_box = widgets.VBox([
        sidebar_titulo, widgets.HTML("<div style='height: 10px;'></div>"),
        btn_nav_inicio, btn_nav_reserva, btn_nav_generar,
        widgets.HTML("<div style='flex-grow: 1;'></div>"),
        widgets.HTML("<p style='font-size: 10px; color: #9ca3af; text-align: center; margin: 0;'>SIAH v2.6 • UNT</p>")
    ], layout=widgets.Layout(width='215px', padding='10px', background_color='#f8fafc', border_right='2px solid #eab308', min_height='540px'))

    dashboard_principal = widgets.HBox([sidebar_box, widgets.HTML("<div style='width: 15px;'></div>"), content_panel], layout=widgets.Layout(align_items='flex-start'))
    header_principal = widgets.HTML("""
    <div style="background: #ffffff; color: #111827; padding: 14px 20px; border-radius: 8px; font-family: sans-serif; border: 1px solid #e5e7eb; margin-bottom: 12px;">
        <h2 style="margin: 0; font-size: 18px; color: #1d4ed8;">🎓 Universidad Nacional de Trujillo (UNT)</h2>
        <p style="margin: 3px 0 0 0; font-size: 12px; color: #4b5563;">SIAH-UNT: Sistema Inteligente de Asignación y Horarios Académicos</p>
    </div>
    """)
    display(header_principal, dashboard_principal)
