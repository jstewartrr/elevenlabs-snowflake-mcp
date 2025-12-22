import os, json, logging, requests
from flask import Flask, request, jsonify, Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = Flask(__name__)

FIGMA_TOKEN = os.environ.get('FIGMA_TOKEN', '')
FIGMA_API = "https://api.figma.com/v1"

MCP_TOOLS = [
    {
        "name": "get_file",
        "description": "Get a Figma file by key. Returns file structure, components, and metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_key": {"type": "string", "description": "The Figma file key (from URL)"},
                "depth": {"type": "integer", "description": "Depth of nodes to return (default: 2)", "default": 2}
            },
            "required": ["file_key"]
        }
    },
    {
        "name": "get_file_nodes",
        "description": "Get specific nodes from a Figma file by their IDs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_key": {"type": "string", "description": "The Figma file key"},
                "node_ids": {"type": "string", "description": "Comma-separated node IDs"}
            },
            "required": ["file_key", "node_ids"]
        }
    },
    {
        "name": "export_nodes",
        "description": "Export nodes as images (PNG, SVG, PDF, JPG).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_key": {"type": "string", "description": "The Figma file key"},
                "node_ids": {"type": "string", "description": "Comma-separated node IDs to export"},
                "format": {"type": "string", "enum": ["png", "svg", "pdf", "jpg"], "default": "png"},
                "scale": {"type": "number", "description": "Scale factor (0.01 to 4)", "default": 2}
            },
            "required": ["file_key", "node_ids"]
        }
    },
    {
        "name": "get_components",
        "description": "Get all components from a Figma file or team library.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_key": {"type": "string", "description": "The Figma file key"}
            },
            "required": ["file_key"]
        }
    },
    {
        "name": "get_styles",
        "description": "Get all styles (colors, text, effects) from a Figma file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_key": {"type": "string", "description": "The Figma file key"}
            },
            "required": ["file_key"]
        }
    },
    {
        "name": "list_files",
        "description": "List files in a Figma project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "The Figma project ID"}
            },
            "required": ["project_id"]
        }
    },
    {
        "name": "list_projects",
        "description": "List projects in a Figma team.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "The Figma team ID"}
            },
            "required": ["team_id"]
        }
    },
    {
        "name": "get_me",
        "description": "Get current user info and verify API connection.",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "create_comment",
        "description": "Add a comment to a Figma file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_key": {"type": "string", "description": "The Figma file key"},
                "message": {"type": "string", "description": "Comment text"},
                "x": {"type": "number", "description": "X coordinate (optional)"},
                "y": {"type": "number", "description": "Y coordinate (optional)"},
                "node_id": {"type": "string", "description": "Node to attach comment to (optional)"}
            },
            "required": ["file_key", "message"]
        }
    },
    {
        "name": "get_comments",
        "description": "Get all comments from a Figma file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_key": {"type": "string", "description": "The Figma file key"}
            },
            "required": ["file_key"]
        }
    }
]

def figma_request(endpoint, method="GET", data=None):
    """Make authenticated request to Figma API"""
    if not FIGMA_TOKEN:
        return {"success": False, "error": "Figma token not configured"}
    
    headers = {"X-Figma-Token": FIGMA_TOKEN}
    url = f"{FIGMA_API}{endpoint}"
    
    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, timeout=60)
        elif method == "POST":
            headers["Content-Type"] = "application/json"
            resp = requests.post(url, headers=headers, json=data, timeout=60)
        else:
            return {"success": False, "error": f"Unsupported method: {method}"}
        
        if resp.status_code == 200:
            return {"success": True, "data": resp.json()}
        else:
            return {"success": False, "error": f"API error {resp.status_code}: {resp.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_file(file_key, depth=2):
    return figma_request(f"/files/{file_key}?depth={depth}")

def get_file_nodes(file_key, node_ids):
    return figma_request(f"/files/{file_key}/nodes?ids={node_ids}")

def export_nodes(file_key, node_ids, format="png", scale=2):
    result = figma_request(f"/images/{file_key}?ids={node_ids}&format={format}&scale={scale}")
    if result.get("success") and "images" in result.get("data", {}):
        return {"success": True, "images": result["data"]["images"]}
    return result

def get_components(file_key):
    result = figma_request(f"/files/{file_key}/components")
    return result

def get_styles(file_key):
    result = figma_request(f"/files/{file_key}/styles")
    return result

def list_files(project_id):
    return figma_request(f"/projects/{project_id}/files")

def list_projects(team_id):
    return figma_request(f"/teams/{team_id}/projects")

def get_me():
    return figma_request("/me")

def create_comment(file_key, message, x=None, y=None, node_id=None):
    data = {"message": message}
    if x is not None and y is not None:
        data["client_meta"] = {"x": x, "y": y}
    if node_id:
        data["client_meta"] = data.get("client_meta", {})
        data["client_meta"]["node_id"] = node_id
    return figma_request(f"/files/{file_key}/comments", method="POST", data=data)

def get_comments(file_key):
    return figma_request(f"/files/{file_key}/comments")

@app.route('/mcp', methods=['GET'])
def mcp_sse():
    return Response(
        f"data: {json.dumps({'jsonrpc':'2.0','method':'notifications/initialized','params':{'serverInfo':{'name':'figma-mcp','version':'1.0.0'},'capabilities':{'tools':{}}}})}\\n\\n",
        mimetype='text/event-stream'
    )

@app.route('/mcp', methods=['POST'])
def mcp_post():
    data = request.get_json()
    method = data.get('method', '')
    params = data.get('params', {})
    rid = data.get('id')
    
    if method == 'initialize':
        return jsonify({
            "jsonrpc": "2.0",
            "id": rid,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "figma-mcp", "version": "1.0.0"},
                "capabilities": {"tools": {}}
            }
        })
    
    if method == 'tools/list':
        return jsonify({"jsonrpc": "2.0", "id": rid, "result": {"tools": MCP_TOOLS}})
    
    if method == 'tools/call':
        name = params.get('name')
        args = params.get('arguments', {})
        
        tool_map = {
            'get_file': get_file,
            'get_file_nodes': get_file_nodes,
            'export_nodes': export_nodes,
            'get_components': get_components,
            'get_styles': get_styles,
            'list_files': list_files,
            'list_projects': list_projects,
            'get_me': get_me,
            'create_comment': create_comment,
            'get_comments': get_comments
        }
        
        if name in tool_map:
            result = tool_map[name](**args)
        else:
            result = {"error": f"Unknown tool: {name}"}
        
        return jsonify({
            "jsonrpc": "2.0",
            "id": rid,
            "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
        })
    
    if method == 'ping':
        return jsonify({"jsonrpc": "2.0", "id": rid, "result": {}})
    
    return jsonify({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "Method not found"}})

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "service": "figma-mcp",
        "token_configured": bool(FIGMA_TOKEN)
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
