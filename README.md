# Image Insight Agent

Description of the project.

## Módulos Principales

*   **`app/ingestion.py`**: Descarga imágenes desde fuentes externas (ej. Pexels API) basado en criterios de búsqueda y las guarda en `data/raw`.
*   **`app/analyzer.py`**: Analiza las imágenes descargadas en `data/raw` para extraer métricas visuales y guarda los resultados como archivos JSON individuales en `data/processed`.
*   **`app/agent.py`**: (Futuro) Contendrá la lógica principal del agente de IA que utiliza las imágenes y sus métricas.
*   **`app/ui.py`**: (Futuro) Componentes de la interfaz de usuario.
*   **`app/main.py`**: Punto de entrada de la aplicación.
*   **`app/utils.py`**: Funciones de utilidad compartidas.

## Análisis de Imágenes (`analyzer.py`)

Este módulo procesa cada imagen encontrada en `data/raw` y genera un archivo JSON correspondiente en `data/processed` (ej. `imagen_x_metrics.json`) que contiene las siguientes métricas visuales. Algunas métricas también incluyen una versión normalizada (`_normalized`) en el rango [0, 1] para facilitar la comparación y el uso por parte del agente.

### Métricas Calculadas:

*   **`filename`**: Nombre del archivo de imagen original.
*   **`image_size`**: Dimensiones de la imagen (ancho x alto) en píxeles.
*   **`entropy` / `entropy_normalized`**: 
    *   **Descripción**: Entropía de Shannon de la imagen en escala de grises. Mide la "aleatoriedad" o "incertidumbre" en la distribución de los niveles de gris. Valores altos indican mayor complejidad y detalle.
    *   **Rango Original**: [0, 8] (para imágenes de 8 bits).
    *   **Normalizado**: [0, 1] (dividido por 8). 0 = imagen uniforme, 1 = máxima aleatoriedad.
*   **`color_entropy` / `color_entropy_normalized`**:
    *   **Descripción**: Promedio de la entropía de Shannon para cada canal de color (R, G, B). Si la imagen es en escala de grises, este valor es igual a `entropy`. Mide la complejidad de la información de color.
    *   **Rango Original**: [0, 8].
    *   **Normalizado**: [0, 1] (dividido por 8). 0 = colores uniformes, 1 = máxima aleatoriedad de color.
*   **`edge_count`**: 
    *   **Descripción**: Número total de píxeles detectados como bordes utilizando el algoritmo Canny con umbrales adaptativos.
    *   **Rango**: [0, total de píxeles].
*   **`edge_density` / `edge_density_normalized`**:
    *   **Descripción**: Proporción de píxeles que son bordes respecto al total de píxeles. Indica cuán "cargada" de bordes está la imagen.
    *   **Rango**: [0, 1] (Naturalmente normalizado). 0 = sin bordes, 1 = todos los píxeles son bordes (teórico).
*   **`color_variance` / `color_variance_normalized`**:
    *   **Descripción**: Varianza de los valores de píxeles en la versión en escala de grises de la imagen. Mide la dispersión de los tonos de gris respecto al promedio. Valores altos indican mayor contraste tonal general.
    *   **Rango Original**: [0, ~16256] (Varianza máxima teórica aprox. (255^2)/4).
    *   **Normalizado**: [0, 1] (dividido por (255^2)/4). 0 = imagen de un solo tono, 1 = máximo contraste teórico.
*   **`histogram_std`**: 
    *   **Descripción**: Desviación estándar del histograma de la imagen en escala de grises. Mide cuán dispersa es la distribución de los niveles de gris. Un valor alto sugiere que muchos niveles de gris diferentes están presentes en cantidades variables, mientras que un valor bajo sugiere una distribución más concentrada o uniforme.
    *   **Rango**: [0, +∞) (Depende del tamaño de la imagen y la distribución).
    *   *Nota: No se proporciona versión normalizada debido a la complejidad de definir un máximo teórico general.* 