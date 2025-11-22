import re
import pytesseract
from pdf2image import convert_from_path
import pdfplumber
from PIL import Image
import io


class DataExtractor:

    def __init__(self):
        pass

    # ---------------------------------------------------------
    # UTILIDAD GENERAL
    # ---------------------------------------------------------
    def clean_text(self, text):
        if not text:
            return ""
        return (
            text.replace("\n", " ")
                .replace("\t", " ")
                .replace("  ", " ")
                .strip()
        )

    # ---------------------------------------------------------
    # OCR → Extrae texto de PDF escaneado
    # ---------------------------------------------------------
    def extract_text_ocr(self, pdf_path):
        try:
            pages = convert_from_path(pdf_path, 300)
            text = ""
            for page in pages:
                text += pytesseract.image_to_string(page, lang='spa+eng')
            return self.clean_text(text)
        except Exception as e:
            print("Error OCR:", e)
            return ""

    # ---------------------------------------------------------
    # PDF DIGITAL → Extrae texto real sin OCR
    # ---------------------------------------------------------
    def extract_text_pdf(self, pdf_path):
        try:
            text = ""
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text += page.extract_text() or ""
            return self.clean_text(text)
        except Exception as e:
            print("Error PDF digital:", e)
            return ""

    # ---------------------------------------------------------
    # DECIDE MÉTODO ADECUADO
    # ---------------------------------------------------------
    def get_pdf_text(self, pdf_path):
        text_pdf = self.extract_text_pdf(pdf_path)
        if len(text_pdf.strip()) < 20:
            print("PDF vacío → usando OCR")
            return self.extract_text_ocr(pdf_path)
        return text_pdf

    # =========================================================
    # ***************   EXTRACCIÓN DE CAMPOS   ****************
    # =========================================================

    # NÚMERO DE FACTURA
    def extract_invoice_number(self, text):
        patrones = [
            r"Factura\s*#?\s*[:\- ]\s*([A-Za-z0-9\-]+)",
            r"Nº\s*Factura\s*[:\- ]\s*([A-Za-z0-9\-]+)",
            r"Invoice\s*#\s*([A-Za-z0-9\-]+)"
        ]
        for p in patrones:
            match = re.search(p, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    # FECHA
    def extract_invoice_date(self, text):
        patrones = [
            r"Fecha\s*[:\- ]\s*(\d{4}[\/\-]\d{2}[\/\-]\d{2})",
            r"Fecha\s*de\s*emisión\s*[:\- ]\s*(\d{2}[\/\-]\d{2}[\/\-]\d{4})",
            r"Date\s*[:\- ]\s*(\d{4}[\/\-]\d{2}[\/\-]\d{2})"
        ]
        for p in patrones:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                return m.group(1)
        return None

    # PROVEEDOR
    def extract_supplier(self, text):
        patrones = [
            r"Proveedor\s*[:\-]\s*(.+?)\s{2,}",
            r"Seller\s*[:\-]\s*(.+?)\s{2,}",
            r"Empresa\s*[:\-]\s*(.+?)\s{2,}"
        ]
        for p in patrones:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return None

    # NIT / RUC / VAT
    def extract_supplier_nit(self, text):
        patrones = [
            r"NIT\s*[:\- ]\s*([0-9\.\-]+)",
            r"RUC\s*[:\- ]\s*([0-9\.\-]+)",
            r"VAT\s*[:\- ]\s*([0-9\.\-]+)"
        ]
        for p in patrones:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                return m.group(1)
        return None

    # DIRECCIÓN
    def extract_address(self, text):
        p = r"Dirección\s*[:\-]\s*(.+?)(?=(Factura|Fecha|NIT|Subtotal|Total))"
        m = re.search(p, text, re.IGNORECASE | re.DOTALL)
        if m:
            return self.clean_text(m.group(1))
        return None

    # SUBTOTAL
    def extract_subtotal(self, text):
        p = r"Subtotal\s*[:\- ]\s*\$?\s*([0-9\.,]+)"
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1)
        return None

    # IMPUESTOS
    def extract_taxes(self, text):
        p = r"(IVA|Impuestos?)\s*[:\- ]\s*\$?\s*([0-9\.,]+)"
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(2)
        return None

    # TOTAL
    def extract_total(self, text):
        p = r"Total\s*[:\- ]\s*\$?\s*([0-9\.,]+)"
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1)
        return None

    # ITEMS DE LA TABLA
    def extract_items(self, text):
        lines = text.split("\n")
        items = []

        for line in lines:
            if re.search(r"\b\d+\b", line) and re.search(r"\$[0-9\.,]+", line):
                items.append(line.strip())

        return items

    # =========================================================
    # MÉTODO PRINCIPAL
    # =========================================================
    def extract_invoice_data(self, pdf_path):

        text = self.get_pdf_text(pdf_path)

        data = {
            "numero_factura": self.extract_invoice_number(text),
            "fecha_emision": self.extract_invoice_date(text),
            "proveedor": self.extract_supplier(text),
            "nit_proveedor": self.extract_supplier_nit(text),
            "direccion_proveedor": self.extract_address(text),
            "subtotal": self.extract_subtotal(text),
            "impuestos": self.extract_taxes(text),
            "total": self.extract_total(text),
            "moneda": "USD" if "$" in text else "COP",
            "items": self.extract_items(text)
        }

        return data
