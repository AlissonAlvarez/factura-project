# Proyecto Final — Agente de Extracción de Datos en Facturas

Este proyecto es una implementación de un agente de software capaz de extraer, analizar y validar datos de facturas utilizando una combinación de tecnologías de Visión por Computador, OCR, Modelos de Lenguaje (LLM) y Recuperación Aumentada por Generación (RAG).

## 1. Descripción General

El sistema procesa archivos de facturas (imágenes o PDF) a través de un pipeline automatizado para:
1.  **Extraer** texto y estructura.
2.  **Identificar** campos clave (N° de factura, fechas, totales, ítems).
3.  **Normalizar** y **completar** datos ambiguos usando un LLM.
4.  **Validar** la información extraída contra un conjunto de reglas de negocio definidas en documentos locales (PDFs).
5.  **Generar** salidas estructuradas en formato JSON y un reporte consolidado en PDF.

## 2. Arquitectura

El proyecto está organizado en los siguientes módulos:

-   `preprocess/`: Funciones para la limpieza y mejora de las imágenes de facturas (deskew, denoise).
-   `ocr_layout/`: Módulo encargado de la extracción de texto y tablas usando Tesseract y pdfplumber.
-   `extractor/`: Contiene la lógica para la extracción semántica de campos específicos mediante expresiones regulares.
-   `llm/`: Integra un modelo de lenguaje de Hugging Face para normalizar datos y asistir en la desambiguación.
-   `rag/`: Implementa el sistema RAG. Construye una base de conocimiento vectorial a partir de documentos de políticas y la usa para validar los datos extraídos.
-   `reporter/`: Genera el reporte final en formato PDF a partir de una plantilla HTML (Jinja2 + WeasyPrint).
-   `data/`: Directorios para almacenar las facturas de entrada y los documentos de reglas.
-   `output/`: Directorios donde se guardan los archivos JSON y los reportes generados.

## 3. Tecnologías Utilizadas

-   **Python 3.10+**
-   **OCR:** Tesseract, pdfplumber
-   **Visión por Computador:** OpenCV
-   **LLM:** `google/flan-t5-base` de Hugging Face Transformers
-   **RAG:** Sentence-Transformers + FAISS
-   **Reportes:** Jinja2 + WeasyPrint
-   **UI de Demostración:** Streamlit

## 4. Cómo Empezar

Para obtener instrucciones detalladas sobre la instalación y el uso, consulta la [**Guía de Uso (GUIA_USO.md)**](GUIA_USO.md).