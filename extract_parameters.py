import spacy
from rapidfuzz import process
from datetime import datetime, timedelta
import parsedatetime
from autocorrect import Speller
import re
import json
from typing import Dict
import os
from dotenv import load_dotenv
from groq import Groq


load_dotenv()  # Load environment variables from .env file
# Load spaCy English model
nlp = spacy.load("en_core_web_sm")
spell = Speller(lang='en')

# City to IATA mapping
city_to_iata = {
    "lahore": "LHE",
    "karachi": "KHI",
    "islamabad": "ISB",
    "rawalpindi": "ISB",   # shares ISB airport
    "multan": "MUX",
    "peshawar": "PEW",
    "quetta": "UET",
    "faisalabad": "LYP",
    "sialkot": "SKT",
    "skardu": "KDU",
    "gilgit": "GIL",
    "sukkur": "SKZ",
    "gwadar": "GWD",
    "turbat": "TUK",
    "bahawalpur": "BHV",
    "dera ghazi khan": "DEA",
    "chitral": "CJL",
    "panjgur": "PJG",
    "moenjodaro": "MJD",
    "parachinar": "PAJ",
    "zhob": "PZH",
    "dalbandin": "DBA",
    "muzaffarabad": "MFG",
    "rahim yar khan": "RYK",
    "nawabshah": "WNS"
}

# Airline name mappings (including common variations and misspellings)
airline_mappings = {
    # Pakistani Airlines
    "airblue": ["airblue", "air blue", "air-blue", "airblue airlines"],
    "serene_air": ["serene air", "serene-air", "sereneair", "serene air lines", "serene airlines"],
    "pia": [
        "pia", "pakistan international airlines", "pakistan international", 
        "pakistan airlines", "pakistan air", "pakistani airlines"
    ],
    "shaheen_air": ["shaheen air", "shaheen-air", "shaheenair", "shaheen airlines"],
    
    # International Airlines (Major ones)
    "emirates": ["emirates", "emirates airlines", "emirates airways", "ek"],
    "qatar_airways": ["qatar airways", "qatar", "qatar airlines", "qr"],
    "etihad": ["etihad", "etihad airways", "etihad airlines", "ey"],
    "turkish_airlines": ["turkish airlines", "turkish", "turkish airways", "tk"],
    "lufthansa": ["lufthansa", "lufthansa airlines", "lufthansa airways", "lh"],
    "british_airways": ["british airways", "british", "ba", "british airlines"],
    "air_arabia": ["air arabia", "air-arabia", "airarabia", "g9"],
    "flydubai": ["flydubai", "fly dubai", "fly-dubai", "fz"],
    "saudia": ["saudia", "saudi airlines", "saudi arabian airlines", "sv"],
    "gulf_air": ["gulf air", "gulf-air", "gulfair", "gulf airlines", "gf"],
    "oman_air": ["oman air", "oman-air", "omanair", "oman airlines", "wy"],
    "kuwait_airways": ["kuwait airways", "kuwait", "kuwait airlines", "ku"],
    "middle_east_airlines": ["middle east airlines", "mea", "middle eastern airlines"],
    "royal_jordanian": ["royal jordanian", "royal-jordanian", "rj", "jordanian airlines"],
    "egyptair": ["egyptair", "egypt air", "egypt-air", "egyptian airlines", "ms"],
    
    # Asian Airlines
    "cathay_pacific": ["cathay pacific", "cathay-pacific", "cathay", "cx"],
    "singapore_airlines": ["singapore airlines", "singapore", "sia", "sq"],
    "malaysia_airlines": ["malaysia airlines", "malaysia", "malaysian airlines", "mh"],
    "thai_airways": ["thai airways", "thai", "thai airlines", "tg"],
    "air_india": ["air india", "air-india", "airindia", "indian airlines", "ai"],
    "indigo": ["indigo", "indigo airlines", "6e"],
    "spicejet": ["spicejet", "spice jet", "spice-jet", "sg"],
    "china_southern": ["china southern", "china-southern", "cz"],
    "china_eastern": ["china eastern", "china-eastern", "mu"],
    
    # European Airlines
    "klm": ["klm", "klm airlines", "klm royal dutch airlines", "kl"],
    "air_france": ["air france", "air-france", "airfrance", "af"],
    "alitalia": ["alitalia", "alitalia airlines", "az"],
    "swiss": ["swiss", "swiss airlines", "swiss international", "lx"],
    "austrian_airlines": ["austrian airlines", "austrian", "os"],
    "scandinavian_airlines": ["sas", "scandinavian airlines", "scandinavian", "sk"],
    
    # American Airlines
    "american_airlines": ["american airlines", "american", "aa"],
    "delta": ["delta", "delta airlines", "delta airways", "dl"],
    "united": ["united", "united airlines", "ua"],
    "southwest": ["southwest", "southwest airlines", "wn"],
    "jetblue": ["jetblue", "jet blue", "jet-blue", "b6"],
    
    # Budget/Low-cost carriers
    "ryanair": ["ryanair", "ryan air", "ryan-air", "fr"],
    "easyjet": ["easyjet", "easy jet", "easy-jet", "u2"],
    "wizz_air": ["wizz air", "wizz-air", "wizzair", "w6"],
    "norwegian": ["norwegian", "norwegian airlines", "dy"],
    "vueling": ["vueling", "vueling airlines", "vy"],
    
    # Other notable airlines
    "aeroflot": ["aeroflot", "aeroflot airlines", "su"],
    "korean_air": ["korean air", "korean-air", "koreanair", "ke"],
    "asiana": ["asiana", "asiana airlines", "oz"],
    "japan_airlines": ["jal", "japan airlines", "japanese airlines", "jl"],
    "ana": ["ana", "all nippon airways", "all nippon", "nh"],
    "etihad_regional": ["etihad regional", "darwin airline"],
    "air_canada": ["air canada", "air-canada", "aircanada", "ac"],
    "westjet": ["westjet", "west jet", "west-jet", "ws"]
}

# Create a flattened list of all airline keywords for fuzzy matching
all_airline_keywords = [(variation.lower(), code) for code, variations in airline_mappings.items() for variation in variations]

city_names = list(city_to_iata.keys())
# Create reverse mapping for IATA codes
iata_codes = set(city_to_iata.values())

def correct_spelling(text):
    return spell(text)

def extract_cities_multiword(text):
    """Extract multi-word cities first, then single word cities, and IATA codes"""
    text_lower = text.lower()
    found_cities = []
    
    # First, check for IATA codes (3-letter uppercase codes)
    iata_pattern = r'\b[A-Z]{3}\b'
    iata_matches = re.finditer(iata_pattern, text.upper())
    
    for match in iata_matches:
        iata_code = match.group()
        if iata_code in iata_codes:
            start_pos = match.start()
            words_before = len(text[:start_pos].split())
            found_cities.append((iata_code, words_before, start_pos))
    
    # Also check for city names (don't return early, combine with IATA codes)
    # Sort cities by length (longest first) to match multi-word cities first
    sorted_cities = sorted(city_names, key=len, reverse=True)
    
    for city in sorted_cities:
        if city in text_lower:
            # Find the position of the city in the text
            start_pos = text_lower.find(city)
            if start_pos != -1:
                # Check if it's a whole word match (not part of another word)
                start_char = start_pos == 0 or not text_lower[start_pos - 1].isalnum()
                end_char = (start_pos + len(city) == len(text_lower) or 
                           not text_lower[start_pos + len(city)].isalnum())
                
                if start_char and end_char:
                    iata = city_to_iata[city]
                    # Calculate approximate token position
                    words_before = len(text_lower[:start_pos].split())
                    found_cities.append((iata, words_before, start_pos))
                    # Remove the matched city from text to avoid overlapping matches
                    text_lower = text_lower.replace(city, " " * len(city), 1)
    
    return found_cities

def extract_cities(query):
    query_lower = query.lower()
    doc = nlp(query_lower)
    
    # First try to extract multi-word cities
    found_cities = extract_cities_multiword(query_lower)
    
    # If no multi-word cities found, try entity recognition and fuzzy matching
    if not found_cities:
        for ent in doc.ents:
            if ent.label_ in ("GPE", "LOC"):
                match, score, _ = process.extractOne(ent.text.lower(), city_names)
                if score > 85:
                    iata = city_to_iata[match]
                    found_cities.append((iata, ent.start, ent.start_char))
    
    # Fallback to token-based fuzzy matching if still no entities found
    if not found_cities:
        tokens = [token.text for token in doc]  # Keep original case for IATA detection
        for i, token in enumerate(tokens):
            # Check if token is an IATA code
            if len(token) == 3 and token.upper() in iata_codes:
                found_cities.append((token.upper(), i, doc[i].idx))
            else:
                # Try fuzzy matching with city names
                match, score, _ = process.extractOne(token.lower(), city_names)
                if score > 90:
                    iata = city_to_iata[match]
                    found_cities.append((iata, i, doc[i].idx))
    
    # Remove duplicates and sort by character position
    seen = set()
    unique_cities = []
    for city, token_idx, char_idx in found_cities:
        if city not in seen:
            seen.add(city)
            unique_cities.append((city, token_idx, char_idx))
    found_cities = sorted(unique_cities, key=lambda x: x[2])  # Sort by character position
    
    # Use improved logic to identify source and destination
    source = destination = None
    
    # Look for directional indicators
    from_indicators = ["from", "leaving", "departing", "starting"]
    to_indicators = ["to", "towards", "going to", "arriving", "destination"]
    
    # Check for explicit directional phrases
    for token in doc:
        if token.text.lower() in from_indicators:
            # Look for cities after "from" indicators
            for city_info in found_cities:
                city_iata, city_token_idx, city_char_idx = city_info
                if city_char_idx > token.idx:  # City appears after the indicator
                    if not source:  # Take the first one found
                        source = city_iata
                        break
        
        elif token.text.lower() in to_indicators or (token.text.lower() == "to" and token.dep_ == "prep"):
            # Look for cities after "to" indicators
            for city_info in found_cities:
                city_iata, city_token_idx, city_char_idx = city_info
                if city_char_idx > token.idx:  # City appears after the indicator
                    if not destination:  # Take the first one found
                        destination = city_iata
                        break
    
    # Fallback: If no clear indicators found, use position-based logic
    if not source and not destination and found_cities:
        if len(found_cities) == 1:
            # Single city - could be either source or destination
            # Check context for clues
            if any(word in query_lower for word in to_indicators + ["going", "want to go"]):
                destination = found_cities[0][0]
            else:
                source = found_cities[0][0]
        else:
            # Multiple cities - first is typically source, second is destination
            source = found_cities[0][0]
            destination = found_cities[1][0]
    
    # Handle cases where we have indicators but cities were assigned to wrong slots
    if source and not destination and len(found_cities) > 1:
        # If we have a source but no destination, and there are multiple cities
        for city_info in found_cities:
            if city_info[0] != source:
                destination = city_info[0]
                break
    
    elif destination and not source and len(found_cities) > 1:
        # If we have a destination but no source, and there are multiple cities
        for city_info in found_cities:
            if city_info[0] != destination:
                source = city_info[0]
                break
    
    # Ensure source != destination
    if source == destination:
        if len(found_cities) > 1:
            # If they're the same, reassign based on position
            source = found_cities[0][0]
            destination = found_cities[1][0]
        else:
            destination = None
    
    return source, destination

def extract_flight_type(query):
    """
    Conservative flight type extraction - only detects return when there are strong indicators.
    Returns 'return' or 'one_way'
    """
    query_lower = query.lower()
    
    # Strong explicit return flight indicators
    strong_return_keywords = [
        "return", "round trip", "round-trip", "roundtrip", "two way", "two-way",
        "return ticket", "return flight", "both ways"
    ]
    
    # Check for explicit return keywords first
    for keyword in strong_return_keywords:
        if keyword in query_lower:
            return "return"
    
    # Very specific return patterns - only strong indicators
    return_patterns = [
        # "back to [city]" patterns - must have "back"
        r'(?:and\s+)?(?:then\s+)?back\s+to\s+\w+',
        r'(?:and\s+)?(?:then\s+)?(?:come\s+)?back\s+(?:to\s+)?\w+',
        
        # "between [date] and [date]" patterns - strong date range indicator
        r'between\s+.?\s+and\s+.?(?:\d|today|tomorrow)',
        
        # Multiple cities with explicit return language
        r'(?:from\s+)?\w+\s+to\s+\w+\s+and\s+(?:then\s+)?(?:back\s+to|return\s+to)\s+\w+',
        r'(?:from\s+)?\w+\s+to\s+\w+.*?(?:and\s+)?(?:then\s+)?(?:back|return)',
        
        # Strong temporal return indicators
        r'(?:go|travel|fly)\s+.*?(?:and\s+)?(?:then\s+)?(?:come\s+)?back',
        r'(?:trip|journey)\s+(?:from\s+)?\w+\s+to\s+\w+\s+and\s+back',
    ]
    
    for pattern in return_patterns:
        if re.search(pattern, query_lower):
            return "return"
    
    # Check for "between" with locations - strong return indicator
    if "between" in query_lower:
        # Look for "between [city] and [city]" or "between [date] and [date]"
        between_pattern = r'between\s+\w+.*?and\s+\w+'
        if re.search(between_pattern, query_lower):
            return "return"
    
    # Check for specific temporal return indicators
    strong_temporal_indicators = [
        "and back", "then back", "return on", "coming back on",
        "back on", "go and come back", "there and back"
    ]
    
    for indicator in strong_temporal_indicators:
        if indicator in query_lower:
            return "return"
    
    # Check for date ranges that suggest return trips
    date_range_patterns = [
        # Clear date ranges: "from 10th to 15th", "10th and 15th", "10th until 15th"
        r'(?:from\s+)?\d+(?:st|nd|rd|th)?\s+.*?(?:to|and|until)\s+\d+(?:st|nd|rd|th)',
        r'(?:on\s+)?\d+(?:st|nd|rd|th)?\s+.*?(?:and\s+back\s+on|and\s+return\s+on)\s+\d+(?:st|nd|rd|th)',
    ]
    
    for pattern in date_range_patterns:
        if re.search(pattern, query_lower):
            return "return"
    
    # Advanced analysis - only if we have strong indicators
    try:
        doc = nlp(query_lower)
        
        # Check for city repetition (same city mentioned multiple times)
        known_cities_mentioned = []
        for city in city_names:
            if city in query_lower:
                # Count how many times this city appears
                count = query_lower.count(city)
                if count > 1:
                    return "return"
                known_cities_mentioned.append(city)
        
        # Only check for multiple unique cities if there are strong connecting words
        if len(known_cities_mentioned) >= 2:
            # Must have explicit connecting words that suggest return journey
            strong_connectors = ["and then to", "and back to", "then to", "then back"]
            for connector in strong_connectors:
                if connector in query_lower:
                    return "return"
        
    except Exception:
        pass
    
    # Final very specific return checks
    final_return_checks = [
        r'\bgo\b.*\bback\b',      # "go ... back"
        r'\bthere\b.*\bback\b',   # "there ... back" 
        r'\bfly\b.*\breturn\b',   # "fly ... return"
    ]
    
    for check in final_return_checks:
        if re.search(check, query_lower):
            return "return"
    
    # Default to one_way - be conservative
    return "one_way"

def extract_flight_class(query):
    """
    Extract flight class from query. Returns 'economy' by default.
    Supported classes: economy, business, first, premium_economy
    Uses multiple strategies with fallbacks for robust extraction.
    """
    query_lower = query.lower()
    
    # Flight class mappings - most specific first
    class_mappings = {
        # First Class variations
        "first": ["first class", "first-class", "firstclass", "1st class", "first", "f class"],
        
        # Business Class variations  
        "business": [
            "business class", "business-class", "businessclass", "biz class", "business", 
            "c class", "club class", "executive class", "executive", "j class"
        ],
        
        # Premium Economy variations
        "premium_economy": [
            "premium economy", "premium-economy", "premiumeconomy", "premium eco", 
            "premium", "w class", "comfort plus", "economy plus", "economy+", 
            "extra comfort", "preferred seating", "premium seating"
        ],
        
        # Economy variations (explicit mentions)
        "economy": [
            "economy class", "economy-class", "economyclass", "eco class", "economy", 
            "y class", "coach", "main cabin", "standard", "regular", "basic economy"
        ]
    }
    
    # Strategy 1: Direct keyword matching (longest phrases first)
    all_keywords = []
    for class_name, keywords in class_mappings.items():
        for keyword in keywords:
            all_keywords.append((keyword, class_name))
    
    # Sort by length (longest first) to match more specific phrases
    all_keywords.sort(key=lambda x: len(x[0]), reverse=True)
    
    for keyword, class_name in all_keywords:
        if keyword in query_lower:
            return class_name
    
    # Strategy 2: NLP-based extraction using spaCy
    try:
        doc = nlp(query_lower)
        
        # Look for class-related entities or patterns
        class_indicators = ["class", "cabin", "seat", "seating", "service"]
        
        for token in doc:
            if token.text in class_indicators:
                # Look for adjectives or descriptors before/after class indicators
                context_window = []
                
                # Get context around the class indicator (2 tokens before and after)
                start_idx = max(0, token.i - 2)
                end_idx = min(len(doc), token.i + 3)
                
                for context_token in doc[start_idx:end_idx]:
                    context_window.append(context_token.text.lower())
                
                context_text = " ".join(context_window)
                
                # Check if any class keywords appear in context
                for keyword, class_name in all_keywords:
                    if keyword in context_text:
                        return class_name
        
        # Look for luxury/comfort indicators that might suggest higher classes
        luxury_indicators = {
            "business": ["professional", "corporate", "executive", "business trip", "work travel"],
            "first": ["luxury", "luxurious", "premium service", "finest", "exclusive", "vip"],
            "premium_economy": ["comfortable", "extra space", "more room", "upgrade", "better seat"]
        }
        
        query_tokens = [token.text.lower() for token in doc]
        query_text_joined = " ".join(query_tokens)
        
        for class_name, indicators in luxury_indicators.items():
            for indicator in indicators:
                if indicator in query_text_joined:
                    return class_name
                    
    except Exception:
        pass
    
    # Strategy 3: Pattern-based extraction
    class_patterns = [
        # Patterns like "in business class", "book first class"
        (r'\b(?:in|book|reserve|want|need|prefer)\s+(\w+(?:\s+\w+)?)\s+class\b', 1),
        (r'\b(\w+(?:\s+\w+)?)\s+class\s+(?:seat|ticket|flight|fare)\b', 1),
        (r'\b(?:fly|travel)\s+(\w+(?:\s+\w+)?)\s+class\b', 1),
        
        # Patterns like "business class flight", "first class ticket"
        (r'\b(\w+(?:\s+\w+)?)\s+class\s+(?:flight|ticket|booking)\b', 1),
        
        # More flexible patterns
        (r'\b(first|business|economy|premium)\s+(?:class\s+)?(?:seat|ticket|flight|cabin)\b', 1),
        (r'\b(?:seat|ticket|flight|cabin)\s+(?:in\s+)?(\w+(?:\s+\w+)?)\s+class\b', 1),
    ]
    
    for pattern, group_idx in class_patterns:
        matches = re.findall(pattern, query_lower)
        if matches:
            for match in matches:
                extracted_class = match.strip() if isinstance(match, str) else match[group_idx-1].strip()
                
                # Map extracted class to standard class names
                for class_name, keywords in class_mappings.items():
                    if extracted_class in keywords or any(keyword.startswith(extracted_class) for keyword in keywords):
                        return class_name
    
    # Strategy 4: Fuzzy matching for misspellings or variations
    try:
        # Extract potential class-related words
        class_related_words = []
        doc = nlp(query_lower)
        
        for token in doc:
            if (token.pos_ in ["NOUN", "ADJ"] and 
                len(token.text) > 3 and 
                any(indicator in token.text for indicator in ["class", "eco", "biz", "prem", "first", "bus"])):
                class_related_words.append(token.text)
        
        # Check fuzzy matching against known class terms
        all_class_terms = []
        for keywords in class_mappings.values():
            all_class_terms.extend(keywords)
        
        for word in class_related_words:
            best_match, score, _ = process.extractOne(word, all_class_terms)
            if score > 75:  # High threshold for class matching
                for class_name, keywords in class_mappings.items():
                    if best_match in keywords:
                        return class_name
                        
    except Exception:
        pass
    
    # Strategy 5: Context-based inference
    # Look for price-related clues or luxury indicators
    context_clues = {
        "first": ["expensive", "costly", "luxury", "premium service", "champagne", "lie flat"],
        "business": ["work", "corporate", "meeting", "conference", "professional", "lounge access"],
        "premium_economy": ["upgrade", "extra legroom", "more space", "comfortable", "priority boarding"]
    }
    
    for class_name, clues in context_clues.items():
        for clue in clues:
            if clue in query_lower:
                # Only return if there's also some flight-related context
                flight_context = ["flight", "fly", "travel", "ticket", "book", "reserve"]
                if any(context in query_lower for context in flight_context):
                    return class_name
    
    # Strategy 6: Abbreviation detection
    abbreviation_map = {
        "f": "first",
        "j": "business", 
        "c": "business",
        "w": "premium_economy",
        "y": "economy"
    }
    
    # Look for single letter class codes
    single_letter_pattern = r'\b([fjcwy])\s+class\b'
    matches = re.findall(single_letter_pattern, query_lower)
    if matches:
        letter = matches[0].lower()
        if letter in abbreviation_map:
            return abbreviation_map[letter]
    
    # Default fallback - return economy
    return "economy"


def extract_passenger_count(query: str) -> Dict[str, int]:
    """
    Extract passenger count using Groq's fast LLM models
    
    Args:
        query (str): User query about flight booking
        
    Returns:
        Dict containing passenger counts
    """
    
    # Initialize Groq client
    try:
        client = Groq(
            api_key=os.environ.get('GROQ_API_KEY')
        )
    except Exception as e:
        # Fallback to default values if API fails
        print(f"Error initializing Groq client: {e}")
        return {
            'adults': 1,
            'children': 0,
            'infants': 0
        }
    
    # Create the prompt for passenger extraction
    prompt = f"""
Extract passenger counts from this travel query. Return ONLY a JSON object, no explanations.

Query: "{query}"

RULES:
- Adults: 18+ years (speaker, wife, husband, parents, friends, child, etc)
- Children: 2-17 years (kids, son, daughter, child, etc)  
- Infants: 0-2 years (baby, infant, newborn, etc)
- "I with wife" = 2 adults total
- "our 3 children" = 3 children
- Age always overrides labels. "2 20 year old children" = 2 adults (not children)
- At least 1 adult if children/infants present

EXAMPLES:
Query: "I want to travel with my wife and our 3 children"
{{"adults": 2, "children": 3, "infants": 0}}

Query: "family of 4"  
{{"adults": 2, "children": 2, "infants": 0}}

Query: "2 adults and 1 baby"
{{"adults": 2, "children": 0, "infants": 1}}

Now extract from: "{query}"

Return only JSON:
"""

    try:
        # Use Groq's fastest model (llama3-8b-8192 or mixtral-8x7b-32768)
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model="meta-llama/llama-4-maverick-17b-128e-instruct",  # Fast and efficient model
            temperature=0.1,  # Low temperature for consistent results
            max_tokens=150,   # Limit response length
            top_p=0.9
        )
        
        response_text = chat_completion.choices[0].message.content.strip()
        print(f"Groq raw response: {response_text}")
        
        # Extract and clean JSON
        passenger_data = extract_and_clean_json(response_text)
        
        # Validate and sanitize the response
        adults = max(0, int(passenger_data.get('adults', 0)))
        children = max(0, int(passenger_data.get('children', 0)))
        infants = max(0, int(passenger_data.get('infants', 0)))
        
        # Business logic validation
        adults, children, infants = validate_passenger_counts(adults, children, infants)
        
        return {
            'adults': adults,
            'children': children,
            'infants': infants
        }

    except Exception as e:
        print(f"Error with Groq API: {e}")
        return fallback_extraction(query)


def extract_and_clean_json(response_text: str) -> dict:
    """
    Extract and clean JSON object from LLM response, handling extra text and malformed JSON
    """
    try:
        # Step 1: Remove markdown code blocks
        clean_text = re.sub(r'```(?:json)?\s*|\s*```', '', response_text, flags=re.IGNORECASE).strip()
        
        # Step 2: Extract ONLY the JSON object (ignore explanation text)
        # Look for the first complete JSON object
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        json_match = re.search(json_pattern, clean_text, re.DOTALL)
        
        if not json_match:
            # Fallback: try to find any JSON-like structure
            json_match = re.search(r'\{.*?\}', clean_text, re.DOTALL)
        
        if not json_match:
            raise ValueError("No JSON object found in response")
        
        json_str = json_match.group().strip()
        
        # Step 3: Clean and fix common JSON issues
        json_str = json_str.replace("'", '"')  # Single to double quotes
        
        # Fix unquoted keys (but be careful not to quote already quoted keys)
        json_str = re.sub(r'(?<!")(\b\w+)(?=\s*:)', r'"\1"', json_str)
        
        # Remove trailing commas
        json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
        
        # Remove any trailing text after the closing brace
        brace_count = 0
        end_index = 0
        for i, char in enumerate(json_str):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_index = i + 1
                    break
        
        if end_index > 0:
            json_str = json_str[:end_index]
        
        # Step 4: Parse the cleaned JSON
        return json.loads(json_str)
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
        print(f"🔍 Attempted to parse: {json_str}")
        print(f"🔍 Full response: {response_text}")
        raise
    except Exception as e:
        print(f"❌ JSON extraction failed: {e}")
        print(f"🔍 Raw response: {response_text}")
        raise


def validate_passenger_counts(adults: int, children: int, infants: int) -> tuple:
    """Apply business logic validation to passenger counts"""
    
    # Ensure at least 1 adult if children/infants present but no adults
    if adults == 0 and (children > 0 or infants > 0):
        adults = 1
        print("⚠️  Added 1 adult to accompany children/infants")
    
    # Ensure at least 1 passenger total
    if adults == 0 and children == 0 and infants == 0:
        adults = 1
        print("⚠️  Defaulted to 1 adult (no passengers specified)")
    
    return adults, children, infants


def fallback_extraction(query: str) -> Dict[str, int]:
    """
    Enhanced fallback extraction using regex patterns
    """
    query_lower = query.lower()
    adults = 0
    children = 0
    infants = 0
    
    print("🔄 Using fallback extraction...")
    
    # Step 1: Handle explicit numbers with passenger types
    adult_patterns = [
        r'(\d+)\s+adults?',
        r'(\d+)\s+(?:people|persons?|passengers?)',
    ]
    
    child_patterns = [
        r'(\d+)\s+(?:children?|kids?|child)',
        r'our\s+(\d+)\s+children',
    ]
    
    infant_patterns = [
        r'(\d+)\s+(?:infants?|babies|baby|newborns?)',
        r'(\d+)\s+(?:month|months?)\s+(?:old|baby)',
    ]
    
    # Extract explicit counts
    for pattern in adult_patterns:
        match = re.search(pattern, query_lower)
        if match:
            adults = max(adults, int(match.group(1)))
    
    for pattern in child_patterns:
        match = re.search(pattern, query_lower)
        if match:
            children = max(children, int(match.group(1)))
    
    for pattern in infant_patterns:
        match = re.search(pattern, query_lower)
        if match:
            infants = max(infants, int(match.group(1)))
    
    # Step 2: Handle relationship-based counts
    if re.search(r'with\s+(?:my\s+)?(?:wife|husband|partner)', query_lower):
        adults = max(adults, 2)  # Speaker + spouse
    
    # Step 3: Handle family counts
    family_match = re.search(r'family of (\d+)', query_lower)
    if family_match:
        total = int(family_match.group(1))
        if adults == 0 and children == 0:  # If no specific counts found
            adults = min(2, total)  # Assume max 2 adults
            children = max(0, total - adults)
    
    # Step 4: Handle age-specific mentions
    age_matches = re.findall(r'(\d+)?\s*(\d+)\s*(?:yr|year)s?\s+old', query_lower)
    for count_str, age_str in age_matches:
        try:
            count = int(count_str) if count_str else 1
            age = int(age_str)
            
            if 0 <= age <= 2:
                infants += count
            elif 3 <= age <= 17:
                children += count
            else:
                adults += count
        except ValueError:
            continue
    
    # Step 5: Handle month-based age for infants
    month_matches = re.findall(r'(?:one|1|\d+)\s+(?:\d+\s+)?months?\s+(?:old|baby)', query_lower)
    if month_matches:
        infants += len(month_matches)
    
    # Step 6: Handle special phrases
    if 'few people' in query_lower:
        adults = max(adults, 3)
    elif 'several people' in query_lower:
        adults = max(adults, 4)
    
    # Step 7: Apply validation
    adults, children, infants = validate_passenger_counts(adults, children, infants)
    
    print(f"🔧 Fallback result: {adults} adults, {children} children, {infants} infants")
    return {
        'adults': adults,
        'children': children,
        'infants': infants
    }


# Alternative function using Groq's Mixtral model for complex cases
def extract_passenger_count_mixtral(query: str) -> Dict[str, int]:
    """
    Use Mixtral model for more complex passenger extraction
    """
    try:
        client = Groq(api_key="your_groq_api_key_here")
        
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at extracting passenger information from travel queries. Always return valid JSON with adults, children, and infants counts."
                },
                {
                    "role": "user",
                    "content": f"""
Extract passenger counts from: "{query}"

Rules:
- Adults: 18+ years
- Children: 2-17 years  
- Infants: 0-2 years
- Age numbers override categories
- "fam of 2 10 yr olds" = 2 children, not adults
- Include speaker in count when mentioned

Return JSON: {{"adults": X, "children": Y, "infants": Z}}
"""
                }
            ],
            model="mixtral-8x7b-32768",  # More capable model
            temperature=0,
            max_tokens=100
        )
        
        response_text = chat_completion.choices[0].message.content.strip()
        passenger_data = extract_and_clean_json(response_text)
        
        adults = max(0, int(passenger_data.get('adults', 0)))
        children = max(0, int(passenger_data.get('children', 0)))
        infants = max(0, int(passenger_data.get('infants', 0)))
        
        adults, children, infants = validate_passenger_counts(adults, children, infants)
        
        return {
            'adults': adults,
            'children': children,
            'infants': infants
        }
        
    except Exception as e:
        print(f"Mixtral extraction failed: {e}")
        return fallback_extraction(query)


def validate_passenger_counts(adults: int, children: int, infants: int) -> tuple:
    """Apply business logic validation to passenger counts"""
    
    # Ensure at least 1 adult if children/infants present but no adults
    if adults == 0 and (children > 0 or infants > 0):
        adults = 1
        print("⚠️  Added 1 adult to accompany children/infants")
    
    # Ensure at least 1 passenger total
    if adults == 0 and children == 0 and infants == 0:
        adults = 1
        print("⚠️  Defaulted to 1 adult (no passengers specified)")
    
    return adults, children, infants


def fallback_extraction(query: str) -> Dict[str, int]:
    """
    Enhanced fallback extraction using regex patterns
    """
    query_lower = query.lower()
    adults = 0
    children = 0
    infants = 0
    
    print("🔄 Using fallback extraction...")
    
    # Enhanced regex patterns
    patterns = {
        'adults': [
            r'(\d+)\s+adults?',
            r'(\d+)\s+(?:people|persons?)',
            r'with\s+(?:my\s+)?(?:wife|husband|partner)',  # +1 for speaker +1 for partner
        ],
        'children': [
            r'(\d+)\s+(?:children?|kids?|child)',
            r'(\d+)\s+(?:\d+\s*(?:yr|year|month)s?\s+old)',  # Age-based
            r'(\d+)\s+(?:10|11|12|13|14|15|16|17)\s*(?:yr|year)',
        ],
        'infants': [
            r'(\d+)\s+(?:infants?|babies|baby|newborns?)',
            r'(\d+)\s+(?:\d+\s*months?\s+old)',
            r'(\d+)\s+(?:0|1|2)\s*(?:yr|year)',
        ]
    }
    
    # Extract using patterns
    for category, pattern_list in patterns.items():
        for pattern in pattern_list:
            matches = re.findall(pattern, query_lower)
            if matches:
                if category == 'adults':
                    adults = max(adults, int(matches[0]))
                elif category == 'children':
                    children = max(children, int(matches[0]))
                elif category == 'infants':
                    infants = max(infants, int(matches[0]))
    
    # Handle special cases
    if 'with wife' in query_lower or 'with husband' in query_lower:
        adults = max(adults, 2)  # Speaker + spouse
    
    if 'family of' in query_lower:
        family_match = re.search(r'family of (\d+)', query_lower)
        if family_match:
            total = int(family_match.group(1))
            if adults == 0:  # If no adults specified yet
                adults = min(2, total)  # Assume 2 adults max
                children = max(0, total - adults)
    
    # Age-specific extraction for the problematic case
    age_matches = re.findall(r'(\d+)\s+(\d+)\s*(?:yr|year)s?\s+old', query_lower)
    for count, age in age_matches:
        count = int(count)
        age = int(age)
        if 0 <= age <= 2:
            infants += count
        elif 3 <= age <= 17:
            children += count
        else:
            adults += count
    
    # Month-based age for infants
    month_matches = re.findall(r'(\d+)\s*months?\s+(?:old|baby)', query_lower)
    for match in month_matches:
        if 'one' in query_lower or '1' in match:
            infants += 1
    
    # Apply validation
    adults, children, infants = validate_passenger_counts(adults, children, infants)
    
    print(f"🔧 Fallback result: {adults} adults, {children} children, {infants} infants")
    return {
        'adults': adults,
        'children': children,
        'infants': infants
    }


# Alternative function using Groq's Mixtral model for complex cases
def extract_passenger_count_mixtral(query: str) -> Dict[str, int]:
    """
    Use Mixtral model for more complex passenger extraction
    """
    try:
        client = Groq(api_key="your_groq_api_key_here")
        
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at extracting passenger information from travel queries. Always return valid JSON with adults, children, and infants counts."
                },
                {
                    "role": "user",
                    "content": f"""
Extract passenger counts from: "{query}"

Rules:
- Adults: 18+ years
- Children: 2-17 years  
- Infants: 0-2 years
- Age numbers override categories
- "fam of 2 10 yr olds" = 2 children, not adults
- Include speaker in count when mentioned

Return JSON: {{"adults": X, "children": Y, "infants": Z}}
"""
                }
            ],
            model="mixtral-8x7b-32768",  # More capable model
            temperature=0,
            max_tokens=100
        )
        
        response_text = chat_completion.choices[0].message.content.strip()
        passenger_data = extract_and_clean_json(response_text)
        
        adults = max(0, int(passenger_data.get('adults', 0)))
        children = max(0, int(passenger_data.get('children', 0)))
        infants = max(0, int(passenger_data.get('infants', 0)))
        
        adults, children, infants = validate_passenger_counts(adults, children, infants)
        
        return {
            'adults': adults,
            'children': children,
            'infants': infants
        }
        
    except Exception as e:
        print(f"Mixtral extraction failed: {e}")
        return fallback_extraction(query)


def extract_dates(text, flight_type=None):
    """
    FIXED: Date extraction function that properly handles age mentions
    """
    original_text = text.lower()
    original_text = correct_spelling(original_text)
    today = datetime.now()

    # FIXED: Remove age mentions before parsing dates to prevent confusion
    # Remove patterns like "10 year old", "1 year old", etc.
    text_cleaned = re.sub(r'\b\d+\s+years?\s+old\b', '', original_text)
    text_cleaned = re.sub(r'\b\d+\s+year\s+old\b', '', text_cleaned)
    
    # ADDED: Remove month age mentions like "15 month", "18 months old", etc.
    text_cleaned = re.sub(r'\b\d+\s+months?\s+(?:old)?\b', '', text_cleaned)
    text_cleaned = re.sub(r'\b\d+\s+month\s+(?:old)?\b', '', text_cleaned)
    
    # Special date mapping
    special_date_map = {
        "day after tomorrow": (today + timedelta(days=2)).strftime("%Y-%m-%d"),
        "tomorrow": (today + timedelta(days=1)).strftime("%Y-%m-%d"),
        "today": today.strftime("%Y-%m-%d"),
    }

    # Fix common date format issues
    text_fixed = re.sub(r'(\d+)(st|nd|rd|th)\s+of\s+', r'\1\2 ', text_cleaned)
    normalized_text = text_fixed.strip().lower()
    dates = []

    # Auto-detect flight type if not provided
    if flight_type is None:
        flight_type = extract_flight_type(text)

    # ---- RETURN FLIGHT HANDLING ---- #
    if flight_type == "return":
        # Strategy 1: Between X and Y
        between_pattern = r'between\s+([^0-9]+?)\s+and\s+([^0-9]+?)(?:\s|$|,|\.)'
        between_matches = re.findall(between_pattern, normalized_text, re.IGNORECASE)

        if between_matches:
            for date1_text, date2_text in between_matches:
                for label, date_str in zip(['departure', 'return'], [date1_text, date2_text]):
                    date_str = re.sub(r'\b(of|the)\b', '', date_str.strip().lower())
                    if date_str in special_date_map:
                        dates.append((label, special_date_map[date_str]))
                    else:
                        try:
                            cal = parsedatetime.Calendar()
                            time_struct, parse_status = cal.parse(date_str)
                            if parse_status >= 1:
                                dates.append((label, datetime(*time_struct[:6]).strftime("%Y-%m-%d")))
                        except:
                            pass
            if len(dates) >= 2:
                return (
                    next((d for l, d in dates if l == 'departure'), None),
                    next((d for l, d in dates if l == 'return'), None)
                )

        # Strategy 2: Date pair patterns (excluding age patterns)
        date_pair_patterns = [
            r'\b(today|tomorrow|day after tomorrow)\b.*?\b(?:and\s+(?:then\s+)?|then\s+)\b.*?\b(today|tomorrow|day after tomorrow)\b',
            r'\bon\s+([^,]+?)\s+and\s+(?:then\s+)?(?:on\s+)?([^,]+?)(?:\s|$|,)',
            r'\b(\d+(?:st|nd|rd|th)?(?:\s+\w+)?)\s+(?:and\s+(?:then\s+)?|then\s+|to\s+)(?:on\s+)?(\d+(?:st|nd|rd|th)?(?:\s+\w+)?)(?:\s|$|,)',
        ]

        for pattern in date_pair_patterns:
            matches = re.findall(pattern, normalized_text)
            for match in matches:
                if len(match) == 2:
                    # Skip if this looks like an age pattern
                    if any(re.search(r'\d+.*?(year|old|month)', m) for m in match):
                        continue
                        
                    for label, date_str in zip(['departure', 'return'], match):
                        date_str = date_str.strip().lower()
                        if date_str in special_date_map:
                            dates.append((label, special_date_map[date_str]))
                        else:
                            try:
                                cal = parsedatetime.Calendar()
                                time_struct, parse_status = cal.parse(date_str)
                                if parse_status >= 1:
                                    parsed_date = datetime(*time_struct[:6])
                                    # FIXED: Ensure parsed date is not in the far future due to age confusion
                                    if parsed_date.year <= today.year + 2:
                                        dates.append((label, parsed_date.strftime("%Y-%m-%d")))
                            except:
                                pass
                if len(dates) >= 2:
                    return (
                        next((d for l, d in dates if l == 'departure'), None),
                        next((d for l, d in dates if l == 'return'), None)
                    )

        # Strategy 3 & 4: Return and Departure Indicators
        indicator_patterns = [
            ("return", [
                r'(?:come\s+back|return|back).*?(?:on\s+|must\s+on\s+|by\s+)([^,\.]+)',
                r'(?:must\s+on|need\s+to\s+(?:come\s+)?back.*?on)\s+([^,\.]+)',
                r'(?:return.*?on|back.*?on)\s+([^,\.]+)'
            ]),
            ("departure", [
                r'(?:depart|leave|going|travel).*?(?:on\s+)([^,\.]+)',
                r'(?:on\s+)([^,\.]+).*?(?:going|travel|depart|leave)'
            ])
        ]

        for label, patterns in indicator_patterns:
            for pattern in patterns:
                matches = re.findall(pattern, normalized_text)
                for match in matches:
                    # Skip age-related matches
                    if re.search(r'\d+.*?(year|old|month)', match):
                        continue
                        
                    date_str = re.sub(r'\b(of|the)\b', '', match.strip().lower())
                    if date_str in special_date_map:
                        dates.append((label, special_date_map[date_str]))
                    else:
                        try:
                            cal = parsedatetime.Calendar()
                            time_struct, parse_status = cal.parse(date_str)
                            if parse_status >= 1:
                                parsed_date = datetime(*time_struct[:6])
                                # FIXED: Ensure parsed date is reasonable
                                if parsed_date.year <= today.year + 2:
                                    dates.append((label, parsed_date.strftime("%Y-%m-%d")))
                        except:
                            pass

        # Strategy 5: Generic fallback special date match
        if not dates:
            sorted_specials = sorted(special_date_map.keys(), key=len, reverse=True)
            for word in sorted_specials:
                if word in normalized_text:
                    context_match = any(phrase in normalized_text for phrase in [
                        f"come back {word}", f"return {word}", f"back {word}", f"must {word}"
                    ])
                    label = 'return' if context_match else 'departure'
                    dates.append((label, special_date_map[word]))

        # Final return for return flight
        departure = next((d for l, d in dates if l == 'departure'), None)
        return_date = next((d for l, d in dates if l == 'return'), None)
        if departure or return_date:
            return departure, return_date
        else:
            # FIXED: Fallback parsing with age filtering
            try:
                cal = parsedatetime.Calendar()
                time_struct, parse_status = cal.parse(normalized_text)
                if parse_status >= 1:
                    departure_date = datetime(*time_struct[:6])
                    # FIXED: Check if the date is reasonable (not far future due to age)
                    if departure_date.year <= today.year + 2:
                        return departure_date.strftime("%Y-%m-%d"), None
            except:
                pass
            return None, None

    # ---- ONE-WAY FLIGHT HANDLING ---- #
    else:
        # Check special dates first
        sorted_specials = sorted(special_date_map.keys(), key=len, reverse=True)
        for word in sorted_specials:
            if word in normalized_text:
                return special_date_map[word]

        # FIXED: Parse with age filtering - also look for relative date patterns
        relative_date_patterns = [
            r'\bnext\s+(\w+day)\b',  # next thursday, next monday, etc.
            r'\bthis\s+(\w+day)\b',  # this friday, this saturday, etc.
            r'\b(\w+day)\s+next\b',  # thursday next, friday next, etc.
        ]
        
        for pattern in relative_date_patterns:
            matches = re.findall(pattern, normalized_text)
            for match in matches:
                try:
                    cal = parsedatetime.Calendar()
                    if isinstance(match, tuple):
                        date_phrase = ' '.join(match)
                    else:
                        date_phrase = f"next {match}" if pattern.startswith(r'\b(\w+day)') else f"next {match}"
                    
                    time_struct, parse_status = cal.parse(date_phrase)
                    if parse_status >= 1:
                        parsed_date = datetime(*time_struct[:6])
                        if parsed_date.year <= today.year + 2:
                            return parsed_date.strftime("%Y-%m-%d")
                except:
                    pass

        # FIXED: Parse with age filtering
        try:
            cal = parsedatetime.Calendar()
            time_struct, parse_status = cal.parse(normalized_text)
            if parse_status >= 1:
                parsed_date = datetime(*time_struct[:6])
                # FIXED: Ensure the parsed date is reasonable (not affected by age mentions)
                if parsed_date.year <= today.year + 2:
                    return parsed_date.strftime("%Y-%m-%d")
        except:
            pass

        return None


# Additional helper function to validate airline extraction
def validate_airline_extraction(query, extracted_airline):
    """
    Validate that the extracted airline makes sense in the context.
    Returns True if valid, False if likely a false positive.
    """
    if not extracted_airline:
        return True  # None is always valid
    
    query_lower = query.lower()
    
    # Check if query explicitly mentions flights or airlines
    flight_indicators = ['flight', 'airline', 'airways', 'fly with', 'book with', 
                        'travel with', 'prefer', 'carrier']
    
    has_flight_context = any(indicator in query_lower for indicator in flight_indicators)
    
    # If no flight context and it's just a route query, likely false positive
    route_only_patterns = [
        r'travel from .+ to .+$',
        r'go from .+ to .+$',
        r'.+ to .+$'
    ]
    
    is_route_only = any(re.search(pattern, query_lower) for pattern in route_only_patterns)
    
    if is_route_only and not has_flight_context:
        return False
        
    return True


def extract_travel_info(query):
    """
    Main function to extract all travel information from a query.
    
    Args:
        query (str): User's travel query
    
    Returns:
        dict: Dictionary containing all extracted travel information
    """
    result = {}
    
    # Extract cities
    source, destination = extract_cities(query)
    
    # Ensure source and destination are different
    if source and destination and source == destination:
        destination = None
    
    if source:
        result["source"] = source
    else:
        result["source"] = None
    if destination:
        result["destination"] = destination
    else:
        result["destination"] = None
    
    # Extract flight type
    flight_type = extract_flight_type(query)
    result["flight_type"] = flight_type
    
    # Extract flight class
    flight_class = extract_flight_class(query)
    result["flight_class"] = flight_class
    
    # Extract dates based on flight type
    if flight_type == "return":
        departure_date, return_date = extract_dates(query, flight_type)
        if departure_date:
            result["departure_date"] = departure_date
        else:
            result["departure_date"] = None
        if return_date:
            result["return_date"] = return_date
        else:
            result["return_date"] = None
    else:
        date = extract_dates(query, flight_type)
        if date:
            result["departure_date"] = date
        else:
            result["departure_date"] = None
    
    # Extract passenger count
    try:
        passenger_counts = extract_passenger_count(query)
        result["passengers"] = passenger_counts
        
        # Also add total passenger count for convenience
        total_passengers = passenger_counts["adults"] + passenger_counts["children"] + passenger_counts["infants"]
        result["total_passengers"] = total_passengers
    except Exception as e:
        print(f"Warning: Passenger count extraction failed: {e}")
        # Fallback to default
        result["passengers"] = {"adults": 1, "children": 0, "infants": 0}
        result["total_passengers"] = 1
    print("debug", result)
    return result

# Enhanced command-line interface
if __name__ == "__main__":
    while True:
        query = input("Enter your travel query: ").strip()
        if query.lower() in ["exit", "quit"]:
            print("Goodbye!")
            break
        if not query:
            continue
        try:
            result = extract_travel_info(query)
            print(result)
        except Exception as e:
            print(f"Error processing query: {e}")