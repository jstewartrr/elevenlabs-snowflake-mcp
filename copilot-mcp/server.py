"""
Copilot MCP Server - Azure OpenAI + Snowflake Hive Mind Integration
Provides GPT-4o access with Sovereign Mind shared memory
"""

import os
import json
from datetime import datetime
from mcp.server.fastmcp import FastMCP
import snowflake.connector
from openai import AzureOpenAI

# Initialize FastMCP server
mcp = FastMCP("Copilot Hive Mind MCP")

# Snowflake connection config
SNOWFLAKE_CONFIG = {
    "account": os.environ.get("SNOWFLAKE_ACCOUNT", "FVPTNGS-GIB78586"),
    "user": os.environ.get("SNOWFLAKE_USER", "JOHN_COPILOT"),
    "password": os.environ.get("SNOWFLAKE_PASSWORD"),
    "warehouse": os.environ.get("SNOWFLAKE_WAREHOUSE", "SOVEREIGN_MIND_WH"),
    "database": os.environ.get("SNOWFLAKE_DATABASE", "SOVEREIGN_MIND"),
    "schema": os.environ.get("SNOWFLAKE_SCHEMA", "RAW"),
}

# Azure OpenAI config
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "https://eastus.api.cognitive.microsoft.com/")
AZURE_OPENAI_KEY = os.environ.get("AZURE_OPENAI_KEY")
AZURE_OPENAI_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
AZURE_OPENAI_API_VERSION = "2024-08-06"


def get_snowflake_connection():
    return snowflake.connector.connect(**SNOWFLAKE_CONFIG)


def get_azure_client():
    return AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_KEY,
        api_version=AZURE_OPENAI_API_VERSION
    )


@mcp.tool()
def query_snowflake(sql: str) -> str:
    """Execute SQL query against Snowflake databases."""
    try:
        conn = get_snowflake_connection()
        cursor = conn.cursor()
        cursor.execute(sql)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        results = [dict(zip(columns, row)) for row in rows]
        cursor.close()
        conn.close()
        return json.dumps({"success": True, "data": results, "row_count": len(results)}, default=str)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def read_shared_memory(limit: int = 20, category: str = None, workstream: str = None) -> str:
    """Read from Hive Mind shared memory."""
    try:
        conn = get_snowflake_connection()
        cursor = conn.cursor()
        query = "SELECT ID, SOURCE, CATEGORY, WORKSTREAM, SUMMARY, STATUS, CREATED_AT FROM SOVEREIGN_MIND.RAW.SHARED_MEMORY WHERE 1=1"
        if category:
            query += f" AND CATEGORY = '{category}'"
        if workstream:
            query += f" AND WORKSTREAM ILIKE '%{workstream}%'"
        query += f" ORDER BY CREATED_AT DESC LIMIT {limit}"
        cursor.execute(query)
        columns = [desc[0] for desc in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return json.dumps({"success": True, "data": results, "row_count": len(results)}, default=str)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def write_to_hive_mind(category: str, workstream: str, summary: str, priority: str = "MEDIUM", status: str = "ACTIVE") -> str:
    """Write entry to Hive Mind shared memory."""
    try:
        conn = get_snowflake_connection()
        cursor = conn.cursor()
        query = f"""INSERT INTO SOVEREIGN_MIND.RAW.SHARED_MEMORY (SOURCE, CATEGORY, WORKSTREAM, SUMMARY, PRIORITY, STATUS)
                    SELECT 'COPILOT', '{category}', '{workstream}', '{summary.replace("'", "''")}', '{priority}', '{status}'"""
        cursor.execute(query)
        conn.commit()
        cursor.close()
        conn.close()
        return json.dumps({"success": True, "message": f"Entry written: {category}/{workstream}"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def gpt4o_generate(prompt: str, system_message: str = None, temperature: float = 0.7, max_tokens: int = 4096) -> str:
    """Generate content using Azure OpenAI GPT-4o."""
    try:
        client = get_azure_client()
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return json.dumps({
            "success": True,
            "response": response.choices[0].message.content,
            "usage": {"total_tokens": response.usage.total_tokens}
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def gpt4o_with_hive_mind(prompt: str, include_context: bool = True) -> str:
    """Generate with GPT-4o and automatic Hive Mind context injection."""
    try:
        system_message = """You are an AI assistant integrated with the Sovereign Mind Hive Mind system.
Address the user as 'Your Grace'. Be direct, concise, and results-oriented."""
        
        if include_context:
            conn = get_snowflake_connection()
            cursor = conn.cursor()
            cursor.execute("""SELECT SOURCE, WORKSTREAM, SUMMARY FROM SOVEREIGN_MIND.RAW.SHARED_MEMORY
                            WHERE STATUS IN ('ACTIVE', 'IN_PROGRESS') ORDER BY CREATED_AT DESC LIMIT 10""")
            entries = cursor.fetchall()
            cursor.close()
            conn.close()
            context = "\n\nRecent Hive Mind Context:\n"
            for e in entries:
                context += f"- [{e[0]}] {e[1]}: {e[2][:200]}...\n"
            system_message += context
        
        client = get_azure_client()
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[{"role": "system", "content": system_message}, {"role": "user", "content": prompt}],
            temperature=0.7, max_tokens=4096
        )
        return json.dumps({"success": True, "response": response.choices[0].message.content})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def get_hive_mind_context() -> str:
    """Get full Hive Mind context summary."""
    try:
        conn = get_snowflake_connection()
        cursor = conn.cursor()
        cursor.execute("""SELECT SOURCE, CATEGORY, WORKSTREAM, SUMMARY, STATUS FROM SOVEREIGN_MIND.RAW.SHARED_MEMORY
                        WHERE STATUS IN ('ACTIVE', 'IN_PROGRESS', 'PLANNING') ORDER BY CREATED_AT DESC LIMIT 15""")
        columns = [desc[0] for desc in cursor.description]
        entries = [dict(zip(columns, row)) for row in cursor.fetchall()]
        cursor.execute("SELECT SOURCE, COUNT(*) FROM SOVEREIGN_MIND.RAW.SHARED_MEMORY GROUP BY SOURCE")
        sources = {row[0]: row[1] for row in cursor.fetchall()}
        cursor.close()
        conn.close()
        return json.dumps({
            "success": True, "hive_mind_status": "ACTIVE", "connected_sources": sources,
            "recent_active_entries": entries,
            "owner_preferences": {"address_as": "Your Grace", "communication": "Direct, concise"}
        }, default=str)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=8000)
