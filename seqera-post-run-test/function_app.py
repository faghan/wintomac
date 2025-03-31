import logging
import azure.functions as func
import json

# Define the function app with authentication level set to FUNCTION (can be changed as needed)
app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

@app.route(route="http_trigger_seqera")
def http_trigger_seqera(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Azure Function triggered by Nextflow pipeline.')

    # Try to get the JSON payload from the request
    try:
        req_body = req.get_json()  # Parse the incoming JSON body
        workflow_id = req_body.get("workflow_id")
        session_id = req_body.get("session_id")
        status = req_body.get("status")

        # Log the information
        logging.info(f"Received request for Workflow {workflow_id} (Session ID: {session_id}) with status: {status}")

        # Construct the response message
        response_message = f"Workflow {workflow_id} (Session: {session_id}) finished with status: {status}"

        # Return the response
        return func.HttpResponse(response_message, status_code=200)

    except ValueError:
        # In case the JSON body is invalid
        return func.HttpResponse(
            "Invalid JSON payload, ensure the correct JSON structure.",
            status_code=400
        )
