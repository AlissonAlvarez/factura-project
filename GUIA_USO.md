# 📘 Guía Práctica de Uso

## Sistema de Extracción Inteligente de Facturas

---

## 🚀 Inicio Rápido (5 minutos)

### 1. Instalación en Un Solo Comando

```bash
# Ejecutar script de instalación automática
chmod +x setup.sh
./setup.sh
```

Este script:
- ✅ Verifica Python 3.8+
- ✅ Crea entorno virtual
- ✅ Instala dependencias
- ✅ Configura Tesseract OCR
- ✅ Instala Ollama + Gemma2
- ✅ Crea estructura de directorios

### 2. Preparar Datos Mínimos

```bash
# Copiar al menos 50 facturas
cp ~/mis_facturas/*.jpg data/invoices/

# Agregar políticas (al menos 1 PDF/DOCX)
cp ~/politicas/*.pdf data/policies/
```

### 3. Lanzar Sistema

**Opción A: Interfaz Web (Recomendado)**
```bash
source venv/bin/activate
streamlit run demo_app.py
```

**Opción B: Línea de Comandos**
```bash
source venv/bin/activate
python main.py --batch data/invoices/
```

---

## 📖 Casos de Uso

### Caso 1: Procesar Factura Individual

```bash
python main.py --invoice data/invoices/factura_001.jpg
```

**Salidas generadas:**
- `data/output/invoice_FAC-001_20251115_143022.json`
- `data/output/report_FAC-001.html`

**Ver reporte:**
```bash
# Abrir en navegador
open data/output/report_FAC-001.html

# O ver JSON
cat data/output/invoice_FAC-001_*.json | jq
```

---

### Caso 2: Procesamiento en Lote

```bash
# Procesar todas las facturas
python main.py --batch data/invoices/ --output results/

# Con clasificador CNN
python main.py --batch data/invoices/ --use-cnn
```

**Salidas:**
- Un JSON por factura
- Un HTML por factura
- `batch_report.json` consolidado

**Analizar resultados:**
```python
import json

# Cargar reporte batch
with open('data/output/batch_report.json') as f:
    report = json.load(f)

print(f"Total procesadas: {report['metadata']['total_invoices']}")
print(f"Válidas: {report['metadata']['valid_invoices']}")
```

---

### Caso 3: Usar Interfaz Web

```bash
streamlit run demo_app.py
```

**Flujo de trabajo:**

1. **Cargar factura** → Drag & drop o seleccionar archivo
2. **Procesar** → Click en botón "Procesar Factura"
3. **Revisar resultados:**
   - Tab "Encabezado" → Info general
   - Tab "Ítems" → Tabla de productos
   - Tab "Totales" → Resumen financiero
   - Tab "Validaciones" → Estado + citas
4. **Descargar** → JSON o HTML

**Shortcuts útiles:**
- `Ctrl + R` → Recargar app
- `Ctrl + K` → Menú de comandos

---

## 🎯 Escenarios Específicos

### Escenario 1: Facturas con Mala Calidad

**Problema:** OCR con baja confianza (<70%)

**Soluciones:**

1. **Preprocesamiento mejorado:**
```python
from preprocess.image_processor import ImagePreprocessor

processor = ImagePreprocessor(target_dpi=300)
img = processor.process('factura_borrosa.jpg')

# Guardar mejorada
processor.save_processed(img, 'factura_mejorada.jpg')
```

2. **Usar EasyOCR en lugar de Tesseract:**
```python
from ocr_layout.extractor import OCRExtractor

ocr = OCRExtractor(engine='easyocr', lang='spa')
text_boxes = ocr.extract_text(img)
```

3. **Combinar ambos motores:**
```python
# Tesseract
ocr_tess = OCRExtractor(engine='tesseract')
boxes_tess = ocr_tess.extract_text(img)

# EasyOCR
ocr_easy = OCRExtractor(engine='easyocr')
boxes_easy = ocr_easy.extract_text(img)

# Combinar resultados
combined = merge_ocr_results(boxes_tess, boxes_easy)
```

---

### Escenario 2: Plantillas Personalizadas

**Problema:** Facturas con formato no estándar

**Solución: Entrenar clasificador CNN**

```python
from templates.classifier import train_classifier

# Organizar dataset:
# data/train/
#   ├── plantilla_A/
#   │   ├── img1.jpg
#   │   └── img2.jpg
#   ├── plantilla_B/
#   └── plantilla_C/

# Entrenar
train_classifier(
    train_dir='data/train/',
    num_epochs=10
)

# Usar modelo entrenado
from templates.classifier import InvoiceTemplateClassifier

classifier = InvoiceTemplateClassifier(num_classes=3)
classifier.model.load_state_dict(
    torch.load('invoice_classifier.pth')
)

class_id, conf, template = classifier.classify('factura.jpg')
```

---

### Escenario 3: Validaciones Personalizadas

**Problema:** Reglas de negocio específicas

**Solución: Extender InvoiceValidator**

```python
from rag.validator import InvoiceValidator

class CustomValidator(InvoiceValidator):
    
    def validate_supplier_category(self, invoice_data):
        """Valida categoría del proveedor"""
        supplier = invoice_data.get('header', {}).get('supplier_name', '')
        
        # Buscar en políticas
        citations = self.indexer.search(
            f"categorías proveedores {supplier}",
            top_k=3
        )
        
        # Lógica de validación...
        return {
            'valid': True,
            'reason': 'Proveedor en categoría permitida',
            'citations': citations
        }

# Usar
validator = CustomValidator(indexer)
result = validator.validate_supplier_category(invoice_data)
```

---

### Escenario 4: Normalización Avanzada con LLM

**Problema:** Campos ambiguos o faltantes

**Solución: Prompts personalizados**

```python
from llm.normalizer import LLMNormalizer
import ollama

normalizer = LLMNormalizer(model='gemma2')

# Prompt personalizado para campo faltante
prompt = f"""
Factura con datos parciales:
- Proveedor: {supplier_name}
- Fecha: {date}
- Total: ${total}

Falta el NIT. Basado en el nombre del proveedor y otros datos,
¿cuál es el formato de NIT más probable en Colombia?

Responde SOLO con el NIT en formato: XXXXXXXXX-X
"""

response = ollama.chat(
    model='gemma2',
    messages=[{'role': 'user', 'content': prompt}]
)

inferred_nit = response['message']['content'].strip()
```

---

## 🔧 Personalización Avanzada

### Agregar Nuevos Campos

**1. Modificar InvoiceHeader/Totals/Item:**

```python
# extractor/field_extractor.py

@dataclass
class InvoiceHeader:
    # Campos existentes...
    purchase_order: Optional[str] = None  # NUEVO
    payment_terms: Optional[str] = None   # NUEVO
```

**2. Actualizar extracción:**

```python
class FieldExtractor:
    
    PATTERNS = {
        # Existentes...
        'purchase_order': [
            r'(?:orden de compra|po|oc)\s*[:\-]?\s*([A-Z0-9\-]+)'
        ]
    }
    
    def extract_header(self, text_boxes, full_text):
        header = InvoiceHeader()
        # Extracciones existentes...
        
        # NUEVO
        header.purchase_order = self._extract_pattern(
            full_text, self.PATTERNS['purchase_order']
        )
        
        return header
```

**3. Actualizar templates:**

```html
<!-- reporter/generator.py - HTML_TEMPLATE -->

<div class="info-box">
    <div class="info-label">Orden de Compra</div>
    <div class="info-value">{{ invoice.header.purchase_order or 'N/A' }}</div>
</div>
```

---

### Integrar Nuevas Fuentes de Validación

**Ejemplo: Validar contra base de datos SQL**

```python
# rag/validator.py

import sqlite3

class DatabaseValidator(InvoiceValidator):
    
    def __init__(self, indexer, db_path='suppliers.db'):
        super().__init__(indexer)
        self.conn = sqlite3.connect(db_path)
    
    def validate_supplier_in_db(self, invoice_data):
        """Valida que proveedor exista en BD"""
        nit = invoice_data.get('header', {}).get('supplier_nit', '')
        
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT name, active FROM suppliers WHERE nit=?",
            (nit,)
        )
        
        result = cursor.fetchone()
        
        if result:
            name, active = result
            if active:
                return {
                    'valid': True,
                    'reason': f'Proveedor registrado: {name}',
                    'citations': []
                }
            else:
                return {
                    'valid': False,
                    'reason': 'Proveedor inactivo',
                    'citations': []
                }
        else:
            return {
                'valid': False,
                'reason': f'NIT {nit} no encontrado en base de datos',
                'citations': []
            }
```

---

## 📊 Análisis de Resultados

### Estadísticas Batch

```python
import json
import pandas as pd

# Cargar reportes
with open('data/output/batch_report.json') as f:
    report = json.load(f)

# Convertir a DataFrame
df = pd.DataFrame([
    {
        'invoice_number': inv['header']['invoice_number'],
        'supplier': inv['header']['supplier_name'],
        'total': float(inv['totals']['total'] or 0),
        'is_valid': inv.get('validation', {}).get('is_valid', False),
        'ocr_confidence': inv['metadata']['ocr_confidence']
    }
    for inv in report['invoices']
])

# Análisis
print("Estadísticas:")
print(f"- Total procesadas: {len(df)}")
print(f"- Total facturado: ${df['total'].sum():,.2f}")
print(f"- Confianza OCR promedio: {df['ocr_confidence'].mean():.2f}%")
print(f"- % Válidas: {(df['is_valid'].sum()/len(df)*100):.1f}%")

# Top proveedores
print("\nTop 5 Proveedores:")
print(df.groupby('supplier')['total'].sum().sort_values(ascending=False).head())

# Visualizar
import matplotlib.pyplot as plt

df['is_valid'].value_counts().plot(kind='bar', title='Facturas Válidas vs Inválidas')
plt.show()
```

---

## 🐛 Debugging

### Activar Logs Detallados

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/debug.log'),
        logging.StreamHandler()
    ]
)

# Usar en código
logger = logging.getLogger(__name__)
logger.debug("Iniciando procesamiento...")
```

### Inspeccionar Resultados OCR

```python
from ocr_layout.extractor import OCRExtractor

ocr = OCRExtractor()
text_boxes = ocr.extract_text(img)

# Ver todas las cajas detectadas
for box in text_boxes:
    print(f"Región: {box.region}")
    print(f"Texto: {box.text}")
    print(f"Confianza: {box.confidence:.2f}%")
    print(f"BBox: {box.bbox}")
    print("-" * 50)

# Filtrar baja confianza
low_conf = [b for b in text_boxes if b.confidence < 60]
print(f"Cajas con baja confianza: {len(low_conf)}")
```

### Verificar Embeddings RAG

```python
from rag.validator import DocumentIndexer

indexer = DocumentIndexer()
indexer.index_documents('data/policies/')

# Test query
results = indexer.search("tasa de IVA", top_k=5)

for i, result in enumerate(results):
    print(f"\n{i+1}. Score: {result['score']:.4f}")
    print(f"   Fuente: {result['metadata']['source']}")
    print(f"   Texto: {result['text'][:100]}...")
```

---

## 💡 Tips y Trucos

### 1. Acelerar Procesamiento

```bash
# Procesar en paralelo (Linux/Mac)
ls data/invoices/*.jpg | parallel -j 4 python main.py --invoice {}
```

### 2. Caché de Resultados OCR

```python
import pickle

def process_with_cache(image_path):
    cache_file = f"{image_path}.ocr_cache"
    
    if os.path.exists(cache_file):
        with open(cache_file, 'rb') as f:
            return pickle.load(f)
    
    # Procesar
    result = process_invoice_ocr(image_path)
    
    # Guardar caché
    with open(cache_file, 'wb') as f:
        pickle.dump(result, f)
    
    return result
```

### 3. Validación Incremental

```bash
# Procesar solo facturas nuevas
find data/invoices -name "*.jpg" -newer data/output/.last_run | \
    xargs -I {} python main.py --invoice {}

# Marcar timestamp
touch data/output/.last_run
```

---

## 🎓 Recursos de Aprendizaje

### Tutoriales Relacionados

1. **Material del Curso:**
   - `CNN_Ollama_Vision.ipynb` - Integración CNN + LLM
   - `ollama_paso_a_paso.md` - Guía Ollama
   - `prueba_api.py` - Ejemplos API

2. **Documentación Externa:**
   - [Tesseract Best Practices](https://tesseract-ocr.github.io/tessdoc/)
   - [Ollama Models](https://ollama.com/library)
   - [FAISS Tutorial](https://github.com/facebookresearch/faiss/wiki)

### Ejercicios Propuestos

1. **Básico:** Agregar campo "Método de Pago"
2. **Intermedio:** Validar contra API externa de proveedores
3. **Avanzado:** Entrenar CNN con transfer learning en facturas propias

---

## 📞 Soporte

**¿Problemas?**

1. Consulta `README.md` sección "Solución de Problemas"
2. Revisa logs en `logs/debug.log`
3. Ejecuta tests de verificación:
   ```bash
   python -c "import cv2, pytesseract, torch, ollama; print('OK')"
   ```

**¿Mejoras?**

Crea un issue en el repositorio con:
- Descripción del problema/mejora
- Logs relevantes
- Ejemplos de facturas (anonimizadas)

---

**Última actualización:** Noviembre 2025  
**Versión:** 1.0

¡Éxito en tu proyecto! 🚀