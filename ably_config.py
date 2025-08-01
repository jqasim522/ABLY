"""Ably configuration"""
# Replace with your Ably API key
ABLY_API_KEY = "Your ABLY KEY" #Add your ABLY API KEY Here

# Channel names
CHANNEL_NAME = "travel-agent"

# Event names
EVENTS = {
    "USER_QUERY": "user-query",
    "AGENT_RESPONSE": "agent-response",
    "EXECUTE_SEARCH": "execute-search",
    "MODIFY_REQUEST": "modify-request",
    "RESET_CONVERSATION": "reset-conversation"
}
