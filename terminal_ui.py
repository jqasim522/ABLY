#!/usr/bin/env python3
"""
Conversational Travel Flight Search Assistant
A natural, chat-based interface for searching flights with AI
"""

import json
import sys
import os
import asyncio
from datetime import datetime
from typing import Dict, Optional, Any
import uuid
from ably import AblyRealtime
from ably_config import ABLY_API_KEY, CHANNEL_NAME, EVENTS

class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'
    
    @classmethod
    def disable(cls):
        """Disable colors for non-color terminals"""
        cls.HEADER = ''
        cls.BLUE = ''
        cls.CYAN = ''
        cls.GREEN = ''
        cls.YELLOW = ''
        cls.RED = ''
        cls.BOLD = ''
        cls.UNDERLINE = ''
        cls.END = ''

class ConversationalTravelTerminal:
    """Natural conversation-based travel agent interface"""
    
    def __init__(self):
        self.conversation_active = True
        self.awaiting_confirmation = False
        self.awaiting_modification = False
        self.search_completed = False
        self.confirmation_shown = False  # Track if confirmation was already shown
        
        # Ably specific attributes
        self.ably = None
        self.channel = None
        self.user_id = str(uuid.uuid4())
        self.connection_state = "initialized"
        self.last_heartbeat = datetime.now()
        
        self.response_event = asyncio.Event()
        self.last_response = None
        self.current_booking_info = {}
        
        # Check if terminal supports colors
        if not (hasattr(sys.stdout, "isatty") and sys.stdout.isatty()):
            Colors.disable()
            
    def _format_flight_results(self, results):
        """Format flight search results for display"""
        if not results:
            print("DEBUG: No results provided to format")
            return None
            
        try:
            formatted_parts = ["📋 Here are the flights I found for you:"]
            flights_added = 0
            
            # print(f"DEBUG: Formatting results of type: {type(results)}")
            
            # Handle the simplified flight results structure from server
            if isinstance(results, dict):
                # print(f"DEBUG: Results keys: {list(results.keys())}")
                
                # Check for simplified flights structure
                if 'flights' in results and isinstance(results['flights'], list):
                    flights = results['flights']
                    # print(f"DEBUG: Found {len(flights)} simplified flights")
                    
                    if flights:
                        total_flights = results.get('total_flights', len(flights))
                        successful_airlines = results.get('successful_airlines', 1)
                        
                        formatted_parts.append(f"\n🔍 Found {total_flights} flight options across {successful_airlines} airlines:")
                        
                        for i, flight in enumerate(flights, 1):
                            flight_info = self._format_simplified_flight(flight, i)
                            if flight_info:
                                formatted_parts.append(flight_info)
                                flights_added += 1
                            else:
                                print(f"DEBUG: Failed to format flight {i}")
                
                # Handle other possible structures (fallback)
                elif 'successful_results' in results:
                    print("DEBUG: Found 'successful_results' structure - using fallback")
                    return "✈️ Flight search completed successfully! I found several options but had trouble displaying them. Please try your search again."
                    
            # Handle list of flights (fallback)
            elif isinstance(results, list):
                print(f"DEBUG: Results is a list with {len(results)} items")
                formatted_parts.append(f"\n🔍 Found {len(results)} flight options:")
                
                for i, flight in enumerate(results[:5], 1):
                    flight_info = self._format_simplified_flight(flight, i)
                    if flight_info:
                        formatted_parts.append(flight_info)
                        flights_added += 1
                        
            # print(f"DEBUG: Successfully formatted {flights_added} flights")
            
            if flights_added > 0:
                formatted_parts.append(f"\n💡 Would you like more details about any of these flights or search with different criteria?")
                return "\n".join(formatted_parts)
            else:
                print("DEBUG: No flights were successfully formatted")
                return "✈️ Flight search completed but I couldn't display the results properly. Please try your search again."
                
        except Exception as e:
            print(f"ERROR: Exception in _format_flight_results: {e}")
            import traceback
            traceback.print_exc()
            return "✈️ Flight search was successful but I had trouble formatting the results. Please try again."

    def _format_simplified_flight(self, flight, flight_number):
        """Format a simplified flight entry from the server"""
        try:
            if not isinstance(flight, dict):
                print(f"DEBUG: Flight is not a dict: {type(flight)}")
                return None
            
            # print(f"DEBUG: Formatting simplified flight {flight_number} with keys: {list(flight.keys())}")
            
            # Extract data from simplified flight structure
            flight_no = flight.get('flight_number', 'N/A')
            airline = flight.get('airline', 'Unknown')
            departure_time = flight.get('departure_time', 'N/A')
            arrival_time = flight.get('arrival_time', 'N/A')
            price = flight.get('price', 'N/A')
            origin = flight.get('origin', '')
            destination = flight.get('destination', '')
            
            # Format price
            if isinstance(price, (int, float)) and price != 'N/A':
                price_str = f"PKR {price:,.0f}"
            else:
                price_str = "Price on request"
            
            # Build the formatted string
            header = f"  ✈️ Flight {flight_number}: {airline} {flight_no}"
            time_info = f"     🕒 {departure_time} → {arrival_time}"
            price_info = f"     💰 {price_str}"
            
            result_parts = [header, time_info, price_info]
            
            # Add route if available
            if origin and destination:
                route_info = f"     📍 {origin} → {destination}"
                result_parts.insert(1, route_info)
            
            # Add fare type if available
            if flight.get('fare_name'):
                fare_info = f"     🎫 {flight['fare_name']}"
                result_parts.append(fare_info)
            
            return "\n".join(result_parts)
            
        except Exception as e:
            print(f"ERROR: Exception in _format_simplified_flight: {e}")
            print(f"DEBUG: Flight data was: {flight}")
            return None

    def _format_single_flight(self, flight, flight_number=None):
        """Format a single flight entry with better error handling and data extraction"""
        try:
            if not isinstance(flight, dict):
                print(f"DEBUG: Flight is not a dict: {type(flight)}")
                return None
            
            print(f"DEBUG: Formatting flight with keys: {list(flight.keys())}")
            
            # Initialize variables
            flight_no = 'N/A'
            departure_time = 'N/A'
            arrival_time = 'N/A'
            price = 'N/A'
            airline = 'N/A'
            route = ''
            
            # Handle BookMeSky API Itinerary structure
            if 'Segments' in flight:
                segments = flight.get('Segments', [])
                if segments:
                    first_segment = segments[0]
                    
                    # Extract flight details from segment
                    operating_carrier = first_segment.get('OperatingCarrier', {})
                    airline = operating_carrier.get('name', operating_carrier.get('iata', 'Unknown'))
                    flight_no = f"{operating_carrier.get('iata', '')}-{first_segment.get('FlightNumber', '')}"
                    
                    # Extract times
                    departure_time = self._format_api_time(first_segment.get('DepartureAt', ''))
                    arrival_time = self._format_api_time(first_segment.get('ArrivalAt', ''))
                    
                    # Extract route
                    from_airport = first_segment.get('From', {})
                    to_airport = first_segment.get('To', {})
                    route = f"{from_airport.get('iata', '')} → {to_airport.get('iata', '')}"
                
                # Extract fare information from parent flight
                fares = flight.get('Fares', [])
                if fares:
                    # Get the cheapest fare
                    cheapest_fare = min(fares, key=lambda x: x.get('ChargedTotalPrice', 999999))
                    price = cheapest_fare.get('ChargedTotalPrice', 'N/A')
                    if isinstance(price, (int, float)):
                        price = f"PKR {price:,.0f}"
            
            # Handle aggregated flight structure (from your agent's processing)
            else:
                # Try multiple field names for each piece of data
                flight_no = (flight.get('flight_number') or 
                            flight.get('FlightNumber') or 
                            flight.get('flightNumber') or 
                            flight.get('number') or 'N/A')
                
                departure_time = (flight.get('departure_time') or 
                                flight.get('DepartureTime') or 
                                flight.get('departureTime') or 
                                flight.get('departure') or 'N/A')
                
                arrival_time = (flight.get('arrival_time') or 
                            flight.get('ArrivalTime') or 
                            flight.get('arrivalTime') or 
                            flight.get('arrival') or 'N/A')
                
                # Try multiple price field names
                price = (flight.get('price') or 
                        flight.get('Price') or 
                        flight.get('fare') or 
                        flight.get('Fare') or 
                        flight.get('total_fare') or 
                        flight.get('Total_Fare') or 
                        flight.get('ChargedTotalPrice') or 
                        flight.get('totalPrice') or 
                        flight.get('cost') or 'N/A')
                
                airline = (flight.get('airline') or 
                        flight.get('Airline') or 
                        flight.get('carrier') or 
                        flight.get('source_airline') or 'N/A')
                
                # Build route if available
                origin = flight.get('origin') or flight.get('from') or flight.get('source')
                destination = flight.get('destination') or flight.get('to') or flight.get('dest')
                if origin and destination:
                    route = f"{origin} → {destination}"
            
            # Format price
            if isinstance(price, (int, float)) and price != 'N/A':
                price = f"PKR {price:,.0f}"
            elif price == 'N/A' or not price:
                price = "Price on request"
            
            # Build the formatted string
            if flight_number:
                header = f"  ✈️ Flight {flight_number}: {airline} {flight_no}"
            else:
                header = f"  ✈️ {airline} {flight_no}"
            
            time_info = f"     🕒 {departure_time} → {arrival_time}"
            price_info = f"     💰 {price}"
            
            result_parts = [header, time_info, price_info]
            
            # Add route if available and not redundant
            if route and route not in header:
                result_parts.insert(1, f"     📍 {route}")
            
            return "\n".join(result_parts)
            
        except Exception as e:
            print(f"ERROR: Exception in _format_single_flight: {e}")
            print(f"DEBUG: Flight data was: {flight}")
            return None
    

    def _format_api_time(self, datetime_str):
        """Format API datetime string to HH:MM format"""
        try:
            if datetime_str:
                # Handle ISO format: 2025-08-04T17:30:00+05:00
                from datetime import datetime
                if 'T' in datetime_str:
                    # Remove timezone info for parsing if present
                    clean_time = datetime_str.split('+')[0].split('-')[0] if '+' in datetime_str else datetime_str
                    if clean_time.count('-') >= 2:  # Full datetime
                        dt = datetime.fromisoformat(clean_time.replace('Z', ''))
                        return dt.strftime('%H:%M')
                    else:  # Just time part
                        time_part = datetime_str.split('T')[1].split('+')[0].split('Z')[0]
                        return time_part[:5]  # HH:MM
                elif ':' in datetime_str:
                    # Already in time format
                    return datetime_str[:5]  # Just take HH:MM part
        except Exception as e:
            print(f"DEBUG: Error formatting time '{datetime_str}': {e}")
        return datetime_str if datetime_str else 'N/A'
            
    async def setup_ably(self, max_retries=3):
        """Initialize Ably connection with connection monitoring"""
        async def connection_state_change(state_change):
            self.connection_state = state_change.current
            print(f"{Colors.CYAN}Connection state changed to: {self.connection_state}{Colors.END}")
            
            if state_change.current == "connected":
                self.last_heartbeat = datetime.now()
            elif state_change.current in ["failed", "suspended", "disconnected"]:
                print(f"{Colors.YELLOW}Connection state: {state_change.current}. Attempting to reconnect...{Colors.END}")
                await self.try_reconnect()
        
        retries = 0
        while retries < max_retries:
            try:
                if self.ably:
                    await self.ably.close()
                    
                self.ably = AblyRealtime(ABLY_API_KEY)
                self.ably.connection.on('state_change', connection_state_change)
                self.channel = self.ably.channels.get(CHANNEL_NAME)
                
                await self.subscribe_to_responses()
                self.connection_state = "connected"
                self.last_heartbeat = datetime.now()
                print(f"{Colors.GREEN}✓ Connected to travel agent service{Colors.END}\n")
                return
                
            except Exception as e:
                retries += 1
                if retries < max_retries:
                    wait_time = retries * 2  # Exponential backoff
                    print(f"{Colors.YELLOW}Connection attempt {retries} failed: {str(e)}")
                    print(f"Retrying in {wait_time} seconds...{Colors.END}")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"{Colors.RED}Failed to connect after {max_retries} attempts: {str(e)}{Colors.END}")
                    raise
                    
    async def try_reconnect(self):
        """Attempt to reconnect to Ably"""
        try:
            if self.ably and not self.ably.connection.state == "connected":
                print(f"{Colors.YELLOW}Attempting to reconnect...{Colors.END}")
                await self.setup_ably(max_retries=1)
        except Exception as e:
            print(f"{Colors.RED}Reconnection failed: {str(e)}{Colors.END}")

    async def subscribe_to_responses(self):
        """Subscribe to agent responses"""
        print("Subscribing to agent responses...")
        async def response_handler(message):
            try:
                
                if message.data.get('user_id') == self.user_id:
                   
                    self.last_response = message.data
                    # print(f"{Colors.CYAN}Received response from agent: {message.data.get('response', 'No response text')}{Colors.END}")
                    # Log flight results if present
                    if 'flight_results' in message.data:
                        # print(f"DEBUG: Flight results found in response: {message.data['flight_results']}")
                        None
                    elif 'response' in message.data and isinstance(message.data['response'], dict):
                        print(f"DEBUG: Flight results in response field: {message.data['response']}")
                    
                    # Only update booking info if it's valid
                    if 'current_info' in message.data:
                        new_info = message.data['current_info']
                        
                        # Ensure we don't lose passenger info
                        if ('passengers' in self.current_booking_info and 
                            'passengers' not in new_info and 
                            new_info.get('total_passengers')):
                            new_info['passengers'] = self.current_booking_info['passengers']
                            
                        self.current_booking_info = new_info
                    
                    self.response_event.set()
            except Exception as e:
                print(f"{Colors.RED}Error handling response: {str(e)}{Colors.END}")

        await self.channel.subscribe(EVENTS['AGENT_RESPONSE'], response_handler)

    async def send_to_agent(self, event_name: str, payload: dict) -> dict:
        """Send message to agent via Ably and wait for response with retry logic"""
        max_retries = 2  # Increased retries to handle temporary issues
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                # Check connection state and debug logging
                
                if self.connection_state != "connected":
                    
                    await self.try_reconnect()
                    if self.connection_state != "connected":
                        raise Exception("Failed to establish connection")
                
                # Clear previous response and prepare payload
                self.response_event.clear()
                start_time = datetime.now()
                
                # Deep copy payload to prevent mutations
                payload_copy = json.loads(json.dumps(payload))
                payload_copy['user_id'] = self.user_id
                payload_copy['query_time'] = start_time.isoformat()
                
                # Send message and wait for response
               
                await self.channel.publish(event_name, payload_copy)
                
                
                await asyncio.wait_for(self.response_event.wait(), timeout=30)
                
                end_time = datetime.now()
                turnaround_time = (end_time - start_time).total_seconds()
                # print(f"Response received in {turnaround_time:.2f} seconds")
                
                if isinstance(self.last_response, dict):
                    
                    self.last_response['turnaround_time'] = turnaround_time
                    self.last_heartbeat = datetime.now()
                    return self.last_response
                else:
                    print(f"DEBUG: Unexpected response type: {type(self.last_response)}")
                    
            except asyncio.TimeoutError:
                retry_count += 1
                if retry_count <= max_retries:
                    wait_time = retry_count * 2
                    self.print_chat_message("Just a moment, I'm still working on your request...", "assistant")
                    await asyncio.sleep(wait_time)
                    continue
                    
            except Exception as e:
                retry_count += 1
                if retry_count <= max_retries:
                    wait_time = retry_count * 2
                    self.print_chat_message("I'm having a bit of trouble, but I'll try again in a moment...", "assistant")
                    await asyncio.sleep(wait_time)
                    continue
        
        # All retries failed
        return {
            "response": "I apologize, but I'm having trouble maintaining a stable connection to the travel agent service. Please try again in a moment.",
            "type": "error",
            "current_info": self.current_booking_info,
            "turnaround_time": 30
        }
        
    
    def print_header(self):
        """Print the application header"""
        print(f"\n{Colors.CYAN}{'='*70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}✈️  CONVERSATIONAL TRAVEL ASSISTANT  ✈️{Colors.END}")
        print(f"{Colors.CYAN}{'='*70}{Colors.END}")
        print(f"{Colors.GREEN}Hey there! I'm your personal travel assistant. Let's chat about your trip!{Colors.END}\n")
    
    def print_separator(self, char='-', length=50):
        """Print a separator line"""
        print(f"{Colors.CYAN}{char * length}{Colors.END}")
    
    def print_chat_message(self, message: str, sender: str = "assistant", turnaround_time: float = None):
        """Print a chat message with proper formatting"""
        timestamp = datetime.now().strftime("%H:%M")
        
        if sender == "user":
            print(f"\n{Colors.CYAN}[{timestamp}] You:{Colors.END}")
            # Format user message with indentation
            for line in message.split('\n'):
                print(f"  {line}")
        else:
            # Show response time for agent messages if available
            time_info = ""
            if turnaround_time is not None:
                time_info = f" (response in {turnaround_time:.2f}s)"
            print(f"\n{Colors.GREEN}[{timestamp}] Travel Assistant{time_info}:{Colors.END}")
            
            # Format assistant message with indentation and better spacing
            for line in message.split('\n'):
                if line.strip():
                    print(f"  {line}")
                else:
                    print()  # Preserve empty lines for spacing
    
    async def get_user_input(self, prompt: str = "") -> str:
        """Get user input with proper formatting"""
        if not prompt:
            prompt = "You:"
        
        try:
            print(f"\n{Colors.YELLOW}💬 {prompt}{Colors.END}")
            user_input = await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: input(f"{Colors.YELLOW}➤ {Colors.END}").strip()
            )
            return user_input
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Chat paused. Type 'quit' to exit or continue chatting!{Colors.END}")
            return ""
        except EOFError:
            return "quit"
    
    def handle_special_commands(self, user_input: str) -> bool:
        """Handle special commands like help, quit, etc."""
        command = user_input.lower().strip()
        
        if command in ['quit', 'exit', 'bye', 'goodbye']:
            self.print_chat_message("It was great helping you with your travel plans! Have a wonderful trip and feel free to come back anytime you need flight assistance. Safe travels! ✈️", "assistant")
            return False
        
        elif command in ['help', 'what can you do', 'how does this work']:
            help_message = """I'm here to help you find and book flights in the most natural way possible! Here's how we can chat:

🗣️ **Just talk to me naturally!** Tell me things like:
   • "I need to fly from Lahore to Karachi next Friday"
   • "Can you find me a business class ticket to Dubai for next week?"
   • "I want to plan a family trip to Islamabad, we're 2 adults and 1 child"

✈️ **I can help you with:**
   • Finding flights across multiple airlines
   • Comparing prices and schedules
   • Booking different classes (economy, business, first)
   • Planning round-trip or one-way journeys
   • Managing group bookings

🤖 **No forms to fill!** Just chat with me like you would with a travel agent friend. I'll ask for any details I need as we go along.

💡 **Quick commands:**
   • 'restart' - Start planning a new trip
   • 'quit' - End our chat
   • 'clear' - Clear our conversation history

Ready to plan your next adventure? Just tell me where you'd like to go! 🌍"""
            
            self.print_chat_message(help_message, "assistant")
            return True
        
        elif command in ['restart', 'new trip', 'start over', 'reset']:
            self.awaiting_confirmation = False
            self.awaiting_modification = False
            self.search_completed = False
            self.confirmation_shown = False
            self.current_booking_info = {}
            
            # Will get welcome message in run_conversation_loop after reset
            return True
        
        elif command in ['clear', 'clear history']:
            self.awaiting_confirmation = False
            self.awaiting_modification = False
            self.confirmation_shown = False
            self.current_booking_info = {}
            self.print_chat_message("I've cleared our conversation history! Let's start fresh. What's your travel plan?", "assistant")
            return True
        
        return True  # Continue conversation
    
    def detect_user_intent(self, user_input: str, current_context: Dict) -> str:
        """Detect what the user intends to do based on their input and context"""
        input_lower = user_input.lower()
        
        # Confirmation-related responses
        confirmation_yes = ['yes', 'yeah', 'yep', 'sure', 'ok', 'okay', 'correct', 'right', 'perfect', 'good', 
                           'looks good', 'that\'s right', 'proceed', 'go ahead', 'search', 'find flights',
                           'everything is great', 'everything looks good', 'that\'s perfect', 'you can search']
        confirmation_no = ['no', 'nope', 'not quite', 'incorrect', 'wrong', 'change', 'modify', 'edit', 'update']
        
        # Modification-related phrases
        modification_phrases = ['change', 'modify', 'edit', 'update', 'different', 'instead', 'actually', 'correction']
        
        # Search-related phrases
        search_phrases = ['search', 'find', 'look for', 'show me', 'get flights', 'book']
        
        if self.awaiting_confirmation:
            if any(phrase in input_lower for phrase in confirmation_yes):
                return "confirm_and_search"
            elif any(phrase in input_lower for phrase in confirmation_no):
                return "request_modification"
            elif any(phrase in input_lower for phrase in modification_phrases):
                return "request_modification"
        
        if self.awaiting_modification or any(phrase in input_lower for phrase in modification_phrases):
            return "modify_details"
        
        if any(phrase in input_lower for phrase in search_phrases):
            return "search_request"
        
        return "general_chat"
    
    def show_booking_summary_naturally(self, booking_info: Dict) -> str:
        """Show booking information in a natural, conversational way"""
        if not booking_info:
            return ""
        
        # Only show summary if we have substantial information
        has_route = booking_info.get('source') and booking_info.get('destination')
        has_date = booking_info.get('departure_date')
        
        if not (has_route and has_date):
            return ""
        
        summary_parts = []
        
        # Route information
        route = f"✈️ {booking_info['source']} → {booking_info['destination']}"
        summary_parts.append(route)
        
        # Trip type and dates
        trip_info = []
        if booking_info.get('flight_type'):
            trip_type = "Round-trip" if booking_info['flight_type'] == 'return' else "One-way"
            trip_info.append(trip_type)
        
        if booking_info.get('departure_date'):
            trip_info.append(f"departing {booking_info['departure_date']}")
        
        if booking_info.get('return_date'):
            trip_info.append(f"returning {booking_info['return_date']}")
        
        if trip_info:
            summary_parts.append(f"📅 {' • '.join(trip_info)}")
        
        # Class and passengers
        passengers = booking_info.get('passengers', {'adults': 1, 'children': 0, 'infants': 0})
        class_text = booking_info.get('flight_class', 'economy').replace('_', ' ').title()
        
        passenger_count = passengers['adults']
        if passengers['children'] > 0 or passengers['infants'] > 0:
            passenger_count += passengers['children'] + passengers['infants']
            passenger_text = f"{passenger_count} passengers"
        else:
            passenger_text = f"{passenger_count} adult(s)"
        
        summary_parts.append(f"👥 {passenger_text} • {class_text}")
        
        # Optional airline
        if booking_info.get('content_provider'):
            airline_name = booking_info['content_provider'].replace('_', ' ').title()
            summary_parts.append(f"🏢 {airline_name}")
        
        return "\n".join(summary_parts)
    
    def should_show_summary(self, booking_info: Dict) -> bool:
        """Determine if we should show the booking summary"""
        # Only show summary when we have complete information for confirmation AND haven't shown it yet
        required_fields = ['source', 'destination', 'departure_date', 'flight_class', 'flight_type']
        has_complete_info = all(booking_info.get(field) for field in required_fields)
        return has_complete_info and not self.confirmation_shown
    
    async def process_conversation_turn(self, user_input: str):
        """Process a single turn in the conversation"""
        # Detect user intent
        current_context = {
            "awaiting_confirmation": self.awaiting_confirmation,
            "awaiting_modification": self.awaiting_modification,
            "search_completed": self.search_completed,
            "current_info": self.current_booking_info
        }
        
        intent = self.detect_user_intent(user_input, current_context)
        
        if intent == "confirm_and_search":
            # User confirmed, proceed with search
            self.awaiting_confirmation = False
            self.confirmation_shown = False
            
            # Show searching message
            self.print_chat_message("🔍 Searching for flights across all available airlines...", "assistant")
            
            result = await self.send_to_agent(EVENTS['EXECUTE_SEARCH'], {
                "current_info": self.current_booking_info
            })
            
            # Enhanced debugging for flight data
           
            if isinstance(result, dict):
                
                for key, value in result.items():
                    # print(f"DEBUG: {key}: {type(value)} - {str(value)[:100] if isinstance(value, str) else value}")
                    pass
            
            self.search_completed = True
            
            if isinstance(result, dict):
                # Look for flight data in multiple possible locations
                flight_data = None
                
                # Priority order for finding flight data
                if "flight_results" in result:
                    flight_data = result["flight_results"]
                    
                elif "flights" in result:
                    flight_data = result["flights"]
                    
                elif "response" in result and isinstance(result["response"], dict):
                    # Check if response contains flight data
                    response_data = result["response"]
                    if any(key in response_data for key in ["flights", "providers", "Itineraries", "data"]):
                        flight_data = response_data
                    
                
                # If we found flight data, try to format it
                if flight_data:
                    
                    formatted_results = self._format_flight_results(flight_data)
                    if formatted_results:
                        
                        self.print_chat_message(formatted_results, "assistant", result.get("turnaround_time"))
                        return
                    else:
                        print(f"DEBUG: Failed to format flight results")
                
                # If we have a text response, show it
                if "response" in result and isinstance(result["response"], str):
                    print(f"DEBUG: Showing text response")
                    self.print_chat_message(result["response"], "assistant", result.get("turnaround_time"))
                    return
                
                # If we have status complete but no flight data, there might be an issue
                if result.get("status") == "complete":
                    print(f"DEBUG: Status is complete but no flight data found")
                    if result.get("type") == "search_complete":
                        # This should have flight results, something went wrong
                        self.print_chat_message(
                            "I completed the flight search, but I'm having trouble displaying the results right now. The search was successful though! Can you please try again?",
                            "assistant",
                            result.get("turnaround_time")
                        )
                        return
            
            # Fallback message if nothing else worked
            print(f"DEBUG: Using fallback message")
            self.print_chat_message(
                "I wasn't able to find any flights matching your criteria. Would you like to try different dates or airlines?",
                "assistant"
            )
        
        elif intent in ["request_modification", "modify_details"]:
            # User wants to modify something
            self.awaiting_confirmation = False
            self.awaiting_modification = True
            self.confirmation_shown = False
            
            result = await self.send_to_agent(EVENTS['MODIFY_REQUEST'], {
                "input": user_input,
                "current_info": self.current_booking_info
            })
            self.print_chat_message(
                result["response"], 
                "assistant",
                result.get("turnaround_time")
            )
            
            # Check if we have all info after modification
            missing_info = result.get("missing_info", [])
            if not missing_info:
                # Move to confirmation state
                self.awaiting_confirmation = True
                self.awaiting_modification = False
        
        else:
            # General conversation - process normally
            result = await self.send_to_agent(EVENTS['USER_QUERY'], {
                "input": user_input,
                "current_info": self.current_booking_info
            })
            self.print_chat_message(
                result["response"], 
                "assistant",
                result.get("turnaround_time")
            )
            
            # Update conversation state based on result
            if result.get("type") == "confirmation":
                self.awaiting_confirmation = True
                self.awaiting_modification = False
                
                # Only show summary if it adds value and hasn't been shown
                if not self.confirmation_shown and self.current_booking_info:
                    summary = self.show_booking_summary_naturally(self.current_booking_info)
                    if summary:
                        self.print_chat_message(f"📋 **Quick Summary:**\n{summary}", "assistant")
                        self.confirmation_shown = True
                        
            elif result.get("type") == "gathering_info":
                self.awaiting_confirmation = False
                self.awaiting_modification = False
                self.confirmation_shown = False
            elif result.get("type") == "modification":
                self.awaiting_modification = True
                self.awaiting_confirmation = False
                self.confirmation_shown = False
    
    async def run_conversation_loop(self):
        """Main async conversation loop"""
        # Initialize Ably
        await self.setup_ably()
        
        # Get welcome message from agent
        result = await self.send_to_agent(EVENTS['RESET_CONVERSATION'], {})
        self.print_chat_message(result["response"], "assistant")
        
        while self.conversation_active:
            try:
                # Get user input
                user_input = await self.get_user_input()
                
                if not user_input:
                    continue
                
                # Handle special commands
                should_continue = self.handle_special_commands(user_input)
                if not should_continue:
                    break
                
                # Skip if it was a special command
                command = user_input.lower().strip()
                if command in ['help', 'what can you do', 'how does this work', 'restart', 'new trip', 
                              'start over', 'reset', 'clear', 'clear history']:
                    continue
                
                # Show user input in chat format
                self.print_chat_message(user_input, "user")
                
                # Process the conversation turn
                await self.process_conversation_turn(user_input)
                
                # Add some spacing for readability
                print()
                
            except KeyboardInterrupt:
                print(f"\n{Colors.YELLOW}Chat paused. Type 'quit' to exit or keep chatting!{Colors.END}")
                continue
            except Exception as e:
                error_msg = f"I apologize, but I encountered an issue: {str(e)}. Let's continue!"
                self.print_chat_message(error_msg, "assistant")
                continue
    
    def show_conversation_tips(self):
        """Show tips for natural conversation"""
        tips = f"""
{Colors.BOLD}{Colors.BLUE}💡 Tips for chatting with me:{Colors.END}

{Colors.GREEN}✅ Natural examples:{Colors.END}
  • "I want to fly to Dubai next Friday"
  • "Can you find me a cheap flight from Lahore to Karachi?"
  • "I need business class tickets for 2 people to Islamabad"
  • "Actually, make that return tickets instead"

{Colors.GREEN}✅ I understand:{Colors.END}
  • Casual language and typos
  • Changes of mind ("actually, let me change that...")
  • Multiple requests in one message
  • Questions about options and alternatives

{Colors.GREEN}✅ You can say:{Colors.END}
  • "That looks perfect!" (to confirm)
  • "Can you change the date?" (to modify)
  • "What airlines do you have?" (to ask questions)
  • "Never mind, let's start over" (to restart)

Just chat naturally - I'm here to help! 😊
"""
        print(tips)
    
    async def run(self):
        """Main application entry point"""
        self.print_header()
        self.show_conversation_tips()
        
        try:
            await self.run_conversation_loop()
        except Exception as e:
            print(f"\n{Colors.RED}An unexpected error occurred: {str(e)}{Colors.END}")
            print(f"{Colors.YELLOW}But don't worry - your travel assistant will be back soon!{Colors.END}")
        finally:
            if self.ably:
                await self.ably.close()
        
        print(f"\n{Colors.CYAN}Thanks for chatting! Come back soon! ✈️{Colors.END}")

def main():
    """Main entry point"""
    app = ConversationalTravelTerminal()
    asyncio.run(app.run())

if __name__ == "__main__":
    main()