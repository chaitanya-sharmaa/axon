import glob
import re

files = glob.glob('examples/*.py') + glob.glob('examples/*/*.py')
for f in files:
    if 'demo_usage.py' in f or 'benchmark' in f or 'MCP' in f or 'patch.py' in f:
        continue
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Update models to use the one Groq model that works
    content = re.sub(r'model=[\'\"].*?[\'\"]', 'model="groq/llama-3.1-8b-instant"', content)
    
    # Fix the environment variable fetching logic
    content = re.sub(r'os\.getenv\([\'\"]OPENAI_API_KEY[\'\"][^\)]*\)', 'os.environ.get("AXON_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY", "dummy-key")', content)
    
    # Also fix dictionary-style fetch if any
    content = re.sub(r'os\.environ\.get\([\'\"]OPENAI_API_KEY[\'\"][^\)]*\)', 'os.environ.get("AXON_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY", "dummy-key")', content)
    
    with open(f, 'w', encoding='utf-8') as file:
        file.write(content)
print("Done patching.")
