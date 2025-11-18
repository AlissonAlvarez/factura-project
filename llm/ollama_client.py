import ollama

class OllamaClient:
    def __init__(self, model="gemma3"):
        self.model = model

    def generate_completion(self, prompt):
        """
        Genera una completación de texto usando Ollama.
        """
        try:
            response = ollama.chat(
                model=self.model,
                messages=[{'role': 'user', 'content': prompt}]
            )
            return response['message']['content']
        except Exception as e:
            print(f"Error al contactar Ollama: {e}")
            return "Error: No se pudo contactar al LLM."
