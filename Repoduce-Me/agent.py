# 1. Import the necessary class
# Based on your initial error, the required import path is likely:
from accra_code.lc_integration.constructor_chat_model import ConstructorModel 

# 2. Instantiate the model (it automatically reads the environment variables)
print("Attempting to connect to ConstructorModel...")
model = ConstructorModel()
print("Connection object created successfully.")

# 3. Invoke the model and print the result
print("Invoking model...")
response = model.invoke("Hi! Do you know Python?")
print("-" * 30)
print("Model Response:")
print(response)
print("-" * 30)