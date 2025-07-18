using namespace System.Net

# Input bindings are passed in via param block.
param($Request, $TriggerMetadata)

# Write to the Azure Functions log stream.
Write-Host "PowerShell HTTP trigger function processed a request."

# Interact with query parameters or the body of the request.
$jenkinsServerFQDN = $Request.Query.JenkinsServerFQDN
if (-not $jenkinsServerFQDN) {
    $jenkinsServerFQDN = $Request.Body.JenkinsServerFQDN
}

$searchString = $Request.Query.SearchString
if (-not $searchString) {
    $searchString = $Request.Body.SearchString
}

$body = "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response."

if ($jenkinsServerFQDN -and $searchString) {
    
    $UserToken = "$env:Token"
    $jenkinsToken = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($UserToken))
    $headers = New-Object "System.Collections.Generic.Dictionary[[String],[String]]"
    $headers.Add("Authorization", "Basic $jenkinsToken")
    $headers.Add("Content-Type", "application/json")

    $response = Invoke-RestMethod "https://$jenkinsServerFQDN/api/json?tree=jobs[name,url]&pretty=true" -Method 'POST' `
        -Headers $headers

    #Filter jobs whose name contains a specific string
    $response = $response.jobs | Where-Object { $_.name -like "*$searchString*" }

    $FilteredJobs = @{
        "jobs" = @($response)
    }

    $body = $FilteredJobs

}
else {

    $UserToken = $env:Token
    $jenkinsToken = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($UserToken))
    $headers = New-Object "System.Collections.Generic.Dictionary[[String],[String]]"
    $headers.Add("Authorization", "Basic $jenkinsToken")
    $headers.Add("Content-Type", "application/json")

    $response = Invoke-RestMethod "https://$jenkinsServerFQDN/api/json?tree=jobs[name,url]&pretty=true" -Method 'POST' `
        -Headers $headers

    $body = $response
}   

# Associate values to output bindings by calling 'Push-OutputBinding'.
Push-OutputBinding -Name Response -Value ([HttpResponseContext]@{
        StatusCode = [HttpStatusCode]::OK
        Body       = $body
    })


