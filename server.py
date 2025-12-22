"""
Sovereign Mind MCP Server - Fixed SSE Implementation
Uses official MCP SDK with SSE transport for ElevenLabs integration
"""

import os
import json
import logging
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
    "role": os.environ.get("SNOWFLAKE_ROLE", "SOVEREIGN_MIND_ROLE"),
}


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
    return JSONResponse({"status": "Sovereign Mind MCP Server running", "transport": "SSE"})


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
