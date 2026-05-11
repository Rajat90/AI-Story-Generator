def get_story_prompt(raw_input: str) -> str:
    return f"""
You are an expert Business Analyst and QA Engineer.

Given this raw feature requirement:
"{raw_input}"

Generate a structured output in the following JSON format ONLY.
No explanations. No markdown. No code blocks. Pure JSON only.

{{
  "story": {{
    "summary": "...",
    "description": "...",
    "business_context": "...",
    "scope": ["...", "..."],
    "acceptance_criteria": [
      {{"id": "AC1", "text": "..."}},
      {{"id": "AC2", "text": "..."}}
    ],
    "out_of_scope": ["...", "..."],
    "dependencies": ["...", "..."]
  }},
  "test_coverage": "All ACs sufficiently covered.",
  "test_cases": [
    {{
      "name": "...",
      "preconditions": ["...", "..."],
      "steps": ["1. ...", "2. ..."],
      "expected_result": ["...", "..."],
      "related_ac": "AC1",
      "test_type": "Positive"
    }},
    {{
      "name": "...",
      "preconditions": ["...", "..."],
      "steps": ["1. ...", "2. ..."],
      "expected_result": ["...", "..."],
      "related_ac": "AC1",
      "test_type": "Negative"
    }},
    {{
      "name": "...",
      "preconditions": ["...", "..."],
      "steps": ["1. ...", "2. ..."],
      "expected_result": ["...", "..."],
      "related_ac": "AC2",
      "test_type": "Edge Case"
    }}
  ]
}}

Rules:
- Minimum 2 test cases, maximum 4 test cases
- Must include at least one Positive, one Negative or one Edge Case
- test_type must be exactly one of: Positive, Negative, Edge Case
- related_ac is a reference only, not strict
- Return pure JSON only — no extra text before or after
- Keep each text field concise — maximum 2 sentences
- Steps maximum 3 per test case
- Expected results maximum 3 points per test case
- Acceptance criteria maximum 3 ACs total
"""