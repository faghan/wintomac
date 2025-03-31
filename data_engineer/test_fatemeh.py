from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
import pandas as pd
from io import StringIO

# Step 1: Set up the connection string or endpoint for your Azure Storage Account
account_name = "dataengineerv1"  # Replace with your storage account name
container_name = "raw"
blob_name = "tourism_dataset.csv"

# Construct the Blob Service Client using DefaultAzureCredentials
blob_service_client = BlobServiceClient(
    account_url=f"https://{account_name}.blob.core.windows.net",
    credential=DefaultAzureCredential()
)

# Step 2: Get the Blob Client
blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)

# Step 3: Download the CSV data from the Blob storage
download_stream = blob_client.download_blob()
csv_content = download_stream.readall().decode('utf-8')  # Decode bytes to string

# Step 4: Load the CSV data into a Pandas DataFrame
df = pd.read_csv(StringIO(csv_content))

# Display the DataFrame
print(df.head())

# Perform Data Analysis

# 1. Group and Aggregate Data
# Group by 'country' and calculate the average 'Rate'
country_rate_avg = df.groupby('Country')['Rating'].mean().reset_index()
country_rate_avg.columns = ['Country', 'Average Rate']

print("\nAverage Rate by Country:")
print(country_rate_avg)

# 2. Identify Top Categories
# Find the top 3 categories with the highest average rate across all countries
top_categories = df.groupby('Category')['Rating'].mean().reset_index()
top_categories.columns = ['Category', 'Average Rate']
top_categories = top_categories.sort_values(by='Average Rate', ascending=False).head(3)

print("\nTop 3 Categories by Average Rate:")
print(top_categories)

# Export Results and Save to VM

# Define your name for the CSV file
first_name = "Fatemeh"  # Replace with your first name
last_name = "Ghanami"    # Replace with your last name
results_file_name = f"{first_name}-{last_name}.csv"

# Combine results into a single DataFrame
results = pd.concat([
    country_rate_avg.assign(DataType='Country Rate'),
    top_categories.assign(DataType='Top Categories')
])

# Save results to a CSV file
results.to_csv(results_file_name, index=False)

print(f"\nResults saved to {results_file_name}")

# Upload to Azure Storage

# Define the new directory name
directory_name = f"{first_name}-{last_name}"

# Create a blob client for the directory
container_client = blob_service_client.get_container_client(container_name)
directory_blob_client = container_client.get_blob_client(f"{directory_name}/{results_file_name}")

# Upload the CSV file to the new directory
with open(results_file_name, "rb") as data:
    directory_blob_client.upload_blob(data, overwrite=True)

print(f"\nUploaded {results_file_name} to Azure Storage in directory '{directory_name}'")
