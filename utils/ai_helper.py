import os
import google.generativeai as genai
from dotenv import load_dotenv
import pytesseract
from PIL import Image
import pdf2image
import json
import pytz
from datetime import datetime
import requests
from forex_python.converter import CurrencyRates
import pycountry

# Load environment variables
load_dotenv()

# Get API key
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

# Configure Gemini API
genai.configure(api_key="AIzaSyB0fZ3wI8jD9zU-mhjOUdZoLfGziEOBGww")

# Initialize models - using Gemini 2.0 Flash
model = genai.GenerativeModel('gemini-2.0-flash')
vision_model = genai.GenerativeModel('gemini-2.0-flash')

# Set Tesseract path for Windows
if os.name == 'nt':  # Windows
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def get_local_currency():
    """Get local currency based on timezone."""
    local_tz = datetime.now().astimezone().tzinfo
    # Map common timezones to currency codes
    timezone_currency_map = {
        'Asia/Kolkata': 'INR',
        'America/New_York': 'USD',
        'Europe/London': 'GBP',
        'Asia/Tokyo': 'JPY',
        'Australia/Sydney': 'AUD',
        # Add more mappings as needed
    }
    return timezone_currency_map.get(str(local_tz), 'USD')  # Default to USD

def convert_price_to_local(price, from_currency='USD'):
    """Convert price to local currency."""
    try:
        c = CurrencyRates()
        local_currency = get_local_currency()
        if local_currency == from_currency:
            return price, local_currency
        converted_price = c.convert(from_currency, local_currency, price)
        return round(converted_price, 2), local_currency
    except:
        return price, 'USD'  # Default to USD if conversion fails

def search_food_image(food_name, description=''):
    """Search for a food image using Gemini to generate a search query."""
    try:
        # Generate an optimized search query using AI
        prompt = f"""
        Generate a specific image search query for this food item:
        Name: {food_name}
        Description: {description}
        Format: return only the search query, no other text.
        Make it specific to find a high-quality food photo.
        """
        
        response = model.generate_content(prompt)
        search_query = response.text.strip()
        
        # Use the search query to find an image
        # For demo, we'll use a placeholder URL
        # In production, integrate with a proper image search API
        placeholder_url = f"/static/img/food/{food_name.lower().replace(' ', '_')}.jpg"
        return placeholder_url
    except Exception as e:
        print(f"Error searching food image: {e}")
        return None

def extract_text_from_image(image_path):
    """
    Extract text from an image using OCR.
    """
    try:
        image = Image.open(image_path)
        # Convert image to RGB if it's not
        if image.mode != 'RGB':
            image = image.convert('RGB')
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception as e:
        print(f"Error in OCR processing: {e}")
        return None

def extract_text_from_pdf(pdf_path):
    """
    Extract text from a PDF using OCR.
    """
    try:
        # Convert PDF to images
        images = pdf2image.convert_from_path(pdf_path)
        text = ""
        for image in images:
            text += pytesseract.image_to_string(image) + "\n"
        return text.strip()
    except Exception as e:
        print(f"Error in PDF processing: {e}")
        return None

def analyze_menu_image(image_path):
    """
    Analyze menu image directly using Gemini Vision API.
    Returns a list of menu items with their details.
    """
    try:
        # Load and validate image
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")
            
        img = Image.open(image_path)
        
        # Convert image to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        prompt = """
        Extract menu items from this image.
        Return a JSON array. Each item must have:
        name, description, price (number), category, preparation_time (minutes).
        Include the currency symbol or code if visible in the menu.
        Format: valid JSON only.
        """
        
        response = vision_model.generate_content([prompt, img])
        
        # Parse the response as JSON
        try:
            # Clean the response text
            text = response.text.strip()
            text = text.replace('```json', '').replace('```', '').strip()
            menu_items = json.loads(text)
            
            if not isinstance(menu_items, list):
                raise ValueError("Response is not a list of menu items")
            
            # Process each menu item
            for item in menu_items:
                if not all(k in item for k in ['name', 'price']):
                    raise ValueError("Menu items missing required fields")
                
                # Convert price to local currency
                price, currency = convert_price_to_local(float(item['price']))
                item['price'] = price
                item['currency'] = currency
                
                # Search for image if not provided
                if not item.get('image_url'):
                    item['image_url'] = search_food_image(item['name'], item.get('description', ''))
                    
            return menu_items
        except json.JSONDecodeError as e:
            print(f"Failed to parse Gemini response as JSON: {e}")
            print(f"Raw response: {response.text}")
            return None
    except Exception as e:
        print(f"Error in Gemini Vision API call: {e}")
        return None

def analyze_menu_text(text):
    """
    Analyze menu text using Gemini AI to extract menu items.
    Returns a list of menu items with their details.
    """
    prompt = f"""
    Analyze the following menu text and extract menu items in JSON format.
    Return ONLY a valid JSON array of items, nothing else.
    
    Menu text:
    {text}
    
    Format each item as:
    {{
        "name": "Item name",
        "description": "Brief description of the item",
        "price": float price,
        "category": "Category name",
        "preparation_time": estimated_time_in_minutes
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        # Parse the response as JSON
        try:
            menu_items = json.loads(response.text)
            return menu_items if isinstance(menu_items, list) else None
        except json.JSONDecodeError:
            print("Failed to parse Gemini response as JSON")
            return None
    except Exception as e:
        print(f"Error in Gemini API call: {e}")
        return None

def generate_item_description(item_name):
    """
    Generate an appealing description for a menu item.
    """
    prompt = f"Write a brief, appealing description (max 100 chars) for: {item_name}"
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Error generating description: {e}")
        return None

def estimate_preparation_time(item_name):
    """
    Estimate preparation time for a menu item.
    """
    try:
        response = model.generate_content(
            f"Preparation time in minutes for {item_name}? Number only."
        )
        time_str = response.text.strip()
        return int(time_str) if time_str.isdigit() else 15
    except Exception as e:
        print(f"Error estimating time: {e}")
        return 15  # Default preparation time

def suggest_menu_improvements(menu_items):
    """
    Suggest improvements for the menu using Gemini AI.
    """
    prompt = f"""
    Analyze these menu items and suggest improvements:
    {menu_items}
    
    Consider:
    1. Item variety
    2. Price points
    3. Category organization
    4. Popular trends
    5. Seasonal suggestions
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error in Gemini API call: {e}")
        return None 