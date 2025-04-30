# Entry point for the application 
import os
import logging
import argparse
import glob
from typing import List, Optional

# Import components
from app.ingestion import fetch_and_save_images
from app.analyzer import analyze_visual_complexity, save_metrics_to_json
from app.agent import ImageAgent

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Determine project paths dynamically
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
DEFAULT_RAW_DIR = os.path.join(_PROJECT_ROOT, 'data', 'raw')
DEFAULT_PROCESSED_DIR = os.path.join(_PROJECT_ROOT, 'data', 'processed')
DEFAULT_OUTPUT_DIR = os.path.join(_PROJECT_ROOT, 'data', 'output')

def create_directories():
    """Create necessary directories for the pipeline."""
    os.makedirs(DEFAULT_RAW_DIR, exist_ok=True)
    os.makedirs(DEFAULT_PROCESSED_DIR, exist_ok=True)
    os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)

def ingest_images(api_key: str, query: str, count: int, orientation: Optional[str] = None) -> List[str]:
    """Ingest images from Pexels API."""
    logging.info(f"Ingesting {count} images for '{query}'...")
    fetch_and_save_images(
        api_key=api_key,
        query=query,
        per_page=count,
        save_dir=DEFAULT_RAW_DIR,
        orientation=orientation
    )
    
    # Return paths of downloaded images
    pattern = os.path.join(DEFAULT_RAW_DIR, f"pexels_*_{query.replace(' ', '_')}*.jpg")
    return glob.glob(pattern)

def analyze_images(image_paths: List[str]) -> List[str]:
    """Analyze images and generate metrics."""
    logging.info(f"Analyzing {len(image_paths)} images...")
    metric_paths = []
    
    for img_path in image_paths:
        base_filename = os.path.basename(img_path).split('.')[0]
        output_file = os.path.join(DEFAULT_PROCESSED_DIR, f"{base_filename}_metrics.json")
        
        # Analyze image complexity
        metrics = analyze_visual_complexity(img_path)
        if metrics:
            save_metrics_to_json(metrics, output_file)
            metric_paths.append(output_file)
            logging.info(f"Generated metrics for {base_filename}")
        else:
            logging.error(f"Failed to analyze {img_path}")
            
    return metric_paths

def process_with_agent(image_paths: List[str], metric_paths: List[str]) -> None:
    """Process images with the agent."""
    logging.info(f"Processing {len(image_paths)} images with agent...")
    
    # Get API key from environment variable
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logging.warning("GOOGLE_API_KEY environment variable not set. Using default key.")
        api_key = "AIzaSyAqkLokEksQMO_4kBaDjXh6Q72lDPHE6y0"  # Default key for demo purposes
    
    # Initialize agent
    agent = ImageAgent(api_key=api_key)
    
    # Process each image
    for i, img_path in enumerate(image_paths):
        if i >= len(metric_paths):
            logging.warning(f"No metrics found for {img_path}")
            continue
            
        logging.info(f"Processing image {i+1}/{len(image_paths)}: {os.path.basename(img_path)}")
        analysis_path, processed_image_path = agent.process_image(img_path, metric_paths[i])
        
        if analysis_path and processed_image_path:
            logging.info(f"Successfully processed {os.path.basename(img_path)}")
        else:
            logging.error(f"Failed to process {os.path.basename(img_path)}")

def run_full_pipeline(query: str, count: int, orientation: Optional[str] = None):
    """Run the full pipeline from ingestion to agent processing."""
    logging.info(f"Starting full pipeline for query '{query}'...")
    
    # Step 1: Ingest images
    pexels_api_key = os.getenv("PEXELS_API_KEY")
    if not pexels_api_key:
        logging.error("PEXELS_API_KEY environment variable not set.")
        return
        
    image_paths = ingest_images(pexels_api_key, query, count, orientation)
    if not image_paths:
        logging.error(f"No images ingested for query '{query}'")
        return
        
    # Step 2: Analyze images
    metric_paths = analyze_images(image_paths)
    if not metric_paths:
        logging.error("No metrics generated. Cannot proceed with agent processing.")
        return
        
    # Step 3: Process with agent
    process_with_agent(image_paths, metric_paths)
    
    logging.info("Pipeline completed successfully.")

def process_existing_images():
    """Process existing images without ingesting new ones."""
    logging.info("Processing existing images...")
    
    # Get all image files in the raw directory
    image_paths = glob.glob(os.path.join(DEFAULT_RAW_DIR, "*.jpg"))
    if not image_paths:
        logging.error("No images found in raw directory.")
        return
        
    logging.info(f"Found {len(image_paths)} images in raw directory.")
    
    # Step 1: Analyze images that don't have metrics yet
    metric_paths = []
    for img_path in image_paths:
        base_filename = os.path.basename(img_path).split('.')[0]
        metric_path = os.path.join(DEFAULT_PROCESSED_DIR, f"{base_filename}_metrics.json")
        
        if os.path.exists(metric_path):
            logging.info(f"Metrics already exist for {base_filename}")
            metric_paths.append(metric_path)
        else:
            metrics = analyze_visual_complexity(img_path)
            if metrics:
                save_metrics_to_json(metrics, metric_path)
                metric_paths.append(metric_path)
                logging.info(f"Generated metrics for {base_filename}")
            else:
                logging.error(f"Failed to analyze {img_path}")
    
    # Step 2: Process with agent
    process_with_agent(image_paths, metric_paths)
    
    logging.info("Processing of existing images completed.")

if __name__ == "__main__":
    # Create necessary directories
    create_directories()
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Image Analysis Pipeline")
    parser.add_argument("--query", help="Search query for Pexels API")
    parser.add_argument("--count", type=int, default=5, help="Number of images to process")
    parser.add_argument("--orientation", choices=["landscape", "portrait", "square"], 
                        help="Image orientation")
    parser.add_argument("--use-existing", action="store_true", 
                        help="Use existing images instead of downloading new ones")
    
    args = parser.parse_args()
    
    if args.use_existing:
        process_existing_images()
    elif args.query:
        run_full_pipeline(args.query, args.count, args.orientation)
    else:
        # Default behavior: process existing images
        process_existing_images() 