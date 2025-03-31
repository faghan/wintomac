import azure.functions as func
import logging

app = func.FunctionApp()

@app.blob_trigger(arg_name="myblob", path="processed/{name}", connection="f1e2ad_STORAGE")
def createfunctest(myblob: func.InputStream):
    try:
        # Log the name and size of the blob
        logging.info(f"Python blob trigger function processed blob \n"
                     f"Name: {myblob.name}\n"
                     f"Blob Size: {myblob.length} bytes")
        
        # Read the content of the blob
        blob_content = myblob.read()
        
        # Ensure the content is correctly decoded if it's a text file
        try:
            blob_content_str = blob_content.decode('utf-8')
        except UnicodeDecodeError:
            blob_content_str = str(blob_content)
        
        # Print the content of the blob
        print("Blob content:")
        print(blob_content_str)
        
        # Log the content of the blob for debugging purposes
        logging.info(f"Blob Content: {blob_content_str}")
        
        # Print the name and path of the blob
        print("Blob Name:", myblob.name)
        print("Blob Path:", f"{myblob.name}")
    except Exception as e:
        logging.error(f"Error processing blob: {e}")
        raise

# Example usage for local testing
if __name__ == "__main__":
    class FakeInputStream:
        def __init__(self, name, length, content):
            self.name = name
            self.length = length
            self._content = content
        
        def read(self):
            return self._content

    # Simulate a test blob
    test_blob = FakeInputStream(name="Hello_World.txt", length=11, content=b"Hello World")
    createfunctest(test_blob)
