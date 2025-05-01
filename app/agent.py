# Core agent logic for image analysis
from google import genai
from google.genai import types
import json
import os
import re
import logging
from PIL import Image, ImageDraw, ImageFont
from PIL import ImageColor
from pydantic import BaseModel
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Determine project paths dynamically
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
DEFAULT_INPUT_DIR = os.path.join(_PROJECT_ROOT, 'data', 'processed')
DEFAULT_OUTPUT_DIR = os.path.join(_PROJECT_ROOT, 'data', 'output')
# Modelos de Gemini
MODEL_NAME_METRICS = "gemini-1.5-flash"
MODEL_NAME_RESOLUTION = "gemini-2.5-pro-exp-03-25"


# Enums for controlled vocabulary
class VarietyLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class QualityLevel(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"

class ConsistencyLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VARIABLE = "variable"

# BaseModel for structured output
class ImageAnalysisResult(BaseModel):
    summary: str
    variety: VarietyLevel
    quality: QualityLevel
    consistency: ConsistencyLevel
    recommended_analysis: List[str]
    notes: str

class BoundingBox(BaseModel):
    label: str
    box_2d: List[int]  # [y1, x1, y2, x2] in thousand-based coordinates
    impact: str

class ImageAgent:
    """
    Agent for processing images with Gemini AI models.
    Handles interpreting analysis metrics and generating bounding boxes.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the image agent with the given API key.
        
        Args:
            api_key: Google Gemini API key
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            logging.warning("No Google API key provided. Set GOOGLE_API_KEY environment variable.")
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None
        
        # Create output directory if it doesn't exist
        os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)
    
    def analyze_metrics(self, metrics_json_path: str) -> Optional[ImageAnalysisResult]:
        """
        Analyze image metrics using the Gemini model.
        
        Args:
            metrics_json_path: Path to the JSON file with image metrics
            
        Returns:
            An ImageAnalysisResult object with the analysis result or None if failed
        """
        if not self.client:
            logging.error("Cannot analyze metrics: No Google API client available")
            return None
            
        try:
            # Prompt for image analysis
            prompt = """
            You are an expert in image analysis with deep knowledge of applied statistics. 
            Your job is to take the following JSON metrics extracted from an image and produce 
            a concise, structured evaluation that will drive downstream pipelines.

            - Interpret each metric in terms of visual complexity, color richness, edge information, and overall image quality.
            - Infer whether the image is suitable for detailed semantic analysis or if it should be deprioritized.
            - Recommend the next analysis steps (e.g., OCR, object detection, semantic segmentation, visual captioning, scene decomposition).
            - Provide any additional technical notes or caveats.
            - Respond clearly and consistently, prioritize critical insights and actionable next steps.

            Metrics JSON:
            {metrics}
            """
            
            # Load the metrics JSON
            with open(metrics_json_path, 'r') as f:
                metrics_json = json.load(f)
            
            # Remove the 'filename' key if it exists to avoid biasing the model
            metrics_json.pop('filename', "unknown_file")
            
            # Generate the response
            response = self.client.models.generate_content(
                model=MODEL_NAME_METRICS,
                contents=prompt.format(metrics=json.dumps(metrics_json)),
                config={
                    "response_mime_type": "application/json",
                    "response_schema": ImageAnalysisResult,
                },
            )
            
            # Parse the response as a JSON object
            result = json.loads(response.text)
            
            # Save the response as a JSON file
            base_filename = os.path.basename(metrics_json_path).replace("_metrics.json", "")
            result_path = os.path.join(DEFAULT_OUTPUT_DIR, f"{base_filename}_analysis.json")
            with open(result_path, 'w') as f:
                json.dump(result, f, indent=2)
                
            logging.info(f"Analysis saved to {result_path}")
            return ImageAnalysisResult(**result)
            
        except Exception as e:
            logging.error(f"Error analyzing metrics: {e}")
            return None
    
    def generate_bounding_boxes(self, 
                              image_path: str, 
                              analysis_result: Optional[Dict[str, Any]] = None,
                              input_user: Optional[str] = None,
                              model: str = MODEL_NAME_RESOLUTION) -> Optional[List[BoundingBox]]:
        """
        Generate bounding boxes for objects in the image.
        
        Args:
            image_path: Path to the image file
            analysis_result: Optional analysis result to include in the prompt
            model: The model to use for bounding box generation
            
        Returns:
            A list of BoundingBox objects or None if failed
        """
        if not self.client:
            logging.error("Cannot generate bounding boxes: No Google API client available")
            return None
            
        try:
            # Load image and resize if needed
            im = Image.open(image_path)
            max_size = (640, 640)
            if im.width > max_size[0] or im.height > max_size[1]:
                im.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Prepare prompt
            prompt_resolution = f"""
            You are a senior marketing designer with solid expertise in storytelling, branding, and visual content focused on conversion.
            The user has provided the following description of their project:
            \"\"\"{input_user}\"\"\"
            Perform the following tasks:
            - Analyze and critique the provided marketing image.
            - Provide specific and practical recommendations to improve its performance.
            - Focus on and prioritize key insights for the user.
            - Group these insights/recommendations into 5 to 7 main elements.
            - For each insight, briefly suggest specific actions to implement it.
            - Classify each recommendation by its impact level: "High", "Medium", or "Low".
            - At the end, generate a JSON list where each entry contains:
                - "box_2d": the bounding box coordinates.
                - "label": a text label explaining the insight (in Spanish).
                - "impact": the impact level of the recommendation (one of "High", "Medium", or "Low").
            """
            
            # Add analysis result if available
            if analysis_result:
                prompt_resolution += f"\n\nYou can also support yourself with the following report JSON:\n{json.dumps(analysis_result)}"
            
            # Run model to find bounding boxes
            response = self.client.models.generate_content(
                model=model,
                contents=[im, prompt_resolution],
                config={
                    "response_mime_type": "application/json",
                },
            )

            # Parse the response
            box_response = self._parse_json_response(response.text)
            
            # Save the raw response
            base_filename = os.path.basename(image_path).split('.')[0]
            box_json_path = os.path.join(DEFAULT_OUTPUT_DIR, f"{base_filename}_boxes.json")
            with open(box_json_path, 'w') as f:
                json.dump(box_response, f, indent=2, ensure_ascii=False)
            
            try:
                # Verificar si box_response es ya una lista o necesita ser parseado
                if isinstance(box_response, str):
                    box_data = json.loads(box_response)
                else:
                    box_data = box_response

                return [BoundingBox(**box) for box in box_data]
            except Exception as e:
                logging.error(f"Error parsing bounding boxes: {e}")
                return None
                
        except Exception as e:
            logging.error(f"Error generating bounding boxes: {e}")
            return None
    
    def _parse_json_response(self, json_output: str) -> dict:
        """
        Parse JSON output from a model response, removing markdown fencing if present
        and properly handling special characters.
    
        Args:
            json_output: The JSON output from the model
            
        Returns:
            Parsed JSON as a Python dictionary with proper character encoding
        """
        # Handle case where response is wrapped in markdown code blocks
        lines = json_output.splitlines()
        for i, line in enumerate(lines):
            if line.strip() == "```json":
                json_output = "\n".join(lines[i+1:])  # Remove everything before "```json"
                json_output = json_output.split("```")[0]  # Remove everything after the closing "```"
                break  # Exit the loop once "```json" is found
    
        # Handle additional cleaning that might be needed
        json_output = json_output.strip()
    
        # If the output is wrapped in quotes and has escaped quotes inside
        if json_output.startswith('"') and json_output.endswith('"'):
            # This handles cases where Gemini returns a JSON string that's been double-serialized
            json_output = json_output[1:-1].replace('\\"', '"')
    
        try:
            # Parse the JSON - this automatically converts \uXXXX sequences to proper characters
            return json.loads(json_output)
        except json.JSONDecodeError as e:
            # Log error and attempt recovery
            logging.error(f"Error decoding JSON: {e}")
        
            # Try to fix common issues (like unescaped newlines)
            clean_output = re.sub(r'(?<!\\)\n', ' ', json_output)
            try:
                return json.loads(clean_output)
            except json.JSONDecodeError:
                # If still failing, return the cleaned string for manual inspection
                logging.error("Failed to parse JSON after cleanup attempt")
                return json_output  # Return as string since we couldn't parse it
    
    def visualize_bounding_boxes(self, 
                                image_path: str, 
                                bounding_boxes: List[Dict[str, Any]],
                                show_labels: bool = True,
                                line_width: int = 4) -> Optional[Image.Image]:
        """
        Visualize bounding boxes on an image.
        
        Args:
            image_path: Path to the image file
            bounding_boxes: List of bounding box dictionaries
            show_labels: Whether to draw text labels (default: True)
            line_width: Width of bounding box lines (default: 4)
            
        Returns:
            PIL Image with bounding boxes drawn or None if failed
        """
        try:
            # Load the image
            img = Image.open(image_path)
            width, height = img.size
            
            # Create a drawing object
            draw = ImageDraw.Draw(img)
            
            # Define colors for different bounding boxes
            colors = [
                'red', 'green', 'blue', 'yellow', 'orange', 'pink', 'purple',
                'brown', 'gray', 'beige', 'turquoise', 'cyan', 'magenta',
                'lime', 'navy', 'maroon', 'teal', 'olive', 'coral', 'lavender',
                'violet', 'gold', 'silver',
            ] + [colorname for (colorname, colorcode) in ImageColor.colormap.items()]
            
            # Try to load a font, with fallbacks
            font = None
            if show_labels:
                try:
                    font = ImageFont.truetype("arial.ttf", size=14)
                except IOError:
                    try:
                        # Try a system font that should be available on most platforms
                        font = ImageFont.truetype("DejaVuSans.ttf", size=14)
                    except IOError:
                        # Use the default font as a last resort
                        font = ImageFont.load_default()
            
            # Draw the bounding boxes
            for i, box in enumerate(bounding_boxes):
                # Select a color from the list
                color = colors[i % len(colors)]
                
                # Get coordinates, normalized from 0-1000 range to pixel values
                try:
                    abs_y1 = int(box["box_2d"][0]/1000 * height)
                    abs_x1 = int(box["box_2d"][1]/1000 * width)
                    abs_y2 = int(box["box_2d"][2]/1000 * height)
                    abs_x2 = int(box["box_2d"][3]/1000 * width)
                    
                    # Make sure coordinates are ordered correctly
                    if abs_x1 > abs_x2:
                        abs_x1, abs_x2 = abs_x2, abs_x1
                    if abs_y1 > abs_y2:
                        abs_y1, abs_y2 = abs_y2, abs_y1
                    
                    # Draw the bounding box
                    draw.rectangle(
                        ((abs_x1, abs_y1), (abs_x2, abs_y2)), outline=color, width=line_width
                    )
                    
                    # Draw the label if it exists and labels are enabled
                    if show_labels and "label" in box and font:
                        draw.text((abs_x1 + 8, abs_y1 + 6), box["label"], fill=color, font=font)
                except (KeyError, IndexError, ValueError) as e:
                    logging.warning(f"Error drawing box {i}: {e}")
                    continue
            
            return img
            
        except Exception as e:
            logging.error(f"Error visualizing bounding boxes: {e}")
            return None
    
    def process_image(self, 
                     image_path: str, 
                     metrics_json_path: Optional[str] = None,
                     project_description: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Complete end-to-end image processing pipeline.
        
        Args:
            image_path: Path to the image file
            metrics_json_path: Optional path to metrics JSON (if None, will be inferred from image_path)
            project_description: Optional description of the project from the user
            
        Returns:
            Tuple of (analysis_json_path, processed_image_path) or (None, None) if failed
        """
        try:
            # If metrics_json_path not provided, try to infer it
            if not metrics_json_path:
                base_filename = os.path.basename(image_path).split('.')[0]
                metrics_json_path = os.path.join(DEFAULT_INPUT_DIR, f"{base_filename}_metrics.json")
                if not os.path.exists(metrics_json_path):
                    logging.error(f"Metrics file not found: {metrics_json_path}")
                    return None, None
            
            # Step 1: Analyze metrics
            analysis_result = self.analyze_metrics(metrics_json_path)
            if not analysis_result:
                logging.error("Failed to analyze metrics")
                return None, None
                
            # Step 2: Generate bounding boxes
            bounding_boxes = self.generate_bounding_boxes(
                image_path=image_path,
                analysis_result=analysis_result.model_dump(),
                input_user=project_description
            )
            if not bounding_boxes:
                logging.error("Failed to generate bounding boxes")
                return None, None
                
            # Step 3: Visualize bounding boxes
            processed_image = self.visualize_bounding_boxes(
                image_path=image_path,
                bounding_boxes=[box.model_dump() for box in bounding_boxes]
            )
            if not processed_image:
                logging.error("Failed to visualize bounding boxes")
                return None, None
                
            # Step 4: Save the processed image
            base_filename = os.path.basename(image_path).split('.')[0]
            processed_image_path = os.path.join(DEFAULT_OUTPUT_DIR, f"{base_filename}_processed.png")
            processed_image.save(processed_image_path)
            logging.info(f"Processed image saved to {processed_image_path}")
            
            # Return paths to the analysis file and processed image
            analysis_json_path = os.path.join(DEFAULT_OUTPUT_DIR, "temp_analysis.json")
            return analysis_json_path, processed_image_path
            
        except Exception as e:
            logging.error(f"Error in process_image: {e}")
            return None, None