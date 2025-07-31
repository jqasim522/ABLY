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
            
            await self.channel.publish(EVENTS['AGENT_RESPONSE'], result)

        async def handle_execute_search(message):
            """Handle flight search requests"""
            user_id = message.data.get('user_id')
            if not user_id:
                return
                
            session = self.get_or_create_session(user_id)
            session.update_last_interaction()
            current_info = message.data.get('current_info', {})
            
            # Execute the search using session's agent
            result = session.agent.execute_flight_search_with_conversation()
            # print(f"🔍 Search result for user {user_id}: {type(result)} - {list(result.keys()) if isinstance(result, dict) else 'Not dict'}")
            
            # Ensure we have a proper response structure
            if isinstance(result, dict):
                result['user_id'] = user_id
                # print(f"Result: {result}")
                # Check if we have flight_results and log what we find
                if 'flight_results' in result:
                    print(f"✈️ Found flight_results in result for user {user_id}")
                    if isinstance(result['flight_results'], dict):
                        print(f"🔍 Flight results keys: {list(result['flight_results'].keys())}")
                elif 'status' in result and result['status'] == 'complete':
                    # If status is complete but no flight_results, there might be an issue
                    print(f"⚠️ Status is complete but no flight_results found for user {user_id}")
                    print(f"🔍 Available result keys: {list(result.keys())}")
                
                # Don't modify the result structure - keep it as returned by the agent
                
            else:
                # Handle non-dict results
                result = {
                    'user_id': user_id,
                    'status': 'error',
                    'response': "An error occurred while searching for flights."
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
            
            await self.channel.publish(EVENTS['AGENT_RESPONSE'], result)

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
            await self.channel.publish(EVENTS['AGENT_RESPONSE'], result)

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
            await self.channel.publish(EVENTS['AGENT_RESPONSE'], result)

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
            if self.ably:
                await self.ably.close()

def main():
    """Main entry point"""
    server = TravelAgentServer()
    asyncio.run(server.run())

if __name__ == "__main__":
    main()