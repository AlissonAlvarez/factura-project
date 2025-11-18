"""
Módulo principal de extracción de datos
Integra OCR + Semantic Extraction con Ollama
"""
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

class DataExtractor:
    def __init__(self, 
                 api_key: str = None,
                 model: str = "llama3.1:8b",
                 ollama_url: str = "http://localhost:11434"):
        """
        Args:
            api_key: Ignorado (para compatibilidad con código anterior)
            model: Modelo de Ollama a usar
            ollama_url: URL del servidor Ollama
        """
        self.model = model
        self.ollama_url = ollama_url
        
        if api_key:
            print("⚠️  Nota: api_key ignorado, usando Ollama local")
    
    def process_invoice(self, image_path: str, ocr_text: str) -> Dict[str, Any]:
        """
        Procesa una factura completa
        
        Args:
            image_path: Ruta a la imagen preprocesada
            ocr_text: Texto extraído por OCR
            
        Returns:
            Diccionario con datos estructurados
        """
        print(f"\n{'='*60}")
        print(f"Procesando: {Path(image_path).name}")
        print(f"{'='*60}")
        
        # Validar entrada
        if not ocr_text or len(ocr_text.strip()) < 10:
            print("⚠️  Advertencia: Texto OCR muy corto o vacío")
            return self._empty_result(image_path)
        
        print(f"✅ Texto OCR recibido: {len(ocr_text)} caracteres")
        
        # Extracción semántica con Ollama
        try:
            # Importar aquí para evitar problemas circulares
            from extractor.semantic_extraction import extract_from_ocr
            
            extracted_data = extract_from_ocr(
                ocr_text, 
                model=self.model,
                base_url=self.ollama_url
            )
            
            # Agregar metadatos
            extracted_data['metadata'] = {
                'source_image': str(image_path),
                'ocr_length': len(ocr_text),
                'items_count': len(extracted_data.get('items', [])),
                'extraction_model': self.model
            }
            
            # Estadísticas
            items_count = len(extracted_data.get('items', []))
            print(f"\n✅ Extracción completada:")
            print(f"   - Items detectados: {items_count}")
            print(f"   - Número factura: {extracted_data.get('numero_factura', 'No detectado')}")
            print(f"   - Proveedor: {extracted_data.get('proveedor', 'No detectado')}")
            print(f"   - Total: {extracted_data.get('total', 0):,.0f} {extracted_data.get('moneda', 'USD')}")
            print(f"   - Confianza: {extracted_data.get('confianza', 'desconocida')}")
            print(f"   - Modelo usado: {extracted_data.get('modelo_usado', 'desconocido')}")
            
            return extracted_data
            
        except Exception as e:
            print(f"❌ Error en extracción semántica: {e}")
            import traceback
            traceback.print_exc()
            return self._empty_result(image_path)
    
    def _empty_result(self, image_path: str = "") -> Dict[str, Any]:
        """Resultado vacío cuando falla la extracción"""
        return {
            "numero_factura": None,
            "fecha_emision": None,
            "proveedor": None,
            "nit_proveedor": None,
            "direccion_proveedor": None,
            "items": [],
            "moneda": "USD",
            "subtotal": 0,
            "impuestos": 0,
            "total": 0,
            "metadata": {
                "source_image": str(image_path),
                "ocr_length": 0,
                "items_count": 0,
                "extraction_model": self.model
            },
            "confianza": "nula",
            "modelo_usado": "ninguno",
            "explicacion": "No se pudo extraer información"
        }
    
    def process_batch(self, invoices_data: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Procesa un lote de facturas
        
        Args:
            invoices_data: Lista de dicts con 'image_path' y 'ocr_text'
            
        Returns:
            Lista de resultados estructurados
        """
        results = []
        total = len(invoices_data)
        
        print(f"\n{'='*60}")
        print(f"📦 PROCESAMIENTO POR LOTES")
        print(f"{'='*60}")
        print(f"Total de facturas: {total}")
        print(f"Modelo: {self.model}")
        print(f"{'='*60}\n")
        
        for i, invoice in enumerate(invoices_data, 1):
            print(f"\n📄 Factura {i}/{total}")
            
            result = self.process_invoice(
                invoice['image_path'],
                invoice['ocr_text']
            )
            results.append(result)
            
            # Mostrar progreso
            progress = (i / total) * 100
            print(f"📊 Progreso: {progress:.1f}% ({i}/{total})")
        
        # Resumen
        successful = sum(1 for r in results if r.get('total', 0) > 0)
        print(f"\n{'='*60}")
        print(f"✅ Lote completado:")
        print(f"   - Total procesadas: {len(results)}")
        print(f"   - Exitosas: {successful}")
        print(f"   - Fallidas: {len(results) - successful}")
        print(f"{'='*60}\n")
        
        return results


# Función de compatibilidad con código anterior
def extract_invoice_data(image_path: str, 
                        ocr_text: str,
                        api_key: str = None) -> Dict[str, Any]:
    """
    Función de compatibilidad con el código anterior.
    
    Args:
        image_path: Ruta a la imagen
        ocr_text: Texto extraído por OCR
        api_key: Ignorado (para compatibilidad)
    
    Returns:
        Diccionario con datos extraídos
    """
    extractor = DataExtractor(api_key=api_key)
    return extractor.process_invoice(image_path, ocr_text)


def main():
    """Función de prueba"""
    # Ejemplo de uso
    sample_ocr = """
    DISTRIBUIDORA ABC S.A.S
    NIT: 900123456-1
    Calle 50 #30-20
    
    FACTURA No: FAC-12345
    Fecha: 15/11/2025
    
    ITEMS:
    1. Producto A - Cant: 10 - Precio: $50.000 - Total: $500.000
    2. Producto B - Cant: 5 - Precio: $80.000 - Total: $400.000
    
    Subtotal: $900.000
    IVA (19%): $171.000
    TOTAL: $1.071.000
    """
    
    print("🧪 PRUEBA DE DATA EXTRACTOR CON OLLAMA")
    print("="*60)
    
    extractor = DataExtractor(model="llama3.1:8b")
    result = extractor.process_invoice("test.jpg", sample_ocr)
    
    print("\n📊 RESULTADO:")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()