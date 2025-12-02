import streamlit as st
import json
import os
import re
import sys
from datetime import timedelta, date, datetime
import io
import base64
from streamlit_quill import st_quill

# --- ReportLab Imports ---
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.lib import colors

# --- Configuration ---
st.set_page_config(page_title="Planeador Docente IMM", page_icon="📝", layout="wide")

# --- Helper Functions ---

def _get_full_path(path):
    """
    Get the absolute path for a file, handling both script execution and PyInstaller (if used later).
    Checks current directory first.
    """
    cwd_path = os.path.join(os.getcwd(), path)
    if os.path.exists(cwd_path):
        return cwd_path
    
    alt_path = os.path.join(r"C:\Users\jaime\Documents\My planer", path)
    if os.path.exists(alt_path):
        return alt_path

    try:
        base = sys._MEIPASS
    except AttributeError:
        base = os.path.dirname(os.path.abspath(__file__))
    
    full = os.path.join(base, path)
    return full

def get_image_base64(path):
    """Encodes an image to base64 for embedding in HTML."""
    full_path = _get_full_path(path)
    if os.path.exists(full_path):
        with open(full_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    return ""

def html_to_reportlab(html_text):
    """
    Convert Quill HTML to ReportLab XML tags.
    """
    if not html_text:
        return ""
    
    # Remove <p> tags, replacing closing </p> with <br/>
    text = html_text.replace("</p>", "<br/>").replace("<p>", "")
    
    # Bold - Handle <strong>, <b>, and span with font-weight: bold
    text = re.sub(r'<span[^>]*style="[^"]*font-weight:\s*bold[^"]*"[^>]*>(.*?)</span>', r'<b>\1</b>', text, flags=re.IGNORECASE)
    text = text.replace("<strong>", "<b>").replace("</strong>", "</b>")
    
    # Italic - Handle <em>, <i>, and span with font-style: italic
    text = re.sub(r'<span[^>]*style="[^"]*font-style:\s*italic[^"]*"[^>]*>(.*?)</span>', r'<i>\1</i>', text, flags=re.IGNORECASE)
    text = text.replace("<em>", "<i>").replace("</em>", "</i>")
    
    # Underline
    text = text.replace("<u>", "<u>").replace("</u>", "</u>")
    
    # Lists
    text = text.replace("<ul>", "").replace("</ul>", "")
    text = text.replace("<ol>", "").replace("</ol>", "")
    text = text.replace("<li>", "<br/>• ").replace("</li>", "")
    
    # Clean up initial <br/> if any
    if text.startswith("<br/>"):
        text = text[5:]
            
    return text

def _embed_image_to_pdf(path, content_list, page_width):
    if path and os.path.exists(path):
        try:
            img = RLImage(path, width=page_width, height=4*inch, kind='proportional')
            content_list.append(img)
            content_list.append(Spacer(1, 0.1 * inch))
        except Exception as e:
            content_list.append(Paragraph(f"<i>[Error al cargar imagen: {os.path.basename(path)}]</i>", getSampleStyleSheet()['Italic']))

def parse_date(date_str):
    """Parses a date string trying ISO format first, then DD/MM/YYYY."""
    if not date_str:
        return date.today()
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        try:
            return datetime.strptime(date_str, "%d/%m/%Y").date()
        except ValueError:
            return date.today()

# --- Initialization & State ---

def init_session_state():
    defaults = {
        "docente_titulo": "Dr.",
        "docente_nombre": "",
        "curso_grado": "1ro",
        "curso_grupos": [],
        "curso_materia": "Matematicas",
        "curso_campo": "Lenguajes",
        "plan_metodologia": "Seleccione metodología",
        "plan_fecha_inicio": date.today(),
        "plan_fecha_fin": date.today(),
        "plan_dias": [],
        "plan_eje1": "Seleccione eje",
        "plan_eje2": "Seleccione eje",
        "plan_eje3": "Seleccione eje",
        "plan_disc1": "Seleccione materia",
        "plan_disc2": "Seleccione materia",
        "plan_disc3": "Seleccione materia",
        "text_problematica": "",
        "text_pda": "",
        "text_objetivos": "",
        "text_perfiles": "",
        "text_producto": "",
        "abpj_presentacion": "",
        "abpj_recoleccion": "",
        "abpj_formulacion": "",
        "abpj_organizacion": "",
        "abpj_experiencia": "",
        "abpj_resultados": "",
        "abpj_materiales": "",
        "abpj_evaluacion": "",
        "abpj_rubrica_path": None,
        "daily_plan_data": {},
        "last_loaded_file_id": None,
        "quill_key_suffix": 0 # Force Quill refresh
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# --- Lists ---
LISTA_MATERIAS = ["Matematicas", "Matematicas I", "Matematicas II", "Matematicas III", "Español", "Español I", "Español II", "Español III", "Educación Civica y Etica", "Educación Civica y Etica I", "Educación Civica y Etica II", "Educación Civica y Etica III", "Ingles", "Ingles I", "Ingles II", "Ingles III", "Informatica", "Informatica I", "Informatica II", "Informatica III", "Historia", "Historia I", "Historia II", "Historia III", "Educación Fisica", "Artes", "Ciencias", "Biología", "Fisica", "Quimica"]
LISTA_METODOLOGIA = ["Seleccione metodología", "Aprendizaje Basado en Proyectos (ABPj)", "Aprendizaje Basado en Problemas (ABP)", "STEAM", "Clase invertida (Flipped Classroom)", "Aprendizaje Servicio (ApS)", "Gamificación", "Aprendizaje autodirigido", "Aprendizaje situado", "Aprendizaje entre pares"]
LISTA_EJES = ["Seleccione eje", "Pensamiento Crítico", "Interculturalidad Crítica", "Igualdad de Género", "Vida Saludable", "Apropiación de las Culturas a través de la Lectura y la Escritura", "Artes y Experiencias Estéticas", "Inclusión"]
LISTA_CAMPOS = ["Lenguajes", "Saberes y Pensamiento Científico", "Ética, Naturaleza y Sociedades", "De lo Humano y lo Comunitario"]
LISTA_GRUPOS = ["A", "B", "C", "D", "E", "F"]
LISTA_DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

# --- Floating Help Button CSS ---
help_img_b64 = get_image_base64("Help.png")
gemini_img_b64 = get_image_base64("Gemini.png")
deepseek_img_b64 = get_image_base64("DeepSeek.png")

st.markdown(f"""
<style>
.floating-container {{
    position: fixed;
    bottom: 20px;
    right: 20px;
    z-index: 1000;
    display: flex;
    flex-direction: column-reverse;
    align-items: center;
    gap: 10px;
}}
.help-button {{
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background-image: url('data:image/png;base64,{help_img_b64}');
    background-size: cover;
    cursor: pointer;
    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    transition: transform 0.3s;
}}
.help-button:hover {{
    transform: scale(1.1);
}}
.popup-icons {{
    display: none;
    flex-direction: column;
    gap: 10px;
    background: white;
    padding: 10px;
    border-radius: 10px;
    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    margin-bottom: 10px;
}}
.floating-container:hover .popup-icons {{
    display: flex;
}}
.icon-link img {{
    width: 40px;
    height: 40px;
    border-radius: 5px;
    transition: transform 0.2s;
}}
.icon-link img:hover {{
    transform: scale(1.1);
}}
</style>

<div class="floating-container">
    <div class="help-button"></div>
    <div class="popup-icons">
        <a href="https://gemini.google.com/" target="_blank" class="icon-link" title="Ir a Gemini">
            <img src="data:image/png;base64,{gemini_img_b64}" alt="Gemini">
        </a>
        <a href="https://www.deepseek.com/" target="_blank" class="icon-link" title="Ir a DeepSeek">
            <img src="data:image/png;base64,{deepseek_img_b64}" alt="DeepSeek">
        </a>
    </div>
</div>
""", unsafe_allow_html=True)

# --- Sidebar Actions ---
with st.sidebar:
    st.header("Acciones")
    
    uploaded_file = st.file_uploader("Cargar Planeación (JSON)", type="json")
    
    if uploaded_file is not None:
        file_id = f"{uploaded_file.name}_{uploaded_file.size}"
        
        if file_id != st.session_state.last_loaded_file_id:
            try:
                data = json.load(uploaded_file)
                docente = data.get("docente", {})
                st.session_state.docente_titulo = docente.get("titulo", "Dr.")
                st.session_state.docente_nombre = docente.get("nombre", "")
                
                curso = data.get("curso", {})
                st.session_state.curso_grado = curso.get("grado", "1ro")
                st.session_state.curso_grupos = curso.get("grupos", [])
                st.session_state.curso_materia = curso.get("materia", "Matematicas")
                st.session_state.curso_campo = curso.get("campo", "Lenguajes")
                
                plan = data.get("planeacion", {})
                st.session_state.plan_metodologia = plan.get("metodologia", "Seleccione metodología")
                
                # Use new parse_date function
                st.session_state.plan_fecha_inicio = parse_date(plan.get("fecha_inicio"))
                st.session_state.plan_fecha_fin = parse_date(plan.get("fecha_fin"))
                
                st.session_state.plan_dias = plan.get("dias_planeados", [])
                st.session_state.plan_eje1 = plan.get("eje1", "Seleccione eje")
                st.session_state.plan_eje2 = plan.get("eje2", "Seleccione eje")
                st.session_state.plan_eje3 = plan.get("eje3", "Seleccione eje")
                st.session_state.plan_disc1 = plan.get("disciplina1", "Seleccione materia")
                st.session_state.plan_disc2 = plan.get("disciplina2", "Seleccione materia")
                st.session_state.plan_disc3 = plan.get("disciplina3", "Seleccione materia")
                
                st.session_state.text_problematica = plan.get("problematica", "")
                st.session_state.text_pda = plan.get("pda", "")
                st.session_state.text_objetivos = plan.get("objetivos", "")
                st.session_state.text_perfiles = plan.get("perfiles", "")
                st.session_state.text_producto = plan.get("producto", "")
                
                abpj = plan.get("secuencia_abpj", {})
                st.session_state.abpj_presentacion = abpj.get("presentacion", "")
                st.session_state.abpj_recoleccion = abpj.get("recoleccion", "")
                st.session_state.abpj_formulacion = abpj.get("formulacion", "")
                st.session_state.abpj_organizacion = abpj.get("organizacion", "")
                st.session_state.abpj_experiencia = abpj.get("experiencia", "")
                st.session_state.abpj_resultados = abpj.get("resultados", "")
                st.session_state.abpj_materiales = abpj.get("materiales", "")
                st.session_state.abpj_evaluacion = abpj.get("evaluacion", "")
                
                daily_list = plan.get("secuencia_diaria", [])
                st.session_state.daily_plan_data = {item["dia_nombre"]: item for item in daily_list}
                
                st.session_state.last_loaded_file_id = file_id
                st.session_state.quill_key_suffix += 1 # Force Quill refresh
                st.success("Planeación cargada correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al cargar: {e}")

    def get_current_data():
        daily_sequence = []
        start = st.session_state.plan_fecha_inicio
        end = st.session_state.plan_fecha_fin
        active_days = st.session_state.plan_dias
        dias_map = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes"}
        
        if start <= end:
            delta = end - start
            for i in range(delta.days + 1):
                current = start + timedelta(days=i)
                wd = current.weekday()
                if wd in dias_map:
                    dia_nombre = dias_map[wd]
                    if dia_nombre in active_days:
                        key = f"{dia_nombre} {current.strftime('%d/%m/%Y')}"
                        if key in st.session_state.daily_plan_data:
                            daily_sequence.append(st.session_state.daily_plan_data[key])
                        else:
                            daily_sequence.append({
                                "dia_nombre": key, "inicio": "", "desarrollo": "", "cierre": "",
                                "materiales": "", "evaluacion": "", "rubrica_path": ""
                            })

        return {
            "docente": {
                "titulo": st.session_state.docente_titulo,
                "nombre": st.session_state.docente_nombre
            },
            "curso": {
                "grado": st.session_state.curso_grado,
                "grupos": st.session_state.curso_grupos,
                "materia": st.session_state.curso_materia,
                "campo": st.session_state.curso_campo
            },
            "planeacion": {
                "metodologia": st.session_state.plan_metodologia,
                "fecha_inicio": st.session_state.plan_fecha_inicio.isoformat(),
                "fecha_fin": st.session_state.plan_fecha_fin.isoformat(),
                "dias_planeados": st.session_state.plan_dias,
                "problematica": st.session_state.text_problematica,
                "pda": st.session_state.text_pda,
                "objetivos": st.session_state.text_objetivos,
                "perfiles": st.session_state.text_perfiles,
                "producto": st.session_state.text_producto,
                "eje1": st.session_state.plan_eje1,
                "eje2": st.session_state.plan_eje2,
                "eje3": st.session_state.plan_eje3,
                "disciplina1": st.session_state.plan_disc1,
                "disciplina2": st.session_state.plan_disc2,
                "disciplina3": st.session_state.plan_disc3,
                "secuencia_abpj": {
                    "presentacion": st.session_state.abpj_presentacion,
                    "recoleccion": st.session_state.abpj_recoleccion,
                    "formulacion": st.session_state.abpj_formulacion,
                    "organizacion": st.session_state.abpj_organizacion,
                    "experiencia": st.session_state.abpj_experiencia,
                    "resultados": st.session_state.abpj_resultados,
                    "materiales": st.session_state.abpj_materiales,
                    "evaluacion": st.session_state.abpj_evaluacion,
                    "rubrica_path": st.session_state.abpj_rubrica_path
                },
                "secuencia_diaria": daily_sequence
            }
        }

    json_data = json.dumps(get_current_data(), indent=4, ensure_ascii=False)
    st.download_button("Guardar Planeación (JSON)", data=json_data, file_name="planeacion.json", mime="application/json")


# --- Main UI ---

col1, col2, col3 = st.columns([1, 3, 1])
with col1:
    logo_imm = _get_full_path("LOGO imm.png")
    if os.path.exists(logo_imm):
        st.image(logo_imm, width=150)
with col2:
    st.markdown("""
    <div style='text-align: center;'>
        <h3>Secretaría De Educación Pública</h3>
        <h4>Dirección De Educación Secundaria</h4>
        <h4>Instituto Mexicano Madero</h4>
        <h2>Planeaciones Docente</h2>
    </div>
    """, unsafe_allow_html=True)
with col3:
    logo_sep = _get_full_path("logo_sep.png")
    if os.path.exists(logo_sep):
        st.image(logo_sep, width=180)

st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs(["Docente y Curso", "Detalles Generales", "Contenido", "Secuencia Didáctica"])

with tab1:
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        st.subheader("Información Docente")
        st.selectbox("Título", ["Dr.", "Dra.", "Mtro.", "Mtra.", "Prof.", "Pasante."], key="docente_titulo")
        st.text_input("Nombre Completo", key="docente_nombre")
    
    with col_d2:
        st.subheader("Información Curso")
        c1, c2 = st.columns(2)
        with c1:
            st.selectbox("Grado", ["1ro", "2do", "3ro"], key="curso_grado")
        with c2:
            st.multiselect("Grupos", LISTA_GRUPOS, key="curso_grupos")
        
        st.selectbox("Materia", LISTA_MATERIAS, key="curso_materia")
        st.selectbox("Campo Formativo", LISTA_CAMPOS, key="curso_campo")

with tab2:
    st.subheader("Detalles de la Planeación")
    st.selectbox("Metodología", LISTA_METODOLOGIA, key="plan_metodologia")
    
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.date_input("Fecha Inicio", format="DD/MM/YYYY", key="plan_fecha_inicio")
    with col_t2:
        st.date_input("Fecha Fin", format="DD/MM/YYYY", key="plan_fecha_fin")
    
    st.multiselect("Días de Clase", LISTA_DIAS, key="plan_dias")
    
    st.markdown("**Ejes Articuladores**")
    c_e1, c_e2, c_e3 = st.columns(3)
    with c_e1: st.selectbox("Eje 1", LISTA_EJES, key="plan_eje1")
    with c_e2: st.selectbox("Eje 2", LISTA_EJES, key="plan_eje2")
    with c_e3: st.selectbox("Eje 3", LISTA_EJES, key="plan_eje3")
    
    st.markdown("**Materias Vinculadas**")
    c_m1, c_m2, c_m3 = st.columns(3)
    with c_m1: st.selectbox("Materia 1", ["Seleccione materia"] + LISTA_MATERIAS, key="plan_disc1")
    with c_m2: st.selectbox("Materia 2", ["Seleccione materia"] + LISTA_MATERIAS, key="plan_disc2")
    with c_m3: st.selectbox("Materia 3", ["Seleccione materia"] + LISTA_MATERIAS, key="plan_disc3")

with tab3:
    st.subheader("Contenido Pedagógico")
    # Quill Editor Configuration
    toolbar = [
        ['bold', 'italic', 'underline'],
        [{'list': 'ordered'}, {'list': 'bullet'}]
    ]
    
    # Use key suffix to force refresh
    ks = st.session_state.quill_key_suffix
    
    st.session_state.text_problematica = st_quill(value=st.session_state.text_problematica, placeholder="Problemática Contextual", toolbar=toolbar, key=f"quill_prob_{ks}")
    st.session_state.text_pda = st_quill(value=st.session_state.text_pda, placeholder="PDA", toolbar=toolbar, key=f"quill_pda_{ks}")
    st.session_state.text_objetivos = st_quill(value=st.session_state.text_objetivos, placeholder="Objetivos", toolbar=toolbar, key=f"quill_obj_{ks}")
    st.session_state.text_perfiles = st_quill(value=st.session_state.text_perfiles, placeholder="Perfiles de Egreso", toolbar=toolbar, key=f"quill_perf_{ks}")
    st.session_state.text_producto = st_quill(value=st.session_state.text_producto, placeholder="Producto Final", toolbar=toolbar, key=f"quill_prod_{ks}")

with tab4:
    st.subheader("Secuencia Didáctica")
    toolbar_simple = [['bold', 'italic', 'underline'], [{'list': 'bullet'}]]
    ks = st.session_state.quill_key_suffix
    
    if "ABPj" in st.session_state.plan_metodologia:
        st.markdown("### Aprendizaje Basado en Proyectos (ABPj)")
        
        col_abp1, col_abp2 = st.columns(2)
        with col_abp1:
            st.session_state.abpj_presentacion = st_quill(value=st.session_state.abpj_presentacion, placeholder="1. Presentación", toolbar=toolbar_simple, key=f"q_abpj_1_{ks}")
            st.session_state.abpj_formulacion = st_quill(value=st.session_state.abpj_formulacion, placeholder="3. Formulación del Problema", toolbar=toolbar_simple, key=f"q_abpj_3_{ks}")
            st.session_state.abpj_experiencia = st_quill(value=st.session_state.abpj_experiencia, placeholder="5. Vivamos la Experiencia", toolbar=toolbar_simple, key=f"q_abpj_5_{ks}")
            st.session_state.abpj_materiales = st_quill(value=st.session_state.abpj_materiales, placeholder="Materiales", toolbar=toolbar_simple, key=f"q_abpj_mat_{ks}")
        
        with col_abp2:
            st.session_state.abpj_recoleccion = st_quill(value=st.session_state.abpj_recoleccion, placeholder="2. Recolección", toolbar=toolbar_simple, key=f"q_abpj_2_{ks}")
            st.session_state.abpj_organizacion = st_quill(value=st.session_state.abpj_organizacion, placeholder="4. Organización del Proyecto", toolbar=toolbar_simple, key=f"q_abpj_4_{ks}")
            st.session_state.abpj_resultados = st_quill(value=st.session_state.abpj_resultados, placeholder="6. Resultados y Análisis", toolbar=toolbar_simple, key=f"q_abpj_6_{ks}")
            
            st.markdown("#### Evaluación")
            st.session_state.abpj_evaluacion = st_quill(value=st.session_state.abpj_evaluacion, placeholder="Evaluación", toolbar=toolbar_simple, key=f"q_abpj_eval_{ks}")
            uploaded_rubric = st.file_uploader("Anexar Rúbrica (Imagen)", type=["png", "jpg", "jpeg"], key="abpj_rubric_uploader")
            if uploaded_rubric:
                temp_path = f"temp_rubric_abpj_{uploaded_rubric.name}"
                with open(temp_path, "wb") as f:
                    f.write(uploaded_rubric.getbuffer())
                st.session_state.abpj_rubrica_path = os.path.abspath(temp_path)
                st.success(f"Rúbrica cargada: {uploaded_rubric.name}")
            
            if st.session_state.abpj_rubrica_path:
                st.caption(f"Rúbrica actual: {os.path.basename(st.session_state.abpj_rubrica_path)}")

    elif st.session_state.plan_metodologia != "Seleccione metodología":
        st.markdown(f"### Planeación Diaria ({st.session_state.plan_metodologia})")
        
        start = st.session_state.plan_fecha_inicio
        end = st.session_state.plan_fecha_fin
        active_days = st.session_state.plan_dias
        dias_map = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes"}
        
        dias_generados = []
        if start <= end:
            delta = end - start
            for i in range(delta.days + 1):
                current = start + timedelta(days=i)
                wd = current.weekday()
                if wd in dias_map:
                    dia_nombre = dias_map[wd]
                    if dia_nombre in active_days:
                        dias_generados.append((current, dia_nombre))
        
        if not dias_generados:
            st.warning("No hay días hábiles seleccionados en el rango de fechas.")
        else:
            for i, (fecha_obj, dia_nombre) in enumerate(dias_generados):
                fecha_str = fecha_obj.strftime("%d/%m/%Y")
                key_base = f"{dia_nombre} {fecha_str}"
                
                if key_base not in st.session_state.daily_plan_data:
                    st.session_state.daily_plan_data[key_base] = {
                        "dia_nombre": key_base, "inicio": "", "desarrollo": "", "cierre": "",
                        "materiales": "", "evaluacion": "", "rubrica_path": ""
                    }
                
                day_data = st.session_state.daily_plan_data[key_base]
                
                with st.expander(f"Sesión {i+1}: {key_base}", expanded=True):
                    c1, c2, c3 = st.columns(3)
                    with c1: day_data["inicio"] = st_quill(value=day_data["inicio"], placeholder="Inicio", key=f"inicio_{key_base}_{ks}", toolbar=toolbar_simple)
                    with c2: day_data["desarrollo"] = st_quill(value=day_data["desarrollo"], placeholder="Desarrollo", key=f"desarrollo_{key_base}_{ks}", toolbar=toolbar_simple)
                    with c3: day_data["cierre"] = st_quill(value=day_data["cierre"], placeholder="Cierre", key=f"cierre_{key_base}_{ks}", toolbar=toolbar_simple)
                    
                    c4, c5 = st.columns(2)
                    with c4: day_data["materiales"] = st_quill(value=day_data["materiales"], placeholder="Materiales", key=f"mat_{key_base}_{ks}", toolbar=toolbar_simple)
                    with c5: 
                        day_data["evaluacion"] = st_quill(value=day_data["evaluacion"], placeholder="Evaluación", key=f"eval_{key_base}_{ks}", toolbar=toolbar_simple)
                        u_rubric = st.file_uploader("Rúbrica", type=["png", "jpg"], key=f"up_{key_base}")
                        if u_rubric:
                            t_path = f"temp_rubric_{i}_{u_rubric.name}"
                            with open(t_path, "wb") as f: f.write(u_rubric.getbuffer())
                            day_data["rubrica_path"] = os.path.abspath(t_path)
                            st.success("Imagen cargada")

# --- AI Prompt Generation ---
st.markdown("---")
if st.button("✨ Generar Prompt IA"):
    d = get_current_data()
    p_data = d['planeacion']
    
    grado = d['curso']['grado']
    edad = "11 a 12 años" if "1" in grado else "12 a 13 años" if "2" in grado else "13 a 15 años"
    
    ejes = ", ".join([e for e in [p_data['eje1'], p_data['eje2'], p_data['eje3']] if e and "Seleccione" not in e])
    disc = ", ".join([x for x in [p_data['disciplina1'], p_data['disciplina2'], p_data['disciplina3']] if x and "Seleccione" not in x])
    dias_txt = ", ".join(p_data['dias_planeados'])
    
    # Clean HTML for prompt (basic strip)
    def clean_html(t): return re.sub(r'<[^>]+>', '', t) if t else ""
    
    prompt = f"Actúa como un docente experto de secundaria en México (SEP, Nueva Escuela Mexicana).\n\n"
    prompt += f"Genera una planeación didáctica para la materia de **{d['curso']['materia']}**.\n"
    prompt += f"- **Grado:** {grado} (Alumnos de aprox. {edad}).\n"
    prompt += f"- **Campo Formativo:** {d['curso']['campo']}.\n"
    prompt += f"- **Metodología:** {p_data['metodologia']}.\n"
    prompt += f"- **Temporalidad:** Del {p_data['fecha_inicio']} al {p_data['fecha_fin']}.\n"
    prompt += f"- **Días de clase:** {dias_txt}.\n"
    if ejes: prompt += f"- **Ejes Articuladores:** {ejes}.\n"
    if disc: prompt += f"- **Materias vinculadas:** {disc}.\n"
    
    prompt += f"- **Problemática Contextual:** {clean_html(p_data['problematica']) or 'No definida. Propón una relevante.'}\n"
    prompt += f"- **PDA:** {clean_html(p_data['pda']) or 'Propón el PDA oficial más adecuado.'}\n"
    prompt += f"- **Objetivos:** {clean_html(p_data['objetivos']) or 'Propón objetivos de aprendizaje adecuados.'}\n"
    prompt += f"- **Perfil de Egreso:** {clean_html(p_data['perfiles']) or 'Propón los rasgos del perfil de egreso que se favorecen.'}\n"
    prompt += f"- **Producto Final:** {clean_html(p_data['producto']) or 'Propón un producto creativo.'}\n"
    
    if "Proyectos" in p_data['metodologia']:
        prompt += "\nDesarrolla la secuencia didáctica siguiendo las fases de **ABPj** (Presentación, Recolección, Formulación, Organización, Vivamos la experiencia, Resultados)."
    else:
        prompt += "\nDesarrolla la secuencia didáctica como una **Planeación Diaria** (Inicio, Desarrollo, Cierre) para cada día."

    prompt += "\nEn la secuencia didáctica, incluye para cada actividad/fase los **Materiales y Recursos** necesarios, así como una propuesta de **Evaluación** (sugiere Lista de Cotejo o Rúbrica si es necesario)."

    st.code(prompt, language="text")
    st.info("Copia el texto de arriba y pégalo en tu IA favorita (ChatGPT, Gemini, DeepSeek).")

# --- PDF Generation ---
def generate_pdf_bytes():
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), topMargin=0.5*inch, bottomMargin=0.5*inch, leftMargin=0.5*inch, rightMargin=0.5*inch)
    elements = []
    styles = getSampleStyleSheet()
    
    ruta_logo_imm = _get_full_path("LOGO imm.png")
    ruta_logo_sep = _get_full_path("logo_sep.png")
    
    if os.path.exists(ruta_logo_imm):
        logo_imm_rl = RLImage(ruta_logo_imm, width=1.5*inch, height=0.75*inch, kind='proportional')
    else:
        logo_imm_rl = Paragraph("[LOGO IMM]", styles['Normal'])
        
    if os.path.exists(ruta_logo_sep):
        logo_sep_rl = RLImage(ruta_logo_sep, width=1.8*inch, height=0.75*inch, kind='proportional')
    else:
        logo_sep_rl = Paragraph("[LOGO SEP]", styles['Normal'])

    header_paragraphs = [Paragraph(t, ParagraphStyle(name='HeaderCenter', alignment=TA_CENTER, fontName='Helvetica-Bold', fontSize=11, leading=14)) for t in ["Secretaría De Educación Pública", "Dirección De Educación Secundaria", "Instituto Mexicano Madero", "Planeaciones Docente"]]
    
    page_width = landscape(letter)[0] - 1*inch
    col_widths_header = [2*inch, page_width - 4*inch, 2*inch]
    header_data = [[logo_imm_rl, header_paragraphs, logo_sep_rl]]
    header_table = Table(header_data, colWidths=col_widths_header)
    header_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('ALIGN', (0, 0), (0, 0), 'LEFT'), ('ALIGN', (1, 0), (1, 0), 'CENTER'), ('ALIGN', (2, 0), (2, 0), 'RIGHT')]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.2 * inch))

    d = get_current_data()
    p = d['planeacion']
    
    P = lambda x: Paragraph(html_to_reportlab(str(x)), styles['Normal'])
    PB = lambda x: Paragraph(f"<b>{x}</b>", styles['Normal'])
    
    grupos_str = ", ".join(d['curso']['grupos'])
    docente_name = f"{d['docente']['titulo']} {d['docente']['nombre']}"
    dias_str = ", ".join(p['dias_planeados'])
    
    # Format dates for PDF
    f_inicio = date.fromisoformat(p['fecha_inicio']).strftime("%d/%m/%Y")
    f_fin = date.fromisoformat(p['fecha_fin']).strftime("%d/%m/%Y")
    
    temp_str = f"Del {f_inicio} al {f_fin}. Días: {dias_str}"
    
    ejes = ", ".join([e for e in [p['eje1'], p['eje2'], p['eje3']] if e and "Seleccione" not in e])
    disc = ", ".join([x for x in [p['disciplina1'], p['disciplina2'], p['disciplina3']] if x and "Seleccione" not in x])

    row0 = [[PB("Escuela:"), P("Instituto Mexicano Madero"), PB("CCT:"), P("21PES0013L"), PB("Docente:"), P(docente_name)]]
    t0 = Table(row0, colWidths=[0.8*inch, 2.7*inch, 0.5*inch, 1*inch, 0.8*inch, 4.2*inch])
    t0.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    
    row1 = [[PB("Grado:"), P(d['curso']['grado']), PB("Grupo:"), P(grupos_str), PB("Fase:"), P("6"), PB("Campo:"), P(d['curso']['campo'])]]
    t1 = Table(row1, colWidths=[0.8*inch, 1.2*inch, 0.8*inch, 1.2*inch, 0.8*inch, 0.8*inch, 1.4*inch, 3*inch])
    t1.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))

    main_data = [
        [t0], [t1],
        [PB("Materia:"), P(d['curso']['materia'])], [PB("Metodología:"), P(p['metodologia'])],
        [PB("Ejes:"), P(ejes)], [PB("Vinculación:"), P(disc)],
        [PB("Problemática:"), P(p['problematica'])], [PB("PDA:"), P(p['pda'])],
        [PB("Objetivos:"), P(p['objetivos'])], [PB("Perfiles:"), P(p['perfiles'])],
        [PB("Temporalidad:"), P(temp_str)], [PB("Producto:"), P(p['producto'])]
    ]
    main_table = Table(main_data, colWidths=[2.0*inch, page_width - 2.0*inch])
    main_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('SPAN', (0, 0), (1, 0)), ('SPAN', (0, 1), (1, 1))
    ]))
    elements.append(main_table)

    if "ABPj" in p['metodologia']:
        elements.append(PageBreak())
        elements.append(Paragraph("Secuencia Didáctica (ABPj)", ParagraphStyle(name='H2', fontSize=12, fontName='Helvetica-Bold', alignment=TA_CENTER)))
        abpj = p['secuencia_abpj']
        seq_data = []
        campos = [("Presentación", "presentacion"), ("Recolección", "recoleccion"), ("Formulación", "formulacion"), ("Organización", "organizacion"), ("Vivamos", "experiencia"), ("Resultados", "resultados"), ("Materiales", "materiales"), ("Evaluación", "evaluacion")]
        
        for label, key in campos:
            content = [P(abpj.get(key, ""))]
            if key == "evaluacion":
                _embed_image_to_pdf(abpj.get("rubrica_path"), content, page_width - 2.0*inch)
            seq_data.append([PB(label), content])
        
        st_table = Table(seq_data, colWidths=[2.0*inch, page_width - 2.0*inch])
        st_table.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('VALIGN', (0,0), (-1,-1), 'TOP')]))
        elements.append(st_table)
    
    elif p['metodologia'] != "Seleccione metodología":
        elements.append(PageBreak())
        elements.append(Paragraph("Secuencia Didáctica (Diaria)", ParagraphStyle(name='H2', fontSize=12, fontName='Helvetica-Bold', alignment=TA_CENTER)))
        daily = p['secuencia_diaria']
        for i, day in enumerate(daily):
            elements.append(Paragraph(f"<b>{day['dia_nombre']}</b>", styles['Normal']))
            eval_content = [P(day.get("evaluacion", ""))]
            _embed_image_to_pdf(day.get("rubrica_path"), eval_content, page_width - 2.0*inch)
            
            d_data = [
                [PB("Inicio"), P(day.get("inicio", ""))],
                [PB("Desarrollo"), P(day.get("desarrollo", ""))],
                [PB("Cierre"), P(day.get("cierre", ""))],
                [PB("Materiales"), P(day.get("materiales", ""))],
                [PB("Evaluación"), eval_content]
            ]
            dt = Table(d_data, colWidths=[2.0*inch, page_width - 2.0*inch])
            dt.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('VALIGN', (0,0), (-1,-1), 'TOP')]))
            elements.append(dt)
            elements.append(Spacer(1, 0.1*inch))

    elements.append(Spacer(1, 1.5*inch))
    elements.append(Paragraph("_____________________________________________", ParagraphStyle(name='Firma', alignment=TA_CENTER)))
    elements.append(Paragraph("Vo. Bo. Director David Pérez Ordoñez", ParagraphStyle(name='Firma', alignment=TA_CENTER)))

    doc.build(elements)
    buffer.seek(0)
    return buffer

st.markdown("### Generar Documento")
if st.button("📄 Generar PDF"):
    try:
        pdf_bytes = generate_pdf_bytes()
        st.download_button(label="Descargar PDF", data=pdf_bytes, file_name="Planeacion.pdf", mime="application/pdf")
        st.success("PDF Generado listo para descargar.")
    except Exception as e:
        st.error(f"Error al generar PDF: {e}")
