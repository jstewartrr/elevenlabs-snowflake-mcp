"""
Simli MCP Server - Manage Simli avatars and agents
FIXED v1.1.0: Use /agents (plural) endpoint, updated API handling
"""
from flask import Flask, request, Response
import requests
import json
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

SIMLI_API_KEY = os.environ.get("SIMLI_API_KEY")
SIMLI_BASE_URL = "https://api.simli.ai"

TOOLS = [
    {
        "name": "list_agents",
        "description": "List all Simli agents/avatars in your account",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_agent",
        "description": "Get details of a specific Simli agent by ID",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "The agent ID to retrieve"
                }
            },
            "required": ["agent_id"]
        }
    },
    {
        "name": "update_agent",
        "description": "Update a Simli agent's settings (face, name, prompt, voice, etc.)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "The agent ID to update"
                },
                "name": {
                    "type": "string",
                    "description": "New name for the agent"
                },
                "face_id": {
                    "type": "string",
                    "description": "New face ID for the avatar"
                },
                "prompt": {
                    "type": "string",
                    "description": "System prompt for the agent"
                },
                "first_message": {
                    "type": "string",
                    "description": "Initial greeting message"
                },
                "voice_id": {
                    "type": "string",
                    "description": "Voice ID (for ElevenLabs or Cartesia)"
                },
                "voice_provider": {
                    "type": "string",
                    "description": "Voice provider: 'elevenlabs' or 'cartesia'"
                },
                "max_idle_time": {
                    "type": "integer",
                    "description": "Max idle time in seconds before timeout"
                },
                "max_session_length": {
                    "type": "integer",
                    "description": "Max session length in seconds"
                }
            },
            "required": ["agent_id"]
        }
    },
    {
        "name": "create_agent",
        "description": "Create a new Simli agent/avatar",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name for the agent"
                },
                "face_id": {
                    "type": "string",
                    "description": "Face ID for the avatar"
                },
                "prompt": {
                    "type": "string",
                    "description": "System prompt for the agent"
                },
                "first_message": {
                    "type": "string",
                    "description": "Initial greeting message"
                },
                "voice_id": {
                    "type": "string",
                    "description": "Voice ID"
                },
                "voice_provider": {
                    "type": "string",
                    "description": "Voice provider: 'elevenlabs' or 'cartesia'",
                    "default": "elevenlabs"
                }
            },
            "required": ["name", "face_id"]
        }
    },
    {
        "name": "delete_agent",
        "description": "Delete a Simli agent",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "The agent ID to delete"
                }
            },
            "required": ["agent_id"]
        }
    },
    {
        "name": "list_faces",
        "description": "List available preset face IDs for avatars",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]

def simli_request(method, endpoint, data=None):
    """Make authenticated request to Simli API"""
    headers = {
        "x-simli-api-key": SIMLI_API_KEY,
        "Content-Type": "application/json"
    }
    url = f"{SIMLI_BASE_URL}{endpoint}"
    
    logger.info(f"Making {method} request to {url}")
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=30)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data, timeout=30)
        elif method == "PUT":
            response = requests.put(url, headers=headers, json=data, timeout=30)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, timeout=30)
        else:
            return {"error": f"Unknown method: {method}"}
        
        logger.info(f"Response status: {response.status_code}")
        
        if response.status_code >= 400:
            return {"error": f"API error {response.status_code}: {response.text}"}
        
        if response.text:
            return response.json()
        return {"success": True}
    except Exception as e:
        logger.error(f"Request error: {e}")
        return {"error": str(e)}

def handle_tool_call(tool_name, arguments):
    """Handle MCP tool calls"""
    
    if tool_name == "list_agents":
        # FIXED: Use /agents (plural) endpoint
        result = simli_request("GET", "/agents")
        if isinstance(result, list):
            return {"success": True, "agents": result, "count": len(result)}
        return result
    
    elif tool_name == "get_agent":
        agent_id = arguments.get("agent_id")
        if not agent_id:
            return {"error": "agent_id is required"}
        # FIXED: Use /agents/{id} endpoint
        return simli_request("GET", f"/agents/{agent_id}")
    
    elif tool_name == "update_agent":
        agent_id = arguments.get("agent_id")
        if not agent_id:
            return {"error": "agent_id is required"}
        
        # Build update payload with only provided fields
        update_data = {"id": agent_id}
        for field in ["name", "face_id", "prompt", "first_message", "voice_id", 
                      "voice_provider", "max_idle_time", "max_session_length"]:
            if field in arguments and arguments[field] is not None:
                update_data[field] = arguments[field]
        
        return simli_request("PUT", "/agents", update_data)
    
    elif tool_name == "create_agent":
        create_data = {
            "name": arguments.get("name", "Untitled Agent"),
            "face_id": arguments.get("face_id"),
            "voice_provider": arguments.get("voice_provider", "elevenlabs")
        }
        
        for field in ["prompt", "first_message", "voice_id"]:
            if field in arguments and arguments[field]:
                create_data[field] = arguments[field]
        
        return simli_request("POST", "/agents", create_data)
    
    elif tool_name == "delete_agent":
        agent_id = arguments.get("agent_id")
        if not agent_id:
            return {"error": "agent_id is required"}
        return simli_request("DELETE", f"/agents/{agent_id}")
    
    elif tool_name == "list_faces":
        # Return known preset faces - Simli doesn't have a public API for this
        preset_faces = {
            "success": True,
            "note": "These are commonly available preset faces. Create custom faces at app.simli.com",
            "preset_faces": [
                {"id": "tmp9i8bbq7c", "name": "Default Male"},
                {"id": "t7cR30LkYqwg", "name": "Default Female"},
            ],
            "custom_faces_url": "https://app.simli.com/create"
        }
        return preset_faces
    
    else:
        return {"error": f"Unknown tool: {tool_name}"}


# MCP Protocol Handlers

@app.route('/mcp', methods=['POST'])
def mcp_handler():
    """Handle MCP JSON-RPC requests"""
    try:
        data = request.get_json()
        method = data.get("method")
        req_id = data.get("id")
        
        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "simli-mcp", "version": "1.1.0"},
                    "capabilities": {"tools": {"listChanged": False}}
                }
            }
        
        elif method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": TOOLS}
            }
        
        elif method == "tools/call":
            params = data.get("params", {})
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            result = handle_tool_call(tool_name, arguments)
            
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
                }
            }
        
        elif method == "notifications/initialized":
            return "", 204
        
        else:
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown method: {method}"}
            }
        
        return Response(json.dumps(response), content_type="application/json")
    
    except Exception as e:
        logger.error(f"Error: {e}")
        return Response(
            json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(e)}}),
            content_type="application/json"
        )


@app.route('/health', methods=['GET'])
def health():
    return {"status": "healthy", "service": "simli-mcp", "version": "1.1.0"}


if __name__ == "__main__":
    if not SIMLI_API_KEY:
        logger.error("SIMLI_API_KEY environment variable required")
        exit(1)
    app.run(host="0.0.0.0", port=8000)
