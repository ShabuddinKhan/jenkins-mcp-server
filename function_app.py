
import json
import logging
import os
import requests
import azure.functions as func

# MCP FunctionApp instance
app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

# Tool property definitions for MCP tool triggers
_JENKINS_SERVER_PROPERTY = "jenkinsServerFQDN"
_SEARCH_STRING_PROPERTY = "searchString"

class ToolProperty:
    def __init__(self, property_name: str, property_type: str, description: str):
        self.propertyName = property_name
        self.propertyType = property_type
        self.description = description

    def to_dict(self):
        return {
            "propertyName": self.propertyName,
            "propertyType": self.propertyType,
            "description": self.description,
        }

tool_properties_list_jobs = [
    ToolProperty(_JENKINS_SERVER_PROPERTY, "string", "The FQDN of the Jenkins server."),
    ToolProperty(_SEARCH_STRING_PROPERTY, "string", "Optional: Filter jobs by name containing this string."),
]
tool_properties_list_jobs_json = json.dumps([prop.to_dict() for prop in tool_properties_list_jobs])

def get_jenkins_token():
    """
    Retrieve Jenkins API token from environment variable or managed identity.
    For production, use Azure Key Vault or Managed Identity.
    """
    token = os.environ.get("Token")
    if not token:
        logging.error("Jenkins API token not found in environment variables.")
        raise Exception("Jenkins API token not configured.")
    username = os.environ.get("JENKINS_USER")
    return username, token

def get_jenkins_jobs(jenkins_fqdn, search_string=None):
    """
    Call Jenkins API to list jobs, optionally filtering by name.
    """
    import base64
    username, token = get_jenkins_token()
    userpass = f"{username}:{token}"
    b64_userpass = base64.b64encode(userpass.encode()).decode()
    url = f"https://{jenkins_fqdn}/api/json?tree=jobs[name,url]"
    headers = {
        "Authorization": f"Basic {b64_userpass}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        jobs = response.json().get("jobs", [])
        if search_string:
            jobs = [job for job in jobs if search_string.lower() in job["name"].lower()]
        return {"jobs": jobs}
    except requests.RequestException as e:
        logging.error(f"Error calling Jenkins API: {e}")
        return {"error": str(e)}

@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="list_jenkins_jobs",
    description="List Jenkins jobs, optionally filtered by name.",
    toolProperties=tool_properties_list_jobs_json,
)
def list_jenkins_jobs(context) -> str:
    """
    MCP tool to list Jenkins jobs via HTTP API.
    Args:
        context: The trigger context containing arguments.
    Returns:
        str: JSON string of jobs or error message.
    """
    try:
        content = json.loads(context)
        args = content.get("arguments", {})
        jenkins_fqdn = args.get(_JENKINS_SERVER_PROPERTY)
        search_string = args.get(_SEARCH_STRING_PROPERTY)
        if not jenkins_fqdn:
            return json.dumps({"error": "Jenkins server FQDN is required."})
        result = get_jenkins_jobs(jenkins_fqdn, search_string)
        return json.dumps(result)
    except Exception as ex:
        logging.error(f"Exception in list_jenkins_jobs: {ex}")
        return json.dumps({"error": str(ex)})
