import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.agent import research_agent

print("=" * 60)
print("Running agent on: RAG evaluation methods")
print("=" * 60)

report = research_agent("RAG evaluation methods")

print()
print("=" * 60)
print("FINAL REPORT")
print("=" * 60)
print(report)
print()
print(f"Report length: {len(report)} characters")