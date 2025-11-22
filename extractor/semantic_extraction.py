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
    text = _get_text_from_output(ocr_output)
    
    if not text:
        return _empty_invoice()
    
    lines = text.split('\n')
    
    data = {
        "numero_factura": _extract_invoice_number(text, lines),
        "fecha_emision": _extract_date(text, lines),
        "proveedor": _extract_provider(text, lines),
        "nit_proveedor": _extract_client_nit(text, lines),
        "direccion_proveedor": _extract_address(text, lines),
        "subtotal": "0.00",
        "impuestos": "0.00",
        "total": "0.00",
        "moneda": _extract_currency(text),
        "items": _extract_items_from_table(text, lines)
    }
    
    print("\n=== DEBUG: Primeras 15 lineas del documento ===")
    for i, line in enumerate(lines[:15]):
        print(f"Linea {i}: {line}")
    print(f"\nNumero de factura detectado: {data['numero_factura']}")
    print("=" * 40 + "\n")
    
    # Variables para almacenar los valores de totales
    total_usd_value = None
    subtotal_value = None
    iva_value = None
    
    print("\n=== DEBUG: Items detectados (antes de filtrar) ===")
    for idx, item in enumerate(data["items"]):
        if isinstance(item, dict):
            print(f"Item {idx}: {item.get('descripcion', 'N/A')} -> Total: {item.get('total', 'N/A')}")
    print("=" * 40 + "\n")
    
    # Extraer totales de los items ANTES de filtrarlos
    for item in data["items"]:
        if isinstance(item, dict):
            desc = item.get('descripcion', '').upper().strip()
            item_total = item.get('total', '0.00')
            
            if isinstance(item_total, (int, float)):
                item_total = str(item_total)
            
            desc = desc.rstrip('.').strip()
            desc = re.sub(r'\s+', ' ', desc)
            
            print(f"DEBUG: Analizando '{desc}' con total '{item_total}'")
            
            if 'TOTAL USD' in desc or desc == 'TOTAL' or ('TOTAL' in desc and 'SUB' not in desc):
                print(f"  -> Total USD detectado! Valor: {item_total}")
                total_usd_value = item_total
            
            elif 'SUB-TOTAL' in desc or 'SUBTOTAL' in desc or 'SUB TOTAL' in desc:
                if subtotal_value is None:
                    print(f"  -> Subtotal detectado! Valor: {item_total}")
                    subtotal_value = item_total
            
            elif 'IVA' in desc:
                print(f"  -> IVA detectado! Valor: {item_total}")
                iva_value = item_total
    
    # Asignar los valores extraídos
    if total_usd_value:
        data["total"] = total_usd_value
        print(f"\nTotal asignado: {total_usd_value}")
    if subtotal_value:
        data["subtotal"] = subtotal_value
        print(f"Subtotal asignado: {subtotal_value}")
    if iva_value:
        data["impuestos"] = iva_value
        print(f"IVA asignado: {iva_value}\n")
    
    # AHORA sí, filtrar los items para eliminar totales
    filtered_items = []
    for item in data["items"]:
        if isinstance(item, dict):
            desc = item.get('descripcion', '').upper()
            if not re.search(r'(SUB-TOTAL|SUBTOTAL|IVA|TOTAL|0\s*-\s*,)', desc, re.IGNORECASE):
                filtered_items.append(item)
    
    data["items"] = filtered_items
    print(f"\nItems filtrados (sin totales): {len(data['items'])} items")
    for item in data["items"]:
        print(f"  - {item.get('descripcion', 'N/A')}")
    
    # Fallback para totales si no se encontraron en los items
    if data["total"] == "0.00":
        alt_total = _extract_gross_worth(text, lines)
        if alt_total:
            data["total"] = str(alt_total)
        else:
            try:
                subtotal_float = float(data["subtotal"].replace(',', ''))
                impuestos_float = float(data["impuestos"].replace(',', ''))
                calculated_total = subtotal_float + impuestos_float
                if calculated_total > 0:
                    data["total"] = f"{calculated_total:.2f}"
            except (ValueError, AttributeError):
                pass
    
    if data["subtotal"] == "0.00":
        alt_subtotal = _extract_net_worth(text, lines)
        if alt_subtotal:
            data["subtotal"] = str(alt_subtotal)
    
    if data["impuestos"] == "0.00":
        alt_impuestos = _extract_vat(text, lines)
        if alt_impuestos:
            data["impuestos"] = str(alt_impuestos)
    
    # Fallback para items si no se encontraron
    if not data.get("items"):
        fallback_items = []
        for m in re.finditer(r"(FLETE|GASTOS|CLEANING|GATE)[^\d]*([\d,.]+)", text, re.I):
            desc = m.group(1).strip()
            if not re.search(r'(SUB-TOTAL|SUBTOTAL|IVA|TOTAL)', desc, re.IGNORECASE):
                fallback_items.append({
                    "descripcion": desc,
                    "cantidad": "N/A",
                    "precio_unitario": "N/A",
                    "total": m.group(2).strip()
                })
        data["items"] = fallback_items
    
    # Normalizar items
    new_items = []
    for item in data["items"]:
        if isinstance(item, dict):
            new_items.append(item)
        else:
            new_items.append({
                "descripcion": str(item),
                "cantidad": "N/A",
                "precio_unitario": "N/A",
                "total": "N/A"
            })
    data["items"] = new_items
    
    # Fallbacks adicionales
    if not data.get("nit_proveedor"):
        nit_alt = re.search(r"NIT[.\s]*[:\-]?\s*([\d\-.]+)", text, re.I)
        if nit_alt:
            data["nit_proveedor"] = nit_alt.group(1).strip()
    
    if not data.get("proveedor"):
        proveedor_alt = re.search(r"(fabricante|proveedor|empresa|shipper)[:\.]?\s*(.{5,50})", text, re.I)
        if proveedor_alt:
            data["proveedor"] = proveedor_alt.group(2).strip()
    
    if not data.get("fecha_emision"):
        fechas = re.findall(r"\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}", text)
        if not fechas:
            fechas = re.findall(r"[A-Za-z]{3,}-\d{1,2}-\d{4}", text)
        if fechas:
            data["fecha_emision"] = fechas[0]
    
    return data

def _get_text_from_output(ocr_output: Any) -> str:
    if isinstance(ocr_output, str):
        return ocr_output
    
    if isinstance(ocr_output, dict):
        text = ocr_output.get('text', '')
        if isinstance(text, dict):
            text = text.get('text', '')
        return str(text)
    
    return str(ocr_output)

def _empty_invoice() -> Dict[str, Any]:
    return {
        "numero_factura": None,
        "fecha_emision": None,
        "proveedor": None,
        "nit_proveedor": None,
        "direccion_proveedor": None,
        "subtotal": "0.00",
        "impuestos": "0.00",
        "total": "0.00",
        "moneda": "USD",
        "items": []
    }

def _extract_invoice_number(text: str, lines: List[str]) -> Optional[str]:
    header = '\n'.join(lines[:25])
    
    match = re.search(r'\b(\d{2})\s+(\d{5,})\b', header)
    if match:
        factura_num = match.group(1) + match.group(2)
        if 'FACTURA' in header[:header.find(match.group(0)) + 100]:
            return factura_num
    
    match = re.search(r'FACTURA\s+ELECTRONICA[^\n]*\n\s*(\d{2}\s+\d{5,})', header, re.IGNORECASE)
    if match:
        return match.group(1).replace(' ', '')
    
    for line in lines[:25]:
        line_clean = line.strip()
        line_match = re.match(r'^(\d{2})\s+(\d{5,})$', line_clean)
        if line_match:
            return line_match.group(1) + line_match.group(2)
    
    patterns = [
        r'Invoice[:\s]+([A-Z0-9\-]+)',
        r'Factura[:\s]+([A-Z0-9\-]+)',
        r'\b(INV-?\d{4,8})\b',
        r'No\.\s*Factura[:\s]*(\d{5,})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, header, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).replace(' ', '')
    
    return "ELECTRONICA"

def _extract_date(text: str, lines: List[str]) -> Optional[str]:
    header = '\n'.join(lines[:20])
    
    patterns = [
        r'(\d{2}/\d{2}/\d{4})\s+\d{1,2}:\d{2}:\d{2}\s+[AP]M',
        r'Date[:\s]+(\d{4}[-/]\d{2}[-/]\d{2})',
        r'Date[:\s]+(\d{2}[-/]\d{2}[-/]\d{4})',
        r'FECHA[:\s]+(\d{2}[-/]\d{2}[-/]\d{4})',
        r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, header, re.IGNORECASE)
        if match:
            date_str = match.group(1)
            try:
                if '/' in date_str or '-' in date_str:
                    parts = re.split(r'[-/]', date_str)
                    
                    if len(parts) == 3:
                        if len(parts[0]) == 4:
                            return f"{parts[0]}-{parts[1]}-{parts[2]}"
                        elif len(parts[2]) == 4:
                            mes, dia, anio = parts[0], parts[1], parts[2]
                            return f"{anio}-{mes.zfill(2)}-{dia.zfill(2)}"
            except:
                continue
    
    return None

def _extract_provider(text: str, lines: List[str]) -> Optional[str]:
    for i, line in enumerate(lines[:10]):
        if re.search(r'Seller:', line, re.IGNORECASE):
            if i + 1 < len(lines):
                provider = lines[i + 1].strip()
                if provider and len(provider) > 3:
                    return provider
    
    shipper_match = re.search(r'SHIPPER:\s*(.+?)(?:ORIGEN|PORT|$)', text, re.IGNORECASE)
    if shipper_match:
        return shipper_match.group(1).strip()
    
    provider_match = re.search(r'(Fabricante|Proveedor):\s*(.+)', text, re.IGNORECASE)
    if provider_match:
        return provider_match.group(2).strip()
    
    return None

def _extract_client_nit(text: str, lines: List[str]) -> Optional[str]:
    nit_patterns = [
        r'NIT[.\s]*[:\-]?\s*([\d\-.]+)',
        r'Tax\s*Id:\s*([0-9\-]+)',
        r'Nit:\s*([\d\-.]+)'
    ]
    
    for pattern in nit_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return None

def _extract_address(text: str, lines: List[str]) -> Optional[str]:
    addr_patterns = [
        r'(CR|CALLE|CARRERA|AV|AVENIDA)\s+[\d\s\-]+(?:\s+\d+)?',
        r'Direccion:\s*(.+)',
        r'Address:\s*(.+)'
    ]
    
    for pattern in addr_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            addr = match.group(0) if pattern.startswith('(CR') else match.group(1)
            return addr.strip()[:100]
    
    for i, line in enumerate(lines[:10]):
        if re.search(r'Seller:', line, re.IGNORECASE):
            if i + 2 < len(lines):
                addr = lines[i + 2].strip()
                if re.search(r'\d+', addr):
                    return addr
    
    return None

def _extract_net_worth(text: str, lines: List[str]) -> Optional[float]:
    summary = '\n'.join(lines[-15:])
    
    subtotal_patterns = [
        r'Sub-total[:\s]+USD?\s*([\d,]+\.?\d*)',
        r'Subtotal[:\s]+\$?\s*([\d,]+\.?\d*)',
        r'Net\s*worth[:\s]+([\d,]+\.?\d*)'
    ]
    
    for pattern in subtotal_patterns:
        match = re.search(pattern, summary, re.IGNORECASE)
        if match:
            value_str = match.group(1).replace(',', '').replace(' ', '')
            try:
                return float(value_str)
            except:
                pass
    
    return None

def _extract_vat(text: str, lines: List[str]) -> Optional[float]:
    for i, line in enumerate(lines):
        if re.search(r'^IVA\s+USD\s+([\d,]+\.?\d*)$', line.strip(), re.IGNORECASE):
            match = re.search(r'([\d,]+\.?\d*)$', line)
            if match:
                value_str = match.group(1).replace(',', '').replace(' ', '')
                try:
                    return float(value_str)
                except:
                    pass
    
    summary_lines = []
    for line in lines:
        if 'Tasa:' in line or 'CUFE:' in line:
            break
        summary_lines.append(line)
    
    summary = '\n'.join(summary_lines[-15:])
    
    vat_patterns = [
        r'IVA\s+USD\s*([\d,]+\.?\d*)',
        r'VAT[:\s]+\$?\s*([\d,]+\.?\d*)',
    ]
    
    for pattern in vat_patterns:
        match = re.search(pattern, summary, re.IGNORECASE)
        if match:
            value_str = match.group(1).replace(',', '').replace(' ', '')
            try:
                return float(value_str)
            except:
                pass
    
    return None

def _extract_gross_worth(text: str, lines: List[str]) -> Optional[float]:
    summary = '\n'.join(lines[-10:])
    
    total_patterns = [
        r'Total\s+USD\s*([\d,]+\.?\d*)',
        r'Total[:\s]+\$?\s*([\d,]+\.?\d*)',
        r'Gross\s*worth[:\s]+([\d,]+\.?\d*)'
    ]
    
    for pattern in total_patterns:
        match = re.search(pattern, summary, re.IGNORECASE)
        if match:
            value_str = match.group(1).replace(',', '').replace(' ', '')
            try:
                return float(value_str)
            except:
                pass
    
    return None

def _extract_currency(text: str) -> str:
    if re.search(r'\bUSD\b', text, re.IGNORECASE):
        return "USD"
    elif re.search(r'\bCOP\b', text, re.IGNORECASE):
        return "COP"
    elif '€' in text or re.search(r'\bEUR\b', text, re.IGNORECASE):
        return "EUR"
    elif '$' in text:
        return "USD"
    
    return "USD"

def _extract_items_from_table(text: str, lines: List[str]) -> List[Dict[str, Any]]:
    items = []
    
    items_start = -1
    items_end = -1
    
    for i, line in enumerate(lines):
        if re.search(r'Codigo\s+Descipcion|Descripcion|Description', line, re.IGNORECASE):
            items_start = i + 1
        # No cortamos temprano, procesamos hasta cerca del final
        if re.search(r'PRACTICAR|RESOLUCION|Fecha Limite|CUFE|Tasa:', line, re.IGNORECASE) and items_start > 0:
            items_end = i
            break
    
    if items_start < 0:
        items_start = 0
    
    if items_end < 0:
        items_end = len(lines)
    
    for i in range(items_start, items_end):
        line = lines[i].strip()
        if not line or len(line) < 3:
            continue
        
        if 'Tasa:' in line or 'CUFE:' in line or 'PRACTICAR' in line:
            continue
        
        # Patrón principal: descripción + valor
        match = re.match(r'^(.+?)\s+([\d,]+\.?\d*)$', line)
        if match:
            desc = match.group(1).strip()
            total = match.group(2).strip()
            
            # Incluimos TODO, incluso Sub-total, IVA y Total
            items.append({
                "descripcion": desc,
                "cantidad": "N/A",
                "precio_unitario": "N/A",
                "total": total
            })
            continue
        
        # Patrón secundario: items numerados
        match = re.match(r'^(\d+)\.?\s+(.+)', line)
        if match:
            item_num = match.group(1)
            descripcion = match.group(2).strip()
            
            search_text = '\n'.join(lines[i:min(i+5, items_end)])
            cantidad_match = re.search(r'(\d+)[.,](\d{2})\s*(?:each)?', search_text)
            precios = re.findall(r'(\d{1,4})[.,](\d{2})', search_text)
            
            if cantidad_match and len(precios) >= 3:
                try:
                    cantidad = float(f"{cantidad_match.group(1)}.{cantidad_match.group(2)}")
                    precio_unitario = float(f"{precios[0][0]}.{precios[0][1]}")
                    total = float(f"{precios[-1][0]}.{precios[-1][1]}")
                    
                    items.append({
                        "descripcion": descripcion[:100],
                        "cantidad": cantidad,
                        "precio_unitario": precio_unitario,
                        "total": total
                    })
                except (ValueError, IndexError):
                    pass
    
    return items

def extract_data_with_llm(text: str) -> Dict[str, Any]:
    return extract_semantic_data({"text": text})