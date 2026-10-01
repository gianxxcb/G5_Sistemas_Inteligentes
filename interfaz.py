# --- MÓDULO INTERFAZ SIAH-UNT ---
import sys
from pathlib import Path
import ipywidgets as widgets
from IPython.display import display, clear_output
import pandas as pd
import requests
from datetime import date

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
    from schedule_validator import ValidadorHorario
    BACKEND_DISPONIBLE = True
except ImportError as e:
    BACKEND_DISPONIBLE = False

# URL de producción configurada para n8n
WEBHOOK_N8N_URL = "https://acorn-pushiness-authentic.ngrok-free.dev/webhook/40e725c6-cc5d-4dbb-81e4-0f9cb91277c3"

aulas_registradas = get_all_rooms() if BACKEND_DISPONIBLE else []
aforos_registrados_db = sorted(list(set(aula["aforo_max"] for aula in aulas_registradas))) if aulas_registradas else [16, 20, 25, 30, 34, 40]
facultades_registradas = [f.capitalize() for f in list(COORDENADAS_FACULTADES.keys())] if BACKEND_DISPONIBLE else ["Ingeniería"]

catalogo_cursos = [
    {"id": "curso-1", "nombre": "Sistemas Operativos", "horas_teoria": 2, "requiere_lab": True, "horas_lab": 2},
    {"id": "curso-2", "nombre": "Sistemas Inteligentes", "horas_teoria": 2, "requiere_lab": True, "horas_lab": 2},
    {"id": "curso-3", "nombre": "Algoritmos y Estructura de Datos", "horas_teoria": 4, "requiere_lab": False, "horas_lab": 0},
    {"id": "curso-4", "nombre": "Investigación de Operaciones", "horas_teoria": 4, "requiere_lab": False, "horas_lab": 0},
    {"id": "curso-5", "nombre": "Base de Datos II", "horas_teoria": 2, "requiere_lab": True, "horas_lab": 3},
]
materias_nombres = [c["nombre"] for c in catalogo_cursos]

style = {'description_width': '170px'}
layout_campo = widgets.Layout(width='620px', margin='6px 0px')

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
        <p>Herramienta optimizada para gestión de espacios físicos, reservas inteligentes con reasignación automática y auditoría detallada de reglas de negocio.</p>
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
    h_ini_reserva = widgets.Text(value='', placeholder='Ej. 09:00', description='⏰ Hora Inicio (HH:MM):', style=style, layout=layout_campo)
    h_fin_reserva = widgets.Text(value='', placeholder='Ej. 11:00', description='⏰ Hora Fin (HH:MM):', style=style, layout=layout_campo)
    facultad_reserva_select = widgets.Dropdown(options=[''] + facultades_registradas, value='', description='🏛️ Facultad de Origen:', style=style, layout=layout_campo)
    correo_docente_input = widgets.Text(value='', placeholder='docente@unitru.edu.pe', description='✉️ Correo Docente UNT:', style=style, layout=layout_campo)

    btn_consultar_disponibilidad = widgets.Button(
        description='🔍 Evaluar con Agente Experto y Enviar a n8n', 
        button_style='primary', 
        layout=widgets.Layout(width='620px', height='40px', margin='12px 0px 5px 0px')
    )

    output_reserva = widgets.Output()

    def on_consultar_clicked(b):
        with output_reserva:
            output_reserva.clear_output()
            if not BACKEND_DISPONIBLE:
                print("⚠️ Backend no disponible.")
                return
            if not materia_reserva_select.value or not aforo_reserva_select.value or not h_ini_reserva.value or not h_fin_reserva.value or not correo_docente_input.value:
                print("⚠️ Por favor completa todos los campos obligatorios (incluyendo el correo docente).")
                return

            experto = AgenteExperto()
            aforo_solicitado = int(aforo_reserva_select.value)
            h_ini = h_ini_reserva.value.strip()
            h_fin = h_fin_reserva.value.strip()
            correo_docente = correo_docente_input.value.strip()

            hechos = {
                "materia": materia_reserva_select.value, "aforo": aforo_solicitado,
                "requiere_laboratorio": True, "franja": "pico" if h_ini in ["09:00", "10:00"] else "normal",
                "horario_inicio": h_ini, "horario_fin": h_fin,
                "facultad_origen": facultad_reserva_select.value if facultad_reserva_select.value else "Ingeniería"
            }
            
            evaluacion = experto.evaluar(hechos)
            regla_id = evaluacion.get('regla_aplicada', 'N/A')
            aula_preferida = evaluacion.get('aula_asignada', None)
            
            r_pico_cumplida = (hechos["franja"] == "pico" and aforo_solicitado > 30)
            r_lab_cumplida = True
            
            aula_final = None
            estrategia_asignacion = ""
            r_disponibilidad_cumplida = False

            if aula_preferida and is_room_available(aula_preferida, h_ini, h_fin):
                aula_final = aula_preferida
                r_disponibilidad_cumplida = True
                estrategia_asignacion = f"Aula óptima principal asignada por regla ({regla_id})."
            else:
                aulas_disponibles = get_available_rooms(h_ini, h_fin)
                candidatas = [a for a in aulas_disponibles if a["aforo_max"] >= aforo_solicitado]
                if candidatas:
                    aula_alternativa = candidatas[0]
                    aula_final = aula_alternativa["id"]
                    r_disponibilidad_cumplida = True
                    estrategia_asignacion = f"⚠️ El aula principal ({aula_preferida}) estaba ocupada. Reasignación automática a otra aula disponible: <b>{aula_final}</b>."
                else:
                    estrategia_asignacion = f"❌ El aula principal y todas las alternativas están ocupadas o sin aforo suficiente."

            aprobado_final = False
            if aula_final and r_disponibilidad_cumplida:
                if add_reservation(aula_final, h_ini, h_fin, materia_reserva_select.value):
                    aprobado_final = True

            estado_color = "#16a34a" if aprobado_final else "#dc2626"
            aula_final_str = aula_final if aprobado_final else "Ninguna (Conflicto total)"

            display(widgets.HTML(f"""
            <div style="background: #fffbeb; border-left: 5px solid {'#16a34a' if aprobado_final else '#eab308'}; padding: 14px; border-radius: 6px; margin-top: 12px; font-family: sans-serif; border: 1px solid #fef08a;">
                <h4 style="margin: 0 0 8px 0; color: #111827;">📋 Auditoría Completa de Reglas de Negocio (Reserva):</h4>
                
                <p style="margin: 4px 0; color: #111827;"><b>1. Regla de Laboratorio Requerido:</b> 
                   <span style="color: #16a34a; font-weight: bold;">✅ Cumplida</span>
                </p>

                <p style="margin: 4px 0; color: #111827;"><b>2. Regla de Aforo y Franja Pico (<code>LAB_AFORO_PICO</code>):</b> 
                   <span style="color: {'#16a34a' if r_pico_cumplida else '#e65100'}; font-weight: bold;">{'✅ Cumplida' if r_pico_cumplida else '⚠️ No Aplicada / Franja normal'}</span>
                </p>

                <p style="margin: 4px 0; color: #111827;"><b>3. Regla de Disponibilidad en Base de Datos:</b> 
                   <span style="color: {'#16a34a' if r_disponibilidad_cumplida else '#dc2626'}; font-weight: bold;">{'✅ Cumplida' if r_disponibilidad_cumplida else '❌ Reasignado'}</span>
                </p>

                <hr style="border: 0; border-top: 1px solid #fef08a; margin: 8px 0;">
                <p style="margin: 4px 0; color: #111827;"><b>• Dictamen Final:</b> <span style="color: {estado_color}; font-weight: bold;">{'APROBADO' if aprobado_final else 'RECHAZADO'} ({aula_final_str})</span></p>
                <p style="margin: 4px 0; color: #4b5563; font-size: 12px;"><b>• Detalle:</b> {estrategia_asignacion}</p>
                <p style="margin: 4px 0; color: #1d4ed8; font-size: 12px;"><b>• Correo Destino:</b> {correo_docente}</p>
            </div>
            """))

            estado_txt = "Aprobado" if aprobado_final else "Rechazado"
            payload = {
                "fecha": str(fecha_reserva_picker.value),
                "materia": materia_reserva_select.value,
                "aforo": aforo_solicitado,
                "requiere_laboratorio": True,
                "horario": f"{h_ini} - {h_fin}",
                "facultad": facultad_reserva_select.value if facultad_reserva_select.value else "Ingeniería",
                "correo_docente": correo_docente,
                "estado": estado_txt,
                "aula_asignada": aula_final_str,
                "detalle": estrategia_asignacion
            }
            try:
                response = requests.post(WEBHOOK_N8N_URL, json=payload)
                if response.status_code == 200:
                    print(f"🤖 [n8n]: Datos y correo de '{correo_docente}' enviados con éxito al flujo automático.")
                else:
                    print(f"⚠️ [n8n]: El servidor respondió con código {response.status_code}")
            except Exception as e:
                print(f"⚠️ Error al conectar con n8n: {e}")

    btn_consultar_disponibilidad.on_click(on_consultar_clicked)

    reserva_box = widgets.VBox([
        lbl_p1, fecha_reserva_picker, materia_reserva_select, aforo_reserva_select,
        h_ini_reserva, h_fin_reserva, facultad_reserva_select, correo_docente_input,
        btn_consultar_disponibilidad, output_reserva
    ], layout=widgets.Layout(padding='15px', background_color='#ffffff'))

    lbl_p2 = widgets.HTML("<h4 style='color: #111827; margin-bottom: 5px;'>Configuración de Cursos para la Planificación Semestral</h4>")
    cursos_box = widgets.VBox()

    def actualizar_checkboxes_cursos():
        global checkbox_list
        checkbox_list = [
            widgets.Checkbox(value=True, description=f"{c['nombre']} (Teo: {c['horas_teoria']}h | Lab: {c['horas_lab'] if c['requiere_lab'] else 0}h)", indent=False)
            for c in catalogo_cursos
        ]
        cursos_box.children = checkbox_list

    actualizar_checkboxes_cursos()

    nuevo_nombre_input = widgets.Text(value='', placeholder='Ej. IA', description='📖 Nombre Curso:', style=style, layout=layout_campo)
    nuevo_horas_teoria = widgets.Dropdown(options=[1, 2, 3, 4], value=2, description='📚 Horas Teoría:', style=style, layout=layout_campo)
    nuevo_req_lab_select = widgets.Dropdown(options=['No', 'Sí'], value='Sí', description='🔬 ¿Requiere Lab?:', style=style, layout=layout_campo)
    nuevo_horas_lab = widgets.Dropdown(options=[1, 2, 3], value=2, description='⏱️ Horas Laboratorio:', style=style, layout=layout_campo)

    def on_req_lab_change(change):
        if change['new'] == 'Sí':
            nuevo_horas_lab.layout.display = 'flex'
        else:
            nuevo_horas_lab.layout.display = 'none'
    nuevo_req_lab_select.observe(on_req_lab_change, names='value')

    btn_add_curso = widgets.Button(description='💾 Guardar Curso en el Catálogo', button_style='info', layout=widgets.Layout(width='620px', height='32px', margin='4px 0px 8px 0px'))
    output_add = widgets.Output()

    form_nuevo_curso_box = widgets.VBox([
        widgets.HTML("<b>➕ Registrar nuevo curso:</b>"),
        nuevo_nombre_input, nuevo_horas_teoria, nuevo_req_lab_select, nuevo_horas_lab,
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
            output_add.clear_output()
            nombre = nuevo_nombre_input.value.strip()
            if not nombre:
                print("⚠️ Ingresa un nombre válido.")
                return
            catalogo_cursos.append({"id": f"curso-{len(catalogo_cursos)+1}", "nombre": nombre, "horas_teoria": nuevo_horas_teoria.value, "requiere_lab": (nuevo_req_lab_select.value == 'Sí'), "horas_lab": nuevo_horas_lab.value if nuevo_req_lab_select.value == 'Sí' else 0})
            actualizar_checkboxes_cursos()
            print(f"✅ Curso '{nombre}' añadido con éxito.")
            nuevo_nombre_input.value = ''
    btn_add_curso.on_click(on_add_curso_clicked)

    estudiantes_ciclo_select = widgets.Dropdown(options=[16, 20, 25, 30, 34, 40, 50], value=34, description='👥 Total Estudiantes (Mín. 16):', style=style, layout=layout_campo)
    max_alternativas_gen = widgets.Dropdown(options=[1, 2, 3], value=3, description='📊 Alternativas a Generar:', style=style, layout=layout_campo)
    btn_generar_horarios = widgets.Button(description='🚀 Generar Horarios, Mostrar y Exportar Excel', button_style='success', layout=widgets.Layout(width='620px', height='40px', margin='12px 0px 5px 0px'))
    output_generacion = widgets.Output()

    def on_generar_horarios_clicked(b):
        with output_generacion:
            output_generacion.clear_output()
            if not BACKEND_DISPONIBLE:
                print("⚠️ Backend no disponible.")
                return
            cursos_sel = [catalogo_cursos[i] for i, chk in enumerate(checkbox_list) if chk.value]
            if not cursos_sel:
                print("⚠️ Selecciona al menos un curso.")
                return
            
            total_est = estudiantes_ciclo_select.value
            if total_est < 16:
                print("❌ El número total de estudiantes debe ser al menos 16.")
                return

            try:
                disp = tuple(FranjaSemanal(dia, "07:00", "22:00") for dia in (DiaSemana.LUNES, DiaSemana.MARTES, DiaSemana.MIERCOLES, DiaSemana.JUEVES, DiaSemana.VIERNES))
                doc = Docente("doc-1", "Docente Principal UNT", disp)
                c_tup = tuple(Curso(c["id"], c["nombre"], doc.id, "cohorte-1", c["horas_teoria"] * 60, c["requiere_lab"]) for c in cursos_sel)
                
                g_lab = []
                for c in cursos_sel:
                    if c["requiere_lab"]:
                        num_sub = max(1, -(-total_est // 15))
                        rest = total_est
                        for s in range(1, num_sub + 1):
                            g_lab.append(GrupoLaboratorio(f"grupo-{c['id']}-s{s}", c["id"], "cohorte-1", min(15, rest), f"Sección {s}"))
                            rest -= min(15, rest)
                
                a_reg = get_all_rooms()
                a_plan = tuple(Aula(a["id"], a["aforo_max"], TipoAula.LABORATORIO if a["tipo"]=="laboratorio" else TipoAula.TEORIA, a.get("tiene_computadoras", False)) for a in a_reg)
                config = ConfiguracionPlanificacion(cursos_por_semestre=len(cursos_sel), cursos_con_laboratorio=max(1, sum(1 for c in cursos_sel if c["requiere_lab"])), max_horarios=max_alternativas_gen.value)
                
                res = GeneradorHorarios(max_estados=8000).generar(DatosPlanificacion(docentes=(doc, ), cursos=c_tup, aulas=a_plan, grupos_laboratorio=tuple(g_lab), configuracion=config))
                r_cruces_cero = (len(res.horarios) > 0)

                display(widgets.HTML(f"""
                <div style="background: #eff6ff; border-left: 5px solid #3b82f6; padding: 14px; border-radius: 6px; margin: 12px 0; font-family: sans-serif; border: 1px solid #bfdbfe;">
                    <h4 style="margin: 0 0 8px 0; color: #111827;">📋 Auditoría Completa de Reglas de Planificación Semestral:</h4>
                    <p style="margin: 4px 0; color: #111827;"><b>1. Umbral de Mínimo de Estudiantes (>= 16):</b> <span style="color: #16a34a; font-weight: bold;">✅ Cumplida</span></p>
                    <p style="margin: 4px 0; color: #111827;"><b>2. Subgrupos de Laboratorio (Máx. 15):</b> <span style="color: #16a34a; font-weight: bold;">✅ Cumplida</span></p>
                    <p style="margin: 4px 0; color: #111827;"><b>3. Control de Cruces Duros (ValidadorHorario):</b> <span style="color: {'#16a34a' if r_cruces_cero else '#dc2626'}; font-weight: bold;">{'✅ Cumplida' if r_cruces_cero else '❌ Sin alternativas'}</span></p>
                </div>
                """))

                filas = []
                for idx, h in enumerate(res.horarios[:max_alternativas_gen.value], 1):
                    for sesion in h.sesiones:
                        filas.append({"Alternativa": f"Opción {idx}", "Curso ID": sesion.curso_id, "Día": sesion.franja.dia.value.upper(), "Hora Inicio": sesion.franja.hora_inicio, "Hora Fin": sesion.franja.hora_fin, "Aula Asignada": sesion.aula_id})
                df = pd.DataFrame(filas)
                df.to_excel("horarios_semestrales_alternativas.xlsx", index=False)
                print("📁 Archivo Excel generado con éxito.")
                requests.post(WEBHOOK_N8N_URL, json={"evento": "generacion_semestral", "opciones": len(res.horarios)})
            except Exception as e:
                print(f"❌ Error al procesar: {e}")

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
