from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
from typing import Dict, Any
import torch

class LLMHandler:
    def __init__(self, model_name: str = "google/flan-t5-base"):
        """
        Inicializa el manejador del LLM cargando el modelo y el tokenizador.
        """
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
            # Usar pipeline para simplificar la inferencia
            self.nlp = pipeline("text2text-generation", model=self.model, tokenizer=self.tokenizer)
            print(f"Modelo LLM '{model_name}' cargado correctamente.")
        except Exception as e:
            print(f"Error al cargar el modelo LLM: {e}")
            print("Funcionalidad de LLM estará deshabilitada.")
            self.nlp = None

    def normalize_and_complete(self, extracted_data: Dict[str, Any], ocr_text: str) -> Dict[str, Any]:
        """
        Usa el LLM para normalizar y completar los datos extraídos.
        """
        if not self.nlp:
            return extracted_data

        # Crear un prompt para el LLM
        prompt = f"""
        Contexto: Se ha extraído el siguiente texto de una factura usando OCR:
        ---
        {ocr_text[:2000]}
        ---
        Tarea: Basado en el texto anterior, normaliza y completa los siguientes campos en formato JSON. 
        No inventes información que no esté en el texto. Si un campo no se encuentra, déjalo como null.

        Datos extraídos preliminarmente:
        {str(extracted_data)}

        Respuesta JSON esperada:
        """

        try:
            # Generar respuesta del LLM
            response = self.nlp(prompt, max_length=512, num_beams=3, early_stopping=True)
            
            # Procesar la respuesta
            if response and response[0]['generated_text']:
                # El LLM debería devolver un string con formato JSON
                llm_json_str = response[0]['generated_text']
                
                # Limpiar y parsear el JSON (esto es frágil y se debe mejorar)
                import json
                try:
                    # Intentar encontrar el JSON en la respuesta
                    json_match = re.search(r'\{.*\}', llm_json_str, re.DOTALL)
                    if json_match:
                        cleaned_json = json.loads(json_match.group(0))
                        
                        # Actualizar los datos extraídos con la versión del LLM
                        # Se debe hacer con cuidado para no sobrescribir datos buenos
                        for key, value in cleaned_json.items():
                            if key in extracted_data and value is not None:
                                extracted_data[key] = value
                        
                        print("Datos normalizados con LLM.")

                except (json.JSONDecodeError, AttributeError) as e:
                    print(f"No se pudo parsear la respuesta del LLM a JSON: {e}")
                    print(f"Respuesta recibida: {llm_json_str}")

        except Exception as e:
            print(f"Error durante la inferencia del LLM: {e}")
            
        return extracted_data

    def explain_ambiguity(self, field: str, value: Any, ocr_text: str) -> str:
        """
        Genera una explicación para un campo o valor ambiguo.
        """
        if not self.nlp:
            return "Funcionalidad de LLM no disponible."

        prompt = f"""
        Contexto: Se está procesando una factura con el siguiente texto:
        ---
        {ocr_text[:1000]}
        ---
        Pregunta: El campo '{field}' con valor '{value}' parece ambiguo o incorrecto. 
        Basado en el contexto, ¿cuál podría ser la interpretación correcta o por qué es ambiguo?
        Respuesta breve:
        """
        try:
            response = self.nlp(prompt, max_length=128)
            return response[0]['generated_text'] if response else "No se pudo generar una explicación."
        except Exception as e:
            print(f"Error al generar explicación con LLM: {e}")
            return "Error al generar explicación."

# Para poder importar la clase directamente
def get_llm_handler(model_name: str = "google/flan-t5-base") -> LLMHandler:
    return LLMHandler(model_name)
