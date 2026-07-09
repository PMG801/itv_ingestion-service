"""Quick debug script to verify LLM settings are loaded correctly."""
import sys
from core.config import settings

print(f"NORMALIZATION_MODE: {settings.NORMALIZATION_MODE}")
print(f"LLM_PROVIDER: {settings.LLM_PROVIDER}")
print(f"LLM_MODEL: {settings.LLM_MODEL}")
print(f"LLM_BATCH_SIZE: {settings.LLM_BATCH_SIZE}")
print(f"LLM_REQUEST_TIMEOUT_S: {settings.LLM_REQUEST_TIMEOUT_S}")
print(f"GROQ_API_KEY (first 20 chars): {settings.GROQ_API_KEY[:20] if settings.GROQ_API_KEY else 'EMPTY'}")

if not settings.GROQ_API_KEY:
    print("\n❌ GROQ_API_KEY is empty! Check .env file.")
    sys.exit(1)

print("\n✅ All settings loaded correctly.")
