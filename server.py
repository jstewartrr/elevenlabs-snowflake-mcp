"""
Sovereign Mind MCP Server - Enhanced with ElevenLabs Agent Configuration
Uses official MCP SDK with SSE transport for ElevenLabs integration
"""

import os
import json
import logging
import httpx
import snowflake.connector
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create MCP server
mcp = FastMCP("Sovereign Mind Snowflake")

# Snowflake connection config from environment
SNOWFLAKE_CONFIG = {
    "account": os.environ.get("SNOWFLAKE_ACCOUNT", "jga82554.east-us-2.azure"),
    "user": os.environ.get("SNOWFLAKE_USER", "JOHN_CLAUDE"),
    "password": os.environ.get("SNOWFLAKE_PASSWORD"),
    "warehouse": os.environ.get("SNOWFLAKE_WAREHOUSE", "SOVEREIGN_MIND_WH"),
    "database": os.environ.get("SNOWFLAKE_DATABASE", "SOVEREIGN_MIND"),
    "schema": os.environ.get("SNOWFLAKE_SCHEMA", "RAW"),
    "role": os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
}

# ElevenLabs config
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1"


def get_snowflake_connection():
    """Create a Snowflake connection"""
    return snowflake.connector.connect(**SNOWFLAKE_CONFIG)


@mcp.tool()
def query_snowflake(sql: str) -> str:
    """
    Execute a SQL query on Snowflake SOVEREIGN_MIND database.
    
    Available tables in SOVEREIGN_MIND.RAW:
    - SHARED_MEMORY: Shared context between Claude instances
      Columns: SOURCE, CATEGORY, WORKSTREAM, SUMMARY, DETAILS, PRIORITY, STATUS, CREATED_AT
    - EMAILS: Email data 
      Columns: SUBJECT, BODY_PREVIEW, BODY_CONTENT, RECEIVED_AT, HAS_ATTACHMENTS
    - CALENDAR_EVENTS: Calendar data
      Columns: SUBJECT, ORGANIZER, ATTENDEES, LOCATION, START_TIME, END_TIME
    - GOODNOTES: Handwritten notes from GoodNotes OCR
    - CONVERSATIONS: Voice transcripts from Plaud
    
    For SHARED_MEMORY writes, use:
    INSERT INTO SOVEREIGN_MIND.RAW.SHARED_MEMORY 
    (SOURCE, CATEGORY, WORKSTREAM, SUMMARY, PRIORITY, STATUS) 
    VALUES ('ABBI', 'CATEGORY', 'WORKSTREAM', 'Summary text', 'HIGH', 'ACTIVE')
    
    Args:
        sql: SQL query to execute (SELECT, INSERT, UPDATE, DELETE all supported)
        
    Returns:
        JSON string with query results or confirmation
    """
    try:
        conn = get_snowflake_connection()
        cursor = conn.cursor()
        cursor.execute(sql)
        
        # Get column names
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        
        # Fetch results
        rows = cursor.fetchall()
        
        # Convert to list of dicts
        data = []
        for row in rows:
            row_dict = {}
            for i, col in enumerate(columns):
                val = row[i]
                # Convert non-serializable types to strings
                if hasattr(val, 'isoformat'):
                    val = val.isoformat()
                elif isinstance(val, bytes):
                    val = val.decode('utf-8', errors='replace')
                row_dict[col] = val
            data.append(row_dict)
        
        cursor.close()
        conn.close()
        
        result = {
            "success": True,
            "data": data,
            "row_count": len(data)
        }
        
        # For INSERT/UPDATE/DELETE, also include rows affected
        if not data and cursor.rowcount >= 0:
            result["rows_affected"] = cursor.rowcount
        
        return json.dumps(result, indent=2, default=str)
        
    except Exception as e:
        logger.error(f"Query error: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        })


@mcp.tool()
def configure_agent(
    agent_id: str,
    turn_timeout: float = None,
    optimize_streaming_latency: int = None,
    stability: float = None,
    similarity_boost: float = None,
    speed: float = None,
    temperature: float = None,
    first_message: str = None,
    prompt: str = None
) -> str:
    """
    Configure ElevenLabs conversational AI agent settings.
    
    This tool provides FULL control over all agent settings including those
    not available in the ElevenLabs console UI with decimal precision.
    
    Args:
        agent_id: The agent ID (e.g., 'agent_0001kcva7evzfbt9q5zc9n2q4vaz')
        turn_timeout: Turn timeout in seconds (e.g., 1.5, 2.0)
        optimize_streaming_latency: Latency optimization level 1-4 (4 = fastest)
        stability: Voice stability 0.0-1.0 (lower = more expressive)
        similarity_boost: Voice similarity 0.0-1.0 (higher = closer to original)
        speed: Speech speed 0.5-2.0 (1.0 = normal)
        temperature: LLM temperature 0.0-1.0 (lower = more consistent)
        first_message: Initial greeting message
        prompt: Full system prompt for the agent
        
    Returns:
        JSON with success status and updated configuration
    """
    try:
        if not ELEVENLABS_API_KEY:
            return json.dumps({"success": False, "error": "ELEVENLABS_API_KEY not configured"})
        
        # Build the update payload
        payload = {"conversation_config": {}}
        
        # Turn settings
        if turn_timeout is not None:
            payload["conversation_config"]["turn"] = {"turn_timeout": turn_timeout}
        
        # TTS settings
        tts_settings = {}
        if optimize_streaming_latency is not None:
            tts_settings["optimize_streaming_latency"] = optimize_streaming_latency
        if stability is not None:
            tts_settings["stability"] = stability
        if similarity_boost is not None:
            tts_settings["similarity_boost"] = similarity_boost
        if speed is not None:
            tts_settings["speed"] = speed
        if tts_settings:
            payload["conversation_config"]["tts"] = tts_settings
        
        # Agent/LLM settings
        agent_settings = {}
        if first_message is not None:
            agent_settings["first_message"] = first_message
        
        prompt_settings = {}
        if temperature is not None:
            prompt_settings["temperature"] = temperature
        if prompt is not None:
            prompt_settings["prompt"] = prompt
        
        if prompt_settings:
            agent_settings["prompt"] = prompt_settings
        if agent_settings:
            payload["conversation_config"]["agent"] = agent_settings
        
        # Make API request
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json"
        }
        
        with httpx.Client() as client:
            response = client.patch(
                f"{ELEVENLABS_BASE_URL}/convai/agents/{agent_id}",
                headers=headers,
                json=payload,
                timeout=30.0
            )
            
            if response.status_code == 200:
                return json.dumps({
                    "success": True,
                    "message": "Agent configuration updated",
                    "updated_settings": payload
                }, indent=2)
            else:
                return json.dumps({
                    "success": False,
                    "error": f"API error {response.status_code}: {response.text}"
                })
                
    except Exception as e:
        logger.error(f"Agent configuration error: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        })


@mcp.tool()
def get_agent_config(agent_id: str) -> str:
    """
    Get full configuration of an ElevenLabs conversational AI agent.
    
    Args:
        agent_id: The agent ID to retrieve
        
    Returns:
        JSON with full agent configuration including all settings
    """
    try:
        if not ELEVENLABS_API_KEY:
            return json.dumps({"success": False, "error": "ELEVENLABS_API_KEY not configured"})
        
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY
        }
        
        with httpx.Client() as client:
            response = client.get(
                f"{ELEVENLABS_BASE_URL}/convai/agents/{agent_id}",
                headers=headers,
                timeout=30.0
            )
            
            if response.status_code == 200:
                config = response.json()
                # Extract key settings for easy viewing
                conv_config = config.get("conversation_config", {})
                summary = {
                    "agent_id": agent_id,
                    "name": config.get("name"),
                    "turn_timeout": conv_config.get("turn", {}).get("turn_timeout"),
                    "optimize_streaming_latency": conv_config.get("tts", {}).get("optimize_streaming_latency"),
                    "stability": conv_config.get("tts", {}).get("stability"),
                    "similarity_boost": conv_config.get("tts", {}).get("similarity_boost"),
                    "speed": conv_config.get("tts", {}).get("speed"),
                    "temperature": conv_config.get("agent", {}).get("prompt", {}).get("temperature"),
                    "llm": conv_config.get("agent", {}).get("prompt", {}).get("llm"),
                    "first_message": conv_config.get("agent", {}).get("first_message"),
                }
                return json.dumps({
                    "success": True,
                    "summary": summary,
                    "full_config": config
                }, indent=2, default=str)
            else:
                return json.dumps({
                    "success": False,
                    "error": f"API error {response.status_code}: {response.text}"
                })
                
    except Exception as e:
        logger.error(f"Get agent config error: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        })


# Create SSE transport for MCP
sse = SseServerTransport("/messages/")


async def handle_sse(request):
    """Handle SSE connection for MCP protocol"""
    logger.info("New SSE connection established")
    async with sse.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await mcp._mcp_server.run(
            streams[0], 
            streams[1],
            mcp._mcp_server.create_initialization_options()
        )


async def handle_messages(request):
    """Handle POST messages for MCP protocol"""
    logger.info("Handling POST message")
    await sse.handle_post_message(request.scope, request.receive, request._send)


async def handle_root(request):
    """Health check endpoint"""
    return JSONResponse({
        "status": "Sovereign Mind MCP Server running",
        "transport": "SSE",
        "tools": ["query_snowflake", "configure_agent", "get_agent_config"]
    })


# Create Starlette app with proper MCP SSE routes
app = Starlette(
    routes=[
        Route("/", endpoint=handle_root),
        Route("/sse", endpoint=handle_sse),
        Route("/messages/", endpoint=handle_messages, methods=["POST"]),
    ]
)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
