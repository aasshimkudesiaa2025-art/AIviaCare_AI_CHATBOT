from openai import AzureOpenAI

# Direct test with your exact portal values
client = AzureOpenAI(
    api_key="Cl3uPce89uV0VFSok4fgE0b8iCi6jtMzQ2b8pBfHiAWGEFCewgdIJQQJ99CCACfhMk5XJ3w3AAABACOGYbBO", 
    api_version="2024-02-15-preview",
    azure_endpoint="https://aasshi.openai.azure.com/"
)

try:
    print("Attempting to reach aasshi.openai.azure.com...")
    response = client.chat.completions.create(
        model="gpt-4.1", 
        messages=[{"role": "user", "content": "Hello Dr. Rishi!"}]
    )
    print("✅ SUCCESS! The connection is working.")
    print(f"Response: {response.choices[0].message.content}")
except Exception as e:
    print("❌ STILL FAILING")
    print(f"Error: {e}")