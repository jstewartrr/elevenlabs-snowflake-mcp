"""
Sovereign Mind MCP Proxy
Bridges ElevenLabs Conversational AI to Snowflake

Deploy to Azure Container Apps
"""

import os
import json
import logging
from typing import Any
import snowflake.connector
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Sovereign Mind MCP Proxy")

# CORS - allow ElevenLabs to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment variables
SNOWFLAKE_CONFIG = {
    "account": os.getenv("SNOWFLAKE_ACCOUNT"),
    "user": os.getenv("SNOWFLAKE_USER"),
    "password": os.getenv("SNOWFLAKE_PASSWORD"),
    "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
    "database": os.getenv("SNOWFLAKE_DATABASE"),
    "role": os.getenv("SNOWFLAKE_ROLE"),
}

# Simple API key for ElevenLabs authentication
API_KEY = os.getenv("MCP_API_KEY", "sovereign-mind-2024")


def get_snowflake_connection():
    """Create Snowflake connection"""
    return snowflake.connector.connect(**SNOWFLAKE_CONFIG)


def execute_query(sql: str) -> dict:
    """Execute SQL and return results"""
    try:
        conn = get_snowflake_connection()
        cursor = conn.cursor()
        cursor.execute(sql)
        
        # Get column names
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        
        # Fetch results
        rows = cursor.fetchall()
        
        # Convert to list of dicts
        results = [dict(zip(columns, row)) for row in rows]
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "data": results,
            "row_count": len(results),
            "columns": columns
        }
    except Exception as e:
        logger.error(f"Query error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================
# MCP Protocol Implementation for ElevenLabs
# ============================================================

class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Any = None
    method: str
    params: dict = {}


@app.get("/")
async def root():
    return {"status": "Sovereign Mind MCP Proxy running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/sse")
@app.post("/sse")
async def sse_endpoint(request: Request):
    """SSE endpoint for MCP protocol"""
    
    async def event_generator():
        # Send initial connection event
        yield {
            "event": "open",
            "data": json.dumps({"status": "connected"})
        }
        
        # Keep connection alive
        while True:
            await asyncio.sleep(30)
            yield {
                "event": "ping",
                "data": ""
            }
    
    return EventSourceResponse(event_generator())


@app.post("/mcp")
async def mcp_handler(
    request: MCPRequest,
    x_api_key: str = Header(None, alias="X-API-Key")
):
    """Handle MCP JSON-RPC requests"""
    
    # Validate API key (optional - can be disabled for testing)
    if API_KEY and x_api_key != API_KEY:
        # Log but don't block for now during testing
        logger.warning(f"Invalid or missing API key: {x_api_key}")
    
    method = request.method
    params = request.params
    request_id = request.id
    
    logger.info(f"MCP request: {method} with params: {params}")
    
    # Handle MCP methods
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "sovereign-mind-snowflake",
                    "version": "1.0.0"
                }
            }
        }
    
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": "query_sovereign_mind",
                        "description": "Query the Sovereign Mind Snowflake database containing emails, calendar events, voice transcripts, and handwritten notes for Your Grace",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "sql": {
                                    "type": "string",
                                    "description": "SQL query to execute. Available schemas: EMAILS, CALENDAR, VOICE_RECORDINGS, HANDWRITTEN_NOTES"
                                }
                            },
                            "required": ["sql"]
                        }
                    },
                    {
                        "name": "list_schemas",
                        "description": "List available schemas in Sovereign Mind database",
                        "inputSchema": {
                            "type": "object",
                            "properties": {}
                        }
                    },
                    {
                        "name": "list_tables",
                        "description": "List tables in a specific schema",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "schema": {
                                    "type": "string",
                                    "description": "Schema name (e.g., EMAILS, CALENDAR)"
                                }
                            },
                            "required": ["schema"]
                        }
                    }
                ]
            }
        }
    
    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        
        if tool_name == "query_sovereign_mind":
            sql = tool_args.get("sql")
            if not sql:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32602, "message": "Missing 'sql' parameter"}
                }
            
            result = execute_query(sql)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2, default=str)
                        }
                    ]
                }
            }
        
        elif tool_name == "list_schemas":
            result = execute_query("SHOW SCHEMAS IN DATABASE SOVEREIGN_MIND")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2, default=str)
                        }
                    ]
                }
            }
        
        elif tool_name == "list_tables":
            schema = tool_args.get("schema", "PUBLIC")
            result = execute_query(f"SHOW TABLES IN SCHEMA SOVEREIGN_MIND.{schema}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2, default=str)
                        }
                    ]
                }
            }
        
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}
            }
    
    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        }


# ============================================================
# Direct REST endpoints (alternative to MCP)
# ============================================================

class QueryRequest(BaseModel):
    sql: str


@app.post("/query")
async def direct_query(
    request: QueryRequest,
    x_api_key: str = Header(None, alias="X-API-Key")
):
    """Direct REST endpoint for queries (simpler than MCP)"""
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    result = execute_query(request.sql)
    return result


@app.get("/schemas")
async def list_schemas_rest():
    """List all schemas"""
    return execute_query("SHOW SCHEMAS IN DATABASE SOVEREIGN_MIND")


@app.get("/tables/{schema}")
async def list_tables_rest(schema: str):
    """List tables in schema"""
    return execute_query(f"SHOW TABLES IN SCHEMA SOVEREIGN_MIND.{schema}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
