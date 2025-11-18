import streamlit as st
from PIL import Image
import os
import json
from datetime import datetime

# Importaciones del proyecto
from preprocess.image_processing import preprocess_image
from ocr_layout.extraction import ocr_process_file
from extractor.semantic_extraction import extract_semantic_data
from rag.knowledge_base import get_knowledge_base
from rag.validator import RAGValidator
from reporter.report_generator_pdf import generate_pdf_report

# --- Configuración de la Página ---
st.set_page_config(
    page_title="Extractor de Datos de Facturas",
    page_icon="🧾"
)

# --- Título y Descripción ---
st.title("🧾 Agente de Extracción de Datos en Facturas")
st.write("Sube una imagen de una factura para extraer la información clave en formato JSON y generar un reporte PDF.")

# --- Creación de Directorios ---
os.makedirs("uploads", exist_ok=True)
os.makedirs("output/json", exist_ok=True)
os.makedirs("output/reports", exist_ok=True)

# --- Inicializar RAG ---
@st.cache_resource
def init_validator():
    try:
        kb = get_knowledge_base("data/docs")
        return RAGValidator(knowledge_base=kb)
    except:
        return None

validator = init_validator()

# --- Subir Archivo ---
uploaded_file = st.file_uploader(
    "Carga una imagen de la factura",
    type=["png", "jpg", "jpeg", "pdf"]
)

if uploaded_file is not None:
    # Guardar archivo
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join("uploads", f"{timestamp}_{uploaded_file.name}")
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    # Mostrar imagen
    if uploaded_file.type.startswith('image'):
        image = Image.open(uploaded_file)
        st.image(image, caption="Factura cargada", use_container_width=True)
    
    st.divider()
    
    # --- Procesar Factura ---
    if st.button("🚀 Procesar Factura", type="primary"):
        
        # Paso 1: Preprocesamiento
        with st.spinner("Paso 1/4: Preprocesando imagen..."):
            try:
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
                    processed = preprocess_image(file_path)
                else:
                    processed = file_path
                st.success("✅ Preprocesamiento completado")
            except Exception as e:
                st.error(f"Error: {e}")
                st.stop()
        
        # Paso 2: OCR
        with st.spinner("Paso 2/4: Extrayendo texto con OCR..."):
            try:
                ocr_output = ocr_process_file(processed)
                
                # Extraer texto limpio
                if isinstance(ocr_output, dict):
                    ocr_text = ocr_output.get('text', '')
                    if isinstance(ocr_text, dict):
                        ocr_text = ocr_text.get('text', '')
                else:
                    ocr_text = str(ocr_output)
                
                st.success(f"✅ Texto extraído: {len(ocr_text)} caracteres")
                
                with st.expander("Ver texto OCR"):
                    st.text_area("", ocr_text, height=150)
            
            except Exception as e:
                st.error(f"Error en OCR: {e}")
                st.stop()
        
        # Paso 3: Extracción de datos
        with st.spinner("Paso 3/4: Extrayendo campos clave..."):
            try:
                extracted_data = extract_semantic_data(ocr_output)
                
                # Validar estructura
                if not extracted_data.get("items"):
                    extracted_data["items"] = []
                
                st.success(f"✅ Datos extraídos: {len(extracted_data['items'])} items detectados")
            
            except Exception as e:
                st.error(f"Error en extracción: {e}")
                extracted_data = {
                    "numero_factura": None,
                    "fecha_emision": None,
                    "proveedor": None,
                    "nit_proveedor": None,
                    "direccion_proveedor": None,
                    "subtotal": None,
                    "impuestos": None,
                    "total": None,
                    "moneda": "USD",
                    "items": []
                }
        
        # Paso 4: Validación
        with st.spinner("Paso 4/4: Validando con base de conocimiento..."):
            if validator:
                try:
                    validated_data = validator.validate(extracted_data, ocr_text)
                    status = validated_data.get("validation_status", "DESCONOCIDO")
                    
                    if status == "APROBADO":
                        st.success(f"✅ Validación: {status}")
                    elif status == "ADVERTENCIA":
                        st.warning(f"⚠️ Validación: {status}")
                    else:
                        st.error(f"❌ Validación: {status}")
                
                except Exception as e:
                    st.warning(f"Error en validación: {e}")
                    validated_data = extracted_data
            else:
                st.info("ℹ️ Validador RAG no disponible")
                validated_data = extracted_data
        
        # GUARDAR EN SESSION STATE <<<<<<< ESTO ES CLAVE
        st.session_state['validated_data'] = validated_data
        st.session_state['timestamp'] = timestamp
        st.session_state['filename'] = uploaded_file.name
        
        # --- Mostrar Resultados ---
        st.divider()
        st.subheader("📊 Resultados")
        
        # Tabs
        tab1, tab2 = st.tabs(["📋 Resumen", "📄 JSON Completo"])
        
        with tab1:
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Información General**")
                st.write(f"**Proveedor:** {validated_data.get('proveedor', 'N/A')}")
                st.write(f"**NIT Cliente:** {validated_data.get('nit_proveedor', 'N/A')}")
                st.write(f"**Dirección:** {validated_data.get('direccion_proveedor', 'N/A')}")
                st.write(f"**Factura #:** {validated_data.get('numero_factura', 'N/A')}")
                st.write(f"**Fecha:** {validated_data.get('fecha_emision', 'N/A')}")
            
            with col2:
                st.write("**Totales**")
                moneda = validated_data.get('moneda', 'USD')
                subtotal = validated_data.get('subtotal')
                impuestos = validated_data.get('impuestos')
                total = validated_data.get('total')
                
                if subtotal:
                    st.metric("Subtotal", f"{subtotal:,.2f} {moneda}")
                if impuestos:
                    st.metric("Impuestos", f"{impuestos:,.2f} {moneda}")
                if total:
                    st.metric("Total", f"{total:,.2f} {moneda}")
            
            # Items
            if validated_data.get("items"):
                st.write(f"**Items ({len(validated_data['items'])})**")
                for idx, item in enumerate(validated_data["items"][:5], 1):  # Mostrar primeros 5
                    with st.expander(f"{idx}. {item.get('descripcion', 'N/A')[:50]}..."):
                        col_a, col_b, col_c = st.columns(3)
                        col_a.write(f"**Cant:** {item.get('cantidad', 'N/A')}")
                        col_b.write(f"**P. Unit:** {item.get('precio_unitario', 0):,.2f}")
                        col_c.write(f"**Total:** {item.get('total', 0):,.2f}")
        
        with tab2:
            st.json(validated_data)
            
            # Guardar JSON
            json_path = os.path.join("output/json", f"factura_{timestamp}.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(validated_data, f, indent=2, ensure_ascii=False)
            
            st.download_button(
                "⬇️ Descargar JSON",
                json.dumps(validated_data, indent=2, ensure_ascii=False),
                f"factura_{timestamp}.json",
                "application/json"
            )
    
    # --- Generar Reporte PDF --- 
    # MOVIDO FUERA del if del botón "Procesar Factura"
    st.divider()
    
    # Verificar si hay datos procesados en session_state
    if 'validated_data' in st.session_state:
        if st.button("📄 Generar Reporte PDF"):
            with st.spinner("Generando reporte PDF..."):
                try:
                    # Recuperar datos de session_state
                    validated_data = st.session_state['validated_data']
                    timestamp = st.session_state['timestamp']
                    filename = st.session_state['filename']
                    
                    report_path = os.path.join("output/reports", f"reporte_{timestamp}.pdf")
                    
                    # Generar PDF usando el nuevo módulo
                    generate_pdf_report(
                        results=[{
                            "source_file": filename,
                            "data": validated_data,
                            "thumbnail_path": None
                        }],
                        output_path=report_path,
                        generation_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    )
                    
                    st.success(f"✅ Reporte PDF generado: `{report_path}`")
                    
                    # Leer archivo para descarga
                    with open(report_path, "rb") as f:
                        pdf_bytes = f.read()
                    
                    st.download_button(
                        "⬇️ Descargar Reporte PDF",
                        pdf_bytes,
                        f"reporte_{timestamp}.pdf",
                        "application/pdf",
                        key="download_pdf"
                    )
                
                except Exception as e:
                    st.error(f"Error al generar reporte PDF: {e}")
                    import traceback
                    st.code(traceback.format_exc())
    else:
        st.info("ℹ️ Primero procesa una factura para poder generar el reporte PDF")

# --- Pie de Página ---
st.markdown("---")
st.write("🎓 Proyecto Final - Curso de Deep Learning v1.1")