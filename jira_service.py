import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Load Jira config from .env
# Think of this as reading Orchestrator assets at Init stage
JIRA_URL        = os.getenv("JIRA_URL")
JIRA_EMAIL      = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN  = os.getenv("JIRA_API_TOKEN")
JIRA_PROJECT    = os.getenv("JIRA_PROJECT_KEY")

# Auth and headers used in every Jira API call
# Like a login session kept open for the whole bot run
AUTH    = (JIRA_EMAIL, JIRA_API_TOKEN)
HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json"
}


def create_story(story: dict) -> dict:
    """
    Creates a Jira Story ticket from approved story dict.
    Returns: { "key": "SCRUM-3", "url": "https://..." }

    RPA Equivalent: HTTP POST activity creating a record
    Input: story dict
    Output: created ticket key + URL
    """

    # Build description in Jira's format (Atlassian Document Format)
    # This is how Jira renders rich text
    description = _build_description(story)

    # Build the request payload
    payload = {
        "fields": {
            "project":     {"key": JIRA_PROJECT},
            "summary":     story["summary"],
            "description": description,
            "issuetype":   {"name": "Story"}
        }
    }

    print(f"📤 Creating Jira Story: {story['summary'][:50]}...")

    response = requests.post(
        f"{JIRA_URL}/rest/api/3/issue",
        headers=HEADERS,
        auth=AUTH,
        data=json.dumps(payload),
        verify=False  # Zscaler fix
    )

    if response.status_code == 201:
        data = response.json()
        key  = data["key"]
        url  = f"{JIRA_URL}/browse/{key}"
        print(f"✅ Story created: {key} → {url}")
        return {"key": key, "url": url}
    else:
        print(f"❌ Jira error: {response.status_code} - {response.text}")
        raise Exception(f"Failed to create story: {response.text}")


def create_subtask(parent_key: str, test_case: dict, index: int) -> dict:
    """
    Creates a Sub-task under the parent Story ticket.
    Returns: { "key": "SCRUM-4", "url": "https://..." }

    RPA Equivalent: HTTP POST creating a child record
    linked to a parent record ID
    """

    # Format test case content for Jira description
    tc_description = _build_tc_description(test_case)

    # Sub-task name includes type badge for quick scanning
    summary = f"[{test_case['test_type']}] {test_case['name']}"

    payload = {
        "fields": {
            "project":     {"key": JIRA_PROJECT},
            "summary":     summary,
            "description": tc_description,
            "issuetype":   {"name": "Subtask"},
            "parent":      {"key": parent_key}
        }
    }

    print(f"📤 Creating sub-task {index}: {summary[:50]}...")

    response = requests.post(
        f"{JIRA_URL}/rest/api/3/issue",
        headers=HEADERS,
        auth=AUTH,
        data=json.dumps(payload),
        verify=False  # Zscaler fix
    )

    if response.status_code == 201:
        data = response.json()
        key  = data["key"]
        url  = f"{JIRA_URL}/browse/{key}"
        print(f"✅ Sub-task created: {key}")
        return {"key": key, "url": url, "name": test_case["name"],
                "test_type": test_case["test_type"]}
    else:
        print(f"❌ Sub-task error: {response.status_code} - {response.text}")
        raise Exception(f"Failed to create sub-task: {response.text}")


def push_to_jira(story: dict, test_cases: list) -> dict:
    """
    Master function — orchestrates full Jira push.
    Creates story + all sub-tasks.
    Returns full result dict with all keys and URLs.

    RPA Equivalent: Process.xaml — calls sub-workflows
    in sequence and collects results.
    """

    print(f"\n{'='*50}")
    print(f"🚀 Starting Jira upload...")
    print(f"{'='*50}")

    # Step 1: Create the Story
    story_result = create_story(story)

    # Step 2: Create sub-tasks for each test case
    subtask_results = []
    for i, tc in enumerate(test_cases, start=1):
        subtask = create_subtask(story_result["key"], tc, i)
        subtask_results.append(subtask)

    print(f"\n✅ Jira upload complete!")
    print(f"   Story:     {story_result['key']}")
    print(f"   Sub-tasks: {len(subtask_results)} created")

    return {
        "story_key":  story_result["key"],
        "story_url":  story_result["url"],
        "subtasks":   subtask_results
    }


# ─────────────────────────────────────────
# PRIVATE HELPER FUNCTIONS
# These build Jira's Atlassian Document Format (ADF)
# Think of ADF as Jira's version of HTML — rich text format
# ─────────────────────────────────────────

def _build_description(story: dict) -> dict:
    """Builds Jira ADF description from story dict."""

    def heading(text, level=3):
        return {"type": "heading",
                "attrs": {"level": level},
                "content": [{"type": "text", "text": text}]}

    def paragraph(text):
        return {"type": "paragraph",
                "content": [{"type": "text", "text": text}]}

    def bullet_list(items):
        return {
            "type": "bulletList",
            "content": [
                {"type": "listItem",
                 "content": [paragraph(str(item))]}
                for item in items if item
            ]
        }

    # Build AC text combining ID and text
    ac_items = [
        f"{ac['id']}: {ac['text']}"
        for ac in story.get("acceptance_criteria", [])
    ]

    content = [
        paragraph(story.get("description", "")),

        heading("Business Context", 3),
        paragraph(story.get("business_context", "")),

        heading("Scope", 3),
        bullet_list(story.get("scope", [])),

        heading("Acceptance Criteria", 3),
        bullet_list(ac_items),

        heading("Out of Scope", 3),
        bullet_list(story.get("out_of_scope", [])),

        heading("Dependencies / Assumptions", 3),
        bullet_list(story.get("dependencies", [])),
    ]

    return {"type": "doc", "version": 1, "content": content}


def _build_tc_description(tc: dict) -> dict:
    """Builds Jira ADF description from test case dict."""

    def heading(text, level=3):
        return {"type": "heading",
                "attrs": {"level": level},
                "content": [{"type": "text", "text": text}]}

    def paragraph(text):
        return {"type": "paragraph",
                "content": [{"type": "text", "text": str(text)}]}

    def bullet_list(items):
        return {
            "type": "bulletList",
            "content": [
                {"type": "listItem",
                 "content": [paragraph(str(item))]}
                for item in items if item
            ]
        }

    content = [
        heading("Test Type", 3),
        paragraph(tc.get("test_type", "")),

        heading("Related AC", 3),
        paragraph(tc.get("related_ac", "")),

        heading("Preconditions", 3),
        bullet_list(tc.get("preconditions", [])),

        heading("Test Steps", 3),
        bullet_list(tc.get("steps", [])),

        heading("Expected Result", 3),
        bullet_list(tc.get("expected_result", [])),
    ]

    return {"type": "doc", "version": 1, "content": content}