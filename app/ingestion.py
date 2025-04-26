# Image ingestion logic
import requests
import os
import logging
import time # Added for rate limiting
import math # Added for calculating image counts

# Determine project root and default save directory dynamically
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
DEFAULT_SAVE_DIR = os.path.join(_PROJECT_ROOT, 'data', 'raw')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_and_save_images(api_key: str, query: str, per_page: int = 15, page: int = 1, save_dir: str = DEFAULT_SAVE_DIR, orientation: str | None = None):
    """
    Fetches images from Pexels API based on a query and saves them to a specified directory.

    Args:
        api_key: Your Pexels API key.
        query: The search term for images.
        per_page: Number of images to fetch per page (max 80).
        page: The page number to fetch.
        save_dir: The directory to save the downloaded images. Defaults to 'data/raw' relative to the project root.
        orientation: Optional image orientation ('landscape', 'portrait', 'square').

    Returns:
        int: The number of API requests made during this function call.
    """
    requests_made = 0
    if not api_key:
        logging.error("Pexels API key is required.")
        return requests_made # Return 0 requests if no key

    # Build the search URL
    search_url = f"https://api.pexels.com/v1/search?query={query}&per_page={per_page}&page={page}"
    if orientation:
        search_url += f"&orientation={orientation}"

    headers = {
        "Authorization": api_key
    }

    try:
        # --- Search Request --- 
        response = requests.get(search_url, headers=headers, timeout=15) # Increased timeout slightly
        requests_made += 1
        response.raise_for_status() # Raises an HTTPError for bad responses (4XX or 5XX)

        data = response.json()
        photos = data.get('photos', [])

        if not photos:
            logging.info(f"No photos found for query: '{query}' with orientation: {orientation}")
            return requests_made # Return requests made so far

        # Ensure the save directory exists
        os.makedirs(save_dir, exist_ok=True)

        logging.info(f"Found {len(photos)} photos for '{query}' (orientation: {orientation}). Downloading up to {per_page}...")

        download_count = 0
        for photo in photos:
            if download_count >= per_page: # Should technically be handled by API's per_page, but as a safeguard
                break

            photo_id = photo['id']
            # Choose the desired image quality, e.g., 'original', 'large', 'medium', 'small'
            img_url = photo['src']['original'] # Or choose another size like 'large2x'
            orientation_tag = f"_{orientation}" if orientation else ""
            img_name = f"pexels_{photo_id}_{query.replace(' ', '_')}{orientation_tag}.jpg"
            img_path = os.path.join(save_dir, img_name)

            try:
                 # --- Image Download Request --- 
                img_response = requests.get(img_url, stream=True, timeout=30) # Increased timeout for download
                requests_made += 1
                img_response.raise_for_status()

                with open(img_path, 'wb') as f:
                    for chunk in img_response.iter_content(chunk_size=8192):
                        f.write(chunk)
                logging.debug(f"Saved image: {img_path}") # Changed to debug to reduce verbosity
                download_count += 1

            except requests.exceptions.RequestException as img_err:
                logging.warning(f"Warning: Error downloading image {img_url}: {img_err}") # Changed to warning
            except IOError as io_err:
                 logging.warning(f"Warning: Error saving image {img_path}: {io_err}") # Changed to warning

        logging.info(f"Successfully downloaded {download_count} images for '{query}' (orientation: {orientation}).")

    except requests.exceptions.Timeout:
        logging.error(f"Request to Pexels API timed out for query: '{query}'.")
    except requests.exceptions.HTTPError as http_err:
        # Log client errors (4xx) differently from server errors (5xx)
        if 400 <= http_err.response.status_code < 500:
             logging.error(f"Client error occurred: {http_err} - URL: {search_url} - Response: {http_err.response.text}")
        else:
            logging.error(f"Server error occurred: {http_err} - URL: {search_url}")
    except requests.exceptions.RequestException as req_err:
        logging.error(f"Error fetching data from Pexels API: {req_err}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")

    return requests_made

# --- Main execution block --- 
if __name__ == "__main__":
    pexels_api_key = os.getenv("PEXELS_API_KEY")
    # Fallback for testing if env var not set (Replace with your key only for temporary testing)
    if not pexels_api_key:
        pexels_api_key = "oFlf0SwIYxw8nHCNWFKBlRHGXHYozzVl8bUIvjzhZu2bqK5R2SW68j0y" # Replace ONLY for testing
        logging.warning("Using fallback API key from code. Set PEXELS_API_KEY environment variable for security.")

    if not pexels_api_key or pexels_api_key == "YOUR_API_KEY": # Added check for placeholder value
         logging.error("PEXELS API key is not set or is invalid. Please set the PEXELS_API_KEY environment variable.")
    else:
        # Configuration
        TARGET_TOPICS = ["digital marketing", "advertising sales", "shopping", "food", "health", "cosmetics"]
        IMAGES_PER_TOPIC = 40
        PORTRAIT_RATIO = 0.80
        PEXELS_HOURLY_LIMIT = 200
        # Use a slightly lower limit in practice to avoid edge cases
        RATE_LIMIT_THRESHOLD = PEXELS_HOURLY_LIMIT - 20 # Leave a buffer of 20 requests
        ONE_HOUR_SECONDS = 3600

        # Calculate image counts per orientation
        num_portrait = math.ceil(IMAGES_PER_TOPIC * PORTRAIT_RATIO)
        num_landscape = IMAGES_PER_TOPIC - num_portrait

        # Rate limiting state
        requests_this_hour = 0
        hour_start_time = time.time()

        logging.info(f"Starting image download for {len(TARGET_TOPICS)} topics...")
        logging.info(f"Target per topic: {num_portrait} portrait, {num_landscape} landscape.")

        for topic in TARGET_TOPICS:
            # --- Rate Limit Check --- 
            current_time = time.time()
            elapsed_time = current_time - hour_start_time

            # Reset counter if hour has passed
            if elapsed_time > ONE_HOUR_SECONDS:
                logging.info("Hourly time window reset.")
                requests_this_hour = 0
                hour_start_time = current_time
                elapsed_time = 0 # Reset elapsed time as well

            # Estimate requests needed for this topic (2 searches + N downloads)
            # Overestimating download requests (per_page) for safety
            estimated_requests = (1 + num_portrait) + (1 + num_landscape)

            if requests_this_hour + estimated_requests > RATE_LIMIT_THRESHOLD:
                wait_time = ONE_HOUR_SECONDS - elapsed_time
                logging.warning(f"Rate limit threshold approaching ({requests_this_hour}/{RATE_LIMIT_THRESHOLD}). Waiting for {wait_time:.1f} seconds...")
                time.sleep(wait_time)
                # Reset counter after waiting
                requests_this_hour = 0
                hour_start_time = time.time()

            logging.info(f"--- Processing topic: {topic} --- ")

            # Fetch portrait images
            if num_portrait > 0:
                logging.info(f"Fetching {num_portrait} portrait images for '{topic}'...")
                reqs = fetch_and_save_images(
                    api_key=pexels_api_key,
                    query=topic,
                    per_page=num_portrait,
                    orientation='portrait'
                )
                requests_this_hour += reqs
                logging.info(f"Requests made this hour: {requests_this_hour}")

            # Fetch landscape images
            if num_landscape > 0:
                logging.info(f"Fetching {num_landscape} landscape images for '{topic}'...")
                reqs = fetch_and_save_images(
                    api_key=pexels_api_key,
                    query=topic,
                    per_page=num_landscape,
                    orientation='landscape'
                )
                requests_this_hour += reqs
                logging.info(f"Requests made this hour: {requests_this_hour}")

            # Optional small delay between topics to be nice to the API
            time.sleep(2)

        logging.info("Image download process finished.")