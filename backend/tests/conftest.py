"""Keep every test run away from configured providers and the saved local database."""

import os

os.environ["OPENAI_API_KEY"] = ""
os.environ["FISH_AUDIO_API_KEY"] = ""
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
