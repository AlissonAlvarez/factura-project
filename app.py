import streamlit as st
from PIL import Image
import os
import json
from datetime import datetime
import re  # <- Para patrones de OCR
import pdfplumber  # <- Ajuste para leer PDFs

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

st.title("🧾 Agente de Extracción de Datos en Facturas")
st.write("Sube una imagen o PDF de una factura para extraer la información clave en JSON y generar un reporte PDF.")

# --- Directorios ---
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

# --- AJUSTE: Función robusta para rellenar campos sin nulos ---
def fill_invoice_robust(data, ocr_text):
    defaults = {
        "proveedor": "N/A",
        "nit_proveedor": "N/A",
        "direccion_proveedor": "N/A",
        "subtotal": "0.00",
        "impuestos": "0.00",
        "total": "0.00",
        "moneda": "USD",
        "numero_factura": "N/A",
        "fecha_emision": "N/A",
        "items": []
    }

    for k, v in defaults.items():
        if k not in data or data[k] in [None, "NULL", "N/A"]:
            data[k] = v

    match = re.search(r"(SHIPPER|Proveedor|Seller)[:\s]*(.+?)(?:\n|MBL_|HBL_|$)", ocr_text, re.IGNORECASE)
    if match:
        data["proveedor"] = match.group(2).strip()

    match = re.search(r"NIT[:\s]*(\d{5,}-?\d*)", ocr_text, re.IGNORECASE)
    if match:
        data["nit_proveedor"] = match.group(1).strip()

    match = re.search(r"(CR|CARRERA|CL|CALLE)\s?\d{1,4}\s?\d{0,4}", ocr_text, re.IGNORECASE)
    if match:
        data["direccion_proveedor"] = match.group(0).strip()

    match = re.search(r"(\d{2}[/-]\d{2}[/-]\d{4})", ocr_text)
    if match:
        fecha = match.group(1).replace("-", "/")
        partes = fecha.split("/")
        if len(partes) == 3:
            mes, dia, anio = partes[0], partes[1], partes[2]
            data["fecha_emision"] = f"{anio}-{mes}-{dia}"

    match = re.search(r"(Factura|Invoice|No\.|Número)[:\s]*(\S+)", ocr_text, re.IGNORECASE)
    if match:
        data["numero_factura"] = match.group(2).strip()

    match = re.search(r"(USD|COP|EUR|MXN)", ocr_text, re.IGNORECASE)
    if match:
        data["moneda"] = match.group(1).upper()

    patterns_totales = {
        "subtotal": r"Subtotal[:\s]*([0-9\.,]+)",
        "impuestos": r"(IVA|Iva|Impuestos)[:\s]*([0-9\.,]+)",
        "total": r"Total[:\s]*([0-9\.,]+)"
    }
    for key, pat in patterns_totales.items():
        match = re.search(pat, ocr_text, re.IGNORECASE)
        if match:
            data[key] = match.groups()[-1].replace(",", "")

    items = []
    lines = [line.strip() for line in ocr_text.splitlines() if line.strip()]
    for line in lines:
        match = re.match(r"(.+?)\s+([0-9]{1,3}[0-9\.,]*)$", line)
        if match:
            items.append({
                "descripcion": match.group(1).strip(),
                "cantidad": "N/A",
                "precio_unitario": "N/A",
                "total": match.group(2).replace(",", "")
            })
    if items:
        data["items"] = items

    return data

# --- AJUSTE: Función para leer PDF ---
def read_pdf_text(pdf_path):
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

# --- Subir archivo ---
uploaded_file = st.file_uploader("Carga una imagen o PDF de la factura", type=["png", "jpg", "jpeg", "pdf"])

if uploaded_file is not None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join("uploads", f"{timestamp}_{uploaded_file.name}")
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    ocr_text = None  # Inicializamos

    if uploaded_file.type.startswith('image'):
        image = Image.open(uploaded_file)
        st.image(image, caption="Factura cargada", use_container_width=True)
    elif uploaded_file.type == "application/pdf":
        ocr_text = read_pdf_text(file_path)

    st.divider()

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
                with st.expander("Ver texto OCR"):
                    st.text_area("", ocr_text, height=150)
            except Exception as e:
                st.error(f"Error en OCR: {e}")
                st.stop()

        # Paso 3: Extracción de datos
        with st.spinner("Paso 3/4: Extrayendo campos clave..."):
            try:
                extracted_data = extract_semantic_data(ocr_text)
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

        # --- AJUSTE: Completar campos con OCR (robusto) ---
        validated_data = fill_invoice_robust(validated_data, ocr_text)

        # Guardar en session state
        st.session_state['validated_data'] = validated_data
        st.session_state['timestamp'] = timestamp
        st.session_state['filename'] = uploaded_file.name

        # --- Mostrar Resultados ---
        st.divider()
        st.subheader("📊 Resultados")
        tab1, tab2 = st.tabs(["📋 Resumen", "📄 JSON Completo"])

        with tab1:
            st.write("**Resumen de Factura**\n")
            general_fields = ["proveedor", "nit_proveedor", "direccion_proveedor", "numero_factura", "fecha_emision"]
            for field in general_fields:
                value = validated_data.get(field)
                st.write(f"{field.replace('_',' ').title()}: {value if value not in [None, 'NULL'] else 'N/A'}")

            st.write("\n**Totales**")
            total_fields = ["subtotal", "impuestos", "total"]
            moneda = validated_data.get('moneda', 'USD')
            for field in total_fields:
                value = validated_data.get(field)
                if isinstance(value, (int, float)):
                    st.write(f"{field.title()}: {value:,.2f} {moneda}")
                else:
                    st.write(f"{field.title()}: {value if value not in [None, 'NULL'] else 'N/A'}")

            # Items
            items = validated_data.get("items", [])
            st.write(f"\n**Items ({len(items)})**")
            for item in items:
                descripcion = item.get("descripcion", "N/A")
                cantidad = item.get("cantidad")
                precio_unitario = item.get("precio_unitario")
                total_item = item.get("total")
                st.write(f"{descripcion}")
                st.write(f"  Cant: {cantidad if cantidad not in [None, 'NULL'] else 'N/A'}")
                st.write(f"  P. Unit: {precio_unitario if precio_unitario not in [None, 'NULL'] else 'N/A'}")
                st.write(f"  Total: {total_item if total_item not in [None, 'NULL'] else 'N/A'}")
                st.write("---")

        with tab2:
            st.json(validated_data)
            json_path = os.path.join("output/json", f"factura_{timestamp}.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(validated_data, f, indent=2, ensure_ascii=False)
            st.download_button(
                "⬇️ Descargar JSON",
                json.dumps(validated_data, indent=2, ensure_ascii=False),
                f"factura_{timestamp}.json",
                "application/json"
            )

        # --- AJUSTE: Mostrar subtotal y total uniforme al final ---
        if 'validated_data' in st.session_state:
            validated_data = st.session_state['validated_data']
            moneda = validated_data.get('moneda', 'USD')

            try:
                subtotal = float(validated_data.get('subtotal', 0))
            except:
                subtotal = 0.0
            try:
                total = float(validated_data.get('total', 0))
            except:
                total = 0.0

            st.divider()
            st.subheader("💰 Resultado Completo de Factura")
            st.write(f"Subtotal: {subtotal:,.2f} {moneda}")
            st.write(f"Total: {total:,.2f} {moneda}")

    # --- Generar Reporte PDF ---
    st.divider()
    if 'validated_data' in st.session_state:
        if st.button("📄 Generar Reporte PDF"):
            with st.spinner("Generando reporte PDF..."):
                try:
                    validated_data = st.session_state['validated_data']
                    timestamp = st.session_state['timestamp']
                    filename = st.session_state['filename']
                    report_path = os.path.join("output/reports", f"reporte_{timestamp}.pdf")
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
        st.info("ℹ️ Primero procesa una factura para generar el reporte PDF")

st.markdown("---")
st.write("🎓 Proyecto Final - Curso de Deep Learning v1.1")
