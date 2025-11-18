"""
Preprocesamiento mejorado de imágenes para OCR
Múltiples estrategias para mejorar la calidad
"""
import cv2
import numpy as np
from pathlib import Path
from PIL import Image
import pytesseract

class ImagePreprocessor:
    def __init__(self, output_dir='temp'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def preprocess(self, image_path: str, strategy='auto') -> str:
        """
        Preprocesa una imagen con múltiples estrategias
        
        Args:
            image_path: Ruta de la imagen
            strategy: 'auto', 'aggressive', 'conservative', 'scan', 'photo'
        
        Returns:
            Ruta de la imagen procesada
        """
        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"No se pudo leer la imagen: {image_path}")
        
        print(f"📸 Imagen original: {img.shape[1]}x{img.shape[0]}")
        
        # Detectar mejor estrategia si es 'auto'
        if strategy == 'auto':
            strategy = self._detect_best_strategy(img)
            print(f"🎯 Estrategia detectada: {strategy}")
        
        # Aplicar estrategia
        if strategy == 'aggressive':
            processed = self._aggressive_preprocessing(img)
        elif strategy == 'conservative':
            processed = self._conservative_preprocessing(img)
        elif strategy == 'scan':
            processed = self._scan_preprocessing(img)
        elif strategy == 'photo':
            processed = self._photo_preprocessing(img)
        else:
            processed = self._aggressive_preprocessing(img)
        
        # Guardar
        output_path = self.output_dir / f"processed_{Path(image_path).name}"
        cv2.imwrite(str(output_path), processed)
        
        print(f"✅ Imagen procesada: {output_path}")
        return str(output_path)
    
    def _detect_best_strategy(self, img):
        """Detecta la mejor estrategia según características de la imagen"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Calcular brillo promedio
        brightness = np.mean(gray)
        
        # Calcular contraste
        contrast = gray.std()
        
        # Detectar si es escaneo o foto
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / edges.size
        
        print(f"   📊 Brillo: {brightness:.1f}, Contraste: {contrast:.1f}, Bordes: {edge_density:.3f}")
        
        # Decidir estrategia
        if brightness < 100 or contrast < 30:
            return 'aggressive'  # Imagen oscura o bajo contraste
        elif edge_density > 0.1:
            return 'photo'  # Muchos bordes = foto de celular
        else:
            return 'scan'  # Parece escaneo limpio
    
    def _aggressive_preprocessing(self, img):
        """Preprocesamiento agresivo para imágenes difíciles"""
        print("   🔧 Aplicando preprocesamiento AGRESIVO...")
        
        # 1. Convertir a escala de grises
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 2. Upscale x3 (mejora OCR significativamente)
        height, width = gray.shape
        gray = cv2.resize(gray, (width*3, height*3), interpolation=cv2.INTER_CUBIC)
        
        # 3. Denoise agresivo
        denoised = cv2.fastNlMeansDenoising(gray, None, h=20, templateWindowSize=7, searchWindowSize=21)
        
        # 4. Mejorar contraste con CLAHE
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        enhanced = clahe.apply(denoised)
        
        # 5. Sharpening
        kernel = np.array([[-1,-1,-1],
                          [-1, 9,-1],
                          [-1,-1,-1]])
        sharpened = cv2.filter2D(enhanced, -1, kernel)
        
        # 6. Binarización adaptativa
        binary = cv2.adaptiveThreshold(
            sharpened, 255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 
            blockSize=15, 
            C=10
        )
        
        # 7. Morfología para limpiar ruido
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2,2))
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        return cleaned
    
    def _conservative_preprocessing(self, img):
        """Preprocesamiento conservador para imágenes buenas"""
        print("   🔧 Aplicando preprocesamiento CONSERVADOR...")
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Upscale moderado
        height, width = gray.shape
        gray = cv2.resize(gray, (width*2, height*2), interpolation=cv2.INTER_CUBIC)
        
        # Denoise suave
        denoised = cv2.fastNlMeansDenoising(gray, None, h=10)
        
        # Binarización simple
        _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        return binary
    
    def _scan_preprocessing(self, img):
        """Para imágenes escaneadas"""
        print("   🔧 Aplicando preprocesamiento para ESCANEO...")
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Deskew (corregir inclinación)
        coords = np.column_stack(np.where(gray > 0))
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        
        if abs(angle) > 0.5:
            (h, w) = gray.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            gray = cv2.warpAffine(gray, M, (w, h), 
                                  flags=cv2.INTER_CUBIC, 
                                  borderMode=cv2.BORDER_REPLICATE)
        
        # Upscale
        height, width = gray.shape
        gray = cv2.resize(gray, (width*2, height*2), interpolation=cv2.INTER_CUBIC)
        
        # Binarización
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        return binary
    
    def _photo_preprocessing(self, img):
        """Para fotos de celular"""
        print("   🔧 Aplicando preprocesamiento para FOTO...")
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Corrección de perspectiva (simplificada)
        # En producción, usar detección de contornos
        
        # Upscale
        height, width = gray.shape
        gray = cv2.resize(gray, (width*3, height*3), interpolation=cv2.INTER_CUBIC)
        
        # Denoise fuerte
        denoised = cv2.fastNlMeansDenoising(gray, None, h=15)
        
        # Mejorar contraste
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(denoised)
        
        # Binarización adaptativa
        binary = cv2.adaptiveThreshold(
            enhanced, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=11,
            C=8
        )
        
        return binary
    
    def preprocess_multipass(self, image_path: str) -> list:
        """
        Genera múltiples versiones procesadas
        Útil para probar cuál da mejor OCR
        
        Returns:
            Lista de rutas de imágenes procesadas
        """
        strategies = ['aggressive', 'conservative', 'scan', 'photo']
        processed_images = []
        
        for strategy in strategies:
            try:
                img = cv2.imread(str(image_path))
                if img is None:
                    continue
                
                if strategy == 'aggressive':
                    processed = self._aggressive_preprocessing(img)
                elif strategy == 'conservative':
                    processed = self._conservative_preprocessing(img)
                elif strategy == 'scan':
                    processed = self._scan_preprocessing(img)
                else:
                    processed = self._photo_preprocessing(img)
                
                output_path = self.output_dir / f"{strategy}_{Path(image_path).name}"
                cv2.imwrite(str(output_path), processed)
                processed_images.append(str(output_path))
                
            except Exception as e:
                print(f"   ⚠️  Error con estrategia {strategy}: {e}")
        
        return processed_images


def extract_text_with_multipass(image_path: str) -> tuple:
    """
    Extrae texto probando múltiples estrategias de preprocesamiento
    Retorna el mejor resultado
    
    Returns:
        (best_text, best_strategy, all_results)
    """
    preprocessor = ImagePreprocessor()
    processed_images = preprocessor.preprocess_multipass(image_path)
    
    results = []
    
    for processed_path in processed_images:
        strategy = Path(processed_path).name.split('_')[0]
        
        try:
            # OCR con configuración optimizada
            img = Image.open(processed_path)
            
            # PSM 6 = bloque uniforme de texto
            # PSM 4 = columna única de texto
            # PSM 3 = automático
            configs = [
                '--oem 3 --psm 6',  # Bloque uniforme
                '--oem 3 --psm 4',  # Columna única
                '--oem 3 --psm 3',  # Automático
            ]
            
            best_text = ""
            best_conf = 0
            
            for config in configs:
                text = pytesseract.image_to_string(img, lang='spa+eng', config=config)
                
                # Calcular "confianza" basado en caracteres legibles
                alpha_count = sum(c.isalnum() for c in text)
                total_count = len(text.replace('\n', '').replace(' ', ''))
                confidence = alpha_count / max(total_count, 1) if total_count > 0 else 0
                
                if confidence > best_conf:
                    best_conf = confidence
                    best_text = text
            
            results.append({
                'strategy': strategy,
                'text': best_text,
                'length': len(best_text),
                'confidence': best_conf,
                'path': processed_path
            })
            
            print(f"   {strategy}: {len(best_text)} chars, confianza: {best_conf:.2f}")
            
        except Exception as e:
            print(f"   ❌ Error en {strategy}: {e}")
    
    if not results:
        return "", "none", []
    
    # Seleccionar mejor resultado
    # Priorizar: confianza > longitud > estrategia
    best = max(results, key=lambda x: (x['confidence'], x['length']))
    
    print(f"\n✨ Mejor resultado: {best['strategy']} ({len(best['text'])} caracteres)")
    
    return best['text'], best['strategy'], results


# Función principal para integración
def extract_text_from_image(image_path: str, multipass: bool = True) -> str:
    """
    Extrae texto de una imagen
    
    Args:
        image_path: Ruta de la imagen
        multipass: Si True, prueba múltiples estrategias
    
    Returns:
        Texto extraído
    """
    if multipass:
        text, strategy, _ = extract_text_with_multipass(image_path)
        return text
    else:
        preprocessor = ImagePreprocessor()
        processed = preprocessor.preprocess(image_path, strategy='auto')
        img = Image.open(processed)
        return pytesseract.image_to_string(img, lang='spa+eng', config='--oem 3 --psm 6')


# Función de compatibilidad con código anterior
def preprocess_image(image_path: str, output_dir: str = 'temp') -> str:
    """
    Función de compatibilidad con el código anterior.
    Preprocesa una imagen y retorna la ruta del resultado.
    
    Args:
        image_path: Ruta de la imagen original
        output_dir: Directorio de salida (default: 'temp')
    
    Returns:
        Ruta de la imagen preprocesada
    """
    preprocessor = ImagePreprocessor(output_dir=output_dir)
    return preprocessor.preprocess(image_path, strategy='auto')


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Uso: python image_processing.py <imagen>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    
    print("🔍 EXTRACCIÓN DE TEXTO CON MULTIPASS")
    print("="*70)
    
    text, strategy, all_results = extract_text_with_multipass(image_path)
    
    print(f"\n📝 TEXTO EXTRAÍDO:")
    print("="*70)
    print(text[:1000])
    if len(text) > 1000:
        print(f"\n... ({len(text) - 1000} caracteres más)")