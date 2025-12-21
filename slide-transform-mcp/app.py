import os, json, logging, requests, base64, io
from flask import Flask, request, jsonify, Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = Flask(__name__)

# Vectorizer.AI credentials
VECTORIZER_API_ID = os.environ.get('VECTORIZER_API_ID', '')
VECTORIZER_API_SECRET = os.environ.get('VECTORIZER_API_SECRET', '')

# Remove.bg API (optional)
REMOVEBG_API_KEY = os.environ.get('REMOVEBG_API_KEY', '')

MCP_TOOLS = [
    {
        "name": "vectorize_image",
        "description": "Convert a raster image (PNG/JPG) to vector SVG using Vectorizer.AI. Returns SVG content.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_url": {"type": "string", "description": "URL of the image to vectorize"},
                "image_base64": {"type": "string", "description": "Base64-encoded image data (alternative to URL)"},
                "output_format": {"type": "string", "enum": ["svg", "pdf", "eps", "dxf"], "default": "svg"},
                "processing_mode": {"type": "string", "enum": ["production", "preview"], "default": "production"}
            }
        }
    },
    {
        "name": "remove_background",
        "description": "Remove background from an image using remove.bg API. Returns PNG with transparent background.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_url": {"type": "string", "description": "URL of the image"},
                "image_base64": {"type": "string", "description": "Base64-encoded image data"}
            }
        }
    },
    {
        "name": "analyze_slide_for_redesign",
        "description": "Analyze a slide image and return suggestions for redesign including color scheme, layout, and graphics improvements.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_base64": {"type": "string", "description": "Base64-encoded slide image"},
                "brand_colors": {"type": "string", "description": "Brand colors to use (e.g., '#003366,#FF6600')"},
                "style": {"type": "string", "enum": ["corporate", "modern", "minimal", "bold"], "default": "corporate"}
            },
            "required": ["image_base64"]
        }
    },
    {
        "name": "extract_slide_elements",
        "description": "Extract text and graphic elements from a slide image for reconstruction.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_base64": {"type": "string", "description": "Base64-encoded slide image"}
            },
            "required": ["image_base64"]
        }
    },
    {
        "name": "get_credits_balance",
        "description": "Check remaining Vectorizer.AI API credits.",
        "inputSchema": {"type": "object", "properties": {}}
    }
]

def vectorize_image(image_url=None, image_base64=None, output_format="svg", processing_mode="production"):
    """Vectorize an image using Vectorizer.AI"""
    try:
        if not VECTORIZER_API_ID or not VECTORIZER_API_SECRET:
            return {"success": False, "error": "Vectorizer.AI credentials not configured"}
        
        auth = (VECTORIZER_API_ID, VECTORIZER_API_SECRET)
        
        data = {
            "output.file_format": output_format,
            "processing.mode": processing_mode
        }
        
        if image_url:
            data["image.url"] = image_url
            response = requests.post(
                "https://api.vectorizer.ai/api/v1/vectorize",
                auth=auth,
                data=data,
                timeout=120
            )
        elif image_base64:
            # Decode base64 and send as file
            image_data = base64.b64decode(image_base64)
            files = {"image": ("image.png", io.BytesIO(image_data), "image/png")}
            response = requests.post(
                "https://api.vectorizer.ai/api/v1/vectorize",
                auth=auth,
                data=data,
                files=files,
                timeout=120
            )
        else:
            return {"success": False, "error": "Either image_url or image_base64 required"}
        
        if response.status_code == 200:
            if output_format == "svg":
                return {"success": True, "svg_content": response.text, "format": "svg"}
            else:
                return {"success": True, "content_base64": base64.b64encode(response.content).decode(), "format": output_format}
        else:
            return {"success": False, "error": f"API error {response.status_code}: {response.text}"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

def remove_background(image_url=None, image_base64=None):
    """Remove background using remove.bg"""
    try:
        if not REMOVEBG_API_KEY:
            return {"success": False, "error": "remove.bg API key not configured"}
        
        headers = {"X-Api-Key": REMOVEBG_API_KEY}
        
        if image_url:
            data = {"image_url": image_url, "size": "auto"}
            response = requests.post(
                "https://api.remove.bg/v1.0/removebg",
                headers=headers,
                data=data,
                timeout=60
            )
        elif image_base64:
            data = {"image_file_b64": image_base64, "size": "auto"}
            response = requests.post(
                "https://api.remove.bg/v1.0/removebg",
                headers=headers,
                data=data,
                timeout=60
            )
        else:
            return {"success": False, "error": "Either image_url or image_base64 required"}
        
        if response.status_code == 200:
            return {"success": True, "image_base64": base64.b64encode(response.content).decode()}
        else:
            return {"success": False, "error": f"API error {response.status_code}: {response.text}"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

def analyze_slide_for_redesign(image_base64, brand_colors=None, style="corporate"):
    """Return analysis prompt - actual AI analysis done by calling Gemini MCP"""
    return {
        "success": True,
        "analysis_prompt": f"""Analyze this slide image for redesign. 
Style preference: {style}
Brand colors: {brand_colors or 'Use professional corporate colors'}

Please identify:
1. Main title and subtitle text
2. Key content points/bullet items  
3. Any graphics, charts, or images present
4. Current color scheme
5. Layout structure

Then suggest:
1. Improved layout for better visual hierarchy
2. Color scheme adjustments (using brand colors if provided)
3. Graphics that could be added or improved
4. Typography recommendations
5. Specific improvements for each element""",
        "note": "Use this prompt with Gemini MCP to analyze the slide image"
    }

def extract_slide_elements(image_base64):
    """Return extraction prompt - actual OCR done by calling Gemini MCP"""
    return {
        "success": True,
        "extraction_prompt": """Extract all elements from this slide image:

1. TEXT ELEMENTS:
   - Title text (exact wording)
   - Subtitle text
   - Body text / bullet points
   - Footer/header text
   - Any labels or captions

2. GRAPHIC ELEMENTS:
   - Charts (type, approximate data)
   - Images (describe content)
   - Icons (describe each)
   - Shapes (rectangles, circles, arrows)
   - Logos

3. LAYOUT:
   - Element positions (top-left, center, etc.)
   - Approximate sizes
   - Alignment patterns

Return as structured JSON.""",
        "note": "Use this prompt with Gemini MCP to extract slide elements"
    }

def get_credits_balance():
    """Check Vectorizer.AI credits"""
    try:
        if not VECTORIZER_API_ID or not VECTORIZER_API_SECRET:
            return {"success": False, "error": "Credentials not configured"}
        
        auth = (VECTORIZER_API_ID, VECTORIZER_API_SECRET)
        response = requests.get(
            "https://api.vectorizer.ai/api/v1/account",
            auth=auth,
            timeout=30
        )
        
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        else:
            return {"success": False, "error": f"API error {response.status_code}: {response.text}"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.route('/mcp', methods=['GET'])
def mcp_sse():
    return Response(
        f"data: {json.dumps({'jsonrpc':'2.0','method':'notifications/initialized','params':{'serverInfo':{'name':'slide-transform-mcp','version':'1.0.0'},'capabilities':{'tools':{}}}})}\n\n",
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
                "serverInfo": {"name": "slide-transform-mcp", "version": "1.0.0"},
                "capabilities": {"tools": {}}
            }
        })
    
    if method == 'tools/list':
        return jsonify({"jsonrpc": "2.0", "id": rid, "result": {"tools": MCP_TOOLS}})
    
    if method == 'tools/call':
        name = params.get('name')
        args = params.get('arguments', {})
        
        if name == 'vectorize_image':
            result = vectorize_image(**args)
        elif name == 'remove_background':
            result = remove_background(**args)
        elif name == 'analyze_slide_for_redesign':
            result = analyze_slide_for_redesign(**args)
        elif name == 'extract_slide_elements':
            result = extract_slide_elements(**args)
        elif name == 'get_credits_balance':
            result = get_credits_balance()
        else:
            result = {"error": "Unknown tool"}
        
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
        "service": "slide-transform-mcp",
        "vectorizer_configured": bool(VECTORIZER_API_ID),
        "removebg_configured": bool(REMOVEBG_API_KEY)
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
