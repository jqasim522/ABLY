#!/usr/bin/env python3
"""
Terminal-based Travel Flight Search Assistant
A clean command-line interface for searching flights with conversational AI
"""

import json
import sys
import os
from datetime import datetime, date
from typing import Dict, List, Optional, Any
import re
import asyncio
from ably import AblyRealtime
import uuid
from ably_config import ABLY_API_KEY
# Add the current directory to the path to import the travel agent
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

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

class TravelTerminal:
    """Terminal-based travel agent interface using Ably only"""
    
    def __init__(self):
        self.conversation_state = 'initial'  # initial, missing_info, confirmation, complete
        self.extracted_info = {}
        self.missing_attributes = []
        self.current_missing_index = 0
        self.chat_history = []
        self.final_results = None
        self.prompts = []
        self.ably = None
        self.channel = None
        self.user_id = str(uuid.uuid4())
        self.response_event = asyncio.Event()
        self.last_result = None
        self.turnaround_start_time = None
        self.turnaround_end_time = None
        
        # Check if terminal supports colors
        if not (hasattr(sys.stdout, "isatty") and sys.stdout.isatty()):
            Colors.disable()

    async def setup_ably(self):
        """Set up Ably Realtime instance and channel"""
        self.ably = AblyRealtime(ABLY_API_KEY)
        self.channel = self.ably.channels.get("travel-agent")

    async def subscribe_to_responses(self):
        async def agent_response_handler(message):
            if message.data.get('user_id') == self.user_id:
                result = message.data.get('result')
                latency = message.data.get('latency') if result else None
                self.last_result = result
                self.response_event.set()
                # Print response in chat format
                print(f"\n{Colors.GREEN}Travel Agent Response:{Colors.END}")
                print(result.get('llm_response') if result and 'llm_response' in result else result)
                # print(f"{Colors.YELLOW}Response time: {latency if latency is not None else 'N/A'}s{Colors.END}")
                # Show round-trip time for each response
                if hasattr(self, 'query_sent_time') and self.query_sent_time:
                    round_trip = (datetime.now() - self.query_sent_time).total_seconds()
                    print(f"{Colors.YELLOW}Round-trip time: {round_trip:.2f} seconds{Colors.END}")
                    self.query_sent_time = None
        await self.channel.subscribe("agent-response", agent_response_handler)

    async def send_query(self, query):
        self.response_event.clear()
        self.query_sent_time = datetime.now()
        await self.channel.publish(
            "user-query",
            {
                "user_id": self.user_id,
                "query": query
            }
        )

    async def run(self):
        self.print_header()
        await self.setup_ably()
        await self.subscribe_to_responses()
        print("Travel Agent Chat started! Type 'exit' to quit.")
        loop = asyncio.get_event_loop()
        while True:
            query = await loop.run_in_executor(None, input, f"{Colors.YELLOW}\nYou: {Colors.END}")
            if query.lower() == 'exit':
                break
            await self.send_query(query)
            await self.response_event.wait()
        self.ably.close()
        print(f"{Colors.CYAN}Goodbye! Safe travels! ✈️{Colors.END}")
    
    def print_header(self):
        """Print the application header"""
        print(f"\n{Colors.CYAN}{'='*70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}✈️  AI TRAVEL FLIGHT SEARCH ASSISTANT  ✈️{Colors.END}")
        print(f"{Colors.CYAN}{'='*70}{Colors.END}")
        print(f"{Colors.GREEN}Tell me about your travel plans and I'll help you find the best flights!{Colors.END}\n")
    
    def print_separator(self, char='-', length=50):
        """Print a separator line"""
        print(f"{Colors.CYAN}{char * length}{Colors.END}")
    
    def print_success(self, message: str):
        """Print success message"""
        print(f"{Colors.GREEN}✅ {message}{Colors.END}")
    
    def print_error(self, message: str):
        """Print error message"""
        print(f"{Colors.RED}❌ {message}{Colors.END}")
    
    def print_warning(self, message: str):
        """Print warning message"""
        print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")
    
    def print_info(self, message: str):
        """Print info message"""
        print(f"{Colors.BLUE}ℹ️  {message}{Colors.END}")
    
    def print_chat_message(self, message: str, sender: str = "assistant"):
        """Print a chat message with proper formatting"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        if sender == "user":
            print(f"{Colors.CYAN}[{timestamp}] You:{Colors.END} {message}")
        else:
            print(f"{Colors.GREEN}[{timestamp}] Assistant:{Colors.END} {message}")
    
    def add_to_chat(self, message: str, sender: str = "user"):
        """Add message to chat history"""
        self.chat_history.append({
            "message": message,
            "sender": sender,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
    
    async def get_user_input(self, prompt: str, allow_empty: bool = False) -> str:
        """Get user input asynchronously with proper formatting"""
        loop = asyncio.get_event_loop()
        while True:
            try:
                user_input = await loop.run_in_executor(None, input, f"{Colors.YELLOW}➤ {prompt}{Colors.END} ")
                user_input = user_input.strip()
                if user_input or allow_empty:
                    return user_input
                print(f"{Colors.RED}Please enter a valid response.{Colors.END}")
            except KeyboardInterrupt:
                print(f"\n{Colors.YELLOW}Operation cancelled.{Colors.END}")
                return ""
            except EOFError:
                print(f"\n{Colors.RED}Input error.{Colors.END}")
                return ""
    
    async def display_travel_info(self, info: Dict[str, Any], editable: bool = False) -> Optional[Dict[str, Any]]:
        """Display travel information asynchronously"""
        print(f"\n{Colors.BOLD}{Colors.BLUE}📝 Your Travel Details{Colors.END}")
        self.print_separator()
        
        # Flight Details
        print(f"{Colors.BOLD}🛫 Flight Details:{Colors.END}")
        print(f"   From (IATA Code): {Colors.CYAN}{info.get('source', '-')}{Colors.END}")
        print(f"   To (IATA Code): {Colors.CYAN}{info.get('destination', '-')}{Colors.END}")
        print(f"   Trip Type: {Colors.CYAN}{info.get('flight_type', '-')}{Colors.END}")
        print(f"   Travel Class: {Colors.CYAN}{info.get('flight_class', '-')}{Colors.END}")
        print(f"   Preferred Airline: {Colors.CYAN}{info.get('content_provider', 'Not selected')}{Colors.END}")
        if not info.get('content_provider'):
            print(f"   {Colors.RED}⚠️ Airline selection required{Colors.END}")
        
        # Travel Dates
        print(f"\n{Colors.BOLD}📅 Travel Dates:{Colors.END}")
        print(f"   Departure Date: {Colors.CYAN}{info.get('departure_date', '-')}{Colors.END}")
        if info.get('flight_type') == "return":
            print(f"   Return Date: {Colors.CYAN}{info.get('return_date', '-')}{Colors.END}")
        
        # Passengers
        print(f"\n{Colors.BOLD}👥 Passengers:{Colors.END}")
        passengers = info.get('passengers', {})
        print(f"   Adults: {Colors.CYAN}{passengers.get('adults', '-')}{Colors.END}")
        print(f"   Children (2-11 years): {Colors.CYAN}{passengers.get('children', '-')}{Colors.END}")
        print(f"   Infants (under 2 years): {Colors.CYAN}{passengers.get('infants', '-')}{Colors.END}")
        
        if not editable:
            return None
        
        # Check if content_provider is missing and make it compulsory
        if not info.get('content_provider'):
            self.print_warning("Airline selection is required before proceeding.")
            airline_options = ["airblue", "serene_air", "pia", "emirates", "qatar_airways", "etihad", "turkish_airlines"]
            print(f"Available airlines: {', '.join(airline_options)}")
            while True:
                airline_choice = await self.get_user_input("Please select an airline: ")
                if airline_choice in airline_options:
                    info['content_provider'] = airline_choice
                    break
                else:
                    self.print_error(f"Invalid airline: {airline_choice}. Please choose from: {', '.join(airline_options)}")
        print(f"\n{Colors.YELLOW}Would you like to modify any details? (y/n){Colors.END}")
        modify = (await self.get_user_input("")).lower()
        if modify not in ['y', 'yes']:
            return info
        return await self.edit_travel_info(info)
    
    async def edit_travel_info(self, info: Dict[str, Any]) -> Dict[str, Any]:
        """Allow user to edit travel information"""
        print(f"\n{Colors.BOLD}{Colors.BLUE}✏️ Edit Your Travel Details{Colors.END}")
        self.print_separator()
        
        # Available options
        source_options = ["LHE", "KHI", "ISB", "MUX", "PEW", "UET", "LYP", "SKT", "KDU", "GIL", "SKZ", "GWD", "TUK", "BHV", "DEA", "CJL", "PJG", "MJD", "PAJ", "PZH", "DBA", "MFG", "RYK", "WNS"]
        flight_types = ["one_way", "return"]
        flight_classes = ["economy", "business", "first", "premium_economy"]
        airline_options = ["", "airblue", "serene_air", "pia", "emirates", "qatar_airways", "etihad", "turkish_airlines"]
        
        updated_info = info.copy()
        
        # Edit source
        print(f"\nCurrent source: {Colors.CYAN}{info.get('source', 'Not set')}{Colors.END}")
        print(f"Available cities: {', '.join(source_options[:10])}...")
        new_source = await self.get_user_input(f"New source (press Enter to keep current): ", allow_empty=True)
        if new_source and new_source.upper() in source_options:
            updated_info['source'] = new_source.upper()
        elif new_source:
            self.print_error(f"Invalid city code: {new_source}")
        
        # Edit destination
        print(f"\nCurrent destination: {Colors.CYAN}{info.get('destination', 'Not set')}{Colors.END}")
        new_dest = await self.get_user_input(f"New destination (press Enter to keep current): ", allow_empty=True)
        if new_dest and new_dest.upper() in source_options:
            updated_info['destination'] = new_dest.upper()
        elif new_dest:
            self.print_error(f"Invalid city code: {new_dest}")
        
        # Edit flight type
        print(f"\nCurrent trip type: {Colors.CYAN}{info.get('flight_type', 'Not set')}{Colors.END}")
        print(f"Options: {', '.join(flight_types)}")
        new_type = await self.get_user_input(f"New trip type (press Enter to keep current): ", allow_empty=True)
        if new_type and new_type in flight_types:
            updated_info['flight_type'] = new_type
        elif new_type:
            self.print_error(f"Invalid flight type: {new_type}")
        
        # Edit flight class
        print(f"\nCurrent travel class: {Colors.CYAN}{info.get('flight_class', 'Not set')}{Colors.END}")
        print(f"Options: {', '.join(flight_classes)}")
        new_class = await self.get_user_input(f"New travel class (press Enter to keep current): ", allow_empty=True)
        if new_class and new_class in flight_classes:
            updated_info['flight_class'] = new_class
        elif new_class:
            self.print_error(f"Invalid flight class: {new_class}")
        
        # Edit airline (now compulsory)
        print(f"\nCurrent airline: {Colors.CYAN}{info.get('content_provider', 'Not set')}{Colors.END}")
        print(f"Available airlines: {', '.join([a for a in airline_options if a])}")
        while True:
            new_airline = await self.get_user_input(f"Select airline (required): ", allow_empty=True)
            if new_airline and new_airline in airline_options:
                updated_info['content_provider'] = new_airline
                break
            elif new_airline == "" and info.get('content_provider'):
                # Keep current if already set
                break
            elif new_airline:
                self.print_error(f"Invalid airline: {new_airline}. Please choose from: {', '.join([a for a in airline_options if a])}")
            else:
                self.print_error("Airline selection is required. Please choose from the available options.")
        
        # Edit departure date
        print(f"\nCurrent departure date: {Colors.CYAN}{info.get('departure_date', 'Not set')}{Colors.END}")
        new_dep_date = await self.get_user_input(f"New departure date (YYYY-MM-DD, press Enter to keep current): ", allow_empty=True)
        if new_dep_date:
            try:
                datetime.strptime(new_dep_date, "%Y-%m-%d")
                updated_info['departure_date'] = new_dep_date
            except ValueError:
                self.print_error("Invalid date format. Use YYYY-MM-DD")
        
        # Edit return date if return flight
        if updated_info.get('flight_type') == 'return':
            print(f"\nCurrent return date: {Colors.CYAN}{info.get('return_date', 'Not set')}{Colors.END}")
            new_ret_date = await self.get_user_input(f"New return date (YYYY-MM-DD, press Enter to keep current): ", allow_empty=True)
            if new_ret_date:
                try:
                    datetime.strptime(new_ret_date, "%Y-%m-%d")
                    updated_info['return_date'] = new_ret_date
                except ValueError:
                    self.print_error("Invalid date format. Use YYYY-MM-DD")
        
        # Edit passengers
        passengers = info.get('passengers', {"adults": 1, "children": 0, "infants": 0})
        print(f"\nCurrent passengers - Adults: {passengers.get('adults', 1)}, Children: {passengers.get('children', 0)}, Infants: {passengers.get('infants', 0)}")
        
        new_adults = await self.get_user_input(f"Number of adults (press Enter to keep current): ", allow_empty=True)
        if new_adults and new_adults.isdigit():
            passengers['adults'] = int(new_adults)
        
        new_children = await self.get_user_input(f"Number of children (press Enter to keep current): ", allow_empty=True)
        if new_children and new_children.isdigit():
            passengers['children'] = int(new_children)
        
        new_infants = await self.get_user_input(f"Number of infants (press Enter to keep current): ", allow_empty=True)
        if new_infants and new_infants.isdigit():
            passengers['infants'] = int(new_infants)
        
        updated_info['passengers'] = passengers
        
        # Validate
        if updated_info.get('source') == updated_info.get('destination'):
            self.print_error("Source and destination cannot be the same!")
            return info
        
        # Ensure content_provider is set
        if not updated_info.get('content_provider'):
            self.print_error("Airline selection is required!")
            print(f"Available airlines: {', '.join([a for a in airline_options if a])}")
            while True:
                airline_choice = await self.get_user_input("Please select an airline: ")
                if airline_choice in [a for a in airline_options if a]:
                    updated_info['content_provider'] = airline_choice
                    break
                else:
                    self.print_error(f"Invalid airline: {airline_choice}. Please choose from the available options.")
        
        return updated_info
    
    def show_help(self):
        """Show help information"""
        print(f"\n{Colors.BOLD}{Colors.BLUE}🛟 Help & Tips{Colors.END}")
        self.print_separator()
        print(f"{Colors.GREEN}How to use:{Colors.END}")
        print("1. Describe your travel plans naturally")
        print("2. Answer any follow-up questions")
        print("3. Confirm your details")
        print("4. Get flight results!")
        
        print(f"\n{Colors.GREEN}Example queries:{Colors.END}")
        print('• "I want to fly from Lahore to Karachi tomorrow"')
        print('• "Business class flight to Dubai next week for 2 people"')
        print('• "Return ticket ISB to LHE on 15th December"')
        
        print(f"\n{Colors.GREEN}Supported airlines:{Colors.END}")
        print("PIA, Emirates, Qatar Airways, Etihad, Turkish Airlines, Airblue, Serene Air")
        
        print(f"\n{Colors.GREEN}Commands:{Colors.END}")
        print("• 'help' - Show this help")
        print("• 'quit' or 'exit' - Exit the application")
        print("• 'restart' - Start a new search")
        print("• 'clear' - Clear chat history")
    
    async def handle_initial_state(self):
        """Handle initial state - get user query"""
        print(f"{Colors.BOLD}🗣️ Describe your travel plans:{Colors.END}")
        print(f"{Colors.CYAN}(Type 'help' for assistance or 'quit' to exit){Colors.END}")
        
        user_query = await self.get_user_input("")
        
        if user_query.lower() in ['quit', 'exit']:
            return False
        elif user_query.lower() == 'help':
            self.show_help()
            return True
        elif user_query.lower() == 'clear':
            self.chat_history = []
            print(f"{Colors.GREEN}Chat history cleared.{Colors.END}")
            return True
        elif user_query.lower() == 'restart':
            self.restart()
            return True
        elif not user_query:
            return True
        
        self.add_to_chat(user_query, "user")
        
        print(f"{Colors.YELLOW}🔄 Processing your request...{Colors.END}")
        # Start turnaround timer
        self.turnaround_start_time = datetime.now()
        # Send query to backend via Ably
        await self.send_query(user_query)
        await self.response_event.wait()
        result = self.last_result
        if not result:
            self.print_error("No response from backend.")
            return True
        
        if result["status"] == "missing_info":
            self.conversation_state = 'missing_info'
            self.extracted_info = result["extracted_info"]
            self.missing_attributes = result["missing_attributes"]
            self.prompts = result["prompts"]
            self.current_missing_index = 0
            
            self.add_to_chat("I need some additional information to search for flights. Let me ask you a few questions.", "assistant")
            self.print_chat_message("I need some additional information to search for flights. Let me ask you a few questions.", "assistant")
        
        elif result["status"] == "ready_for_confirmation":
            self.conversation_state = 'confirmation'
            self.extracted_info = result["extracted_info"]
            self.add_to_chat("Great! I've gathered all the information. Please review and confirm your travel details.", "assistant")
            self.print_chat_message("Great! I've gathered all the information. Please review and confirm your travel details.", "assistant")
        
        elif result["status"] == "error":
            error_msg = f"❌ Error: {result['message']}"
            self.add_to_chat(error_msg, "assistant")
            self.print_chat_message(error_msg, "assistant")
        
        return True

    async def handle_missing_info_state(self):
        """Handle missing information collection"""
        if self.current_missing_index < len(self.missing_attributes):
            current_attr = self.missing_attributes[self.current_missing_index]
            current_prompt = self.prompts[self.current_missing_index]
            
            print(f"\n{Colors.BLUE}Question {self.current_missing_index + 1} of {len(self.missing_attributes)}:{Colors.END}")
            self.print_chat_message(current_prompt, "assistant")
            
            user_input = await self.get_user_input("")
            
            if user_input.lower() in ['quit', 'exit']:
                return False
            elif user_input.lower() == 'restart':
                self.restart()
                return True
            elif not user_input:
                self.print_warning("Please provide an answer.")
                return True
            
            self.add_to_chat(current_prompt, "assistant")
            self.add_to_chat(user_input, "user")
            # Send missing attribute info to backend via Ably
            payload = {
                "user_id": self.user_id,
                "missing_attribute": current_attr,
                "user_input": user_input,
                "extracted_info": self.extracted_info
            }
            print(f"[DEBUG] Publishing user-missing-info: {payload}")
            self.response_event.clear()
            self.query_sent_time = datetime.now()
            await self.channel.publish("user-missing-info", payload)
            print("[DEBUG] Waiting for agent-response event...")
            await self.response_event.wait()
            await asyncio.sleep(0)
            print(f"[DEBUG] Received agent-response: {self.last_result}")
            result = self.last_result
            if not result:
                self.print_error("No response from backend.")
                return True
            self.extracted_info = result.get("extracted_info", self.extracted_info)
            self.current_missing_index += 1
        else:
            # All missing info collected, move to confirmation
            self.conversation_state = 'confirmation'
        
        return True

    async def handle_confirmation_state(self):
        """Handle confirmation state"""
        self.print_separator()
        updated_info = await self.display_travel_info(self.extracted_info, editable=True)
        if updated_info:
            print(f"\n{Colors.YELLOW}Confirm and search for flights? (y/n){Colors.END}")
            confirm = await self.get_user_input("")
            if confirm.lower() in ['y', 'yes']:
                self.add_to_chat("Perfect! Searching for flights with your confirmed details...", "assistant")
                self.print_chat_message("Perfect! Searching for flights with your confirmed details...", "assistant")
                print(f"{Colors.YELLOW}🔍 Searching for flights...{Colors.END}")
                payload = {
                    "user_id": self.user_id,
                    "confirmed_info": updated_info
                }
                self.response_event.clear()
                self.query_sent_time = datetime.now()
                await self.channel.publish("user-confirm-info", payload)
                await self.response_event.wait()
                search_result = self.last_result
                if search_result and search_result["status"] == "complete":
                    self.conversation_state = 'complete'
                    self.extracted_info = updated_info
                    self.final_results = search_result
                    # End turnaround timer
                    self.turnaround_end_time = datetime.now()
                    self.add_to_chat(search_result["llm_response"], "assistant")
                    self.print_chat_message(search_result["llm_response"], "assistant")
                else:
                    error_msg = f"❌ Error during search: {search_result.get('message', 'Unknown error') if search_result else 'Unknown error'}"
                    self.add_to_chat(error_msg, "assistant")
                    self.print_chat_message(error_msg, "assistant")
        return True

    async def handle_complete_state(self):
        """Handle complete state"""
        print(f"\n{Colors.BOLD}{Colors.GREEN}🎉 Flight Search Complete!{Colors.END}")
        await self.display_travel_info(self.extracted_info, editable=False)
        # Show turnaround time if available
        if self.turnaround_start_time and self.turnaround_end_time:
            turnaround = (self.turnaround_end_time - self.turnaround_start_time).total_seconds()
            print(f"{Colors.YELLOW}Total turnaround time: {turnaround:.2f} seconds{Colors.END}")
        print(f"\n{Colors.YELLOW}What would you like to do next?{Colors.END}")
        print("1. Start a new search")
        print("2. View technical details")
        print("3. Modify current search")
        print("4. Exit")
        choice = await self.get_user_input("Enter your choice (1-4): ")
        if choice == '1':
            self.restart()
        elif choice == '2':
            self.show_technical_details()
        elif choice == '3':
            self.conversation_state = 'confirmation'
        elif choice == '4':
            return False
        return True

    def show_technical_details(self):
        """Show technical details"""
        if not self.final_results:
            self.print_error("No results available.")
            return
        
        print(f"\n{Colors.BOLD}{Colors.BLUE}🔧 Technical Details{Colors.END}")
        self.print_separator()
        
        print(f"{Colors.GREEN}API Request Payload:{Colors.END}")
        print(json.dumps(self.final_results.get("api_payload", {}), indent=2))
        
        print(f"\n{Colors.GREEN}Raw Flight Results:{Colors.END}")
        print(json.dumps(self.final_results.get("flight_results", {}), indent=2))
        
        input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.END}")
    
    def restart(self):
        """Restart the application"""
        self.conversation_state = 'initial'
        self.extracted_info = {}
        self.missing_attributes = []
        self.current_missing_index = 0
        self.chat_history = []
        self.final_results = None
        self.prompts = []
        self.turnaround_start_time = None
        self.turnaround_end_time = None
        print(f"{Colors.GREEN}Starting fresh! Let's plan your next trip.{Colors.END}")
    
    async def run(self):
        """Main application loop (async)"""
        await self.setup_ably()
        await self.subscribe_to_responses()
        self.print_header()
        while True:
            try:
                if self.conversation_state == 'initial':
                    if not await self.handle_initial_state():
                        break
                elif self.conversation_state == 'missing_info':
                    if not await self.handle_missing_info_state():
                        break
                elif self.conversation_state == 'confirmation':
                    if not await self.handle_confirmation_state():
                        break
                elif self.conversation_state == 'complete':
                    if not await self.handle_complete_state():
                        break
                print()  # Add spacing between interactions
            except KeyboardInterrupt:
                print(f"\n{Colors.YELLOW}Thanks for using the Travel Flight Search Assistant! ✈️{Colors.END}")
                break
            except Exception as e:
                self.print_error(f"An unexpected error occurred: {str(e)}")
                print(f"{Colors.YELLOW}Would you like to restart? (y/n){Colors.END}")
                answer = await self.get_user_input("")
                if answer.lower() in ['y', 'yes']:
                    self.restart()
                else:
                    break
        print(f"{Colors.CYAN}Goodbye! Safe travels! ✈️{Colors.END}")

def main():
    app = TravelTerminal()
    asyncio.run(app.run())

if __name__ == "__main__":
    main()