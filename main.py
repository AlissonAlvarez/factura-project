import os
import json
import argparse
from tqdm import tqdm

# Importar módulos del proyecto
from preprocess import preprocess_image
from ocr_layout import ocr_process_file
from extractor import extract_semantic_data

# ✅ ELIMINADO: from llm.gemini_client import GeminiClient
# ✅ AHORA: Solo usamos extracción local

from rag import get_knowledge_base, RAGValidator
from reporter import generate_report

def main(args):
    """
    Función principal que orquesta el pipeline de extracción de datos de facturas.
    Pipeline: Preprocesamiento → OCR → Extracción Semántica → Validación RAG → Reporte
    """
    # --- 1. Configuración de directorios ---
    base_dir = os.path.dirname(os.path.abspath(__file__))
    facturas_dir = args.facturas_dir or os.path.join(base_dir, 'data', 'facturas')
    output_dir = args.output_dir or os.path.join(base_dir, 'output')
    docs_dir = args.docs_dir or os.path.join(base_dir, 'data', 'docs')
    
    json_output_dir = os.path.join(output_dir, 'json')
    report_output_dir = os.path.join(output_dir, 'reports')
    os.makedirs(json_output_dir, exist_ok=True)
    os.makedirs(report_output_dir, exist_ok=True)
    
    print("=" * 70)
    print("🧾 AGENTE DE EXTRACCIÓN DE DATOS EN FACTURAS")
    print("=" * 70)
    print(f"📁 Directorio de facturas: {facturas_dir}")
    print(f"💾 Directorio de salida: {output_dir}")
    print(f"📚 Directorio de documentos: {docs_dir}")
    print(f"🔧 Modo: {'Con' if args.use_rag else 'Sin'} validación RAG")
    print("=" * 70)
    
    # --- 2. Inicializar componentes ---
    print("\n🔄 Inicializando Componentes...")
    
    kb = None
    validator = None
    
    if args.use_rag:
        try:
            print("📚 Cargando base de conocimiento (RAG)...")
            kb = get_knowledge_base(docs_dir)
            
            if kb and kb.index and kb.index.ntotal > 0:
                print(f"✅ Base de conocimiento cargada: {kb.index.ntotal} vectores")
                
                # ✅ Inicializar validador SIN LLM client
                print("🔍 Inicializando validador RAG (local)...")
                validator = RAGValidator(knowledge_base=kb)
                print("✅ Validador RAG inicializado")
            else:
                print("⚠️  Base de conocimiento vacía. Continuando sin RAG.")
                args.use_rag = False
        
        except Exception as e:
            print(f"❌ Error al inicializar RAG: {e}")
            print("⚠️  Continuando sin validación RAG.")
            args.use_rag = False
    else:
        print("ℹ️  Modo sin RAG (--no-rag especificado)")
    
    # --- 3. Procesar cada factura ---
    print("\n" + "=" * 70)
    print("📄 PROCESANDO FACTURAS")
    print("=" * 70)
    
    all_results = []
    
    # Buscar archivos de facturas
    factura_files = [
        f for f in os.listdir(facturas_dir) 
        if f.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg'))
    ]
    
    if not factura_files:
        print("❌ No se encontraron facturas en el directorio especificado.")
        print(f"   Verifica que existan archivos PDF/PNG/JPG/JPEG en: {facturas_dir}")
        return
    
    print(f"📊 Total de facturas encontradas: {len(factura_files)}\n")
    
    for idx, filename in enumerate(tqdm(factura_files, desc="Procesando"), 1):
        file_path = os.path.join(facturas_dir, filename)
        
        print(f"\n{'─' * 70}")
        print(f"[{idx}/{len(factura_files)}] 📄 {filename}")
        print(f"{'─' * 70}")
        
        try:
            # a) Preprocesamiento
            processed_input = file_path
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                print("  🖼️  Preprocesando imagen...")
                try:
                    processed_input = preprocess_image(file_path)
                    print("  ✅ Preprocesamiento completado")
                except Exception as e:
                    print(f"  ⚠️  Error en preprocesamiento: {e}")
                    print("  ℹ️  Usando imagen original")
                    processed_input = file_path
            
            # b) OCR
            print("  📝 Extrayendo texto con OCR...")
            ocr_output = ocr_process_file(processed_input)
            
            if not ocr_output or not ocr_output.get("text", "").strip():
                print("  ❌ No se pudo extraer texto. Saltando archivo.")
                continue
            
            ocr_text = ocr_output.get("text", "")
            print(f"  ✅ Texto extraído: {len(ocr_text)} caracteres")
            
            # c) Extracción semántica
            print("  🔍 Extrayendo campos clave...")

            # ======================================================
            #   ✅ AJUSTE QUE FALTABA (ENVÍA TEXTO COMPLETO AL EXTRACTOR)
            # ======================================================
            extracted_data = extract_semantic_data({
                "text": ocr_text,
                "file_path": file_path
            })
            # ======================================================

            if not isinstance(extracted_data, dict):
                extracted_data = {}
            
            # Campos mínimos
            extracted_data.setdefault("numero_factura", None)
            extracted_data.setdefault("fecha_emision", None)
            extracted_data.setdefault("proveedor", None)
            extracted_data.setdefault("nit_proveedor", None)
            extracted_data.setdefault("direccion_proveedor", None)
            extracted_data.setdefault("subtotal", None)
            extracted_data.setdefault("impuestos", None)
            extracted_data.setdefault("total", None)
            extracted_data.setdefault("moneda", "COP")
            extracted_data.setdefault("items", [])
            
            print("  ✅ Campos extraídos")
            
            # d) Validación RAG local
            final_data = extracted_data
            
            if validator:
                print("  🔎 Validando con base de conocimiento...")
                try:
                    final_data = validator.validate(extracted_data, ocr_text)

                    # ✅ AJUSTE AÑADIDO (EVITA ERROR GEMINI_API_KEY)
                    final_data["llm_used"] = "none"
                    final_data["llm_status"] = "disabled"

                    status = final_data.get("validation_status", "DESCONOCIDO")
                    validations = final_data.get("validations", {})
                    
                    status_emoji = {
                        "APROBADO": "✅",
                        "ADVERTENCIA": "⚠️",
                        "FALLIDO": "❌"
                    }.get(status, "ℹ️")
                    
                    print(f"  {status_emoji} Estado: {status}")
                    
                    if validations:
                        for field, val_info in validations.items():
                            field_status = val_info.get("status", "N/A")
                            emoji = {
                                "APROBADO": "✓",
                                "ADVERTENCIA": "!",
                                "FALLIDO": "✗"
                            }.get(field_status, "?")
                            print(f"     {emoji} {field}: {field_status}")
                
                except Exception as e:
                    print(f"  ⚠️  Error en validación: {e}")
                    final_data = extracted_data
                    final_data["validations"] = {}
                    final_data["validation_status"] = "ERROR"

                    # ✅ AJUSTE AÑADIDO
                    final_data["llm_used"] = "none"
                    final_data["llm_status"] = "disabled"

            else:
                print("  ℹ️  Saltando validación (RAG no disponible)")
                final_data["validations"] = {}
                final_data["validation_status"] = "NO_VALIDADO"

                # ✅ AJUSTE AÑADIDO
                final_data["llm_used"] = "none"
                final_data["llm_status"] = "disabled"
            
            # Guardar JSON
            json_filename = f"{os.path.splitext(filename)[0]}.json"
            json_path = os.path.join(json_output_dir, json_filename)
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(final_data, f, ensure_ascii=False, indent=2, default=str)
            
            print(f"  💾 JSON guardado: {json_filename}")
            
            all_results.append({
                "source_file": filename,
                "data": final_data,
                "thumbnail_path": None
            })
        
        except Exception as e:
            print(f"  ❌ Error procesando {filename}: {e}")
            import traceback
            print(f"  📋 Traceback: {traceback.format_exc()}")
            continue
    
    # --- 4. Generar reporte ---
    if all_results:
        print("\n" + "=" * 70)
        print("📊 GENERANDO REPORTE CONSOLIDADO")
        print("=" * 70)
        
        try:
            report_path = os.path.join(report_output_dir, 'reporte_final.html')
            template_path = os.path.join(base_dir, 'templates', 'report_template.html')
            
            if not os.path.exists(template_path):
                print(f"⚠️  Template no encontrado: {template_path}")
                print("   Creando reporte en formato JSON...")
                report_path = os.path.join(report_output_dir, 'reporte_final.json')
                with open(report_path, 'w', encoding='utf-8') as f:
                    json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
            else:
                from datetime import datetime
                generate_report(
                    results=all_results,
                    template_path=template_path,
                    output_path=report_path,
                    generation_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
            
            print(f"✅ Reporte generado: {report_path}")
            
            print("\n📈 RESUMEN:")
            print(f"   • Total procesadas: {len(all_results)}")
            
            if args.use_rag:
                aprobadas = sum(1 for r in all_results if r['data'].get('validation_status') == 'APROBADO')
                advertencias = sum(1 for r in all_results if r['data'].get('validation_status') == 'ADVERTENCIA')
                fallidas = sum(1 for r in all_results if r['data'].get('validation_status') == 'FALLIDO')
                
                print(f"   • ✅ Aprobadas: {aprobadas}")
                print(f"   • ⚠️  Con advertencias: {advertencias}")
                print(f"   • ❌ Fallidas: {fallidas}")
        
        except Exception as e:
            print(f"❌ Error generando reporte: {e}")
            import traceback
            print(traceback.format_exc())
    else:
        print("\n⚠️  No se procesaron facturas exitosamente.")
    
    print("\n" + "=" * 70)
    print("✅ PROCESO FINALIZADO")
    print("=" * 70)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="🧾 Agente de Extracción de Datos en Facturas (Sin Gemini)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python main.py
  python main.py --facturas_dir ./mis_facturas
  python main.py --no-rag
  python main.py --facturas_dir ./data/facturas --output_dir ./resultados
        """
    )
    
    parser.add_argument(
        '--facturas_dir', 
        type=str, 
        help='Directorio con las facturas a procesar (default: data/facturas)'
    )
    parser.add_argument(
        '--output_dir', 
        type=str, 
        help='Directorio donde se guardarán los resultados (default: output)'
    )
    parser.add_argument(
        '--docs_dir', 
        type=str, 
        help='Directorio con documentos de conocimiento para RAG (default: data/docs)'
    )
    parser.add_argument(
        '--no-rag', 
        action='store_false', 
        dest='use_rag', 
        help='Deshabilitar validación con RAG'
    )
    
    parser.set_defaults(use_rag=True)
    
    args = parser.parse_args()
    
    try:
        main(args)
    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso interrumpido por el usuario")
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
