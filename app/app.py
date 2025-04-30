import streamlit as st
import os
import json
from PIL import Image, ImageDraw, ImageFont
from PIL import ImageColor
import logging
from analyzer import analyze_visual_complexity, save_metrics_to_json
from agent import ImageAgent
import tempfile
import copy

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Determine project paths dynamically
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
DEFAULT_PROCESSED_DIR = os.path.join(_PROJECT_ROOT, 'data', 'processed')
DEFAULT_OUTPUT_DIR = os.path.join(_PROJECT_ROOT, 'data', 'output')

# Define colors for UI elements - Paleta mejorada con tonos más vibrantes
PRIMARY_COLOR = "#5B68FF"  # Azul vibrante
SECONDARY_COLOR = "#FF6B6B"  # Rojo coral
ACCENT_COLOR = "#58D68D"  # Verde menta
NEUTRAL_COLOR = "#F5F7FA"  # Gris claro
DARK_COLOR = "#2C3E50"  # Azul oscuro

def create_temp_directories():
    """Create temporary directories for processing."""
    os.makedirs(DEFAULT_PROCESSED_DIR, exist_ok=True)
    os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)

def process_uploaded_image(uploaded_file, project_description=None):
    """Process the uploaded image through the pipeline."""
    # Get file extension from the original filename
    file_ext = os.path.splitext(uploaded_file.name)[1].lower()
    if not file_ext:
        file_ext = '.jpg'  # Default to jpg if no extension found
    
    # Create a temporary file to save the uploaded image with correct extension
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        image_path = tmp_file.name

    try:
        # Step 1: Analyze image complexity
        metrics = analyze_visual_complexity(image_path)
        if not metrics:
            st.error("Error al analizar la imagen")
            return None, None, None, None

        # Save metrics to JSON
        metrics_path = os.path.join(DEFAULT_PROCESSED_DIR, "temp_metrics.json")
        save_metrics_to_json(metrics, metrics_path)

        # Step 2: Process with agent
        #api_key = os.getenv("GOOGLE_API_KEY")
        api_key = "AIzaSyAqkLokEksQMO_4kBaDjXh6Q72lDPHE6y0"
        if not api_key:
            st.error("No se encontró la clave de API de Google. Configure la variable de entorno GOOGLE_API_KEY.")
            return None, None, None, None

        agent = ImageAgent(api_key=api_key)
        analysis_path, processed_image_path = agent.process_image(image_path, metrics_path, project_description)

        if not analysis_path or not processed_image_path:
            st.error("Error al procesar la imagen con el agente")
            return None, None, None, None

        # Load results
        with open(analysis_path, 'r') as f:
            analysis_result = json.load(f)
            
        # Get the boxes json path
        base_filename = os.path.basename(image_path).split('.')[0]
        boxes_json_path = os.path.join(DEFAULT_OUTPUT_DIR, f"{base_filename}_boxes.json")
        
        # Load boxes if exists
        boxes_data = None
        if os.path.exists(boxes_json_path):
            with open(boxes_json_path, 'r') as f:
                boxes_data = json.load(f)

        return metrics, analysis_result, processed_image_path, boxes_data

    except Exception as e:
        st.error(f"Error durante el procesamiento: {str(e)}")
        return None, None, None, None

    finally:
        # Clean up temporary file
        if os.path.exists(image_path):
            os.unlink(image_path)

def draw_selected_boxes_using_agent(image_path, boxes, selected_indices):
    """
    Utiliza el agente para dibujar solo los cuadros de las recomendaciones seleccionadas.
    
    Args:
        image_path: Ruta a la imagen original
        boxes: Lista de cuadros delimitadores
        selected_indices: Índices de los cuadros seleccionados
    
    Returns:
        Imagen PIL con los cuadros delimitadores dibujados
    """
    # Crear una instancia del agente
    agent = ImageAgent()
    
    # Filtrar solo las cajas seleccionadas
    selected_boxes = [boxes[idx] for idx in selected_indices if idx < len(boxes)]
    
    # Usar visualize_bounding_boxes con los parámetros adecuados
    return agent.visualize_bounding_boxes(
        image_path=image_path,
        bounding_boxes=selected_boxes,
        show_labels=False,  # No mostrar texto
        line_width=5        # Líneas más gruesas para mayor visibilidad
    )

def sort_recommendations_by_impact(boxes_data):
    """
    Ordena las recomendaciones por nivel de impacto (High -> Medium -> Low)
    
    Args:
        boxes_data: Lista de diccionarios con las recomendaciones
    
    Returns:
        Lista de tuplas (índice original, diccionario) ordenadas por impacto
    """
    if not boxes_data:
        return []
    
    # Crear lista de tuplas (índice, diccionario)
    indexed_boxes = [(i, box) for i, box in enumerate(boxes_data)]
    
    # Función para asignar prioridad según impacto
    def get_impact_priority(box_tuple):
        _, box = box_tuple
        impact = box.get("impact", "").lower()
        if impact == "high":
            return 0  # Alta prioridad (primero)
        elif impact == "medium":
            return 1  # Prioridad media
        else:
            return 2  # Baja prioridad (último)
    
    # Ordenar por impacto
    return sorted(indexed_boxes, key=get_impact_priority)

def main():
    st.set_page_config(
        page_title="Analizador de Imágenes",
        page_icon="🖼️",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    # Custom CSS simplificado, enfocado en el texto y los marcadores
    st.markdown("""
    <style>
    /* Fondo sutil */
    .stApp {
        background-color: #FFFFFF;
    }
    
    /* Estilo para el título principal */
    .main-header {
        font-size: 2.5rem;
        font-weight: 600;
        color: #5B68FF;
        margin-bottom: 1.5rem;
        text-align: center;
    }
    
    /* Estilo para subtítulos */
    .subheader {
        font-size: 1.8rem;
        font-weight: 500;
        color: #2C3E50;
        margin-top: 1rem;
        margin-bottom: 1rem;
        border-bottom: 1px solid #E0E6ED;
        padding-bottom: 0.5rem;
    }
    
    /* Estilo para los botones */
    .stButton>button {
        background-color: #5B68FF;
        color: white;
        border: none;
        border-radius: 4px;
        font-weight: 500;
        transition: all 0.2s;
    }
    
    .stButton>button:hover {
        background-color: #4957E3;
    }
    
    /* Text area with project description */
    .project-description {
        border: 1px solid #E0E6ED;
        border-radius: 4px;
        padding: 10px;
        background-color: #F9FAFC;
        margin-bottom: 15px;
    }
    
    /* Etiquetas de prioridad */
    .priority-indicator {
        display: inline-block;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        margin-right: 8px;
    }
    
    .high-priority {
        background-color: #FF6B6B;
    }
    
    .medium-priority {
        background-color: #FFBE0B;
    }
    
    .low-priority {
        background-color: #58D68D;
    }
    
    /* Separador entre recomendaciones */
    .recommendation-divider {
        border-bottom: 1px solid #E0E6ED;
        margin: 8px 0;
    }
    
    /* Estilo para el texto de las recomendaciones */
    .recommendation-text {
        font-size: 1rem;
        color: #2C3E50;
        margin-left: 20px;
        padding: 8px 0;
    }
    
    /* Estilos para alinear botones a la derecha */
    .right-align {
        display: flex;
        justify-content: flex-end;
    }
    
    /* Footer simple */
    .footer {
        text-align: center;
        margin-top: 3rem;
        padding: 1rem;
        font-size: 0.8rem;
        color: #8395a7;
        border-top: 1px solid #e0e6ed;
    }
    </style>
    """, unsafe_allow_html=True)

    # Encabezado de la aplicación
    st.markdown("<h1 class='main-header'>🖼️ Analizador de Imágenes</h1>", unsafe_allow_html=True)
    
    # Descripción
    st.markdown("""
    <div style="text-align: center; max-width: 800px; margin: 0 auto; margin-bottom: 2rem; color: #2C3E50;">
        <p>Sube una imagen para analizarla y recibe recomendaciones personalizadas para mejorarla.</p>
    </div>
    """, unsafe_allow_html=True)

    # Create necessary directories
    create_temp_directories()

    # Interface para carga de archivos
    col_upload1, col_upload2 = st.columns([3, 1])
    
    with col_upload1:
        uploaded_file = st.file_uploader("Selecciona una imagen para analizar", type=['png', 'jpg', 'jpeg'])
    
    with col_upload2:
        # Alinear botón a la derecha
        st.markdown("<div class='right-align'>", unsafe_allow_html=True)
        process_button = st.button("✨ Analizar Imagen", type="primary", disabled=uploaded_file is None)
        st.markdown("</div>", unsafe_allow_html=True)

    # Project description section
    if uploaded_file is not None:
        st.markdown("<h3 class='subheader'>Descripción del Proyecto</h3>", unsafe_allow_html=True)
        
        # Information about the purpose of the description
        st.markdown("""
        <div style="font-size: 0.9rem; color: #505A68; margin-bottom: 10px;">
            Proporciona una breve descripción de tu proyecto o campaña. Esta información ayudará a mejorar las recomendaciones para tu imagen.
        </div>
        """, unsafe_allow_html=True)
        
        # Text area for project description with custom CSS
        st.markdown("<div class='project-description'>", unsafe_allow_html=True)
        project_description = st.text_area(
            label="Descripción del proyecto",
            value="",
            placeholder="Ejemplo: Campaña promocional para zapatillas deportivas dirigida a jóvenes de 18-25 años que busca destacar comodidad y estilo.",
            height=100,
            label_visibility="collapsed"
        )
        st.markdown("</div>", unsafe_allow_html=True)

    # Store session state to preserve data between rerenders
    if 'processed' not in st.session_state:
        st.session_state.processed = False
    if 'metrics' not in st.session_state:
        st.session_state.metrics = None
    if 'analysis_result' not in st.session_state:
        st.session_state.analysis_result = None
    if 'original_image_path' not in st.session_state:
        st.session_state.original_image_path = None
    if 'boxes_data' not in st.session_state:
        st.session_state.boxes_data = None
    if 'selected_recommendations' not in st.session_state:
        st.session_state.selected_recommendations = []
    if 'image' not in st.session_state:
        st.session_state.image = None
    if 'displayed_image' not in st.session_state:
        st.session_state.displayed_image = None

    if uploaded_file is not None:
        # Process the image if the button was clicked
        if process_button:
            with st.spinner('Procesando imagen...'):
                metrics, analysis_result, processed_image_path, boxes_data = process_uploaded_image(uploaded_file, project_description)
                
                if metrics and analysis_result and processed_image_path:
                    st.session_state.processed = True
                    st.session_state.metrics = metrics
                    st.session_state.analysis_result = analysis_result
                    st.session_state.original_image_path = processed_image_path
                    st.session_state.boxes_data = boxes_data
                    st.session_state.selected_recommendations = []
                    
                    # Guardar la imagen original para utilizarla después
                    st.session_state.image = Image.open(uploaded_file)
        
        # Create two columns for layout (left for image, right for analysis)
        col1, col2 = st.columns([1, 1])

        with col1:
            st.markdown("<h2 class='subheader'>Imagen</h2>", unsafe_allow_html=True)
            
            # Mostrar imagen original o con recuadros seleccionados
            if uploaded_file:
                # Cargar imagen original si aún no está en la sesión
                if st.session_state.image is None:
                    st.session_state.image = Image.open(uploaded_file)
                    st.session_state.displayed_image = st.session_state.image
                
                # Si hay recomendaciones seleccionadas, mostrar imagen con recuadros
                if st.session_state.processed and st.session_state.boxes_data and st.session_state.selected_recommendations:
                    # Crear archivo temporal para visualizar la imagen con recuadros
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_img_file:
                        st.session_state.image.save(temp_img_file, format='JPEG')
                        img_with_boxes = draw_selected_boxes_using_agent(
                            temp_img_file.name, 
                            st.session_state.boxes_data, 
                            st.session_state.selected_recommendations
                        )
                    st.session_state.displayed_image = img_with_boxes
                    
                    # Borrar archivo temporal
                    os.unlink(temp_img_file.name)
                # Si no hay selecciones pero sí procesamiento, mostrar la imagen original
                elif st.session_state.processed:
                    st.session_state.displayed_image = st.session_state.image
                
                # Mostrar la imagen actual (original o con recuadros)
                st.image(st.session_state.displayed_image, use_container_width=True)

        with col2:
            if st.session_state.processed and st.session_state.analysis_result:
                # Título y botón alineado a la derecha
                col_title, col_btn = st.columns([3, 1])
                
                with col_title:
                    st.markdown("<h2 class='subheader'>Recomendaciones</h2>", unsafe_allow_html=True)
                
                with col_btn:
                    # Alinear botón a la derecha
                    st.markdown("<div class='right-align'>", unsafe_allow_html=True)
                    if st.button("🔄 Limpiar"):
                        st.session_state.selected_recommendations = []
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
                
                # Leyenda de prioridades
                st.markdown("""
                <div style="display: flex; gap: 15px; margin: 10px 0 20px 0;">
                    <div style="display: flex; align-items: center;">
                        <span class="priority-indicator high-priority"></span>
                        <span style="font-size: 0.85rem; color: #505A68;">Alta</span>
                    </div>
                    <div style="display: flex; align-items: center;">
                        <span class="priority-indicator medium-priority"></span>
                        <span style="font-size: 0.85rem; color: #505A68;">Media</span>
                    </div>
                    <div style="display: flex; align-items: center;">
                        <span class="priority-indicator low-priority"></span>
                        <span style="font-size: 0.85rem; color: #505A68;">Baja</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Display bounding box recommendations with checkboxes
                if st.session_state.boxes_data:                    
                    # Ordenar recomendaciones por impacto
                    sorted_boxes = sort_recommendations_by_impact(st.session_state.boxes_data)
                    
                    # Create checkboxes for each recommendation
                    new_selections = []
                    
                    # Primero mostramos las recomendaciones de alto impacto
                    current_impact = None
                    
                    for original_idx, box in sorted_boxes:
                        impact = box.get("impact", "").lower()
                        
                        # Añadir separadores entre diferentes niveles de impacto
                        if current_impact != impact:
                            current_impact = impact
                            impact_title = ""
                            if impact == "high":
                                impact_title = "Prioridad Alta"
                            elif impact == "medium":
                                impact_title = "Prioridad Media"
                            else:
                                impact_title = "Prioridad Baja"
                        
                        # Determinar clase CSS basada en el impacto
                        priority_class = ""
                        if impact == "high":
                            priority_class = "high-priority"
                        elif impact == "medium":
                            priority_class = "medium-priority"
                        else:
                            priority_class = "low-priority"
                        
                        # Añadir indicador de prioridad con el texto
                        st.markdown(f"<div style='display: flex; align-items: flex-start; padding: 5px 0;'><span class='priority-indicator {priority_class}'></span>", unsafe_allow_html=True)
                        
                        # Add checkbox for each recommendation
                        if st.checkbox(
                            f"{box.get('label', f'Recomendación {original_idx+1}')}",
                            value=original_idx in st.session_state.selected_recommendations,
                            key=f"rec_{original_idx}"
                        ):
                            new_selections.append(original_idx)
                        
                        st.markdown("</div>", unsafe_allow_html=True)
                        
                        # Añadir separador entre recomendaciones
                        st.markdown("<div class='recommendation-divider'></div>", unsafe_allow_html=True)
                    
                    # Update selected recommendations
                    if new_selections != st.session_state.selected_recommendations:
                        st.session_state.selected_recommendations = new_selections
                        st.rerun()
                
                else:
                    # Display text recommendations if no bounding boxes
                    for i, rec in enumerate(st.session_state.analysis_result['recommended_analysis']):
                        st.markdown(f"<div style='display: flex; align-items: flex-start; padding: 5px 0;'><span class='priority-indicator'></span><div class='recommendation-text'>{rec}</div></div>", unsafe_allow_html=True)
                        if i < len(st.session_state.analysis_result['recommended_analysis']) - 1:
                            st.markdown("<div class='recommendation-divider'></div>", unsafe_allow_html=True)
    
    # Footer simple
    st.markdown("""
    <div class="footer">
        <p>Analizador de Imágenes v1.0</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()