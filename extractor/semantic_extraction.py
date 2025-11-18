"""
Extractor semántico mejorado que detecta correctamente items, totales y fechas.
Diseñado para funcionar con facturas reales con formato tabular.
"""
import re
from typing import Dict, Any, List, Optional
from datetime import datetime


def extract_semantic_data(ocr_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrae campos semánticos de una factura.
    Maneja correctamente formatos con tablas y totales al final.
    """
    # Extraer texto
    text = _get_text_from_output(ocr_output)
    
    if not text:
        return _empty_invoice()
    
    # Dividir en líneas para análisis estructurado
    lines = text.split('\n')
    
    # Extraer datos
    data = {
        "numero_factura": _extract_invoice_number(text, lines),
        "fecha_emision": _extract_date(text, lines),
        "proveedor": _extract_provider(text, lines),
        "nit_proveedor": _extract_client_nit(text, lines),  # NIT del cliente
        "direccion_proveedor": _extract_address(text, lines),
        "subtotal": _extract_net_worth(text, lines),
        "impuestos": _extract_vat(text, lines),
        "total": _extract_gross_worth(text, lines),
        "moneda": _extract_currency(text),
        "items": _extract_items_from_table(text, lines)
    }
    
    return data


def _get_text_from_output(ocr_output: Any) -> str:
    """Extrae texto limpio del output de OCR."""
    if isinstance(ocr_output, str):
        return ocr_output
    
    if isinstance(ocr_output, dict):
        text = ocr_output.get('text', '')
        if isinstance(text, dict):
            text = text.get('text', '')
        return str(text)
    
    return str(ocr_output)


def _empty_invoice() -> Dict[str, Any]:
    """Estructura vacía de factura."""
    return {
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


def _extract_invoice_number(text: str, lines: List[str]) -> Optional[str]:
    """Extrae número de factura o genera uno si no existe."""
    patterns = [
        r'Invoice[:\s]+([A-Z0-9\-]+)',
        r'Factura[:\s]+([A-Z0-9\-]+)',
        r'\b(INV-?\d{4,8})\b'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    
    # Si no hay número, buscar IBAN como identificador alternativo
    iban_match = re.search(r'IBAN:\s*([A-Z0-9]+)', text)
    if iban_match:
        return f"INV-{iban_match.group(1)[-8:]}"
    
    return None


def _extract_date(text: str, lines: List[str]) -> Optional[str]:
    """Extrae fecha de emisión."""
    # Buscar patrones de fecha en las primeras 15 líneas
    header = '\n'.join(lines[:15])
    
    patterns = [
        r'Date[:\s]+(\d{4}[-/]\d{2}[-/]\d{2})',
        r'Date[:\s]+(\d{2}[-/]\d{2}[-/]\d{4})',
        r'(\d{4}[-/]\d{2}[-/]\d{2})',
        r'(\d{2}[-/]\d{2}[-/]\d{4})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, header)
        if match:
            date_str = match.group(1)
            # Validar que no sea Tax ID (formato XXX-XX-XXXX)
            if not re.match(r'\d{3}-\d{2}-\d{4}', date_str):
                try:
                    # Intentar parsear
                    if '-' in date_str or '/' in date_str:
                        parts = re.split(r'[-/]', date_str)
                        if len(parts[0]) == 4:  # YYYY-MM-DD
                            return date_str.replace('/', '-')
                        elif len(parts[2]) == 4:  # DD-MM-YYYY
                            return f"{parts[2]}-{parts[1]}-{parts[0]}"
                except:
                    continue
    
    return None


def _extract_provider(text: str, lines: List[str]) -> Optional[str]:
    """Extrae nombre del proveedor (después de Seller:)."""
    for i, line in enumerate(lines[:10]):
        if re.search(r'Seller:', line, re.IGNORECASE):
            # El proveedor está en la siguiente línea
            if i + 1 < len(lines):
                provider = lines[i + 1].strip()
                if provider and len(provider) > 3:
                    return provider
    
    return None


def _extract_client_nit(text: str, lines: List[str]) -> Optional[str]:
    """Extrae NIT del CLIENTE (después de Client:)."""
    # Buscar sección Client
    client_section = ""
    in_client = False
    
    for line in lines:
        if re.search(r'Client:', line, re.IGNORECASE):
            in_client = True
        if in_client:
            client_section += line + "\n"
            if re.search(r'Tax Id:', line, re.IGNORECASE):
                break
    
    # Buscar Tax Id en la sección del cliente
    match = re.search(r'Tax Id:\s*([0-9\-]+)', client_section)
    if match:
        return match.group(1).strip()
    
    return None


def _extract_address(text: str, lines: List[str]) -> Optional[str]:
    """Extrae dirección del proveedor."""
    # Buscar en las líneas después de Seller
    for i, line in enumerate(lines[:10]):
        if re.search(r'Seller:', line, re.IGNORECASE):
            # La dirección suele estar 2 líneas después del nombre
            if i + 2 < len(lines):
                addr = lines[i + 2].strip()
                if re.search(r'\d+', addr):  # Tiene números
                    return addr
    
    return None


def _extract_net_worth(text: str, lines: List[str]) -> Optional[float]:
    """
    Extrae Net worth (subtotal).
    Busca en las últimas líneas: "$5600,17 — $560,02"
    """
    # Buscar patrón de montos al final
    summary = '\n'.join(lines[-15:])
    
    # Buscar línea con dos montos separados por guión
    match = re.search(r'\$\s*([0-9,]+[.,]\d{2})\s*[—\-]\s*\$\s*([0-9,]+[.,]\d{2})', summary)
    if match:
        # Primer monto es subtotal, segundo es impuestos
        subtotal_str = match.group(1).replace(',', '').replace(' ', '')
        try:
            return float(subtotal_str)
        except:
            pass
    
    # Buscar "Net worth" explícitamente
    match = re.search(r'Net\s*worth[:\s]+([0-9,]+[.,]?\d*)', summary, re.IGNORECASE)
    if match:
        value_str = match.group(1).replace(',', '').replace(' ', '')
        try:
            return float(value_str)
        except:
            pass
    
    return None


def _extract_vat(text: str, lines: List[str]) -> Optional[float]:
    """Extrae VAT (impuestos)."""
    summary = '\n'.join(lines[-15:])
    
    # Buscar en línea con dos montos
    match = re.search(r'\$\s*[0-9,]+[.,]\d{2}\s*[—\-]\s*\$\s*([0-9,]+[.,]\d{2})', summary)
    if match:
        vat_str = match.group(1).replace(',', '').replace(' ', '')
        try:
            return float(vat_str)
        except:
            pass
    
    # Buscar "VAT" explícitamente
    match = re.search(r'VAT[:\s]+\$?\s*([0-9,]+[.,]\d{2})', summary, re.IGNORECASE)
    if match:
        value_str = match.group(1).replace(',', '').replace(' ', '')
        try:
            return float(value_str)
        except:
            pass
    
    return None


def _extract_gross_worth(text: str, lines: List[str]) -> Optional[float]:
    """Extrae Gross worth (total)."""
    summary = '\n'.join(lines[-10:])
    
    # Buscar último monto con formato $X XXX,XX
    matches = re.findall(r'\$\s*([0-9\s,]+[.,]\d{2})', summary)
    if matches:
        # Tomar el último (suele ser el total)
        total_str = matches[-1].replace(',', '').replace(' ', '')
        try:
            return float(total_str)
        except:
            pass
    
    return None


def _extract_currency(text: str) -> str:
    """Extrae moneda."""
    if '$' in text:
        if re.search(r'\bUSD\b', text):
            return "USD"
        elif re.search(r'\bCOP\b', text):
            return "COP"
        # Formato con punto decimal y comas en miles → USD
        if re.search(r'\d{1,3},\d{3}\.\d{2}', text):
            return "USD"
    
    if '€' in text:
        return "EUR"
    
    return "USD"


def _extract_items_from_table(text: str, lines: List[str]) -> List[Dict[str, Any]]:
    """
    Extrae items de la tabla de productos.
    Formato esperado:
    1. Descripción (varias líneas)
    Cantidad, precio, total en líneas posteriores
    """
    items = []
    
    # Encontrar sección ITEMS
    items_start = -1
    items_end = -1
    
    for i, line in enumerate(lines):
        if re.search(r'ITEMS|No\.\s*[—\-]\s*Descr', line, re.IGNORECASE):
            items_start = i + 1
        if re.search(r'SUMMARY|Total', line, re.IGNORECASE) and items_start > 0:
            items_end = i
            break
    
    if items_start < 0:
        return items
    
    if items_end < 0:
        items_end = len(lines)
    
    # Buscar líneas que empiezan con número
    i = items_start
    while i < items_end:
        line = lines[i].strip()
        
        # Detectar inicio de item (línea con número)
        match = re.match(r'^(\d+)\.?\s+(.+)', line)
        if match:
            item_num = match.group(1)
            descripcion_parts = [match.group(2)]
            
            # Capturar líneas de descripción hasta encontrar datos numéricos
            j = i + 1
            while j < items_end and j < i + 5:  # Máximo 5 líneas por item
                next_line = lines[j].strip()
                
                # Si es otra línea de descripción (sin números al inicio)
                if not re.match(r'^\d+\.?\s+', next_line) and next_line:
                    # Verificar si tiene datos numéricos de cantidad/precio
                    if re.search(r'\d+[.,]\d{2}', next_line):
                        break
                    descripcion_parts.append(next_line)
                    j += 1
                else:
                    break
            
            descripcion = ' '.join(descripcion_parts).strip()
            
            # Buscar datos numéricos en las siguientes líneas
            # Formato: cantidad, precio unitario, precio neto, precio bruto
            search_text = '\n'.join(lines[i:min(i+8, items_end)])
            
            # Buscar cantidades (ej: "3,00" o "3.00")
            cantidad_match = re.search(r'(\d+)[.,](\d{2})\s*(?:each)?', search_text)
            
            # Buscar precios (con formato XX,XX o XXX,XX o X.XXX,XX)
            precios = re.findall(r'(\d{1,4})[.,](\d{2})', search_text)
            
            if cantidad_match and len(precios) >= 3:
                try:
                    cantidad = float(f"{cantidad_match.group(1)}.{cantidad_match.group(2)}")
                    
                    # Precios: [precio_unitario, neto, bruto]
                    precio_unitario = float(f"{precios[0][0]}.{precios[0][1]}")
                    total = float(f"{precios[-1][0]}{precios[-1][1]}.{precios[-1][2]}" if len(precios[-1]) == 3 else f"{precios[-1][0]}.{precios[-1][1]}")
                    
                    # Si el precio parece estar en formato europeo (XXX,XX), ajustar
                    if total < 10:  # Probablemente falta un dígito
                        # Buscar precio bruto más grande
                        for precio in reversed(precios):
                            test_val = float(f"{precio[0]}{precio[1] if len(precio) > 1 else ''}")
                            if test_val > total:
                                total = test_val
                                break
                    
                    item = {
                        "descripcion": descripcion[:100],
                        "cantidad": cantidad,
                        "precio_unitario": precio_unitario,
                        "total": total
                    }
                    items.append(item)
                
                except (ValueError, IndexError):
                    pass
            
            i = j
        else:
            i += 1
    
    return items


# Alias para compatibilidad
def extract_data_with_llm(text: str) -> Dict[str, Any]:
    """Compatibilidad con llamadas antiguas."""
    return extract_semantic_data({"text": text})