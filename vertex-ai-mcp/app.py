import os, json, logging, base64
from flask import Flask, request, jsonify, Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = Flask(__name__)

# Load credentials from environment
GOOGLE_CREDENTIALS_JSON = os.environ.get('GOOGLE_CREDENTIALS_JSON', '')
PROJECT_ID = os.environ.get('GOOGLE_PROJECT_ID', 'innate-concept-481918-h9')
LOCATION = os.environ.get('GOOGLE_LOCATION', 'us-central1')

# Initialize clients lazily
_vertexai_initialized = False
_vision_client = None
_documentai_client = None

def init_vertexai():
    global _vertexai_initialized
    if _vertexai_initialized:
        return True
    try:
        import vertexai
        if GOOGLE_CREDENTIALS_JSON:
            import json as json_module
            from google.oauth2 import service_account
            creds_dict = json_module.loads(GOOGLE_CREDENTIALS_JSON)
            credentials = service_account.Credentials.from_service_account_info(creds_dict)
            vertexai.init(project=PROJECT_ID, location=LOCATION, credentials=credentials)
        else:
            vertexai.init(project=PROJECT_ID, location=LOCATION)
        _vertexai_initialized = True
        return True
    except Exception as e:
        logger.error(f"Failed to init Vertex AI: {e}")
        return False

def get_vision_client():
    global _vision_client
    if _vision_client:
        return _vision_client
    try:
        from google.cloud import vision
        if GOOGLE_CREDENTIALS_JSON:
            import json as json_module
            from google.oauth2 import service_account
            creds_dict = json_module.loads(GOOGLE_CREDENTIALS_JSON)
            credentials = service_account.Credentials.from_service_account_info(creds_dict)
            _vision_client = vision.ImageAnnotatorClient(credentials=credentials)
        else:
            _vision_client = vision.ImageAnnotatorClient()
        return _vision_client
    except Exception as e:
        logger.error(f"Failed to init Vision client: {e}")
        return None

def get_documentai_client():
    global _documentai_client
    if _documentai_client:
        return _documentai_client
    try:
        from google.cloud import documentai
        if GOOGLE_CREDENTIALS_JSON:
            import json as json_module
            from google.oauth2 import service_account
            creds_dict = json_module.loads(GOOGLE_CREDENTIALS_JSON)
            credentials = service_account.Credentials.from_service_account_info(creds_dict)
            _documentai_client = documentai.DocumentProcessorServiceClient(credentials=credentials)
        else:
            _documentai_client = documentai.DocumentProcessorServiceClient()
        return _documentai_client
    except Exception as e:
        logger.error(f"Failed to init Document AI client: {e}")
        return None

MCP_TOOLS = [
    # === GEMINI TOOLS ===
    {
        "name": "gemini_generate",
        "description": "Generate text content using Gemini models. Supports gemini-2.0-flash-exp, gemini-1.5-pro, gemini-1.5-flash.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "The prompt to generate content from"},
                "model": {"type": "string", "default": "gemini-2.0-flash-exp", "description": "Model to use"},
                "temperature": {"type": "number", "default": 0.7, "description": "Temperature (0-1)"},
                "max_tokens": {"type": "integer", "default": 8192, "description": "Max output tokens"}
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "gemini_chat",
        "description": "Multi-turn chat conversation with Gemini.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "messages": {"type": "array", "description": "Array of {role, content} messages"},
                "model": {"type": "string", "default": "gemini-2.0-flash-exp"},
                "system_instruction": {"type": "string", "description": "System prompt"}
            },
            "required": ["messages"]
        }
    },
    {
        "name": "gemini_analyze_image",
        "description": "Analyze an image using Gemini's multimodal capabilities.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_base64": {"type": "string", "description": "Base64-encoded image"},
                "prompt": {"type": "string", "description": "Analysis prompt", "default": "Describe this image in detail"},
                "model": {"type": "string", "default": "gemini-2.0-flash-exp"}
            },
            "required": ["image_base64"]
        }
    },
    {
        "name": "gemini_analyze_document",
        "description": "Analyze a document (PDF pages as images) using Gemini.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "document_text": {"type": "string", "description": "Document text content"},
                "analysis_prompt": {"type": "string", "description": "What to analyze"},
                "model": {"type": "string", "default": "gemini-1.5-pro"}
            },
            "required": ["document_text", "analysis_prompt"]
        }
    },
    # === IMAGEN TOOLS ===
    {
        "name": "imagen_generate",
        "description": "Generate images using Imagen 3. Returns base64-encoded images.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Text description of image to generate"},
                "number_of_images": {"type": "integer", "default": 1, "description": "Number of images (1-4)"},
                "aspect_ratio": {"type": "string", "default": "1:1", "enum": ["1:1", "9:16", "16:9", "3:4", "4:3"]},
                "negative_prompt": {"type": "string", "description": "What to avoid in the image"}
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "imagen_edit",
        "description": "Edit an existing image using Imagen.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_base64": {"type": "string", "description": "Base64-encoded source image"},
                "prompt": {"type": "string", "description": "Edit instructions"},
                "mask_base64": {"type": "string", "description": "Optional mask for inpainting"}
            },
            "required": ["image_base64", "prompt"]
        }
    },
    # === VISION AI TOOLS ===
    {
        "name": "vision_ocr",
        "description": "Extract text from an image using Cloud Vision OCR.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_base64": {"type": "string", "description": "Base64-encoded image"},
                "language_hints": {"type": "array", "items": {"type": "string"}, "description": "Language hints (e.g., ['en', 'ja'])"}
            },
            "required": ["image_base64"]
        }
    },
    {
        "name": "vision_detect_labels",
        "description": "Detect labels/objects in an image.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_base64": {"type": "string", "description": "Base64-encoded image"},
                "max_results": {"type": "integer", "default": 10}
            },
            "required": ["image_base64"]
        }
    },
    {
        "name": "vision_detect_objects",
        "description": "Detect and localize objects in an image with bounding boxes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_base64": {"type": "string", "description": "Base64-encoded image"}
            },
            "required": ["image_base64"]
        }
    },
    {
        "name": "vision_detect_faces",
        "description": "Detect faces and facial attributes in an image.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_base64": {"type": "string", "description": "Base64-encoded image"}
            },
            "required": ["image_base64"]
        }
    },
    {
        "name": "vision_detect_logos",
        "description": "Detect logos/brands in an image.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_base64": {"type": "string", "description": "Base64-encoded image"}
            },
            "required": ["image_base64"]
        }
    },
    # === DOCUMENT AI TOOLS ===
    {
        "name": "document_parse_pdf",
        "description": "Parse a PDF document and extract structured text, tables, and form fields using Document AI.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pdf_base64": {"type": "string", "description": "Base64-encoded PDF"},
                "processor_id": {"type": "string", "description": "Document AI processor ID (optional, uses default OCR)"}
            },
            "required": ["pdf_base64"]
        }
    },
    {
        "name": "document_extract_tables",
        "description": "Extract tables from a document image or PDF page.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_base64": {"type": "string", "description": "Base64-encoded image of document page"}
            },
            "required": ["image_base64"]
        }
    },
    # === UTILITY TOOLS ===
    {
        "name": "list_models",
        "description": "List available Vertex AI models.",
        "inputSchema": {"type": "object", "properties": {}}
    }
]

# === GEMINI IMPLEMENTATIONS ===
def gemini_generate(prompt, model="gemini-2.0-flash-exp", temperature=0.7, max_tokens=8192):
    try:
        if not init_vertexai():
            return {"success": False, "error": "Vertex AI not initialized"}
        from vertexai.generative_models import GenerativeModel, GenerationConfig
        gen_model = GenerativeModel(model)
        config = GenerationConfig(temperature=temperature, max_output_tokens=max_tokens)
        response = gen_model.generate_content(prompt, generation_config=config)
        return {"success": True, "text": response.text, "model": model}
    except Exception as e:
        return {"success": False, "error": str(e)}

def gemini_chat(messages, model="gemini-2.0-flash-exp", system_instruction=None):
    try:
        if not init_vertexai():
            return {"success": False, "error": "Vertex AI not initialized"}
        from vertexai.generative_models import GenerativeModel, Content, Part
        gen_model = GenerativeModel(model, system_instruction=system_instruction)
        chat = gen_model.start_chat()
        
        # Process message history
        for msg in messages[:-1]:
            role = "user" if msg.get("role") == "user" else "model"
            chat.history.append(Content(role=role, parts=[Part.from_text(msg.get("content", ""))]))
        
        # Send last message
        last_msg = messages[-1].get("content", "")
        response = chat.send_message(last_msg)
        return {"success": True, "response": response.text, "model": model}
    except Exception as e:
        return {"success": False, "error": str(e)}

def gemini_analyze_image(image_base64, prompt="Describe this image in detail", model="gemini-2.0-flash-exp"):
    try:
        if not init_vertexai():
            return {"success": False, "error": "Vertex AI not initialized"}
        from vertexai.generative_models import GenerativeModel, Part, Image
        gen_model = GenerativeModel(model)
        image_bytes = base64.b64decode(image_base64)
        image_part = Part.from_image(Image.from_bytes(image_bytes))
        response = gen_model.generate_content([prompt, image_part])
        return {"success": True, "analysis": response.text, "model": model}
    except Exception as e:
        return {"success": False, "error": str(e)}

def gemini_analyze_document(document_text, analysis_prompt, model="gemini-1.5-pro"):
    try:
        if not init_vertexai():
            return {"success": False, "error": "Vertex AI not initialized"}
        from vertexai.generative_models import GenerativeModel
        gen_model = GenerativeModel(model)
        full_prompt = f"{analysis_prompt}\n\nDocument content:\n{document_text}"
        response = gen_model.generate_content(full_prompt)
        return {"success": True, "analysis": response.text, "model": model}
    except Exception as e:
        return {"success": False, "error": str(e)}

# === IMAGEN IMPLEMENTATIONS ===
def imagen_generate(prompt, number_of_images=1, aspect_ratio="1:1", negative_prompt=None):
    try:
        if not init_vertexai():
            return {"success": False, "error": "Vertex AI not initialized"}
        from vertexai.preview.vision_models import ImageGenerationModel
        model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-001")
        response = model.generate_images(
            prompt=prompt,
            number_of_images=min(number_of_images, 4),
            aspect_ratio=aspect_ratio,
            negative_prompt=negative_prompt
        )
        images = []
        for img in response.images:
            img_bytes = img._image_bytes
            images.append(base64.b64encode(img_bytes).decode())
        return {"success": True, "images": images, "count": len(images)}
    except Exception as e:
        return {"success": False, "error": str(e)}

def imagen_edit(image_base64, prompt, mask_base64=None):
    try:
        if not init_vertexai():
            return {"success": False, "error": "Vertex AI not initialized"}
        from vertexai.preview.vision_models import ImageGenerationModel, Image
        model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-001")
        source_image = Image(image_bytes=base64.b64decode(image_base64))
        mask_image = Image(image_bytes=base64.b64decode(mask_base64)) if mask_base64 else None
        response = model.edit_image(
            base_image=source_image,
            prompt=prompt,
            mask=mask_image
        )
        images = []
        for img in response.images:
            images.append(base64.b64encode(img._image_bytes).decode())
        return {"success": True, "images": images, "count": len(images)}
    except Exception as e:
        return {"success": False, "error": str(e)}

# === VISION AI IMPLEMENTATIONS ===
def vision_ocr(image_base64, language_hints=None):
    try:
        client = get_vision_client()
        if not client:
            return {"success": False, "error": "Vision client not initialized"}
        from google.cloud import vision
        image = vision.Image(content=base64.b64decode(image_base64))
        image_context = vision.ImageContext(language_hints=language_hints) if language_hints else None
        response = client.text_detection(image=image, image_context=image_context)
        texts = []
        for text in response.text_annotations:
            texts.append({"description": text.description, "locale": text.locale if hasattr(text, 'locale') else None})
        full_text = texts[0]["description"] if texts else ""
        return {"success": True, "full_text": full_text, "annotations": texts[1:] if len(texts) > 1 else []}
    except Exception as e:
        return {"success": False, "error": str(e)}

def vision_detect_labels(image_base64, max_results=10):
    try:
        client = get_vision_client()
        if not client:
            return {"success": False, "error": "Vision client not initialized"}
        from google.cloud import vision
        image = vision.Image(content=base64.b64decode(image_base64))
        response = client.label_detection(image=image, max_results=max_results)
        labels = [{"description": l.description, "score": l.score, "topicality": l.topicality} for l in response.label_annotations]
        return {"success": True, "labels": labels}
    except Exception as e:
        return {"success": False, "error": str(e)}

def vision_detect_objects(image_base64):
    try:
        client = get_vision_client()
        if not client:
            return {"success": False, "error": "Vision client not initialized"}
        from google.cloud import vision
        image = vision.Image(content=base64.b64decode(image_base64))
        response = client.object_localization(image=image)
        objects = []
        for obj in response.localized_object_annotations:
            vertices = [{"x": v.x, "y": v.y} for v in obj.bounding_poly.normalized_vertices]
            objects.append({"name": obj.name, "score": obj.score, "bounding_box": vertices})
        return {"success": True, "objects": objects}
    except Exception as e:
        return {"success": False, "error": str(e)}

def vision_detect_faces(image_base64):
    try:
        client = get_vision_client()
        if not client:
            return {"success": False, "error": "Vision client not initialized"}
        from google.cloud import vision
        image = vision.Image(content=base64.b64decode(image_base64))
        response = client.face_detection(image=image)
        faces = []
        for face in response.face_annotations:
            faces.append({
                "confidence": face.detection_confidence,
                "joy": str(face.joy_likelihood),
                "sorrow": str(face.sorrow_likelihood),
                "anger": str(face.anger_likelihood),
                "surprise": str(face.surprise_likelihood)
            })
        return {"success": True, "faces": faces, "count": len(faces)}
    except Exception as e:
        return {"success": False, "error": str(e)}

def vision_detect_logos(image_base64):
    try:
        client = get_vision_client()
        if not client:
            return {"success": False, "error": "Vision client not initialized"}
        from google.cloud import vision
        image = vision.Image(content=base64.b64decode(image_base64))
        response = client.logo_detection(image=image)
        logos = [{"description": l.description, "score": l.score} for l in response.logo_annotations]
        return {"success": True, "logos": logos}
    except Exception as e:
        return {"success": False, "error": str(e)}

# === DOCUMENT AI IMPLEMENTATIONS ===
def document_parse_pdf(pdf_base64, processor_id=None):
    try:
        client = get_documentai_client()
        if not client:
            return {"success": False, "error": "Document AI client not initialized"}
        from google.cloud import documentai
        
        # Use default OCR processor if none specified
        if not processor_id:
            processor_id = os.environ.get('DOCUMENTAI_PROCESSOR_ID', '')
            if not processor_id:
                return {"success": False, "error": "No Document AI processor ID configured"}
        
        name = f"projects/{PROJECT_ID}/locations/{LOCATION}/processors/{processor_id}"
        raw_document = documentai.RawDocument(content=base64.b64decode(pdf_base64), mime_type="application/pdf")
        request = documentai.ProcessRequest(name=name, raw_document=raw_document)
        result = client.process_document(request=request)
        
        document = result.document
        return {
            "success": True,
            "text": document.text,
            "pages": len(document.pages),
            "entities": [{"type": e.type_, "text": e.mention_text} for e in document.entities] if document.entities else []
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def document_extract_tables(image_base64):
    try:
        # Use Vision API for table detection from images
        client = get_vision_client()
        if not client:
            return {"success": False, "error": "Vision client not initialized"}
        from google.cloud import vision
        image = vision.Image(content=base64.b64decode(image_base64))
        response = client.document_text_detection(image=image)
        
        # Extract text blocks that might be tables
        pages = response.full_text_annotation.pages if response.full_text_annotation else []
        tables = []
        for page in pages:
            for block in page.blocks:
                if block.block_type == vision.Block.BlockType.TABLE:
                    tables.append({"type": "table", "confidence": block.confidence})
        
        return {"success": True, "text": response.full_text_annotation.text if response.full_text_annotation else "", "tables_detected": len(tables)}
    except Exception as e:
        return {"success": False, "error": str(e)}

def list_models():
    return {
        "success": True,
        "models": {
            "gemini": ["gemini-2.0-flash-exp", "gemini-1.5-pro-002", "gemini-1.5-flash-002"],
            "imagen": ["imagen-3.0-generate-001"],
            "vision": ["Cloud Vision API v1"],
            "document_ai": ["Document AI API v1"]
        }
    }

# === MCP ENDPOINTS ===
@app.route('/mcp', methods=['GET'])
def mcp_sse():
    return Response(
        f"data: {json.dumps({'jsonrpc':'2.0','method':'notifications/initialized','params':{'serverInfo':{'name':'vertex-ai-mcp','version':'2.0.0'},'capabilities':{'tools':{}}}})}\n\n",
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
                "serverInfo": {"name": "vertex-ai-mcp", "version": "2.0.0"},
                "capabilities": {"tools": {}}
            }
        })
    
    if method == 'tools/list':
        return jsonify({"jsonrpc": "2.0", "id": rid, "result": {"tools": MCP_TOOLS}})
    
    if method == 'tools/call':
        name = params.get('name')
        args = params.get('arguments', {})
        
        tool_map = {
            "gemini_generate": gemini_generate,
            "gemini_chat": gemini_chat,
            "gemini_analyze_image": gemini_analyze_image,
            "gemini_analyze_document": gemini_analyze_document,
            "imagen_generate": imagen_generate,
            "imagen_edit": imagen_edit,
            "vision_ocr": vision_ocr,
            "vision_detect_labels": vision_detect_labels,
            "vision_detect_objects": vision_detect_objects,
            "vision_detect_faces": vision_detect_faces,
            "vision_detect_logos": vision_detect_logos,
            "document_parse_pdf": document_parse_pdf,
            "document_extract_tables": document_extract_tables,
            "list_models": list_models
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
        "service": "vertex-ai-mcp",
        "version": "2.0.0",
        "project": PROJECT_ID,
        "features": ["gemini", "imagen", "vision", "document_ai"]
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
