"""
Sovereign Mind Asana MCP Server
Uses official MCP SDK with SSE transport for ElevenLabs integration
Modeled after the working Snowflake MCP server
"""

import os
import json
import logging
import httpx
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.responses import JSONResponse
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create MCP server
mcp = FastMCP("Sovereign Mind Asana")

# Asana configuration from environment
ASANA_TOKEN = os.environ.get("ASANA_TOKEN")
ASANA_WORKSPACE_ID = os.environ.get("ASANA_WORKSPACE_ID", "373563495855656")
ASANA_BASE_URL = "https://app.asana.com/api/1.0"

def get_headers():
    """Get Asana API headers"""
    return {
        "Authorization": f"Bearer {ASANA_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


@mcp.tool()
def get_my_tasks() -> str:
    """
    Get tasks assigned to me in Asana.
    Returns a list of tasks with names, due dates, and project info.
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            # Get current user
            user_resp = client.get(f"{ASANA_BASE_URL}/users/me", headers=get_headers())
            user_data = user_resp.json()
            user_gid = user_data.get("data", {}).get("gid")
            
            # Get tasks assigned to user
            params = {
                "workspace": ASANA_WORKSPACE_ID,
                "assignee": user_gid,
                "opt_fields": "name,due_on,completed,projects.name,notes"
            }
            resp = client.get(f"{ASANA_BASE_URL}/tasks", headers=get_headers(), params=params)
            data = resp.json()
            
            tasks = data.get("data", [])
            return json.dumps({"success": True, "tasks": tasks, "count": len(tasks)}, indent=2)
    except Exception as e:
        logger.error(f"Error getting tasks: {e}")
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def create_task(name: str, notes: str = "", due_on: str = None, project_id: str = None) -> str:
    """
    Create a new task in Asana.
    
    Args:
        name: Task name/title
        notes: Task description (optional)
        due_on: Due date in YYYY-MM-DD format (optional)
        project_id: Project GID to add task to (optional)
    
    Returns:
        JSON with created task details
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            # Get current user
            user_resp = client.get(f"{ASANA_BASE_URL}/users/me", headers=get_headers())
            user_data = user_resp.json()
            user_gid = user_data.get("data", {}).get("gid")
            
            task_data = {
                "data": {
                    "name": name,
                    "notes": notes,
                    "workspace": ASANA_WORKSPACE_ID,
                    "assignee": user_gid
                }
            }
            
            if due_on:
                task_data["data"]["due_on"] = due_on
            if project_id:
                task_data["data"]["projects"] = [project_id]
            
            resp = client.post(f"{ASANA_BASE_URL}/tasks", headers=get_headers(), json=task_data)
            data = resp.json()
            
            return json.dumps({"success": True, "task": data.get("data", {})}, indent=2)
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def complete_task(task_id: str) -> str:
    """
    Mark a task as complete.
    
    Args:
        task_id: The Asana task GID
    
    Returns:
        JSON with confirmation
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            update_data = {"data": {"completed": True}}
            resp = client.put(f"{ASANA_BASE_URL}/tasks/{task_id}", headers=get_headers(), json=update_data)
            data = resp.json()
            
            return json.dumps({"success": True, "task": data.get("data", {})}, indent=2)
    except Exception as e:
        logger.error(f"Error completing task: {e}")
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def search_tasks(query: str) -> str:
    """
    Search for tasks by name.
    
    Args:
        query: Search query string
    
    Returns:
        JSON with matching tasks
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            params = {
                "text": query,
                "opt_fields": "name,due_on,completed,assignee.name,projects.name"
            }
            resp = client.get(
                f"{ASANA_BASE_URL}/workspaces/{ASANA_WORKSPACE_ID}/tasks/search",
                headers=get_headers(),
                params=params
            )
            data = resp.json()
            
            tasks = data.get("data", [])
            return json.dumps({"success": True, "tasks": tasks, "count": len(tasks)}, indent=2)
    except Exception as e:
        logger.error(f"Error searching tasks: {e}")
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def get_projects() -> str:
    """
    Get all projects in the workspace.
    
    Returns:
        JSON with list of projects
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            params = {"workspace": ASANA_WORKSPACE_ID, "opt_fields": "name,owner.name,archived"}
            resp = client.get(f"{ASANA_BASE_URL}/projects", headers=get_headers(), params=params)
            data = resp.json()
            
            projects = data.get("data", [])
            return json.dumps({"success": True, "projects": projects, "count": len(projects)}, indent=2)
    except Exception as e:
        logger.error(f"Error getting projects: {e}")
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def get_project_tasks(project_id: str) -> str:
    """
    Get all tasks in a specific project.
    
    Args:
        project_id: The Asana project GID
    
    Returns:
        JSON with list of tasks in the project
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            params = {"opt_fields": "name,due_on,completed,assignee.name,notes"}
            resp = client.get(
                f"{ASANA_BASE_URL}/projects/{project_id}/tasks",
                headers=get_headers(),
                params=params
            )
            data = resp.json()
            
            tasks = data.get("data", [])
            return json.dumps({"success": True, "tasks": tasks, "count": len(tasks)}, indent=2)
    except Exception as e:
        logger.error(f"Error getting project tasks: {e}")
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def add_comment(task_id: str, text: str) -> str:
    """
    Add a comment to a task.
    
    Args:
        task_id: The Asana task GID
        text: Comment text
    
    Returns:
        JSON with confirmation
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            story_data = {"data": {"text": text}}
            resp = client.post(
                f"{ASANA_BASE_URL}/tasks/{task_id}/stories",
                headers=get_headers(),
                json=story_data
            )
            data = resp.json()
            
            return json.dumps({"success": True, "story": data.get("data", {})}, indent=2)
    except Exception as e:
        logger.error(f"Error adding comment: {e}")
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def update_task(task_id: str, name: str = None, notes: str = None, due_on: str = None, assignee: str = None) -> str:
    """
    Update task details.
    
    Args:
        task_id: The Asana task GID
        name: New task name (optional)
        notes: New task notes (optional)
        due_on: New due date YYYY-MM-DD (optional)
        assignee: New assignee user GID (optional)
    
    Returns:
        JSON with updated task
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            update_data = {"data": {}}
            if name:
                update_data["data"]["name"] = name
            if notes:
                update_data["data"]["notes"] = notes
            if due_on:
                update_data["data"]["due_on"] = due_on
            if assignee:
                update_data["data"]["assignee"] = assignee
            
            resp = client.put(f"{ASANA_BASE_URL}/tasks/{task_id}", headers=get_headers(), json=update_data)
            data = resp.json()
            
            return json.dumps({"success": True, "task": data.get("data", {})}, indent=2)
    except Exception as e:
        logger.error(f"Error updating task: {e}")
        return json.dumps({"success": False, "error": str(e)})


# Create SSE transport for MCP - same pattern as Snowflake MCP
sse_transport = SseServerTransport("/messages/")


async def handle_sse(request):
    """Handle SSE connection for MCP protocol"""
    logger.info("New SSE connection established")
    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await mcp._mcp_server.run(
            streams[0], 
            streams[1],
            mcp._mcp_server.create_initialization_options()
        )


async def handle_root(request):
    """Health check endpoint"""
    return JSONResponse({"status": "Sovereign Mind Asana MCP Server running", "transport": "SSE"})


# Create Starlette app with proper MCP SSE routes - same as Snowflake MCP
app = Starlette(
    routes=[
        Route("/", endpoint=handle_root),
        Route("/sse", endpoint=handle_sse),
        Mount("/messages", app=sse_transport.handle_post_message),
    ]
)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
