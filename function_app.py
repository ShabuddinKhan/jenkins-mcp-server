"""
function_app.py
----------------
This Azure Function App exposes an MCP tool trigger to list Jenkins jobs from a specified Jenkins server.
It supports optional filtering by job name. The function uses HTTP Basic Auth with credentials from environment variables.
"""

import json
import logging
import os
import requests
import azure.functions as func

# Create the MCP FunctionApp instance with HTTP authentication level set to FUNCTION
app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

# Property keys for Jenkins tool triggers
_JENKINS_SERVER_PROPERTY = "jenkinsServerFQDN"  # Jenkins server FQDN property key (required)
_SEARCH_STRING_PROPERTY = "searchString"         # Optional search string property key for filtering jobs

class ToolProperty:
    """
    Describes a property required by an MCP tool, including its name, type, and description.
    """
    def __init__(self, property_name: str, property_type: str, description: str):
        self.propertyName = property_name  # Name of the property
        self.propertyType = property_type  # Data type of the property (e.g., 'string')
        self.description = description     # Description of the property

    def to_dict(self):
        """
        Convert the ToolProperty instance to a dictionary for serialization.
        """
        return {
            "propertyName": self.propertyName,
            "propertyType": self.propertyType,
            "description": self.description,
        }

# List of properties required for the list_jenkins_jobs tool
tool_properties_list_jobs = [
    ToolProperty(_JENKINS_SERVER_PROPERTY, "string", "The FQDN of the Jenkins server (e.g., 'jenkins.example.com')."),
    ToolProperty(_SEARCH_STRING_PROPERTY, "string", "Optional: Filter jobs by name containing this string."),
]
# Serialize the tool properties to JSON for use in the trigger definition
tool_properties_list_jobs_json = json.dumps([prop.to_dict() for prop in tool_properties_list_jobs])

def get_jenkins_token():
    """
    Retrieve Jenkins API token and username from environment variables.
    Returns:
        tuple: (username, token)
    Raises:
        Exception: If the token is not found in environment variables.
    Note:
        For production, consider using Azure Key Vault or Managed Identity for better security.
    """
    token = os.environ.get("Token")
    if not token:
        logging.error("Jenkins API token not found in environment variables.")
        raise Exception("Jenkins API token not configured.")
    username = os.environ.get("JENKINS_USER")
    return username, token

def get_jenkins_jobs(jenkins_fqdn, search_string=None):
    """
    Call the Jenkins API to list jobs, optionally filtering by job name.
    Args:
        jenkins_fqdn (str): The FQDN of the Jenkins server.
        search_string (str, optional): Filter jobs by name containing this string.
    Returns:
        dict: Dictionary containing the list of jobs or an error message.
    """
    import base64
    username, token = get_jenkins_token()
    userpass = f"{username}:{token}"
    # Encode credentials for HTTP Basic Auth
    b64_userpass = base64.b64encode(userpass.encode()).decode()
    url = f"https://{jenkins_fqdn}/api/json?tree=jobs[name,url]"
    headers = {
        "Authorization": f"Basic {b64_userpass}",
        "Content-Type": "application/json"
    }
    try:
        # Make the GET request to Jenkins API
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        jobs = response.json().get("jobs", [])
        # If a search string is provided, filter jobs by name
        if search_string:
            jobs = [job for job in jobs if search_string.lower() in job["name"].lower()]
        return {"jobs": jobs}
    except requests.RequestException as e:
        logging.error(f"Error calling Jenkins API: {e}")
        return {"error": str(e)}

# Register the MCP tool trigger for listing Jenkins jobs
@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="list_jenkins_jobs",
    description="List Jenkins jobs, optionally filtered by name. This trigger allows you to query a Jenkins server for all jobs, or filter by a substring in the job name.",
    toolProperties=tool_properties_list_jobs_json,
)
def list_jenkins_jobs(context) -> str:
    """
    MCP tool function to list Jenkins jobs via HTTP API.
    Args:
        context (str): The trigger context containing arguments as a JSON string. Should include 'jenkinsServerFQDN' and optionally 'searchString'.
    Returns:
        str: JSON string of jobs or error message.
    Example context:
        '{"arguments": {"jenkinsServerFQDN": "jenkins.example.com", "searchString": "pipeline"}}'
    """
    try:
        # Parse the context to extract arguments
        content = json.loads(context)
        args = content.get("arguments", {})
        jenkins_fqdn = args.get(_JENKINS_SERVER_PROPERTY)
        search_string = args.get(_SEARCH_STRING_PROPERTY)
        if not jenkins_fqdn:
            return json.dumps({"error": "Jenkins server FQDN is required."})
        # Call the helper to get jobs from Jenkins
        result = get_jenkins_jobs(jenkins_fqdn, search_string)
        return json.dumps(result)
    except Exception as ex:
        logging.error(f"Exception in list_jenkins_jobs: {ex}")
        return json.dumps({"error": str(ex)})
