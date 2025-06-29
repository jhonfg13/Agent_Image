# Image analysis module
import cv2
import numpy as np
from skimage.measure import shannon_entropy
import os
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Determine project paths dynamically
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
DEFAULT_INPUT_DIR = os.path.join(_PROJECT_ROOT, 'data', 'raw')
DEFAULT_OUTPUT_DIR = os.path.join(_PROJECT_ROOT, 'data', 'processed')

# Constants for normalization
MAX_ENTROPY = 8.0 # Theoretical max for 8-bit images
MAX_VARIANCE = (255**2) / 4 # Approximate max variance for grayscale

def analyze_visual_complexity(img_path: str) -> dict | None:
    """
    Analyzes visual complexity metrics for a given image, including normalized values.

    Args:
        img_path: Path to the image file.

    Returns:
        A dictionary containing original and normalized visual complexity metrics, or None if analysis fails.
        Normalized metrics (0-1 range) have the suffix '_normalized'.
    """
    try:
        # Verificar existencia del archivo
        if not os.path.exists(img_path):
            logging.error(f"Image not found: {img_path}")
            return None

        # Cargar imagen
        img = cv2.imread(img_path)
        if img is None:
            logging.error(f"Could not load image: {img_path}")
            return None

        # Obtener dimensiones
        height, width = img.shape[:2]
        pixel_count = height * width
        if pixel_count == 0:
             logging.error(f"Invalid image dimensions (0 pixels): {img_path}")
             return None

        # Conversión a escala de grises
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 1. Entropía visual (grayscale)
        entropy = float(round(shannon_entropy(gray), 4))
        entropy_normalized = round(min(entropy / MAX_ENTROPY, 1.0), 4) # Cap at 1.0

        # 2. Bordes detectados con Canny (umbrales adaptativos)
        median_value = np.median(gray)
        # Avoid division by zero or invalid thresholds if median is 0
        sigma = 0.33
        lower = int(max(0, (1.0 - sigma) * median_value))
        upper = int(min(255, (1.0 + sigma) * median_value))
        # Ensure lower is less than upper for Canny
        if lower >= upper:
            lower = max(0, upper - 1) # Adjust slightly if they are equal or inverted

        edges = cv2.Canny(gray, lower, upper)
        edge_count = np.sum(edges > 0)
        edge_density = float(round(edge_count / pixel_count, 4) if pixel_count > 0 else 0)

        # 3. Varianza de la escala de grises (complejidad tonal)
        variance = float(round(np.var(gray), 2))
        variance_normalized = round(min(variance / MAX_VARIANCE, 1.0), 4) if MAX_VARIANCE > 0 else 0 # Cap at 1.0

        # 4. Histograma (desviación estándar como medida de dispersión tonal)
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        hist_std = float(round(np.std(hist), 2))

        # 5. Análisis de entropía de color (promedio de canales)
        color_entropy = 0.0
        if len(img.shape) == 3 and img.shape[2] == 3: # Check if it's a color image
            color_entropy = float(round(np.mean([shannon_entropy(img[:,:,i]) for i in range(img.shape[2])]), 4))
        else: # Grayscale or single channel image
             color_entropy = entropy # Use grayscale entropy if not color
        color_entropy_normalized = round(min(color_entropy / MAX_ENTROPY, 1.0), 4) # Cap at 1.0


        return {
            # Original Metrics
            "filename": os.path.basename(img_path),
            "width_height": f"{width}x{height}",
            "entropy": entropy,
            "color_entropy": color_entropy,
            "edge_count": int(edge_count),
            "edge_density": edge_density,
            "color_variance": variance,
            "histogram_std": hist_std,
            # Normalized Metrics (0-1 range)
            "entropy_normalized": entropy_normalized,
            "color_entropy_normalized": color_entropy_normalized,
            "color_variance_normalized": variance_normalized,
        }

    except cv2.error as cv_err:
         logging.error(f"OpenCV error analyzing {img_path}: {cv_err}")
         return None
    except Exception as e:
        logging.error(f"Unexpected error analyzing {img_path}: {e}")
        return None


def save_metrics_to_json(metrics_data: dict, output_path: str):
    """
    Saves a single metric dictionary to a JSON file.

    Args:
        metrics_data: A dictionary of metrics for a single image.
        output_path: The full path to the output JSON file.
    """
    try:
        # Ensure the output directory exists
        output_dir = os.path.dirname(output_path)
        os.makedirs(output_dir, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(metrics_data, f, indent=4, ensure_ascii=False)
        logging.info(f"Metrics successfully saved to: {output_path}")

    except IOError as io_err:
        logging.error(f"Error writing JSON file {output_path}: {io_err}")
    except TypeError as type_err:
        logging.error(f"Error serializing data to JSON: {type_err}")
    except Exception as e:
         logging.error(f"Unexpected error saving JSON to {output_path}: {e}")