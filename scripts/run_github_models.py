import os
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential

endpoint = os.environ.get("GITHUB_MODELS_ENDPOINT", "https://models.github.ai/inference")
model = os.environ.get("LLM_MODEL", "openai/gpt-4.1-mini")
token = os.environ.get("GITHUB_TOKEN")

if not token:
    raise SystemExit("GITHUB_TOKEN not set in environment")

client = ChatCompletionsClient(
    endpoint=endpoint,
    credential=AzureKeyCredential(token),
)

try:
    response = client.complete(
        messages=[
            SystemMessage("You are a helpful assistant."),
            UserMessage("What is the capital of France?"),
        ],
        temperature=1.0,
        top_p=1.0,
        model=model,
    )
    # Print the returned message content (OpenAI-compatible shape)
    print(response.choices[0].message.content)
except Exception as exc:
    print("ERROR:", type(exc).__name__, str(exc))
