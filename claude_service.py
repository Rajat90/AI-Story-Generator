import httpx
import json
from anthropic import Anthropic
from prompts import get_story_prompt


# Zscaler fix — same as Week 1
client = Anthropic(
    http_client=httpx.Client(verify=False)
)


def generate_story(raw_input: str) -> dict:
    """
    Send raw input to Claude.
    Get back structured story + test cases as Python dict.
    
    Think of this as: one custom UiPath activity
    Input: raw text
    Output: structured dictionary
    """
    
    print(f"📤 Sending to Claude: {raw_input[:50]}...")
    
    # Call Claude API
    message = client.messages.create(
       model="claude-sonnet-4-5",
        max_tokens=4000,
        messages=[
            {
                "role": "user",
                "content": get_story_prompt(raw_input)
            }
        ]
    )
    
    # Extract the text response
    response_text = message.content[0].text
    print(f"📥 Claude responded ({len(response_text)} chars)")
    # Strip markdown code blocks if Claude added them
    # Claude sometimes wraps JSON in ```json ... ```
    # json.loads() can't handle that — we strip it first
    if response_text.strip().startswith("```"):
        lines = response_text.strip().split("\n")
        # Remove first line (```json) and last line (```)
        response_text = "\n".join(lines[1:-1])
        print("🧹 Stripped markdown code blocks")

    print(f"📥 CLEAN RESPONSE (first 100 chars): {response_text[:100]}")
    
    
    # Parse JSON response into Python dict
    # This is like reading a structured queue item in UiPath
    try:
        result = json.loads(response_text)
        print("✅ JSON parsed successfully")
        return result
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing failed: {e}")
        raise ValueError(f"Claude returned invalid JSON: {e}")