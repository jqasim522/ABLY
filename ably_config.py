"""Ably configuration"""
# Replace with your Ably API key
ABLY_API_KEY = "wy5x6w.3ECUmg:SoTIivChQwX67WHjV9fG2BuHUA9_jGjscVwZXRzCDfA"

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
