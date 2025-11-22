"""
Módulo de extracción OCR mejorado
Usa multipass para obtener el mejor resultado
"""
from pathlib import Path
from PIL import Image
import pytesseract
import cv2
import numpy as np

# ============================
# AJUSTE NECESARIO PARA WINDOWS
# ============================
# Ruta del ejecutable de Tesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def extract_text_from_image(image_path: str, use_multipass: bool = True) -> str:
    """
    Extrae texto de una imagen usando la mejor estrategia
    
    Args:
        image_path: Ruta de la imagen (ya preprocesada o no)
        use_multipass: Si True, intenta múltiples configuraciones
    
    Returns:
        Texto extraído
    """
    try:
        img = Image.open(image_path)
        
        if use_multipass:
            return _extract_with_multipass(img)
        else:
            return _extract_simple(img)
            
    except Exception as e:
        print(f"❌ Error en OCR: {e}")
        return ""


def _extract_simple(img: Image) -> str:
    """Extracción simple con configuración estándar"""
    config = '--oem 3 --psm 6 -c preserve_interword_spaces=1'
    return pytesseract.image_to_string(img, lang='spa+eng', config=config)


def _extract_with_multipass(img: Image) -> str:
    """
    Prueba múltiples configuraciones de Tesseract y retorna el mejor resultado
    """
    configs = [
        ('--oem 3 --psm 6', 'Bloque uniforme'),
        ('--oem 3 --psm 4', 'Columna única'),
        ('--oem 3 --psm 3', 'Automático'),
        ('--oem 3 --psm 11', 'Texto disperso'),
    ]
    
    results = []
    
    for config, name in configs:
        try:
            text = pytesseract.image_to_string(img, lang='spa+eng', config=config)
            
            # Calcular score de calidad
            score = _calculate_text_quality(text)
            
            results.append({
                'text': text,
                'score': score,
                'config': name,
                'length': len(text)
            })
            
        except Exception as e:
            print(f"   ⚠️  Config {name} falló: {e}")
    
    if not results:
        return ""
    
    # Seleccionar mejor resultado
    best = max(results, key=lambda x: x['score'])
    
    print(f"   ✨ Mejor config: {best['config']} (score: {best['score']:.2f}, {best['length']} chars)")
    
    return best['text']


def _calculate_text_quality(text: str) -> float:
    """
    Calcula un score de calidad del texto OCR
    
    Criterios:
    - Mayor % de caracteres alfanuméricos = mejor
    - Presencia de palabras comunes en español = mejor
    - Menos símbolos raros = mejor
    """
    if not text or len(text) < 10:
        return 0.0
    
    # Contar caracteres alfanuméricos
    alnum_count = sum(c.isalnum() or c.isspace() for c in text)
    total_chars = len(text)
    alnum_ratio = alnum_count / total_chars
    
    # Contar palabras reconocibles (más de 2 letras)
    words = text.split()
    valid_words = sum(1 for w in words if len(w) > 2 and w.isalpha())
    word_ratio = valid_words / max(len(words), 1)
    
    # Detectar palabras clave de facturas
    keywords = ['factura', 'total', 'subtotal', 'iva', 'nit', 'fecha', 
                'cliente', 'producto', 'cantidad', 'precio', 'valor']
    keyword_count = sum(1 for kw in keywords if kw.lower() in text.lower())
    keyword_bonus = min(keyword_count * 0.1, 0.5)
    
    # Penalizar exceso de caracteres especiales consecutivos
    special_penalty = 0
    consecutive_special = 0
    for c in text:
        if not c.isalnum() and not c.isspace():
            consecutive_special += 1
            if consecutive_special > 5:
                special_penalty += 0.01
        else:
            consecutive_special = 0
    
    # Score final
    score = (alnum_ratio * 0.4 + word_ratio * 0.4 + keyword_bonus) - special_penalty
    
    return max(0, min(score, 1.0))


def extract_with_confidence(image_path: str) -> dict:
    """
    Extrae texto y retorna también la confianza del OCR
    
    Returns:
        {
            'text': str,
            'confidence': float,
            'word_count': int,
            'char_count': int
        }
    """
    try:
        img = Image.open(image_path)
        text = _extract_with_multipass(img)
        confidence = _calculate_text_quality(text)
        
        return {
            'text': text,
            'confidence': confidence,
            'word_count': len(text.split()),
            'char_count': len(text)
        }
    except Exception as e:
        print(f"❌ Error: {e}")
        return {
            'text': '',
            'confidence': 0.0,
            'word_count': 0,
            'char_count': 0
        }


# Función de compatibilidad con código anterior
def ocr_process_file(image_path: str) -> str:
    """
    Función de compatibilidad con el código anterior.
    Procesa un archivo de imagen y retorna el texto extraído.
    
    Args:
        image_path: Ruta de la imagen a procesar
    
    Returns:
        Texto extraído por OCR
    """
    return extract_text_from_image(image_path, use_multipass=True)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Uso: python extraction.py <imagen>")
        sys.exit(1)
    
    result = extract_with_confidence(sys.argv[1])
    
    print(f"\n📊 RESULTADO:")
    print(f"   Caracteres: {result['char_count']}")
    print(f"   Palabras: {result['word_count']}")
    print(f"   Confianza: {result['confidence']:.2%}")
    print(f"\n📝 TEXTO:")
    print("="*70)
    print(result['text'][:500])



# ===========================================================
# === AQUI AGREGO EL EXTRACTOR SEMÁNTICO COMPLETO (NUEVO) ===
# ===========================================================

import re

def extract_semantic_data(ocr_output):
    """
    Extrae información clave desde texto OCR.
    Compatible con formatos de facturas: imagen, PDF, escaneadas, fotos.
    NO modifica NADA del OCR, solo interpreta el texto.
    """

    text = ocr_output if isinstance(ocr_output, str) else ocr_output.get("text", "")
    clean = text.replace("\n", " ").replace("  ", " ")

    data = {}

    # -------------------------
    # CAMPOS PRINCIPALES
    # -------------------------

    factura = re.search(r"(factura|invoice|bill)[^\d]*(\d+)", clean, re.I)
    data["numero_factura"] = factura.group(2) if factura else None

    fechas = re.findall(r"(20\d{2}[\/\-.]\d{1,2}[\/\-.]\d{1,2})", clean)
    data["fecha_emision"] = fechas[0] if fechas else None

    proveedor = re.search(r"(fabricante|proveedor|empresa|shipper)[: ]+(.{5,40})", clean, re.I)
    data["proveedor"] = proveedor.group(2).strip() if proveedor else None

    nit = re.search(r"NIT[:.\- ]+(\d[\d\-.]+)", clean, re.I)
    data["nit_proveedor"] = nit.group(1) if nit else None

    direccion = re.search(r"(dir|dirección|address)[: ]+(.{5,50})", clean, re.I)
    data["direccion_proveedor"] = direccion.group(2).strip() if direccion else None

    sub = re.search(r"Sub[- ]?total[: ]+\$?([\d,.]+)", clean, re.I)
    data["subtotal"] = sub.group(1) if sub else None

    iva = re.search(r"IVA[: ]+\$?([\d,.]+)", clean, re.I)
    data["impuestos"] = iva.group(1) if iva else None

    total = re.search(r"Total[: ]+\$?([\d,.]+)", clean, re.I)
    data["total"] = total.group(1) if total else None

    total_usd = re.search(r"Total USD[: ]+([\d,.]+)", clean, re.I)
    data["total_usd"] = total_usd.group(1) if total_usd else None

    trm = re.search(r"Tasa[: ]+\$?([\d,.]+)", clean, re.I)
    data["tasa_cambio"] = trm.group(1) if trm else None

    # Moneda
    data["moneda"] = "USD" if "USD" in clean else "COP"

    # -------------------------
    # ITEMS / DETALLES
    # -------------------------

    items = []
    lineas = text.split("\n")

    for linea in lineas:
        if any(tag in linea.upper() for tag in ["USD", "$", "INGRESOS", "GATE", "CLEANING", "SUB-", "SUBTOTAL"]):
            items.append(linea.strip())

    if len(items) < 2:
        items = lineas

    data["items"] = items

    # -------------------------
    # EXTRACCIÓN ESPECIAL
    # -------------------------

    shipper = re.search(r"SHIPPER[: ]+(.+?)CONSIGNEE", clean, re.I)
    data["shipper"] = shipper.group(1).strip() if shipper else None

    consignee = re.search(r"CONSIGNEE[: ]+(.+?)DESTINO", clean, re.I)
    data["consignee"] = consignee.group(1).strip() if consignee else None

    peso = re.search(r"PESO[: ]+([\d,.]+)", clean, re.I)
    data["peso"] = peso.group(1) if peso else None

    volumen = re.search(r"VOLUMEN[: ]+([\d,.]+)", clean, re.I)
    data["volumen"] = volumen.group(1) if volumen else None

    hbl = re.search(r"HBL[_\- ]?HAWB[: ]+([A-Z0-9]+)", clean, re.I)
    mbl = re.search(r"MBL[_\- ]?MAWB[: ]+([A-Z0-9]+)", clean, re.I)
    data["hbl"] = hbl.group(1) if hbl else None
    data["mbl"] = mbl.group(1) if mbl else None

    ica = re.search(r"ICA[: ]+([\d.,]+)", clean, re.I)
    data["ica"] = ica.group(1) if ica else None

    ret = re.search(r"RETENCION.*?(\d+%|\d\.\d+%)", clean, re.I)
    data["retencion_fuente"] = ret.group(1) if ret else None

    return data
