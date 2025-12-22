import os, json, logging, requests
from flask import Flask, request, jsonify, Response
from google.oauth2 import service_account
from google.auth.transport.requests import Request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = Flask(__name__)

GOOGLE_CREDENTIALS_JSON = os.environ.get('GOOGLE_CREDENTIALS_JSON', '{}')
GOOGLE_PROJECT_NUMBER = os.environ.get('GOOGLE_PROJECT_NUMBER', '524579447726')
GOOGLE_LOCATION = os.environ.get('GOOGLE_LOCATION', 'global')
IMPERSONATE_USER = os.environ.get('IMPERSONATE_USER', '')  # e.g., jstewart@middleground.com

SCOPES = ['https://www.googleapis.com/auth/cloud-platform']
BASE_URL = f"https://{GOOGLE_LOCATION}-discoveryengine.googleapis.com/v1alpha/projects/{GOOGLE_PROJECT_NUMBER}/locations/{GOOGLE_LOCATION}"

credentials = None
try:
    credentials_info = json.loads(GOOGLE_CREDENTIALS_JSON)
    if IMPERSONATE_USER:
        # Domain-wide delegation: impersonate user
        credentials = service_account.Credentials.from_service_account_info(
            credentials_info, 
            scopes=SCOPES,
            subject=IMPERSONATE_USER
        )
        logger.info(f"Initialized credentials impersonating: {IMPERSONATE_USER}")
    else:
        credentials = service_account.Credentials.from_service_account_info(credentials_info, scopes=SCOPES)
        logger.info(f"Initialized credentials for project: {GOOGLE_PROJECT_NUMBER}")
except Exception as e:
    logger.error(f"Init failed: {e}")

def get_headers():
    if credentials:
        credentials.refresh(Request())
        return {"Authorization": f"Bearer {credentials.token}", "Content-Type": "application/json"}
    return {}

MCP_TOOLS = [
    {"name": "create_notebook", "description": "Create a new NotebookLM notebook", "inputSchema": {"type": "object", "properties": {"title": {"type": "string", "description": "Title for the notebook"}}, "required": ["title"]}},
    {"name": "get_notebook", "description": "Get notebook details by ID", "inputSchema": {"type": "object", "properties": {"notebook_id": {"type": "string"}}, "required": ["notebook_id"]}},
    {"name": "list_notebooks", "description": "List recently viewed notebooks", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "add_source", "description": "Add a text source to a notebook", "inputSchema": {"type": "object", "properties": {"notebook_id": {"type": "string"}, "content": {"type": "string", "description": "Text content to add"}, "title": {"type": "string", "description": "Title for the source"}}, "required": ["notebook_id", "content"]}},
    {"name": "add_web_source", "description": "Add a web URL as source to a notebook", "inputSchema": {"type": "object", "properties": {"notebook_id": {"type": "string"}, "url": {"type": "string", "description": "URL of web content"}, "title": {"type": "string", "description": "Display name for the source"}}, "required": ["notebook_id", "url"]}},
    {"name": "add_youtube_source", "description": "Add a YouTube video as source to a notebook", "inputSchema": {"type": "object", "properties": {"notebook_id": {"type": "string"}, "url": {"type": "string", "description": "YouTube video URL"}}, "required": ["notebook_id", "url"]}},
    {"name": "delete_notebook", "description": "Delete a notebook", "inputSchema": {"type": "object", "properties": {"notebook_id": {"type": "string"}}, "required": ["notebook_id"]}},
    {"name": "share_notebook", "description": "Share a notebook with users", "inputSchema": {"type": "object", "properties": {"notebook_id": {"type": "string"}, "email": {"type": "string"}, "role": {"type": "string", "description": "VIEWER or EDITOR"}}, "required": ["notebook_id", "email", "role"]}}
]

def create_notebook(title):
    try:
        r = requests.post(f"{BASE_URL}/notebooks", headers=get_headers(), json={"title": title})
        return {"success": r.ok, "data": r.json() if r.ok else r.text}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_notebook(notebook_id):
    try:
        r = requests.get(f"{BASE_URL}/notebooks/{notebook_id}", headers=get_headers())
        return {"success": r.ok, "data": r.json() if r.ok else r.text}
    except Exception as e:
        return {"success": False, "error": str(e)}

def list_notebooks():
    try:
        r = requests.get(f"{BASE_URL}/notebooks:listRecentlyViewed", headers=get_headers())
        return {"success": r.ok, "data": r.json() if r.ok else r.text}
    except Exception as e:
        return {"success": False, "error": str(e)}

def add_source(notebook_id, content, title="Untitled"):
    """Add raw text content as a source - uses textContent per Google API docs"""
    try:
        payload = {"userContents": [{"textContent": {"sourceName": title, "content": content}}]}
        r = requests.post(f"{BASE_URL}/notebooks/{notebook_id}/sources:batchCreate", headers=get_headers(), json=payload)
        return {"success": r.ok, "data": r.json() if r.ok else r.text}
    except Exception as e:
        return {"success": False, "error": str(e)}

def add_web_source(notebook_id, url, title="Web Source"):
    """Add web URL as a source"""
    try:
        payload = {"userContents": [{"webContent": {"url": url, "sourceName": title}}]}
        r = requests.post(f"{BASE_URL}/notebooks/{notebook_id}/sources:batchCreate", headers=get_headers(), json=payload)
        return {"success": r.ok, "data": r.json() if r.ok else r.text}
    except Exception as e:
        return {"success": False, "error": str(e)}

def add_youtube_source(notebook_id, url):
    """Add YouTube video as a source"""
    try:
        payload = {"userContents": [{"videoContent": {"url": url}}]}
        r = requests.post(f"{BASE_URL}/notebooks/{notebook_id}/sources:batchCreate", headers=get_headers(), json=payload)
        return {"success": r.ok, "data": r.json() if r.ok else r.text}
    except Exception as e:
        return {"success": False, "error": str(e)}

def delete_notebook(notebook_id):
    try:
        r = requests.delete(f"{BASE_URL}/notebooks/{notebook_id}", headers=get_headers())
        return {"success": r.ok, "data": "Deleted" if r.ok else r.text}
    except Exception as e:
        return {"success": False, "error": str(e)}

def share_notebook(notebook_id, email, role="VIEWER"):
    try:
        payload = {"accountAndRoles": [{"email": email, "role": role}]}
        r = requests.post(f"{BASE_URL}/notebooks/{notebook_id}:share", headers=get_headers(), json=payload)
        return {"success": r.ok, "data": r.json() if r.ok else r.text}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.route('/mcp', methods=['GET'])
def mcp_sse():
    return Response(f"data: {json.dumps({'jsonrpc':'2.0','method':'notifications/initialized','params':{'serverInfo':{'name':'notebooklm-mcp','version':'1.1.0'},'capabilities':{'tools':{}}}})}\n\n", mimetype='text/event-stream')

@app.route('/mcp', methods=['POST'])
def mcp_post():
    data = request.get_json()
    method, params, rid = data.get('method',''), data.get('params',{}), data.get('id')
    if method == 'initialize': return jsonify({"jsonrpc":"2.0","id":rid,"result":{"protocolVersion":"2024-11-05","serverInfo":{"name":"notebooklm-mcp","version":"1.1.0"},"capabilities":{"tools":{}}}})
    if method == 'tools/list': return jsonify({"jsonrpc":"2.0","id":rid,"result":{"tools":MCP_TOOLS}})
    if method == 'tools/call':
        n, a = params.get('name'), params.get('arguments',{})
        if n=='create_notebook': r = create_notebook(**a)
        elif n=='get_notebook': r = get_notebook(**a)
        elif n=='list_notebooks': r = list_notebooks()
        elif n=='add_source': r = add_source(**a)
        elif n=='add_web_source': r = add_web_source(**a)
        elif n=='add_youtube_source': r = add_youtube_source(**a)
        elif n=='delete_notebook': r = delete_notebook(**a)
        elif n=='share_notebook': r = share_notebook(**a)
        else: r = {"error":"Unknown tool"}
        return jsonify({"jsonrpc":"2.0","id":rid,"result":{"content":[{"type":"text","text":json.dumps(r,indent=2)}]}})
    if method == 'ping': return jsonify({"jsonrpc":"2.0","id":rid,"result":{}})
    return jsonify({"jsonrpc":"2.0","id":rid,"error":{"code":-32601,"message":"Method not found"}})

@app.route('/health', methods=['GET'])
def health(): return jsonify({"status":"healthy","service":"notebooklm-mcp","version":"1.1.0","impersonating":IMPERSONATE_USER or "none"})

if __name__ == '__main__': app.run(host='0.0.0.0', port=int(os.environ.get('PORT',8080)))
