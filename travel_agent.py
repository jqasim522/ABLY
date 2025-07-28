import json
import requests
from datetime import datetime
from extract_parameters import extract_travel_info, extract_flight_class, extract_flight_type, extract_cities, extract_airline
import google.generativeai as genai
from dotenv import load_dotenv
import os
import asyncio
from ably import AblyRealtime
from ably_config import ABLY_API_KEY

# Load environment variables
load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

class TravelAgent:
    def __init__(self):
        self.auth_url = "https://bookmesky.com/partner/api/auth/token"
        self.api_url = "https://bookmesky.com/air/api/search"
        self.username = os.getenv("BOOKME_SKY_USERNAME")
        self.password = os.getenv("BOOKME_SKY_PASSWORD")
        self.api_token = self.get_api_token()  # 🔑 get token dynamically

        self.api_headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_token}'
        }

        self.model = genai.GenerativeModel('gemini-pro')

    def get_api_token(self):
        """Fetch API token using credentials from environment variables"""
        try:
            payload = {
                "username": self.username,
                "password": self.password
            }
            response = requests.post(
                self.auth_url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=10
            )

            if response.ok:
                token = response.json().get("Token")  # Adjust based on actual response structure
                if token:
                    return token
                else:
                    raise Exception("Token not found in API response.")
            else:
                raise Exception(f"Auth failed: {response.status_code} - {response.text}")

        except Exception as e:
            print(f"🔥 Error fetching token: {str(e)}")
            raise

        
    def process_initial_query(self, query):
        """Process the initial travel query and extract all possible information"""
        try:
            extracted_info = extract_travel_info(query)
            return extracted_info
        except Exception as e:
            return {"error": f"Failed to process query: {str(e)}"}
    
    def identify_missing_attributes(self, extracted_info):
        """Identify which required attributes are missing"""
        missing = []
        
        # Check required fields
        if not extracted_info.get("source"):
            missing.append("source_city")
        if not extracted_info.get("destination"):
            missing.append("destination_city")
        if not extracted_info.get("departure_date"):
            missing.append("departure_date")
        if not extracted_info.get("flight_class"):
            missing.append("flight_class")
        if not extracted_info.get("flight_type"):
            missing.append("flight_type")
        
        # Check return date if flight type is return
        if extracted_info.get("flight_type") == "return" and not extracted_info.get("return_date"):
            missing.append("return_date")
            
        return missing
    
    def get_missing_info_prompts(self, missing_attributes):
        """Generate user-friendly prompts for missing information"""
        prompts = {
            "source_city": "Which city are you departing from?",
            "destination_city": "Which city are you traveling to?",
            "departure_date": "What is your departure date? (e.g., tomorrow, 15th December, 2024-12-15)",
            "return_date": "What is your return date? (e.g., next Friday, 20th December, 2024-12-20)",
            "flight_class": "Which class would you prefer? (economy, business, first, premium_economy)",
            "flight_type": "Is this a one-way or return trip?"
        }
        
        return [prompts.get(attr, f"Please provide {attr}") for attr in missing_attributes]
    
    def process_missing_attribute(self, attribute, user_input, current_info):
        """Process user input for a specific missing attribute"""
        try:
            if attribute == "flight_class":
                result = extract_flight_class(user_input)
                current_info["flight_class"] = result
                
            elif attribute == "flight_type":
                result = extract_flight_type(user_input)
                current_info["flight_type"] = result
                
            elif attribute in ["source_city", "destination_city"]:
                source, destination = extract_cities(user_input)
                if attribute == "source_city" and source:
                    current_info["source"] = source
                elif attribute == "destination_city" and destination:
                    current_info["destination"] = destination
                elif attribute == "source_city" and destination:  # User might have said destination when asked for source
                    current_info["source"] = destination
                elif attribute == "destination_city" and source:  # User might have said source when asked for destination
                    current_info["destination"] = source
                    
            elif attribute in ["departure_date", "return_date"]:
                from extract_parameters import extract_dates
                if attribute == "departure_date":
                    date_result = extract_dates(user_input, "one_way")
                    if date_result:
                        current_info["departure_date"] = date_result
                else:  # return_date
                    date_result = extract_dates(user_input, "one_way")
                    if date_result:
                        current_info["return_date"] = date_result
                        
            return current_info
            
        except Exception as e:
            print(f"Error processing {attribute}: {str(e)}")
            return current_info
    
    def validate_and_correct_info(self, info):
        """Validate and correct the extracted information using the extraction functions"""
        corrected_info = info.copy()
        
        try:
            # Re-validate cities to ensure IATA codes are correct
            if info.get("source") or info.get("destination"):
                query_text = f"from {info.get('source', '')} to {info.get('destination', '')}"
                source, destination = extract_cities(query_text)
                if source:
                    corrected_info["source"] = source
                if destination:
                    corrected_info["destination"] = destination
            
            # Re-validate airline if present
            if info.get("content_provider"):
                airline_query = f"flying with {info.get('content_provider')}"
                airline = extract_airline(airline_query)
                if airline:
                    corrected_info["content_provider"] = airline
                    
        except Exception as e:
            print(f"Error during validation: {str(e)}")
            
        return corrected_info
    
    def format_api_payload(self, info):
        """Format the extracted information into API payload"""
        try:
            # Build locations
            locations = []
            if info.get("source"):
                locations.append({"IATA": info["source"], "Type": "airport"})
            if info.get("destination"):
                locations.append({"IATA": info["destination"], "Type": "airport"})
            
            # Build traveling dates
            traveling_dates = []
            if info.get("departure_date"):
                traveling_dates.append(info["departure_date"])
            if info.get("return_date"):
                traveling_dates.append(info["return_date"])
            
            # Build travelers
            passengers = info.get("passengers", {"adults": 1, "children": 0, "infants": 0})
            travelers = []
            if passengers["adults"] > 0:
                travelers.append({"Type": "adult", "Count": passengers["adults"]})
            if passengers["children"] > 0:
                travelers.append({"Type": "child", "Count": passengers["children"]})
            if passengers["infants"] > 0:
                travelers.append({"Type": "infant", "Count": passengers["infants"]})
            
            # Build payload
            payload = {
                "Locations": locations,
                "Currency": "PKR",
                "TravelClass": info.get("flight_class", "economy"),
                "TripType": info.get("flight_type", "one_way"),
                "TravelingDates": traveling_dates,
                "Travelers": travelers
            }
            
            # Add content provider if specified
            if info.get("content_provider"):
                payload["ContentProvider"] = info["content_provider"]
                
            return payload
            
        except Exception as e:
            return {"error": f"Failed to format payload: {str(e)}"}
    
    def search_flights(self, payload):
        """Make API call to search for flights"""
        try:
            response = requests.post(
                self.api_url,
                headers=self.api_headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "error": f"API request failed with status {response.status_code}",
                    "message": response.text
                }
                
        except requests.exceptions.RequestException as e:
            return {"error": f"Network error: {str(e)}"}
        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}"}
    
    def generate_llm_response(self, flight_data, user_query, search_params):
        """Generate a natural language response using LLM"""
        try:
            # Prepare context for LLM
            context = f"""
            User Query: {user_query}
            
            Search Parameters:
            - From: {search_params.get('Locations', [{}])[0].get('IATA', 'N/A')}
            - To: {search_params.get('Locations', [{}])[1].get('IATA', 'N/A') if len(search_params.get('Locations', [])) > 1 else 'N/A'}
            - Travel Class: {search_params.get('TravelClass', 'N/A')}
            - Trip Type: {search_params.get('TripType', 'N/A')}
            - Travel Dates: {', '.join(search_params.get('TravelingDates', []))}
            - Travelers: {search_params.get('Travelers', [])}
            
            Flight Search Results:
            {json.dumps(flight_data, indent=2)}
            
            Please provide a helpful, natural response about the flight search results. Include:
            1. A summary of the search
            2. Key flight options if available
            3. Prices and times if provided
            4. Any recommendations or important notes
            5. Be conversational and helpful
            
            If there are no results or an error, explain what might have gone wrong and suggest alternatives.
            """
            
            response = self.model.generate_content(context)
            return response.text
            
        except Exception as e:
            return f"I found flight information for your search, but had trouble formatting the response. Here's the raw data: {json.dumps(flight_data, indent=2)}"
    
    def process_full_request(self, query):
        """Process the complete travel request from start to finish"""
        # Step 1: Extract initial information
        extracted_info = self.process_initial_query(query)
        
        if "error" in extracted_info:
            return {"status": "error", "message": extracted_info["error"]}
        
        # Step 2: Check for missing attributes
        missing = self.identify_missing_attributes(extracted_info)
        
        if missing:
            return {
                "status": "missing_info",
                "extracted_info": extracted_info,
                "missing_attributes": missing,
                "prompts": self.get_missing_info_prompts(missing)
            }
        
        # Step 3: Validate and correct information (but don't make API call yet)
        corrected_info = self.validate_and_correct_info(extracted_info)
        
        return {
            "status": "ready_for_confirmation",
            "extracted_info": corrected_info
        }
    
    def execute_flight_search(self, confirmed_info):
        """Execute the flight search after user confirmation"""
        try:
            # Step 1: Format API payload
            payload = self.format_api_payload(confirmed_info)
            
            if "error" in payload:
                return {"status": "error", "message": payload["error"]}
            
            # Step 2: Search flights
            flight_results = self.search_flights(payload)
            
            # Step 3: Generate LLM response
            llm_response = self.generate_llm_response(flight_results, "confirmed flight search", payload)
            
            return {
                "status": "complete",
                "extracted_info": confirmed_info,
                "api_payload": payload,
                "flight_results": flight_results,
                "llm_response": llm_response
            }
            
        except Exception as e:
            return {"status": "error", "message": f"Search execution failed: {str(e)}"}

ABLY_CHANNEL = "travel-agent"
USER_EVENT = "user-query"
AGENT_EVENT = "agent-response"

async def ably_travel_agent():
    ably = AblyRealtime(ABLY_API_KEY)
    channel = ably.channels.get(ABLY_CHANNEL)
    agent = TravelAgent()

    async def handle_query(message):
        user_id = message.data.get("user_id")
        query = message.data.get("query")
        if not user_id or not query:
            return
        print(f"Received query from user {user_id}: {query}")
        start_time = datetime.now()
        result = agent.process_full_request(query)
        end_time = datetime.now()
        latency = round((end_time - start_time).total_seconds(), 2)
        result["latency"] = latency
        await channel.publish(
            AGENT_EVENT,
            {
                "user_id": user_id,
                "result": result,
                "latency": latency
            }
        )

    async def handle_missing_info(message):
        user_id = message.data.get("user_id")
        missing_attribute = message.data.get("missing_attribute")
        user_input = message.data.get("user_input")
        extracted_info = message.data.get("extracted_info")
        print(f"[DEBUG] Received user-missing-info event: user_id={user_id}, missing_attribute={missing_attribute}, user_input={user_input}, extracted_info={extracted_info}")
        if not user_id or not missing_attribute or not user_input or not extracted_info:
            print("[DEBUG] Missing required fields in user-missing-info event.")
            return
        start_time = datetime.now()
        updated_info = agent.process_missing_attribute(missing_attribute, user_input, extracted_info)
        missing = agent.identify_missing_attributes(updated_info)
        if missing:
            result = {
                "status": "missing_info",
                "extracted_info": updated_info,
                "missing_attributes": missing,
                "prompts": agent.get_missing_info_prompts(missing)
            }
        else:
            corrected_info = agent.validate_and_correct_info(updated_info)
            result = {
                "status": "ready_for_confirmation",
                "extracted_info": corrected_info
            }
        end_time = datetime.now()
        latency = round((end_time - start_time).total_seconds(), 2)
        result["latency"] = latency
        print(f"[DEBUG] Publishing agent-response for user-missing-info: user_id={user_id}, result={result}")
        await channel.publish(
            AGENT_EVENT,
            {
                "user_id": user_id,
                "result": result,
                "latency": latency
            }
        )

    async def handle_confirm_info(message):
        user_id = message.data.get("user_id")
        confirmed_info = message.data.get("confirmed_info")
        print(f"[DEBUG] Received user-confirm-info event: user_id={user_id}, confirmed_info={confirmed_info}")
        if not user_id or not confirmed_info:
            print("[DEBUG] Missing required fields in user-confirm-info event.")
            return
        start_time = datetime.now()
        result = agent.execute_flight_search(confirmed_info)
        end_time = datetime.now()
        latency = round((end_time - start_time).total_seconds(), 2)
        result["latency"] = latency
        print(f"[DEBUG] Publishing agent-response for user-confirm-info: user_id={user_id}, result={result}")
        await channel.publish(
            AGENT_EVENT,
            {
                "user_id": user_id,
                "result": result,
                "latency": latency
            }
        )

    await channel.subscribe(USER_EVENT, handle_query)
    await channel.subscribe("user-missing-info", handle_missing_info)
    await channel.subscribe("user-confirm-info", handle_confirm_info)
    print(f"TravelAgent listening on Ably channel '{ABLY_CHANNEL}' for events '{USER_EVENT}', 'user-missing-info', and 'user-confirm-info'")
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(ably_travel_agent())