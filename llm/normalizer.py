"""
Normalizador con LLM local (Ollama) para mejorar extracción.
Se usa SOLO si Ollama está disponible, sino usa regex puro.
"""
import requests
import json
from typing import Dict, Any, Optional


class LLMNormalizer:
    """
    Usa Ollama (local) para normalizar y completar datos extraídos.
    Cumple con requisito: "LLM para normalizar, completar y explicar campos ambiguos"
    """
    
    def __init__(self, model: str = "llama2", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self.api_url = f"{base_url}/api/generate"
        self.available = self._check_availability()
    
    def _check_availability(self) -> bool:
        """Verifica si Ollama está disponible."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def normalize_extracted_data(self, raw_data: Dict[str, Any], ocr_text: str) -> Dict[str, Any]:
        """
        Normaliza y completa datos usando LLM.
        
        Args:
            raw_data: Datos extraídos por regex
            ocr_text: Texto original OCR
        
        Returns:
            Datos normalizados y completados
        """
        if not self.available:
            print("⚠️  LLM local no disponible, usando extracción basada en reglas")
            return raw_data
        
        # Identificar campos faltantes o ambiguos
        missing_fields = [k for k, v in raw_data.items() if v is None and k != "validations"]
        
        if not missing_fields:
            return raw_data  # Nada que normalizar
        
        print(f"🤖 LLM: Intentando completar campos: {', '.join(missing_fields)}")
        
        # Usar LLM para completar campos específicos
        for field in missing_fields:
            if field in ["numero_factura", "fecha_emision", "nit_proveedor"]:
                value = self._extract_field_with_llm(field, ocr_text)
                if value:
                    raw_data[field] = value
                    print(f"   ✓ {field}: {value}")
        
        return raw_data
    
    def _extract_field_with_llm(self, field_name: str, text: str) -> Optional[str]:
        """Extrae un campo específico usando LLM."""
        
        prompts = {
            "numero_factura": """Encuentra el número de factura en este texto. 
Busca términos como "Invoice", "Factura", "Bill Number".
Responde SOLO con el número, sin explicaciones.
Si no lo encuentras, responde "NULL".""",
            
            "fecha_emision": """Encuentra la fecha de emisión de la factura.
Busca términos como "Date", "Fecha", cerca del inicio del documento.
Responde en formato YYYY-MM-DD.
Si no la encuentras, responde "NULL".""",
            
            "nit_proveedor": """Encuentra el NIT o Tax ID del CLIENTE (Client), NO del vendedor (Seller).
Busca después de "Client:" o "Buyer:".
Responde SOLO con el número.
Si no lo encuentras, responde "NULL"."""
        }
        
        prompt = prompts.get(field_name)
        if not prompt:
            return None
        
        full_prompt = f"""{prompt}

Texto de la factura:
---
{text[:1000]}  
---

Respuesta:"""
        
        try:
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 50
                    }
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                answer = result.get("response", "").strip()
                
                # Limpiar respuesta
                answer = answer.replace("NULL", "").replace("N/A", "").strip()
                
                if answer and answer.lower() != "null":
                    return answer
        
        except Exception as e:
            print(f"   ⚠️  Error en LLM para {field_name}: {e}")
        
        return None
    
    def explain_ambiguity(self, field_name: str, extracted_value: Any, ocr_text: str) -> str:
        """
        Genera explicación de por qué un campo es ambiguo.
        Cumple requisito: "explicar campos ambiguos o faltantes"
        """
        if not self.available:
            return "Campo ambiguo o no encontrado."
        
        prompt = f"""Explica brevemente por qué el campo "{field_name}" 
con valor "{extracted_value}" podría ser ambiguo o incorrecto en esta factura.

Contexto:
{ocr_text[:500]}

Respuesta (máximo 50 palabras):"""
        
        try:
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 100}
                },
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json().get("response", "").strip()
        except:
            pass
        
        return "Campo ambiguo o no encontrado."


# Singleton global
_normalizer_instance = None

def get_llm_normalizer() -> LLMNormalizer:
    """Obtiene instancia única del normalizador."""
    global _normalizer_instance
    if _normalizer_instance is None:
        _normalizer_instance = LLMNormalizer()
    return _normalizer_instance