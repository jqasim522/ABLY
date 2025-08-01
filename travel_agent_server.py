#!/usr/bin/env python3
"""
Travel Agent Server
Handles flight search requests via Ably realtime channels
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any
import os
import sys
from ably import AblyRealtime
from travel_agent import ConversationalTravelAgent
from ably_config import ABLY_API_KEY, CHANNEL_NAME, EVENTS

class UserSession:
    """Maintains state for each user session"""
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.agent = ConversationalTravelAgent()
        self.last_interaction = datetime.now()
    
    def update_last_interaction(self):
        """Update the last interaction timestamp"""
        self.last_interaction = datetime.now()

class TravelAgentServer:
    def __init__(self):
        self.ably = None
        self.channel = None
        self.active_sessions = {}  # Map of user_id to UserSession
        self.cleanup_task = None
        self.SESSION_TIMEOUT = 1800  # 30 minutes

    def get_or_create_session(self, user_id: str) -> UserSession:
        """Get existing session or create new one for user"""
        if user_id not in self.active_sessions:
            print(f"📝 Creating new session for user {user_id}")
            self.active_sessions[user_id] = UserSession(user_id)
        return self.active_sessions[user_id]

    async def cleanup_inactive_sessions(self):
        """Periodically clean up inactive sessions"""
        while True:
            current_time = datetime.now()
            inactive_sessions = []
            
            for user_id, session in self.active_sessions.items():
                time_diff = (current_time - session.last_interaction).total_seconds()
                if time_diff > self.SESSION_TIMEOUT:
                    inactive_sessions.append(user_id)
            
            for user_id in inactive_sessions:
                print(f"🧹 Cleaning up inactive session for user: {user_id}")
                del self.active_sessions[user_id]
            
            await asyncio.sleep(300)  # Check every 5 minutes

    def prepare_flight_data_for_client(self, flight_results):
        """Prepare flight data in a format the client can easily handle"""
        try:
            if not isinstance(flight_results, dict):
                return None
            
            # Extract flights from the results
            flights = flight_results.get('flights', [])
            if not flights:
                return None
            
            # Limit to top 5 flights and keep only essential fields for transmission
            simplified_flights = []
            
            for flight in flights[:5]:  # Limit to 5 flights
                try:
                    # Create a simplified flight object with only essential data
                    simplified_flight = {}
                    
                    # Flight identification
                    simplified_flight['flight_number'] = (
                        flight.get('flight_number') or 
                        flight.get('FlightNumber') or 
                        'N/A'
                    )
                    
                    # Airline
                    simplified_flight['airline'] = (
                        flight.get('airline') or 
                        flight.get('source_airline') or 
                        flight.get('Airline') or 
                        'Unknown'
                    )
                    
                    # Times
                    simplified_flight['departure_time'] = (
                        flight.get('departure_time') or 
                        flight.get('DepartureTime') or 
                        'N/A'
                    )
                    
                    simplified_flight['arrival_time'] = (
                        flight.get('arrival_time') or 
                        flight.get('ArrivalTime') or 
                        'N/A'
                    )
                    
                    # Price - try multiple fields
                    price = (
                        flight.get('price') or 
                        flight.get('sortable_price') or
                        flight.get('total_fare') or 
                        flight.get('ChargedTotalPrice') or 
                        flight.get('totalPrice') or 
                        flight.get('cost')
                    )
                    
                    if price and isinstance(price, (int, float)):
                        simplified_flight['price'] = int(price)
                    else:
                        simplified_flight['price'] = 'N/A'
                    
                    # Route information
                    simplified_flight['origin'] = flight.get('origin', '')
                    simplified_flight['destination'] = flight.get('destination', '')
                    
                    # Add any fare options if available (but simplified)
                    if flight.get('fare_options'):
                        fare_options = flight['fare_options']
                        if isinstance(fare_options, list) and fare_options:
                            cheapest_fare = min(fare_options, key=lambda x: x.get('total_fare', 999999))
                            simplified_flight['price'] = cheapest_fare.get('total_fare', simplified_flight['price'])
                            simplified_flight['fare_name'] = cheapest_fare.get('fare_name', 'Standard')
                    
                    simplified_flights.append(simplified_flight)
                    
                except Exception as e:
                    print(f"❌ Error simplifying flight: {e}")
                    continue
            
            if not simplified_flights:
                return None
            
            # Create the simplified result structure
            simplified_result = {
                'flights': simplified_flights,
                'total_flights': len(simplified_flights),
                'successful_airlines': flight_results.get('successful_airlines', 1),
                'search_completed': True
            }
            
            return simplified_result
            
        except Exception as e:
            print(f"❌ Error preparing flight data: {e}")
            return None

    def calculate_message_size(self, data):
        """Calculate approximate message size in bytes"""
        try:
            json_str = json.dumps(data, default=str)
            return len(json_str.encode('utf-8'))
        except:
            return 0

    async def setup(self):
        """Initialize Ably connection and start cleanup task"""
        print("🚀 Starting Travel Agent Server...")
        self.ably = AblyRealtime(ABLY_API_KEY)
        self.channel = self.ably.channels.get(CHANNEL_NAME)
        
        # Start the cleanup task
        self.cleanup_task = asyncio.create_task(self.cleanup_inactive_sessions())
        
        # Subscribe to all relevant events
        await self.subscribe_to_events()
        print("✅ Travel Agent Server is ready!")

    async def subscribe_to_events(self):
        """Subscribe to all Ably events"""
        async def handle_user_query(message):
            """Handle general user queries"""
            user_id = message.data.get('user_id')
            if not user_id:
                return
                
            session = self.get_or_create_session(user_id)
            session.update_last_interaction()
            
            user_input = message.data.get('input')
            current_info = message.data.get('current_info', {})
            
            # Process the query using session's agent
            result = session.agent.process_user_input_conversationally(user_input)
            result['user_id'] = user_id
            
            # Calculate turnaround time
            if 'query_time' in message.data:
                try:
                    query_time = datetime.fromisoformat(message.data['query_time'])
                    turnaround_time = (datetime.now() - query_time).total_seconds()
                    result['turnaround_time'] = turnaround_time
                except Exception as e:
                    print(f"Error calculating turnaround time: {e}")
            
            # Send response
            try:
                message_size = self.calculate_message_size(result)
                print(f"📤 Sending user query response ({message_size} bytes)")
                await self.channel.publish(EVENTS['AGENT_RESPONSE'], result)
            except Exception as e:
                print(f"❌ Error sending user query response: {e}")

        async def handle_execute_search(message):
            """Handle flight search requests"""
            user_id = message.data.get('user_id')
            if not user_id:
                return
                
            session = self.get_or_create_session(user_id)
            session.update_last_interaction()
            
            try:
                print(f"🔍 Starting flight search for user {user_id}")
                
                # Execute the search using session's agent
                result = session.agent.execute_flight_search_with_conversation()
                
                if isinstance(result, dict):
                    result['user_id'] = user_id
                    
                    # Calculate turnaround time
                    if 'query_time' in message.data:
                        try:
                            query_time = datetime.fromisoformat(message.data['query_time'])
                            turnaround_time = (datetime.now() - query_time).total_seconds()
                            result['turnaround_time'] = turnaround_time
                        except Exception as e:
                            print(f"Error calculating turnaround time: {e}")
                    
                    # Debug logging
                    if 'flight_results' in result:
                        flight_data = result['flight_results']
                        if isinstance(flight_data, dict) and 'flights' in flight_data:
                            print(f"✈️ Raw flight results: {len(flight_data['flights'])} flights")
                            
                            # Prepare simplified flight data for client
                            simplified_flight_data = self.prepare_flight_data_for_client(flight_data)
                            
                            if simplified_flight_data:
                                # Replace the complex flight_results with simplified version
                                result['flight_results'] = simplified_flight_data
                                print(f"✅ Simplified to {len(simplified_flight_data['flights'])} flights")
                            else:
                                print("❌ Failed to simplify flight data")
                                # Remove flight_results if we can't simplify it
                                result.pop('flight_results', None)
                    
                    # Check final message size
                    message_size = self.calculate_message_size(result)
                    print(f"📤 Sending flight search response ({message_size} bytes)")
                    
                    # If still too large, send just the text response
                    if message_size > 60000:  # 60KB limit
                        print("⚠️ Message still too large, sending text-only response")
                        text_result = {
                            'user_id': user_id,
                            'response': result.get('response', 'Flight search completed but results too large to display'),
                            'type': 'search_complete',
                            'status': 'complete',
                            'turnaround_time': result.get('turnaround_time', 0)
                        }
                        await self.channel.publish(EVENTS['AGENT_RESPONSE'], text_result)
                    else:
                        await self.channel.publish(EVENTS['AGENT_RESPONSE'], result)
                else:
                    # Handle non-dict results
                    error_result = {
                        'user_id': user_id,
                        'status': 'error',
                        'response': "An error occurred while searching for flights.",
                        'type': 'search_error'
                    }
                    await self.channel.publish(EVENTS['AGENT_RESPONSE'], error_result)
                    
            except Exception as e:
                print(f"❌ Error in flight search: {e}")
                import traceback
                traceback.print_exc()
                
                error_result = {
                    'user_id': user_id,
                    'status': 'error',
                    'response': f"An error occurred during flight search: {str(e)}",
                    'type': 'search_error'
                }
                await self.channel.publish(EVENTS['AGENT_RESPONSE'], error_result)

        async def handle_modify_request(message):
            """Handle modification requests"""
            user_id = message.data.get('user_id')
            if not user_id:
                return
                
            session = self.get_or_create_session(user_id)
            session.update_last_interaction()
            
            user_input = message.data.get('input')
            current_info = message.data.get('current_info', {})
            
            # Process modification using session's agent
            result = session.agent.handle_modification_request(user_input)
            result['user_id'] = user_id
            
            # Calculate turnaround time
            if 'query_time' in message.data:
                try:
                    query_time = datetime.fromisoformat(message.data['query_time'])
                    turnaround_time = (datetime.now() - query_time).total_seconds()
                    result['turnaround_time'] = turnaround_time
                except Exception as e:
                    print(f"Error calculating turnaround time: {e}")
            
            # Send response
            try:
                message_size = self.calculate_message_size(result)
                print(f"📤 Sending modify response ({message_size} bytes)")
                await self.channel.publish(EVENTS['AGENT_RESPONSE'], result)
            except Exception as e:
                print(f"❌ Error sending modify response: {e}")

        async def handle_reset_conversation(message):
            """Handle conversation reset requests"""
            user_id = message.data.get('user_id')
            if not user_id:
                return
                
            session = self.get_or_create_session(user_id)
            session.update_last_interaction()
            
            # Reset conversation using session's agent
            welcome_msg = session.agent.reset_conversation()
            result = {
                "response": welcome_msg,
                "type": "welcome",
                "user_id": user_id
            }
            
            # Calculate turnaround time
            if 'query_time' in message.data:
                try:
                    query_time = datetime.fromisoformat(message.data['query_time'])
                    turnaround_time = (datetime.now() - query_time).total_seconds()
                    result['turnaround_time'] = turnaround_time
                except Exception as e:
                    print(f"Error calculating turnaround time: {e}")
            
            # Send response
            try:
                await self.channel.publish(EVENTS['AGENT_RESPONSE'], result)
            except Exception as e:
                print(f"❌ Error sending reset response: {e}")

        # Subscribe to all events
        await self.channel.subscribe(EVENTS['USER_QUERY'], handle_user_query)
        await self.channel.subscribe(EVENTS['EXECUTE_SEARCH'], handle_execute_search)
        await self.channel.subscribe(EVENTS['MODIFY_REQUEST'], handle_modify_request)
        await self.channel.subscribe(EVENTS['RESET_CONVERSATION'], handle_reset_conversation)

    async def run(self):
        """Main server loop"""
        await self.setup()
        try:
            # Keep the server running
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 Shutting down Travel Agent Server...")
        finally:
            if self.cleanup_task:
                self.cleanup_task.cancel()
            if self.ably:
                await self.ably.close()

def main():
    """Main entry point"""
    server = TravelAgentServer()
    asyncio.run(server.run())

if __name__ == "__main__":
    main()