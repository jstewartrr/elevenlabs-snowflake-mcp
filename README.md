# Sovereign Mind MCP Proxy for ElevenLabs

Custom MCP server that bridges ElevenLabs Conversational AI to your Snowflake database.

## Architecture

```
ElevenLabs Agent (Abbi)
        │
        ▼
Azure Container App (This Proxy)
        │
        ▼
Snowflake (SOVEREIGN_MIND database)
```

## Deployment Steps

### Step 1: Create GitHub Repository

1. Go to https://github.com/new
2. Create a new repository named `elevenlabs-snowflake-mcp`
3. Upload these three files:
   - `server.py`
   - `requirements.txt`
   - `Dockerfile`

### Step 2: Deploy to Azure Container Apps

1. Go to Azure Portal → **Create a resource** → **Container App**

2. **Basics tab:**
   - Subscription: Your subscription
   - Resource Group: `sovereign-mind-rg` (or existing)
   - Container app name: `elevenlabs-mcp-proxy`
   - Region: East US
   - Container Apps Environment: Create new or use existing

3. **Container tab:**
   - Image source: **GitHub**
   - Connect your GitHub account
   - Select repository: `elevenlabs-snowflake-mcp`
   - Branch: `main`
   - Dockerfile: `Dockerfile`

4. **Environment Variables** (add all of these):

   | Name | Value |
   |------|-------|
   | SNOWFLAKE_ACCOUNT | jga82554.east-us-2.azure |
   | SNOWFLAKE_USER | JOHN_CLAUDE |
   | SNOWFLAKE_PASSWORD | [your password] |
   | SNOWFLAKE_WAREHOUSE | SOVEREIGN_MIND_WH |
   | SNOWFLAKE_DATABASE | SOVEREIGN_MIND |
   | SNOWFLAKE_ROLE | JOHN_CLAUDE |
   | MCP_API_KEY | [generate a secure key] |

5. **Ingress tab:**
   - Ingress: ✅ Enabled
   - Ingress traffic: **Accepting traffic from anywhere**
   - Ingress type: HTTP
   - Target port: 8000

6. Click **Review + create** → **Create**

### Step 3: Get Your Endpoint URL

After deployment, find your URL in Azure Portal:
- Go to your Container App → Overview
- Copy the **Application Url** (e.g., `https://elevenlabs-mcp-proxy.blueocean-xxxxx.eastus.azurecontainerapps.io`)

### Step 4: Configure ElevenLabs

In your ElevenLabs Agent settings, add MCP server:

**Option A: Using MCP Protocol**
```
URL: https://your-app-url.azurecontainerapps.io/mcp
Type: URL
```

**Option B: Using Direct REST (if MCP doesn't work)**
Configure as a custom tool with webhook:
```
URL: https://your-app-url.azurecontainerapps.io/query
Method: POST
Headers: 
  X-API-Key: [your MCP_API_KEY]
Body:
  {"sql": "{{user_query}}"}
```

## Available Tools (MCP Mode)

1. **query_sovereign_mind** - Execute SQL queries
2. **list_schemas** - Show available schemas
3. **list_tables** - Show tables in a schema

## Testing

Test the endpoint with curl:

```bash
# Health check
curl https://your-app-url.azurecontainerapps.io/health

# List schemas
curl https://your-app-url.azurecontainerapps.io/schemas

# Direct query
curl -X POST https://your-app-url.azurecontainerapps.io/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"sql": "SELECT COUNT(*) FROM EMAILS.EMAILS"}'
```

## Troubleshooting

**ElevenLabs can't connect:**
- Check Azure Container App logs for errors
- Verify ingress is set to "Accepting traffic from anywhere"
- Try the /health endpoint to confirm the app is running

**Snowflake errors:**
- Verify environment variables are correct
- Check that JOHN_CLAUDE user has proper permissions
- Test with a simple query like `SELECT 1`
