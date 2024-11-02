import pymongo
from pymongo import MongoClient
from datetime import datetime

# Connect to MongoDB (replace with your connection URI)
client = MongoClient('mongodb://localhost:27017')

# Access your database and collection
db = client['pokeman']  # Replace with your database name
collection = db['products']  # Replace with your collection name

# Function to convert orderDate from string to DateTime
def convert_order_date():
    # Find all documents where orderDate is a string
    cursor = collection.find({"orderDate": {"$type": "string"}})

    # Iterate over each document
    for doc in cursor:
        try:
            # Extract the string date
            order_date_str = doc['orderDate']
            
            # Check if the string contains fractional seconds
            if '.' in order_date_str:
                # Format with fractional seconds
                order_date_dt = datetime.strptime(order_date_str, "%Y-%m-%dT%H:%M:%S.%f+00:00")
            else:
                # Format without fractional seconds
                order_date_dt = datetime.strptime(order_date_str, "%Y-%m-%dT%H:%M:%S+00:00")
            
            # Update the document with the new DateTime object
            collection.update_one(
                {"_id": doc["_id"]},  # Match by _id
                {"$set": {"orderDate": order_date_dt}}  # Update orderDate
            )
            print(f"Updated document with _id: {doc['_id']}")

        except Exception as e:
            print(f"Error updating document with _id: {doc['_id']} - {e}")

# Call the function to perform the update
convert_order_date()

# Close the MongoDB connection
client.close()
