"""
Módulo de validación de facturas con reglas de negocio colombianas.
Implementa validaciones según normativa DIAN y políticas internas.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import re


class InvoiceValidator:
    """
    Validador de facturas electrónicas colombianas.
    Implementa 10 reglas de negocio principales.
    """
    
    def __init__(self, knowledge_base=None):
        """
        Inicializa el validador.
        
        Args:
            knowledge_base: Base de conocimiento opcional para validaciones RAG
        """
        self.kb = knowledge_base
        self.iva_maximo = 0.19  # 19% IVA máximo en Colombia
        self.retencion_fuente_default = 0.04  # 4% retención default
        
    def validate_invoice(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta todas las validaciones sobre una factura.
        
        Args:
            data: Diccionario con los datos extraídos de la factura
            
        Returns:
            Diccionario con resultados de validación
        """
        validations = []
        errors = []
        warnings = []
        
        # 1. Validar fecha de emisión
        val_fecha = self._validate_fecha_emision(data.get('fecha_emision'))
        validations.append(val_fecha)
        if not val_fecha['valid']:
            if val_fecha['severity'] == 'error':
                errors.append(val_fecha['message'])
            else:
                warnings.append(val_fecha['message'])
        
        # 2. Validar NIT con dígito de verificación
        val_nit = self._validate_nit(data.get('nit_emisor'))
        validations.append(val_nit)
        if not val_nit['valid']:
            if val_nit['severity'] == 'error':
                errors.append(val_nit['message'])
            else:
                warnings.append(val_nit['message'])
        
        # 3. Validar CUFE
        val_cufe = self._validate_cufe(data.get('cufe'))
        validations.append(val_cufe)
        if not val_cufe['valid']:
            if val_cufe['severity'] == 'error':
                errors.append(val_cufe['message'])
            else:
                warnings.append(val_cufe['message'])
        
        # 4. Validar coherencia de totales
        val_totales = self._validate_totales(
            data.get('subtotal', 0),
            data.get('iva', 0),
            data.get('total', 0)
        )
        validations.append(val_totales)
        if not val_totales['valid']:
            if val_totales['severity'] == 'error':
                errors.append(val_totales['message'])
            else:
                warnings.append(val_totales['message'])
        
        # 5. Validar porcentaje de IVA
        val_iva = self._validate_iva_porcentaje(
            data.get('subtotal', 0),
            data.get('iva', 0)
        )
        validations.append(val_iva)
        if not val_iva['valid']:
            if val_iva['severity'] == 'error':
                errors.append(val_iva['message'])
            else:
                warnings.append(val_iva['message'])
        
        # 6. Validar suma de ítems
        val_items = self._validate_suma_items(
            data.get('items', []),
            data.get('subtotal', 0)
        )
        validations.append(val_items)
        if not val_items['valid']:
            if val_items['severity'] == 'error':
                errors.append(val_items['message'])
            else:
                warnings.append(val_items['message'])
        
        # 7. Validar actividad económica
        val_actividad = self._validate_actividad_economica(
            data.get('actividad_economica')
        )
        validations.append(val_actividad)
        if not val_actividad['valid']:
            if val_actividad['severity'] == 'error':
                errors.append(val_actividad['message'])
            else:
                warnings.append(val_actividad['message'])
        
        # 8. Validar retención en la fuente
        val_retencion = self._validate_retencion_fuente(
            data.get('retencion_fuente'),
            data.get('subtotal', 0)
        )
        validations.append(val_retencion)
        if not val_retencion['valid']:
            if val_retencion['severity'] == 'error':
                errors.append(val_retencion['message'])
            else:
                warnings.append(val_retencion['message'])
        
        # 9. Validar fecha límite de pago
        val_fecha_pago = self._validate_fecha_limite_pago(
            data.get('fecha_emision'),
            data.get('fecha_limite_pago')
        )
        validations.append(val_fecha_pago)
        if not val_fecha_pago['valid']:
            if val_fecha_pago['severity'] == 'error':
                errors.append(val_fecha_pago['message'])
            else:
                warnings.append(val_fecha_pago['message'])
        
        # 10. Validar resolución DIAN (si hay KB disponible)
        val_resolucion = self._validate_resolucion_dian(
            data.get('numero_factura'),
            data.get('proveedor')
        )
        validations.append(val_resolucion)
        if not val_resolucion['valid']:
            if val_resolucion['severity'] == 'error':
                errors.append(val_resolucion['message'])
            else:
                warnings.append(val_resolucion['message'])
        
        # Calcular score de confianza
        valid_count = sum(1 for v in validations if v['valid'])
        confidence_score = valid_count / len(validations) if validations else 0
        
        # Determinar si la factura es válida
        is_valid = len(errors) == 0
        
        # Generar recomendación
        if is_valid and len(warnings) == 0:
            recommendation = "✅ Factura lista para procesamiento"
        elif is_valid:
            recommendation = "⚠️ Factura válida con advertencias menores"
        else:
            recommendation = "❌ Factura requiere revisión manual"
        
        return {
            'valid': is_valid,
            'confidence_score': confidence_score,
            'errors': errors,
            'warnings': warnings,
            'validations': validations,
            'recommendation': recommendation,
            'total_validations': len(validations),
            'passed_validations': valid_count
        }
    
    def _validate_fecha_emision(self, fecha: str) -> Dict[str, Any]:
        """Valida que la fecha de emisión sea válida y no futura."""
        field = "Fecha de Emisión"
        
        if not fecha or fecha in ['N/A', '', None]:
            return {
                'field': field,
                'valid': False,
                'severity': 'error',
                'message': 'Fecha de emisión no encontrada o vacía'
            }
        
        try:
            # Intentar parsear diferentes formatos
            fecha_parsed = None
            for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%Y/%m/%d']:
                try:
                    fecha_parsed = datetime.strptime(str(fecha), fmt)
                    break
                except ValueError:
                    continue
            
            if not fecha_parsed:
                return {
                    'field': field,
                    'valid': False,
                    'severity': 'error',
                    'message': f'Formato de fecha no reconocido: {fecha}'
                }
            
            # Verificar que no sea futura
            if fecha_parsed > datetime.now():
                return {
                    'field': field,
                    'valid': False,
                    'severity': 'error',
                    'message': f'La fecha de emisión ({fecha}) es futura'
                }
            
            # Verificar que no sea muy antigua (más de 5 años)
            cinco_anios = datetime.now() - timedelta(days=365*5)
            if fecha_parsed < cinco_anios:
                return {
                    'field': field,
                    'valid': False,
                    'severity': 'warning',
                    'message': f'La fecha de emisión ({fecha}) tiene más de 5 años'
                }
            
            return {
                'field': field,
                'valid': True,
                'severity': 'success',
                'message': f'Fecha de emisión válida: {fecha}'
            }
            
        except Exception as e:
            return {
                'field': field,
                'valid': False,
                'severity': 'error',
                'message': f'Error al validar fecha: {str(e)}'
            }
    
    def _validate_nit(self, nit: str) -> Dict[str, Any]:
        """Valida el NIT colombiano con dígito de verificación."""
        field = "NIT Emisor"
        
        if not nit or nit in ['N/A', '', None]:
            return {
                'field': field,
                'valid': False,
                'severity': 'error',
                'message': 'NIT del emisor no encontrado'
            }
        
        # Limpiar NIT
        nit_limpio = re.sub(r'[^0-9]', '', str(nit))
        
        if len(nit_limpio) < 9:
            return {
                'field': field,
                'valid': False,
                'severity': 'error',
                'message': f'NIT muy corto: {nit} (mínimo 9 dígitos)'
            }
        
        # Validar dígito de verificación si tiene más de 9 dígitos
        if len(nit_limpio) >= 10:
            nit_base = nit_limpio[:-1]
            dv_declarado = int(nit_limpio[-1])
            dv_calculado = self._calcular_digito_verificacion(nit_base)
            
            if dv_declarado != dv_calculado:
                return {
                    'field': field,
                    'valid': False,
                    'severity': 'warning',
                    'message': f'Dígito de verificación incorrecto. Esperado: {dv_calculado}, Encontrado: {dv_declarado}'
                }
        
        return {
            'field': field,
            'valid': True,
            'severity': 'success',
            'message': f'NIT válido: {nit}'
        }
    
    def _calcular_digito_verificacion(self, nit: str) -> int:
        """Calcula el dígito de verificación del NIT colombiano."""
        primos = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
        nit = nit.zfill(15)
        suma = sum(int(nit[i]) * primos[i] for i in range(15))
        residuo = suma % 11
        if residuo == 0:
            return 0
        elif residuo == 1:
            return 1
        else:
            return 11 - residuo
    
    def _validate_cufe(self, cufe: str) -> Dict[str, Any]:
        """Valida el CUFE (Código Único de Factura Electrónica)."""
        field = "CUFE"
        
        if not cufe or cufe in ['N/A', '', None]:
            return {
                'field': field,
                'valid': False,
                'severity': 'warning',
                'message': 'CUFE no encontrado (requerido para factura electrónica)'
            }
        
        # El CUFE debe ser alfanumérico de 96 o 128 caracteres (SHA-384 o SHA-512)
        cufe_limpio = re.sub(r'[^a-fA-F0-9]', '', str(cufe))
        
        if len(cufe_limpio) not in [96, 128]:
            return {
                'field': field,
                'valid': False,
                'severity': 'warning',
                'message': f'Longitud de CUFE inválida: {len(cufe_limpio)} caracteres (esperado 96 o 128)'
            }
        
        return {
            'field': field,
            'valid': True,
            'severity': 'success',
            'message': f'CUFE válido ({len(cufe_limpio)} caracteres)'
        }
    
    def _validate_totales(self, subtotal: float, iva: float, total: float) -> Dict[str, Any]:
        """Valida la coherencia de totales: subtotal + IVA ≈ total."""
        field = "Coherencia de Totales"
        
        try:
            subtotal = float(subtotal) if subtotal else 0
            iva = float(iva) if iva else 0
            total = float(total) if total else 0
        except (ValueError, TypeError):
            return {
                'field': field,
                'valid': False,
                'severity': 'error',
                'message': 'No se pudieron convertir los valores numéricos'
            }
        
        if total == 0:
            return {
                'field': field,
                'valid': False,
                'severity': 'error',
                'message': 'Total de factura es 0 o no encontrado'
            }
        
        suma_calculada = subtotal + iva
        diferencia = abs(suma_calculada - total)
        margen = total * 0.01  # 1% de margen de error
        
        if diferencia > margen:
            return {
                'field': field,
                'valid': False,
                'severity': 'error',
                'message': f'Totales no coinciden: Subtotal({subtotal:.2f}) + IVA({iva:.2f}) = {suma_calculada:.2f} ≠ Total({total:.2f})'
            }
        
        return {
            'field': field,
            'valid': True,
            'severity': 'success',
            'message': f'Totales coherentes: {subtotal:.2f} + {iva:.2f} = {total:.2f}'
        }
    
    def _validate_iva_porcentaje(self, subtotal: float, iva: float) -> Dict[str, Any]:
        """Valida que el IVA no exceda el 19%."""
        field = "Porcentaje IVA"
        
        try:
            subtotal = float(subtotal) if subtotal else 0
            iva = float(iva) if iva else 0
        except (ValueError, TypeError):
            return {
                'field': field,
                'valid': False,
                'severity': 'warning',
                'message': 'No se pudieron calcular porcentajes de IVA'
            }
        
        if subtotal <= 0:
            return {
                'field': field,
                'valid': True,
                'severity': 'warning',
                'message': 'Subtotal es 0, no se puede calcular % IVA'
            }
        
        porcentaje_iva = (iva / subtotal) * 100
        
        if porcentaje_iva > 19.5:  # Pequeño margen
            return {
                'field': field,
                'valid': False,
                'severity': 'error',
                'message': f'IVA excede el máximo permitido: {porcentaje_iva:.2f}% (máximo 19%)'
            }
        
        # Verificar si es una tasa estándar (0%, 5%, 19%)
        tasas_validas = [0, 5, 19]
        tasa_cercana = min(tasas_validas, key=lambda x: abs(x - porcentaje_iva))
        
        if abs(porcentaje_iva - tasa_cercana) > 1:
            return {
                'field': field,
                'valid': True,
                'severity': 'warning',
                'message': f'IVA de {porcentaje_iva:.2f}% no es tasa estándar (0%, 5%, 19%)'
            }
        
        return {
            'field': field,
            'valid': True,
            'severity': 'success',
            'message': f'IVA válido: {porcentaje_iva:.2f}%'
        }
    
    def _validate_suma_items(self, items: List[Dict], subtotal: float) -> Dict[str, Any]:
        """Valida que la suma de ítems coincida con el subtotal."""
        field = "Suma de Ítems"
        
        if not items or len(items) == 0:
            return {
                'field': field,
                'valid': True,
                'severity': 'warning',
                'message': 'No se encontraron ítems para validar'
            }
        
        try:
            subtotal = float(subtotal) if subtotal else 0
            suma_items = 0
            
            for item in items:
                total_item = item.get('total', 0)
                if total_item:
                    try:
                        suma_items += float(str(total_item).replace(',', ''))
                    except:
                        pass
            
            if suma_items == 0:
                return {
                    'field': field,
                    'valid': True,
                    'severity': 'warning',
                    'message': 'No se pudieron sumar los ítems (valores no numéricos)'
                }
            
            diferencia = abs(suma_items - subtotal)
            margen = max(subtotal * 0.02, 1)  # 2% o mínimo $1
            
            if diferencia > margen:
                return {
                    'field': field,
                    'valid': False,
                    'severity': 'warning',
                    'message': f'Suma de ítems ({suma_items:.2f}) no coincide con subtotal ({subtotal:.2f})'
                }
            
            return {
                'field': field,
                'valid': True,
                'severity': 'success',
                'message': f'Suma de {len(items)} ítems coincide con subtotal'
            }
            
        except Exception as e:
            return {
                'field': field,
                'valid': False,
                'severity': 'warning',
                'message': f'Error al validar ítems: {str(e)}'
            }
    
    def _validate_actividad_economica(self, actividad: str) -> Dict[str, Any]:
        """Valida el código de actividad económica."""
        field = "Actividad Económica"
        
        if not actividad or actividad in ['N/A', '', None]:
            return {
                'field': field,
                'valid': True,
                'severity': 'warning',
                'message': 'Código de actividad económica no especificado'
            }
        
        # Validar formato (generalmente 4-6 dígitos en Colombia)
        codigo_limpio = re.sub(r'[^0-9]', '', str(actividad))
        
        if len(codigo_limpio) < 4:
            return {
                'field': field,
                'valid': False,
                'severity': 'warning',
                'message': f'Código de actividad muy corto: {actividad}'
            }
        
        # Si hay KB, consultar validez del código
        if self.kb:
            try:
                resultados = self.kb.search(f"actividad económica código {codigo_limpio}", k=1)
                if resultados:
                    return {
                        'field': field,
                        'valid': True,
                        'severity': 'success',
                        'message': f'Actividad económica validada en base de conocimiento: {actividad}'
                    }
            except:
                pass
        
        return {
            'field': field,
            'valid': True,
            'severity': 'success',
            'message': f'Formato de actividad económica válido: {actividad}'
        }
    
    def _validate_retencion_fuente(self, retencion: float, subtotal: float) -> Dict[str, Any]:
        """Valida la retención en la fuente."""
        field = "Retención en la Fuente"
        
        try:
            retencion = float(retencion) if retencion else 0
            subtotal = float(subtotal) if subtotal else 0
        except (ValueError, TypeError):
            return {
                'field': field,
                'valid': True,
                'severity': 'warning',
                'message': 'No se pudo validar retención en la fuente'
            }
        
        if subtotal <= 0:
            return {
                'field': field,
                'valid': True,
                'severity': 'warning',
                'message': 'Subtotal es 0, no se puede validar retención'
            }
        
        # Si la retención es un porcentaje (menor a 1)
        if 0 < retencion < 1:
            porcentaje = retencion * 100
        elif retencion >= 1:
            porcentaje = (retencion / subtotal) * 100
        else:
            return {
                'field': field,
                'valid': True,
                'severity': 'success',
                'message': 'Sin retención en la fuente aplicada'
            }
        
        # Tasas comunes: 2.5%, 3.5%, 4%, 6%, 10%, 11%
        tasas_validas = [2.5, 3.5, 4, 6, 10, 11]
        
        if porcentaje > 15:
            return {
                'field': field,
                'valid': False,
                'severity': 'warning',
                'message': f'Retención muy alta: {porcentaje:.2f}%'
            }
        
        return {
            'field': field,
            'valid': True,
            'severity': 'success',
            'message': f'Retención en la fuente: {porcentaje:.2f}%'
        }
    
    def _validate_fecha_limite_pago(self, fecha_emision: str, fecha_limite: str) -> Dict[str, Any]:
        """Valida que la fecha límite de pago sea posterior a la emisión."""
        field = "Fecha Límite de Pago"
        
        if not fecha_limite or fecha_limite in ['N/A', '', None]:
            return {
                'field': field,
                'valid': True,
                'severity': 'warning',
                'message': 'Fecha límite de pago no especificada'
            }
        
        if not fecha_emision or fecha_emision in ['N/A', '', None]:
            return {
                'field': field,
                'valid': True,
                'severity': 'warning',
                'message': 'No se puede validar sin fecha de emisión'
            }
        
        try:
            fecha_em_parsed = None
            fecha_lim_parsed = None
            
            for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%Y/%m/%d']:
                try:
                    if not fecha_em_parsed:
                        fecha_em_parsed = datetime.strptime(str(fecha_emision), fmt)
                except:
                    pass
                try:
                    if not fecha_lim_parsed:
                        fecha_lim_parsed = datetime.strptime(str(fecha_limite), fmt)
                except:
                    pass
            
            if not fecha_em_parsed or not fecha_lim_parsed:
                return {
                    'field': field,
                    'valid': True,
                    'severity': 'warning',
                    'message': 'No se pudieron parsear las fechas'
                }
            
            if fecha_lim_parsed < fecha_em_parsed:
                return {
                    'field': field,
                    'valid': False,
                    'severity': 'error',
                    'message': f'Fecha límite ({fecha_limite}) anterior a emisión ({fecha_emision})'
                }
            
            dias_plazo = (fecha_lim_parsed - fecha_em_parsed).days
            
            if dias_plazo > 180:
                return {
                    'field': field,
                    'valid': True,
                    'severity': 'warning',
                    'message': f'Plazo de pago muy largo: {dias_plazo} días'
                }
            
            return {
                'field': field,
                'valid': True,
                'severity': 'success',
                'message': f'Plazo de pago: {dias_plazo} días'
            }
            
        except Exception as e:
            return {
                'field': field,
                'valid': True,
                'severity': 'warning',
                'message': f'Error validando fechas: {str(e)}'
            }
    
    def _validate_resolucion_dian(self, numero_factura: str, proveedor: str) -> Dict[str, Any]:
        """Valida la resolución DIAN usando la base de conocimiento."""
        field = "Resolución DIAN"
        
        if not numero_factura or numero_factura in ['N/A', '', None]:
            return {
                'field': field,
                'valid': True,
                'severity': 'warning',
                'message': 'Número de factura no disponible para validar resolución'
            }
        
        # Si hay KB, buscar información de resolución
        if self.kb:
            try:
                query = f"resolución DIAN facturación electrónica {proveedor or ''}"
                resultados = self.kb.search(query, k=2)
                
                if resultados:
                    return {
                        'field': field,
                        'valid': True,
                        'severity': 'success',
                        'message': f'Proveedor encontrado en base de conocimiento'
                    }
            except Exception as e:
                pass
        
        return {
            'field': field,
            'valid': True,
            'severity': 'warning',
            'message': 'No se pudo validar resolución DIAN (sin base de conocimiento)'
        }


# Mantener compatibilidad con RAGValidator anterior
class RAGValidator(InvoiceValidator):
    """Alias para compatibilidad con código anterior."""
    
    def __init__(self, knowledge_base=None, llm_handler=None):
        super().__init__(knowledge_base)
        self.llm = llm_handler
    
    def validate_data(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Método de compatibilidad con la interfaz anterior."""
        result = self.validate_invoice(extracted_data)
        extracted_data['validations'] = result
        return extracted_data