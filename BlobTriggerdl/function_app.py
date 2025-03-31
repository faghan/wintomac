import logging
import azure.functions as func


app = func.FunctionApp()

# @app.event_grid_trigger(arg_name="azeventgrid")
# def dataanalyticsdev000(azeventgrid: func.EventGridEvent):
#     logging.info('Python EventGrid trigger processed an event')


# @app.event_grid_trigger(arg_name="azeventgrid")
# def EventGridTrigger(azeventgrid: func.EventGridEvent):
#     logging.info('Python EventGrid trigger processed an event')



@app.blob_trigger(arg_name="myblob", path="raw",
                               connection="AzureWebJobsStorage") 
def BlobTriggerdl(myblob: func.InputStream):
    logging.info(f"Python blob trigger function processed blob"
                f"Name: {myblob.name}"
                f"Blob Size: {myblob.length} bytes")
    print("heloo")
