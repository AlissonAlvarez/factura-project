"""
Módulo para generar reportes de facturas en JSON y PDF
Ubicación: reporter/generate_report.py
"""

import json
import os
from datetime import datetime
from .report_generator_pdf import generate_pdf_report


class ReportGenerator:
    """Generador de reportes en múltiples formatos"""
    
    def __init__(self, template_dir='templates'):
        """
        Inicializar generador de reportes
        
        Args:
            template_dir: Directorio de plantillas (no se usa con ReportLab pero se mantiene para compatibilidad)
        """
        self.template_dir = template_dir
    
    def to_json(self, data, output_path):
        """
        Guardar datos en formato JSON
        
        Args:
            data: Diccionario con datos a guardar
            output_path: Ruta del archivo de salida
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        
        return output_path
    
    def to_pdf(self, data, validation_results=None, file_name=None, output_path=None):
        """
        Generar reporte en PDF usando ReportLab
        
        Args:
            data: Diccionario con datos de la factura
            validation_results: Resultados de validación (opcional, se puede incluir en data)
            file_name: Nombre del archivo fuente
            output_path: Ruta del archivo PDF de salida
        
        Returns:
            str: Ruta del archivo generado
        """
        # Asegurar que validation_results esté en data
        if validation_results and 'validations' not in data:
            data['validations'] = validation_results
        
        # Preparar estructura de resultados
        results = [{
            'source_file': file_name or 'factura.jpg',
            'data': data,
            'thumbnail_path': None
        }]
        
        # Generar PDF
        return generate_pdf_report(
            results=results,
            output_path=output_path,
            generation_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )


def generate_report(results, template_path=None, output_path=None, generation_date=None):
    """
    Función helper para generar reportes (mantiene compatibilidad con código existente)
    
    Args:
        results: Lista de resultados de facturas procesadas
        template_path: Ruta de plantilla (no se usa con ReportLab)
        output_path: Ruta del archivo de salida
        generation_date: Fecha de generación
    
    Returns:
        str: Ruta del archivo generado
    """
    if output_path is None:
        output_path = f"output/reports/reporte_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    return generate_pdf_report(
        results=results,
        output_path=output_path,
        generation_date=generation_date
    )