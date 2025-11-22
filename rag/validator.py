from .knowledge_base import KnowledgeBase
from llm.llm_handler import LLMHandler
from typing import Dict, Any, List, Tuple

class RAGValidator:
    def __init__(self, knowledge_base: KnowledgeBase, llm_handler: LLMHandler):
        """
        Inicializa el validador RAG.
        """
        self.kb = knowledge_base
        self.llm = llm_handler

    def validate_data(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valida los datos extraídos usando el sistema RAG.
        """
        validations = {}

        # 1. Validar NIT/RUT del proveedor
        nit = extracted_data.get("nit_proveedor")
        if nit:
            validations["nit_proveedor"] = self._validate_field(
                "NIT del proveedor", nit,
                "¿El NIT del proveedor es válido y está en la lista de proveedores autorizados?"
            )

        # 2. Validar coherencia de totales
        subtotal = extracted_data.get("subtotal", 0.0) or 0.0
        impuestos = extracted_data.get("impuestos", 0.0) or 0.0
        total = extracted_data.get("total", 0.0) or 0.0
        if subtotal > 0 and total > 0:
            if abs((subtotal + impuestos) - total) > 0.02: # Margen de error pequeño
                validations["totales"] = {
                    "status": "FALLIDO",
                    "explicacion": f"La suma del subtotal ({subtotal}) y los impuestos ({impuestos}) no coincide con el total ({total}).",
                    "contexto_documental": []
                }
            else:
                 validations["totales"] = {
                    "status": "APROBADO",
                    "explicacion": "La suma de subtotal e impuestos coincide con el total.",
                    "contexto_documental": []
                }

        # 3. Validar porcentaje de IVA
        if subtotal > 0 and impuestos > 0:
            iva_percent = (impuestos / subtotal) * 100
            validations["iva_porcentaje"] = self._validate_field(
                "Porcentaje de IVA", f"{iva_percent:.2f}%",
                f"¿Es un {iva_percent:.2f}% de IVA un porcentaje permitido según las políticas de gastos?"
            )

        extracted_data["validations"] = validations
        return extracted_data

    def _validate_field(self, field_name: str, value: str, question: str) -> Dict[str, Any]:
        """
        Función genérica para validar un campo usando RAG + LLM.
        """
        # Buscar contexto en la base de conocimiento
        context_results = self.kb.search(question, k=2)
        context = "\n".join([f"- {chunk} (Fuente: {source})" for chunk, source in context_results])

        # Crear prompt para el LLM
        prompt = f"""
        Contexto extraído de documentos de políticas internas:
        ---
        {context if context else "No se encontró contexto relevante en los documentos."} 
        ---
        Tarea: Evalúa la siguiente información de una factura y determina si es válida según el contexto.
        - Campo: {field_name}
        - Valor: {value}
        - Pregunta de validación: {question}

        Responde con "APROBADO" si el valor es claramente válido según el contexto, "FALLIDO" si es inválido,
        o "ADVERTENCIA" si no hay suficiente información para decidir.
        Justifica brevemente tu respuesta.

        Formato de respuesta: [ESTADO] | [Justificación]
        """

        # =====================================================
        # 🔧 AJUSTE NECESARIO — MANEJO CUANDO FALTA EL LLM/API
        # =====================================================
        if not self.llm or not hasattr(self.llm, "nlp") or self.llm.nlp is None:
            return {
                "status": "ADVERTENCIA",
                "explicacion": "El modelo LLM no está inicializado o no tiene clave configurada.",
                "contexto_documental": context_results
            }
        # =====================================================

        # Obtener respuesta del LLM
        response = self.llm.nlp(prompt, max_length=256)[0]['generated_text']
        
        # Parsear respuesta
        status = "ADVERTENCIA"
        explanation = response
        if "|" in response:
            parts = response.split("|", 1)
            status_str = parts[0].strip().upper()
            if status_str in ["APROBADO", "FALLIDO", "ADVERTENCIA"]:
                status = status_str
            explanation = parts[1].strip()

        return {
            "status": status,
            "explicacion": explanation,
            "contexto_documental": [{"chunk": r[0], "source": r[1]} for r in context_results]
        }
