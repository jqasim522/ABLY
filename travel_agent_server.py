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

class TravelAgentServer:
    def __init__(self):
        self.ably = None
        self.channel = None
        self.agent = ConversationalTravelAgent()
        self.active_sessions = {}

    async def setup(self):
        """Initialize Ably connection"""
        print("🚀 Starting Travel Agent Server...")
        self.ably = AblyRealtime(ABLY_API_KEY)
        self.channel = self.ably.channels.get(CHANNEL_NAME)
        
        # Subscribe to all relevant events
        await self.subscribe_to_events()
        print("✅ Travel Agent Server is ready!")

    async def subscribe_to_events(self):
        """Subscribe to all Ably events"""
        async def handle_user_query(message):
            """Handle general user queries"""
            user_id = message.data.get('user_id')
            user_input = message.data.get('input')
            current_info = message.data.get('current_info', {})
            
            # Process the query
            result = self.agent.process_user_input_conversationally(user_input)
            result['user_id'] = user_id
            
            # Send response
            await self.channel.publish(EVENTS['AGENT_RESPONSE'], result)

        async def handle_execute_search(message):
            """Handle flight search requests"""
            user_id = message.data.get('user_id')
            current_info = message.data.get('current_info', {})
            
            # Execute the search
            result = self.agent.execute_flight_search_with_conversation()
            result['user_id'] = user_id
            
            # Send response
            await self.channel.publish(EVENTS['AGENT_RESPONSE'], result)

        async def handle_modify_request(message):
            """Handle modification requests"""
            user_id = message.data.get('user_id')
            user_input = message.data.get('input')
            current_info = message.data.get('current_info', {})
            
            # Process modification
            result = self.agent.handle_modification_request(user_input)
            result['user_id'] = user_id
            
            # Send response
            await self.channel.publish(EVENTS['AGENT_RESPONSE'], result)

        async def handle_reset_conversation(message):
            """Handle conversation reset requests"""
            user_id = message.data.get('user_id')
            
            # Reset conversation
            welcome_msg = self.agent.reset_conversation()
            result = {
                "response": welcome_msg,
                "type": "welcome",
                "user_id": user_id
            }
            
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
