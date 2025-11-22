import streamlit as st
from PIL import Image
import os
import json
from datetime import datetime
import re
import pdfplumber

# Importaciones del proyecto
from preprocess.image_processing import preprocess_image
from ocr_layout.extraction import ocr_process_file
from extractor.semantic_extraction import extract_semantic_data
from rag.knowledge_base import get_knowledge_base
from rag.validator import InvoiceValidator  # ← Cambiado: Usar el nuevo validador

# --- Configuración de la Página ---
st.set_page_config(
    page_title="Extractor de Datos de Facturas",
    page_icon="🧾",
    layout="wide"
)

st.title("🧾 Agente de Extracción de Datos en Facturas")
st.write("Sube una imagen o PDF de una factura para extraer la información clave, validar reglas de negocio y generar reportes.")

# --- Directorios ---
os.makedirs("uploads", exist_ok=True)
os.makedirs("output/json", exist_ok=True)
os.makedirs("output/reports", exist_ok=True)
os.makedirs("output/validations", exist_ok=True)

# --- Inicializar Validador con Base de Conocimiento ---
@st.cache_resource
def init_validator():
    """Inicializa el validador con acceso a la base de conocimiento."""
    try:
        kb = get_knowledge_base("data/docs")
        validator = InvoiceValidator(knowledge_base=kb)
        return validator, "✅ Validador con base de conocimiento"
    except Exception as e:
        # Si falla, usar validador sin KB
        validator = InvoiceValidator()
        return validator, f"⚠️ Validador sin base de conocimiento: {str(e)}"

validator, validator_status = init_validator()

# Mostrar status del validador en sidebar
with st.sidebar:
    st.subheader("🔧 Estado del Sistema")
    st.write(validator_status)
    st.divider()
    st.subheader("📋 Reglas Validadas")
    st.markdown("""
    - ✅ Fecha de emisión
    - ✅ NIT con dígito de verificación
    - ✅ CUFE (Código Único)
    - ✅ Coherencia de totales
    - ✅ IVA (máximo 19%)
    - ✅ Suma de ítems
    - ✅ Actividad económica
    - ✅ Retención en la fuente
    - ✅ Fecha límite de pago
    - ✅ Resolución DIAN vigente
    """)

# --- Funciones auxiliares ---

def fill_invoice_robust(data, ocr_text):
    """Rellena campos faltantes pero respeta valores ya extraídos."""
    defaults = {
        "proveedor": "N/A",
        "nit_emisor": "N/A",  # ← Cambiado de nit_proveedor
        "direccion_proveedor": "N/A",
        "subtotal": 0.00,
        "iva": 0.00,  # ← Cambiado de impuestos
        "total": 0.00,
        "moneda": "USD",
        "numero_factura": "N/A",
        "fecha_emision": "N/A",
        "cufe": "N/A",
        "actividad_economica": "N/A",
        "retencion_fuente": 0.04,
        "forma_pago": "N/A",
        "fecha_limite_pago": "N/A",
        "items": []
    }
    
    for k, v in defaults.items():
        if k not in data or data[k] in [None, "NULL", ""]:
            data[k] = v
    
    # Extracciones adicionales del OCR
    if data.get("proveedor") in [None, "N/A", ""]:
        match = re.search(r"(SHIPPER|Proveedor|Seller)[:\s]*(.+?)(?:\n|MBL_|HBL_|$)", ocr_text, re.IGNORECASE)
        if match:
            data["proveedor"] = match.group(2).strip()
    
    if data.get("nit_emisor") in [None, "N/A", ""]:
        match = re.search(r"NIT[:\s.]*(\d{5,}-?\d*)", ocr_text, re.IGNORECASE)
        if match:
            data["nit_emisor"] = match.group(1).strip()
    
    if data.get("cufe") in [None, "N/A", ""]:
        match = re.search(r"CUFE:([a-f0-9]{128})", ocr_text, re.IGNORECASE)
        if match:
            data["cufe"] = match.group(1).strip()
    
    if data.get("fecha_emision") in [None, "N/A", ""]:
        match = re.search(r"(\d{2}[/-]\d{2}[/-]\d{4})", ocr_text)
        if match:
            data["fecha_emision"] = match.group(1)
    
    # Convertir valores numéricos
    for field in ["subtotal", "iva", "total"]:
        if isinstance(data.get(field), str):
            try:
                data[field] = float(data[field].replace(",", ""))
            except:
                data[field] = 0.00
    
    return data


def read_pdf_text(pdf_path):
    """Lee texto de un PDF."""
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        st.error(f"No se pudo leer el PDF: {e}")
    return text


def display_validation_results(validation_result):
    """Muestra los resultados de validación de forma visual."""
    st.subheader("📊 Resultados de Validación")
    
    # Status principal con color
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if validation_result['valid']:
            st.success("✅ FACTURA VÁLIDA")
        else:
            st.error("❌ FACTURA RECHAZADA")
    
    with col2:
        score = validation_result['confidence_score']
        color = "green" if score >= 0.95 else "orange" if score >= 0.80 else "red"
        st.metric("Confidence Score", f"{score*100:.1f}%")
    
    with col3:
        st.info(validation_result['recommendation'])
    
    # Errores críticos
    if validation_result['errors']:
        st.error(f"**❌ Errores Críticos ({len(validation_result['errors'])})**")
        for i, error in enumerate(validation_result['errors'], 1):
            st.write(f"{i}. {error}")
    
    # Advertencias
    if validation_result['warnings']:
        st.warning(f"**⚠️ Advertencias ({len(validation_result['warnings'])})**")
        for i, warning in enumerate(validation_result['warnings'], 1):
            st.write(f"{i}. {warning}")
    
    # Detalle de validaciones
    with st.expander("📋 Ver Detalle Completo de Validaciones"):
        for val in validation_result['validations']:
            icon = "✅" if val['valid'] else "❌"
            severity_color = {
                'success': 'green',
                'error': 'red',
                'warning': 'orange'
            }.get(val['severity'], 'gray')
            
            st.markdown(f"**{icon} {val['field']}**")
            st.markdown(f"<p style='color:{severity_color}; margin-left:20px;'>{val['message']}</p>", 
                       unsafe_allow_html=True)


# --- Interfaz Principal ---
uploaded_file = st.file_uploader(
    "Carga una imagen o PDF de la factura", 
    type=["png", "jpg", "jpeg", "pdf"]
)

if uploaded_file is not None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join("uploads", f"{timestamp}_{uploaded_file.name}")
    
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    ocr_text = None
    
    # Mostrar preview
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if uploaded_file.type.startswith('image'):
            image = Image.open(uploaded_file)
            st.image(image, caption="Factura cargada", use_container_width=True)
        elif uploaded_file.type == "application/pdf":
            st.info("📄 PDF cargado correctamente")
            ocr_text = read_pdf_text(file_path)
    
    with col2:
        st.metric("Archivo", uploaded_file.name)
        st.metric("Tamaño", f"{uploaded_file.size / 1024:.2f} KB")
        st.metric("Tipo", uploaded_file.type)
    
    st.divider()
    
    # Botón de procesamiento
    if st.button("🚀 Procesar y Validar Factura", type="primary", use_container_width=True):
        
        # Paso 1: Preprocesamiento
        with st.spinner("📸 Paso 1/5: Preprocesando imagen..."):
            try:
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
                    processed = preprocess_image(file_path)
                else:
                    processed = file_path
                st.success("✅ Preprocesamiento completado")
            except Exception as e:
                st.error(f"Error en preprocesamiento: {e}")
                st.stop()
        
        # Paso 2: OCR
        with st.spinner("🔍 Paso 2/5: Extrayendo texto con OCR..."):
            try:
                if ocr_text is None:
                    ocr_output = ocr_process_file(processed)
                    ocr_text = ''
                    if isinstance(ocr_output, dict):
                        ocr_text = ocr_output.get('text', '')
                        if isinstance(ocr_text, dict):
                            ocr_text = ocr_text.get('text', '')
                    else:
                        ocr_text = str(ocr_output)
                
                st.success(f"✅ Texto extraído: {len(ocr_text)} caracteres")
                
                with st.expander("Ver texto OCR completo"):
                    st.text_area("", ocr_text, height=200)
                    
            except Exception as e:
                st.error(f"Error en OCR: {e}")
                st.stop()
        
        # Paso 3: Extracción semántica
        with st.spinner("🧠 Paso 3/5: Extrayendo campos clave con IA..."):
            try:
                extracted_data = extract_semantic_data(ocr_text)
                if not extracted_data.get("items"):
                    extracted_data["items"] = []
                st.success(f"✅ Datos extraídos")
            except Exception as e:
                st.error(f"Error en extracción: {e}")
                extracted_data = {}
        
        # Paso 4: Completar campos faltantes
        with st.spinner("🔧 Paso 4/5: Completando campos..."):
            extracted_data = fill_invoice_robust(extracted_data, ocr_text)
            st.success("✅ Campos completados")
        
        # Paso 5: VALIDACIÓN CON REGLAS DE NEGOCIO
        with st.spinner("✅ Paso 5/5: Validando reglas de negocio..."):
            try:
                validation_result = validator.validate_invoice(extracted_data)
                
                # Agregar resultado de validación a los datos
                extracted_data['validation'] = validation_result
                
                st.success("✅ Validación completada")
                
            except Exception as e:
                st.error(f"Error en validación: {e}")
                import traceback
                st.code(traceback.format_exc())
                validation_result = {
                    'valid': False,
                    'errors': [str(e)],
                    'warnings': [],
                    'confidence_score': 0.0,
                    'recommendation': '❌ Error en validación'
                }
        
        # Guardar en session_state
        st.session_state['extracted_data'] = extracted_data
        st.session_state['validation_result'] = validation_result
        st.session_state['timestamp'] = timestamp
        st.session_state['filename'] = uploaded_file.name
        st.session_state['ocr_text'] = ocr_text
        
        st.divider()
        
        # --- MOSTRAR RESULTADOS DE VALIDACIÓN ---
        display_validation_results(validation_result)
        
        st.divider()
        
        # --- Mostrar Datos Extraídos ---
        st.subheader("📋 Datos Extraídos")
        
        tab1, tab2, tab3 = st.tabs(["📄 Resumen", "📊 JSON Completo", "✅ Validaciones"])
        
        with tab1:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Información General**")
                st.write(f"**Proveedor:** {extracted_data.get('proveedor', 'N/A')}")
                st.write(f"**NIT:** {extracted_data.get('nit_emisor', 'N/A')}")
                st.write(f"**Factura #:** {extracted_data.get('numero_factura', 'N/A')}")
                st.write(f"**Fecha:** {extracted_data.get('fecha_emision', 'N/A')}")
                st.write(f"**Forma de Pago:** {extracted_data.get('forma_pago', 'N/A')}")
            
            with col2:
                st.markdown("**Totales**")
                moneda = extracted_data.get('moneda', 'USD')
                subtotal = extracted_data.get('subtotal', 0)
                iva = extracted_data.get('iva', 0)
                total = extracted_data.get('total', 0)
                
                st.metric("Subtotal", f"${subtotal:,.2f} {moneda}")
                st.metric("IVA", f"${iva:,.2f} {moneda}")
                st.metric("Total", f"${total:,.2f} {moneda}", 
                         delta=f"{((iva/subtotal)*100 if subtotal > 0 else 0):.1f}% IVA")
            
            # Items
            items = extracted_data.get("items", [])
            if items:
                st.markdown(f"**Items ({len(items)})**")
                for i, item in enumerate(items, 1):
                    with st.expander(f"Item {i}: {item.get('descripcion', 'N/A')}"):
                        st.write(f"Cantidad: {item.get('cantidad', 'N/A')}")
                        st.write(f"Precio Unitario: {item.get('precio_unitario', 'N/A')}")
                        st.write(f"Total: {item.get('total', 'N/A')}")
        
        with tab2:
            st.json(extracted_data)
            
            # Guardar JSON
            json_path = os.path.join("output/json", f"factura_{timestamp}.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(extracted_data, f, indent=2, ensure_ascii=False)
            
            st.download_button(
                "⬇️ Descargar JSON",
                json.dumps(extracted_data, indent=2, ensure_ascii=False),
                f"factura_{timestamp}.json",
                "application/json",
                use_container_width=True
            )
        
        with tab3:
            # Mostrar tabla de validaciones
            st.markdown("**Detalle de Todas las Validaciones**")
            
            validations_data = []
            for val in validation_result['validations']:
                validations_data.append({
                    "Campo": val['field'],
                    "Estado": "✅" if val['valid'] else "❌",
                    "Severidad": val['severity'].upper(),
                    "Mensaje": val['message']
                })
            
            st.table(validations_data)
            
            # Guardar reporte de validación
            validation_path = os.path.join("output/validations", f"validation_{timestamp}.json")
            with open(validation_path, "w", encoding="utf-8") as f:
                json.dump(validation_result, f, indent=2, ensure_ascii=False)
            
            st.download_button(
                "⬇️ Descargar Reporte de Validación",
                json.dumps(validation_result, indent=2, ensure_ascii=False),
                f"validation_{timestamp}.json",
                "application/json",
                use_container_width=True
            )

# --- Generar Reporte PDF ---
st.divider()

if 'extracted_data' in st.session_state:
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📄 Generar Reporte PDF Completo", use_container_width=True):
            with st.spinner("Generando reporte PDF..."):
                try:
                    from reporter.report_generator_pdf import generate_pdf_report
                    
                    extracted_data = st.session_state['extracted_data']
                    validation_result = st.session_state['validation_result']
                    timestamp = st.session_state['timestamp']
                    filename = st.session_state['filename']
                    
                    report_path = os.path.join("output/reports", f"reporte_{timestamp}.pdf")
                    
                    generate_pdf_report(
                        results=[{
                            "source_file": filename,
                            "data": extracted_data,
                            "validation": validation_result,
                            "thumbnail_path": None
                        }],
                        output_path=report_path,
                        generation_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    )
                    
                    st.success(f"✅ Reporte PDF generado")
                    
                    with open(report_path, "rb") as f:
                        pdf_bytes = f.read()
                    
                    st.download_button(
                        "⬇️ Descargar Reporte PDF",
                        pdf_bytes,
                        f"reporte_{timestamp}.pdf",
                        "application/pdf",
                        key="download_pdf",
                        use_container_width=True
                    )
                    
                except Exception as e:
                    st.error(f"Error al generar reporte PDF: {e}")
                    import traceback
                    st.code(traceback.format_exc())
    
    with col2:
        if st.button("🔄 Procesar Otra Factura", use_container_width=True):
            # Limpiar session state
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    with col3:
        # Mostrar resumen rápido
        validation_result = st.session_state.get('validation_result', {})
        if validation_result.get('valid'):
            st.success("✅ Factura lista para procesar")
        else:
            st.error("❌ Factura requiere revisión")

else:
    st.info("ℹ️ Primero procesa una factura para generar reportes")

# --- Footer ---
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    st.write("🎓 **Proyecto Final**")
    st.write("Curso de Deep Learning v1.1")

with col2:
    st.write("📊 **Validaciones Implementadas**")
    st.write("10 reglas de negocio activas")

with col3:
    st.write("🔧 **Estado del Sistema**")
    st.write(validator_status)