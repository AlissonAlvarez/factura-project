import os
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from pdfplumber import open as open_pdf
# Para DOCX, necesitaríamos python-docx
# from docx import Document
from typing import List, Tuple

class KnowledgeBase:
    def __init__(self, documents_path: str, model_name: str = 'all-MiniLM-L6-v2'):
        """
        Inicializa la base de conocimiento.
        """
        self.documents_path = documents_path
        self.model = SentenceTransformer(model_name)
        self.index = None
        self.chunks = []
        self.chunk_sources = []

    def build(self):
        """
        Construye el índice FAISS a partir de los documentos en la ruta especificada.
        """
        print("Construyendo base de conocimiento...")
        self._extract_chunks_from_docs()
        
        if not self.chunks:
            print("No se encontraron fragmentos de texto en los documentos. La base de conocimiento está vacía.")
            return

        print(f"Codificando {len(self.chunks)} fragmentos de texto...")
        embeddings = self.model.encode(self.chunks, show_progress_bar=True)
        
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings)
        
        print(f"Base de conocimiento construida con {self.index.ntotal} vectores.")

    def _extract_chunks_from_docs(self):
        """
        Extrae fragmentos de texto de los archivos PDF y DOCX.
        """
        for filename in os.listdir(self.documents_path):
            file_path = os.path.join(self.documents_path, filename)
            
            if filename.lower().endswith('.pdf'):
                try:
                    with open_pdf(file_path) as pdf:
                        for i, page in enumerate(pdf.pages):
                            text = page.extract_text()
                            if text:
                                # Dividir en fragmentos más pequeños (párrafos)
                                paragraphs = text.split('\n\n')
                                for para in paragraphs:
                                    if para.strip():
                                        self.chunks.append(para.strip())
                                        self.chunk_sources.append(f"{filename}, página {i+1}")
                except Exception as e:
                    print(f"Error al leer el PDF {filename}: {e}")

            # elif filename.lower().endswith('.docx'):
            #     try:
            #         doc = Document(file_path)
            #         for para in doc.paragraphs:
            #             if para.text.strip():
            #                 self.chunks.append(para.text.strip())
            #                 self.chunk_sources.append(f"{filename}")
            #     except Exception as e:
            #         print(f"Error al leer el DOCX {filename}: {e}")

    def search(self, query: str, k: int = 3) -> List[Tuple[str, str]]:
        """
        Busca en la base de conocimiento los fragmentos más relevantes para una consulta.
        """
        if not self.index or self.index.ntotal == 0:
            return []
            
        query_embedding = self.model.encode([query])
        distances, indices = self.index.search(query_embedding, k)
        
        results = []
        for i in indices[0]:
            if i != -1:
                results.append((self.chunks[i], self.chunk_sources[i]))
        
        return results

def get_knowledge_base(documents_path: str) -> KnowledgeBase:
    kb = KnowledgeBase(documents_path)
    kb.build()
    return kb