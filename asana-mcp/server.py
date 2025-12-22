"""
Asana MCP Server - Direct Asana API access for ABBI
Provides task management tools for Sovereign Mind voice interface
"""

import os
import json
import requests
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("Asana MCP")

# Asana config
ASANA_TOKEN = os.environ.get("ASANA_TOKEN")
ASANA_WORKSPACE_ID = os.environ.get("ASANA_WORKSPACE_ID", "373563495855656")
ASANA_BASE_URL = "https://app.asana.com/api/1.0"

HEADERS = {
    "Authorization": f"Bearer {ASANA_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}


def asana_request(method: str, endpoint: str, data: dict = None, params: dict = None) -> dict:
    """Make authenticated request to Asana API."""
    url = f"{ASANA_BASE_URL}/{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url, headers=HEADERS, params=params)
        elif method == "POST":
            response = requests.post(url, headers=HEADERS, json={"data": data} if data else None)
        elif method == "PUT":
            response = requests.put(url, headers=HEADERS, json={"data": data} if data else None)
        else:
            return {"success": False, "error": f"Unsupported method: {method}"}
        
        if response.status_code in [200, 201]:
            return {"success": True, "data": response.json().get("data", {})}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}: {response.text[:500]}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def get_my_tasks(limit: int = 20) -> str:
    """Get tasks assigned to the current user."""
    result = asana_request("GET", "tasks", params={
        "workspace": ASANA_WORKSPACE_ID,
        "assignee": "me",
        "opt_fields": "name,due_on,completed,projects.name,notes",
        "limit": limit,
        "completed_since": "now"  # Only incomplete tasks
    })
    
    if result["success"]:
        tasks = result["data"]
        formatted = []
        for t in tasks:
            projects = ", ".join([p["name"] for p in t.get("projects", [])]) or "No project"
            formatted.append({
                "gid": t["gid"],
                "name": t["name"],
                "due": t.get("due_on", "No due date"),
                "project": projects,
                "notes": (t.get("notes", "") or "")[:100]
            })
        return json.dumps({"success": True, "tasks": formatted, "count": len(formatted)})
    return json.dumps(result)


@mcp.tool()
def create_task(name: str, project_id: str = None, due_on: str = None, notes: str = None, assignee: str = "me") -> str:
    """Create a new task in Asana.
    
    Args:
        name: Task name
        project_id: Project GID to add task to (optional)
        due_on: Due date in YYYY-MM-DD format (optional)
        notes: Task description (optional)
        assignee: User to assign to, defaults to 'me'
    """
    data = {
        "name": name,
        "workspace": ASANA_WORKSPACE_ID,
        "assignee": assignee
    }
    
    if project_id:
        data["projects"] = [project_id]
    if due_on:
        data["due_on"] = due_on
    if notes:
        data["notes"] = notes
    
    result = asana_request("POST", "tasks", data=data)
    
    if result["success"]:
        task = result["data"]
        return json.dumps({
            "success": True,
            "message": f"Task created: {task['name']}",
            "task_id": task["gid"]
        })
    return json.dumps(result)


@mcp.tool()
def complete_task(task_id: str) -> str:
    """Mark a task as complete."""
    result = asana_request("PUT", f"tasks/{task_id}", data={"completed": True})
    
    if result["success"]:
        return json.dumps({"success": True, "message": "Task marked complete"})
    return json.dumps(result)


@mcp.tool()
def search_tasks(query: str, limit: int = 10) -> str:
    """Search for tasks by name in the workspace."""
    result = asana_request("GET", f"workspaces/{ASANA_WORKSPACE_ID}/tasks/search", params={
        "text": query,
        "opt_fields": "name,due_on,completed,assignee.name,projects.name",
        "limit": limit
    })
    
    if result["success"]:
        tasks = result["data"]
        formatted = []
        for t in tasks:
            formatted.append({
                "gid": t["gid"],
                "name": t["name"],
                "due": t.get("due_on", "No due date"),
                "completed": t.get("completed", False),
                "assignee": t.get("assignee", {}).get("name", "Unassigned")
            })
        return json.dumps({"success": True, "tasks": formatted, "count": len(formatted)})
    return json.dumps(result)


@mcp.tool()
def get_projects(limit: int = 20) -> str:
    """List projects in the workspace."""
    result = asana_request("GET", "projects", params={
        "workspace": ASANA_WORKSPACE_ID,
        "opt_fields": "name,owner.name,due_date,current_status.title",
        "limit": limit,
        "archived": False
    })
    
    if result["success"]:
        projects = result["data"]
        formatted = []
        for p in projects:
            formatted.append({
                "gid": p["gid"],
                "name": p["name"],
                "owner": p.get("owner", {}).get("name", "No owner"),
                "due": p.get("due_date", "No due date")
            })
        return json.dumps({"success": True, "projects": formatted, "count": len(formatted)})
    return json.dumps(result)


@mcp.tool()
def get_project_tasks(project_id: str, limit: int = 50) -> str:
    """Get tasks in a specific project."""
    result = asana_request("GET", f"projects/{project_id}/tasks", params={
        "opt_fields": "name,due_on,completed,assignee.name,notes",
        "limit": limit
    })
    
    if result["success"]:
        tasks = result["data"]
        formatted = []
        for t in tasks:
            formatted.append({
                "gid": t["gid"],
                "name": t["name"],
                "due": t.get("due_on", "No due date"),
                "completed": t.get("completed", False),
                "assignee": t.get("assignee", {}).get("name", "Unassigned")
            })
        return json.dumps({"success": True, "tasks": formatted, "count": len(formatted)})
    return json.dumps(result)


@mcp.tool()
def add_comment(task_id: str, text: str) -> str:
    """Add a comment to a task."""
    result = asana_request("POST", f"tasks/{task_id}/stories", data={"text": text})
    
    if result["success"]:
        return json.dumps({"success": True, "message": "Comment added"})
    return json.dumps(result)


@mcp.tool()
def update_task(task_id: str, name: str = None, due_on: str = None, notes: str = None, assignee: str = None) -> str:
    """Update a task's details."""
    data = {}
    if name:
        data["name"] = name
    if due_on:
        data["due_on"] = due_on
    if notes:
        data["notes"] = notes
    if assignee:
        data["assignee"] = assignee
    
    if not data:
        return json.dumps({"success": False, "error": "No fields to update"})
    
    result = asana_request("PUT", f"tasks/{task_id}", data=data)
    
    if result["success"]:
        return json.dumps({"success": True, "message": "Task updated"})
    return json.dumps(result)


if __name__ == "__main__":
    mcp.run(transport="sse")
