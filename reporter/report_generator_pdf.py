"""
Módulo para generar reportes de facturas en formato PDF
Ubicación: reporter/report_generator_pdf.py
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime
import os


class PDFReportGenerator:
    """Generador de reportes PDF para facturas procesadas"""
    
    def __init__(self, output_path, page_size=letter):
        self.output_path = output_path
        self.page_size = page_size
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        
    def _setup_custom_styles(self):
        """Configurar estilos personalizados"""
        # Título principal
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#667eea'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Subtítulo de factura
        self.styles.add(ParagraphStyle(
            name='InvoiceTitle',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#667eea'),
            spaceAfter=12,
            spaceBefore=12,
            fontName='Helvetica-Bold'
        ))
        
        # Sección
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#764ba2'),
            spaceAfter=8,
            spaceBefore=8,
            fontName='Helvetica-Bold'
        ))
        
        # Normal con mejor espaciado
        self.styles.add(ParagraphStyle(
            name='CustomNormal',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=6
        ))
    
    def generate_report(self, results, generation_date=None):
        """
        Generar reporte PDF completo
        
        Args:
            results: Lista de diccionarios con información de facturas
            generation_date: Fecha de generación (opcional)
        """
        if generation_date is None:
            generation_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Crear documento
        doc = SimpleDocTemplate(
            self.output_path,
            pagesize=self.page_size,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        # Contenedor de elementos
        story = []
        
        # Encabezado del reporte
        story.extend(self._create_header(generation_date))
        story.append(Spacer(1, 0.3*inch))
        
        # Procesar cada factura
        for idx, result in enumerate(results):
            story.extend(self._create_invoice_section(result))
            
            # Salto de página entre facturas (excepto la última)
            if idx < len(results) - 1:
                story.append(PageBreak())
        
        # Pie de página
        story.extend(self._create_footer())
        
        # Construir PDF
        doc.build(story)
        
        return self.output_path
    
    def _create_header(self, generation_date):
        """Crear encabezado del reporte"""
        elements = []
        
        # Título (sin emoji para compatibilidad)
        title = Paragraph("Reporte de Facturas Procesadas", self.styles['CustomTitle'])
        elements.append(title)
        
        # Fecha de generación
        date_text = f"<i>Generado: {generation_date}</i>"
        date_para = Paragraph(date_text, self.styles['Normal'])
        elements.append(date_para)
        
        # Línea separadora
        elements.append(Spacer(1, 0.2*inch))
        
        return elements
    
    def _create_invoice_section(self, result):
        """Crear sección de una factura"""
        elements = []
        data = result.get('data', {})
        source_file = result.get('source_file', 'N/A')
        
        # Título de la factura
        invoice_title = Paragraph(f"Factura: {source_file}", self.styles['InvoiceTitle'])
        elements.append(invoice_title)
        elements.append(Spacer(1, 0.1*inch))
        
        # Información general
        elements.extend(self._create_info_grid(data))
        elements.append(Spacer(1, 0.2*inch))
        
        # Tabla de items
        elements.extend(self._create_items_table(data))
        elements.append(Spacer(1, 0.2*inch))
        
        # Totales
        elements.extend(self._create_totals_section(data))
        elements.append(Spacer(1, 0.2*inch))
        
        # Validaciones
        if data.get('validations'):
            elements.extend(self._create_validations_section(data))
        
        return elements
    
    def _create_info_grid(self, data):
        """Crear grid de información general"""
        elements = []
        
        # Datos a mostrar
        info_data = [
            ['Numero de Factura:', str(data.get('numero_factura', 'N/A'))],
            ['Fecha de Emision:', str(data.get('fecha_emision', 'N/A'))],
            ['Proveedor:', str(data.get('proveedor', 'N/A'))],
            ['NIT:', str(data.get('nit_proveedor', 'N/A'))],
            ['Direccion:', str(data.get('direccion_proveedor', 'N/A'))],
            ['Moneda:', str(data.get('moneda', 'COP'))]
        ]
        
        # Crear tabla
        table = Table(info_data, colWidths=[2*inch, 4*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#667eea')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(table)
        return elements
    
    def _create_items_table(self, data):
        """Crear tabla de items"""
        elements = []
        
        # Encabezado
        section_title = Paragraph("Items de la Factura", self.styles['SectionHeader'])
        elements.append(section_title)
        elements.append(Spacer(1, 0.1*inch))
        
        items = data.get('items', [])
        
        if not items:
            no_items = Paragraph(
                "<i>No se encontraron items en esta factura</i>",
                self.styles['CustomNormal']
            )
            elements.append(no_items)
            return elements
        
        # Datos de la tabla
        table_data = [['Descripcion', 'Cantidad', 'Precio Unitario', 'Total']]
        moneda = data.get('moneda', 'COP')
        
        for item in items:
            desc = item.get('descripcion') or item.get('description', 'N/A')
            cant = str(item.get('cantidad') or item.get('quantity', 'N/A'))
            precio = item.get('precio_unitario') or item.get('unit_price', 0)
            total = item.get('total', 0)
            
            # Truncar descripción larga
            if len(str(desc)) > 50:
                desc = str(desc)[:47] + "..."
            
            # Formatear precios
            try:
                precio_fmt = f"{float(precio):,.2f} {moneda}"
            except:
                precio_fmt = f"{precio} {moneda}"
            
            try:
                total_fmt = f"{float(total):,.2f} {moneda}"
            except:
                total_fmt = f"{total} {moneda}"
            
            table_data.append([
                str(desc),
                str(cant),
                precio_fmt,
                total_fmt
            ])
        
        # Crear tabla
        table = Table(table_data, colWidths=[3*inch, 0.8*inch, 1.3*inch, 1.3*inch])
        table.setStyle(TableStyle([
            # Encabezado
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('ALIGN', (1, 0), (-1, 0), 'CENTER'),
            
            # Cuerpo
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # Alternar colores de fila
            *[('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f8f9fa'))
              for i in range(2, len(table_data), 2)]
        ]))
        
        elements.append(table)
        return elements
    
    def _create_totals_section(self, data):
        """Crear sección de totales"""
        elements = []
        
        moneda = data.get('moneda', 'COP')
        
        # Convertir a float de forma segura
        try:
            subtotal = float(data.get('subtotal', 0))
        except:
            subtotal = 0.0
        
        try:
            impuestos = float(data.get('impuestos', 0))
        except:
            impuestos = 0.0
        
        try:
            total = float(data.get('total', 0))
        except:
            total = 0.0
        
        # Datos
        totals_data = [
            ['Subtotal:', f"{subtotal:,.2f} {moneda}"],
            ['Impuestos:', f"{impuestos:,.2f} {moneda}"],
            ['TOTAL:', f"{total:,.2f} {moneda}"]
        ]
        
        # Tabla
        table = Table(totals_data, colWidths=[4.5*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, 1), 10),
            ('FONTSIZE', (0, 2), (-1, 2), 12),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#667eea')),
            ('TEXTCOLOR', (0, 2), (-1, 2), colors.HexColor('#667eea')),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('PADDING', (0, 0), (-1, -1), 10),
            ('BOX', (0, 0), (-1, -1), 1, colors.grey),
        ]))
        
        elements.append(table)
        return elements
    
    def _create_validations_section(self, data):
        """Crear sección de validaciones"""
        elements = []
        
        # Encabezado
        section_title = Paragraph("Validaciones Realizadas", self.styles['SectionHeader'])
        elements.append(section_title)
        elements.append(Spacer(1, 0.1*inch))
        
        validations = data.get('validations', {})
        
        for field, validation in validations.items():
            status = validation.get('status', 'DESCONOCIDO')
            explicacion = validation.get('explicacion', '')
            contexto = validation.get('contexto_documental', [])
            
            # Color según estado
            if status == 'APROBADO':
                text_color = colors.HexColor('#155724')
            elif status == 'ADVERTENCIA':
                text_color = colors.HexColor('#856404')
            else:
                text_color = colors.HexColor('#721c24')
            
            # Título del campo
            field_name = field.replace('_', ' ').title()
            field_text = f"<b>{field_name}</b> - <font color='{text_color.hexval()}'>{status}</font>"
            field_para = Paragraph(field_text, self.styles['CustomNormal'])
            elements.append(field_para)
            
            # Explicación
            if explicacion:
                # Limpiar texto para PDF
                explicacion_clean = str(explicacion).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                expl_para = Paragraph(explicacion_clean, self.styles['CustomNormal'])
                elements.append(expl_para)
            
            # Contexto documental
            if contexto and len(contexto) > 0:
                source = contexto[0].get('source', 'N/A')
                ref_text = f"<i>Referencia: {source}</i>"
                ref_para = Paragraph(ref_text, self.styles['CustomNormal'])
                elements.append(ref_para)
            
            elements.append(Spacer(1, 0.1*inch))
        
        return elements
    
    def _create_footer(self):
        """Crear pie de página"""
        elements = []
        
        elements.append(Spacer(1, 0.3*inch))
        
        footer_text = """
        <para align=center>
        <i>Reporte generado automaticamente por el Sistema de Procesamiento de Facturas</i><br/>
        (c) 2025 - Deep Learning Project
        </para>
        """
        
        footer_para = Paragraph(footer_text, self.styles['Normal'])
        elements.append(footer_para)
        
        return elements


def generate_pdf_report(results, output_path, generation_date=None):
    """
    Función helper para generar reporte PDF
    
    Args:
        results: Lista de resultados de facturas
        output_path: Ruta del archivo PDF de salida
        generation_date: Fecha de generación (opcional)
    
    Returns:
        str: Ruta del archivo generado
    """
    # Crear directorio si no existe
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Generar reporte
    generator = PDFReportGenerator(output_path)
    return generator.generate_report(results, generation_date)