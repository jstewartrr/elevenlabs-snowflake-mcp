"""
NotebookLM MCP Server - Fixed Version v2
Corrects API field naming for sources.batchCreate
"""
import os
import json
import logging
from flask import Flask, request, jsonify
import requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
PROJECT_NUMBER = os.environ.get("GOOGLE_PROJECT_NUMBER", "524579447726")
LOCATION = os.environ.get("GOOGLE_LOCATION", "global")
ENDPOINT_PREFIX = os.environ.get("ENDPOINT_PREFIX", "global")
IMPERSONATE_USER = os.environ.get("IMPERSONATE_USER", "")

# Scopes for NotebookLM
SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/generativelanguage"
]

def get_credentials():
    """Get Google credentials from environment"""
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if not creds_json:
        logger.error("No GOOGLE_CREDENTIALS_JSON found")
        return None
    
    try:
        creds_data = json.loads(creds_json)
        credentials = service_account.Credentials.from_service_account_info(
            creds_data,
            scopes=SCOPES
        )
        
        # Handle domain-wide delegation if impersonating
        if IMPERSONATE_USER:
            credentials = credentials.with_subject(IMPERSONATE_USER)
            logger.info(f"Impersonating user: {IMPERSONATE_USER}")
        
        return credentials
    except Exception as e:
        logger.error(f"Failed to load credentials: {e}")
        return None

def get_access_token():
    """Get OAuth2 access token"""
    credentials = get_credentials()
    if not credentials:
        return None
    
    try:
        credentials.refresh(Request())
        return credentials.token
    except Exception as e:
        logger.error(f"Failed to refresh token: {e}")
        return None

def get_base_url():
    """Construct the NotebookLM API base URL"""
    return f"https://{ENDPOINT_PREFIX}-discoveryengine.googleapis.com/v1alpha/projects/{PROJECT_NUMBER}/locations/{LOCATION}/notebooks"

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "version": "2.0.0-fixed"})

@app.route("/mcp", methods=["POST"])
def mcp_handler():
    """Main MCP SSE endpoint"""
    data = request.get_json() or {}
    
    # Handle MCP protocol
    method = data.get("method", "")
    params = data.get("params", {})
    
    # tools/list - Return available tools
    if method == "tools/list":
        return jsonify({
            "tools": [
                {
                    "name": "list_notebooks",
                    "description": "List recently viewed notebooks",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "get_notebook",
                    "description": "Get notebook details by ID",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "notebook_id": {"type": "string"}
                        },
                        "required": ["notebook_id"]
                    }
                },
                {
                    "name": "create_notebook",
                    "description": "Create a new NotebookLM notebook",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Title for the notebook"}
                        },
                        "required": ["title"]
                    }
                },
                {
                    "name": "add_source",
                    "description": "Add a text source to a notebook",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "notebook_id": {"type": "string"},
                            "content": {"type": "string", "description": "Text content to add"},
                            "title": {"type": "string", "description": "Title for the source"}
                        },
                        "required": ["notebook_id", "content"]
                    }
                },
                {
                    "name": "delete_notebook",
                    "description": "Delete a notebook",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "notebook_id": {"type": "string"}
                        },
                        "required": ["notebook_id"]
                    }
                },
                {
                    "name": "share_notebook",
                    "description": "Share a notebook with users",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "notebook_id": {"type": "string"},
                            "email": {"type": "string"},
                            "role": {"type": "string", "description": "VIEWER or EDITOR"}
                        },
                        "required": ["notebook_id", "email", "role"]
                    }
                }
            ]
        })
    
    # tools/call - Execute a tool
    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        
        result = execute_tool(tool_name, tool_args)
        return jsonify({"content": [{"type": "text", "text": json.dumps(result)}]})
    
    return jsonify({"error": f"Unknown method: {method}"}), 400

def execute_tool(tool_name, args):
    """Execute a tool by name"""
    logger.info(f"Executing tool: {tool_name} with args: {args}")
    
    if tool_name == "list_notebooks":
        return list_notebooks()
    elif tool_name == "get_notebook":
        return get_notebook(args.get("notebook_id"))
    elif tool_name == "create_notebook":
        return create_notebook(args.get("title", "Untitled"))
    elif tool_name == "add_source":
        return add_source(
            args.get("notebook_id"),
            args.get("content"),
            args.get("title", "Text Source")
        )
    elif tool_name == "delete_notebook":
        return delete_notebook(args.get("notebook_id"))
    elif tool_name == "share_notebook":
        return share_notebook(
            args.get("notebook_id"),
            args.get("email"),
            args.get("role", "VIEWER")
        )
    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}

def list_notebooks():
    """List all notebooks"""
    token = get_access_token()
    if not token:
        return {"success": False, "error": "No access token available"}
    
    try:
        resp = requests.get(
            get_base_url(),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )
        return {"success": resp.ok, "data": resp.json()}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_notebook(notebook_id):
    """Get a specific notebook"""
    token = get_access_token()
    if not token:
        return {"success": False, "error": "No access token available"}
    
    try:
        resp = requests.get(
            f"{get_base_url()}/{notebook_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )
        return {"success": resp.ok, "data": resp.json()}
    except Exception as e:
        return {"success": False, "error": str(e)}

def create_notebook(title):
    """Create a new notebook"""
    token = get_access_token()
    if not token:
        return {"success": False, "error": "No access token available"}
    
    try:
        resp = requests.post(
            get_base_url(),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={"title": title}
        )
        logger.info(f"Create notebook response: {resp.status_code} - {resp.text}")
        return {"success": resp.ok, "data": resp.json() if resp.text else {}}
    except Exception as e:
        return {"success": False, "error": str(e)}

def add_source(notebook_id, content, title):
    """
    Add a text source to a notebook - FIXED VERSION
    Uses correct field names: 'content' and 'sourceName'
    (NOT 'inlineContent' and 'displayName' which was the bug)
    """
    token = get_access_token()
    if not token:
        return {"success": False, "error": "No access token available"}
    
    # CORRECT payload structure per Google API docs
    # https://cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/api-notebooks-sources
    payload = {
        "userContents": [
            {
                "textContent": {
                    "sourceName": title,    # FIXED: was "displayName"
                    "content": content      # FIXED: was "inlineContent"
                }
            }
        ]
    }
    
    logger.info(f"Adding source to notebook {notebook_id}")
    logger.info(f"Payload: {json.dumps(payload)}")
    
    try:
        resp = requests.post(
            f"{get_base_url()}/{notebook_id}/sources:batchCreate",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json=payload
        )
        logger.info(f"Add source response: {resp.status_code} - {resp.text}")
        return {"success": resp.ok, "data": resp.json() if resp.text else {}}
    except Exception as e:
        logger.error(f"Add source error: {e}")
        return {"success": False, "error": str(e)}

def delete_notebook(notebook_id):
    """Delete a notebook"""
    token = get_access_token()
    if not token:
        return {"success": False, "error": "No access token available"}
    
    try:
        resp = requests.delete(
            f"{get_base_url()}/{notebook_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )
        return {"success": resp.ok, "data": resp.json() if resp.text else {}}
    except Exception as e:
        return {"success": False, "error": str(e)}

def share_notebook(notebook_id, email, role):
    """Share a notebook with a user"""
    token = get_access_token()
    if not token:
        return {"success": False, "error": "No access token available"}
    
    # This endpoint may vary - check actual API
    try:
        resp = requests.post(
            f"{get_base_url()}/{notebook_id}:share",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={
                "shareSettings": [
                    {"email": email, "role": role}
                ]
            }
        )
        return {"success": resp.ok, "data": resp.json() if resp.text else {}}
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting NotebookLM MCP server on port {port}")
    logger.info(f"Project: {PROJECT_NUMBER}, Location: {LOCATION}")
    logger.info(f"Impersonate user: {IMPERSONATE_USER or 'None'}")
    app.run(host="0.0.0.0", port=port, debug=False)
