from flask import Flask, render_template, request, session, flash
import urllib3
import os
from dotenv import load_dotenv
from claude_service import generate_story
from jira_service import push_to_jira

# Load .env variables
load_dotenv()

# Suppress SSL warnings (Zscaler fix)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback-secret-key")

# Input limits
MAX_INPUT_LENGTH = 1000


# ─────────────────────────────────────────
# Route 1: Home page
# ─────────────────────────────────────────
@app.route("/")
def home():
    return render_template("index.html")


# ─────────────────────────────────────────
# Route 2: Generate story via Claude
# ─────────────────────────────────────────
@app.route("/generate", methods=["POST"])
def generate():
    raw_input = request.form.get("raw_story", "").strip()

    # ── Validation ──────────────────────────
    if not raw_input:
        flash("Please enter a feature description before generating.", "error")
        return render_template("index.html")

    if len(raw_input) < 10:
        flash("Description too short. Please provide more detail.", "error")
        return render_template("index.html")

    if len(raw_input) > MAX_INPUT_LENGTH:
        flash(f"Description too long. Maximum {MAX_INPUT_LENGTH} characters allowed.", "error")
        return render_template("index.html")

    print(f"\n{'='*50}")
    print(f"New request received ({len(raw_input)} chars)")
    print(f"{'='*50}")
                    
    # ── Claude API call ──────────────────────
    try:
        result = generate_story(raw_input)

    except ValueError as e:
        # JSON parsing failed — Claude returned bad output
        print(f"❌ Claude parsing error: {e}")
        flash("Claude returned an unexpected response. Please try again.", "error")
        return render_template("index.html")

    except Exception as e:
        # Network error, API key wrong, timeout etc
        print(f"❌ Claude API error: {e}")
        error_msg = _get_claude_error_message(str(e))
        flash(error_msg, "error")
        return render_template("index.html")

    # ── Store in session ─────────────────────
    session["story"]         = result["story"]
    session["test_cases"]    = result["test_cases"]
    session["test_coverage"] = result["test_coverage"]
    session["raw_input"]     = raw_input

    return render_template("review.html",
                           story=result["story"],
                           test_cases=result["test_cases"],
                           test_coverage=result["test_coverage"])


# ─────────────────────────────────────────
# Route 3: Approve + push to Jira
# ─────────────────────────────────────────
@app.route("/approve", methods=["POST"])
def approve():

    # ── Read story from form ─────────────────
    story = {
        "summary":          request.form.get("summary", "").strip(),
        "description":      request.form.get("description", "").strip(),
        "business_context": request.form.get("business_context", "").strip(),
        "scope":            [x for x in request.form.getlist("scope") if x.strip()],
        "acceptance_criteria": [],
        "out_of_scope":     [x for x in request.form.getlist("out_of_scope") if x.strip()],
        "dependencies":     [x for x in request.form.getlist("dependencies") if x.strip()]
    }

    # Validate summary exists
    if not story["summary"]:
        flash("Story summary cannot be empty.", "error")
        return render_template("review.html",
                               story=session.get("story", {}),
                               test_cases=session.get("test_cases", []),
                               test_coverage=session.get("test_coverage", ""))

    # Build ACs
    ac_ids   = request.form.getlist("ac_id")
    ac_texts = request.form.getlist("ac_text")
    for ac_id, ac_text in zip(ac_ids, ac_texts):
        if ac_text.strip():
            story["acceptance_criteria"].append({
                "id": ac_id, "text": ac_text
            })

    # Build test cases
    tc_names         = request.form.getlist("tc_name")
    tc_types         = request.form.getlist("tc_type")
    tc_acs           = request.form.getlist("tc_ac")
    tc_preconditions = request.form.getlist("tc_preconditions")
    tc_steps_list    = request.form.getlist("tc_steps")
    tc_expecteds     = request.form.getlist("tc_expected")

    test_cases = []
    for i in range(len(tc_names)):
        if tc_names[i].strip():
            test_cases.append({
                "name":            tc_names[i],
                "test_type":       tc_types[i],
                "related_ac":      tc_acs[i],
                "preconditions":   [l for l in tc_preconditions[i].split("\n") if l.strip()],
                "steps":           [l for l in tc_steps_list[i].split("\n") if l.strip()],
                "expected_result": [l for l in tc_expecteds[i].split("\n") if l.strip()]
            })

    if not test_cases:
        flash("Please keep at least one test case.", "error")
        return render_template("review.html",
                               story=session.get("story", {}),
                               test_cases=session.get("test_cases", []),
                               test_coverage=session.get("test_coverage", ""))

    # ── Push to Jira ─────────────────────────
    try:
        jira_result = push_to_jira(story, test_cases)
        print(f"✅ Full flow complete: {jira_result['story_key']}")
        return render_template("success.html",
                               story=story,
                               test_cases=test_cases,
                               jira_result=jira_result)

    except Exception as e:
        print(f"❌ Jira error: {e}")
        error_msg = _get_jira_error_message(str(e))
        return render_template("success.html",
                               story=story,
                               test_cases=test_cases,
                               jira_result=None,
                               error=error_msg)


# ─────────────────────────────────────────
# Helper: Human-readable error messages
# ─────────────────────────────────────────
def _get_claude_error_message(error: str) -> str:
    """
    Converts technical Claude errors into friendly messages.
    Like a UiPath catch block with specific exception types.
    """
    if "401" in error or "authentication" in error.lower():
        return "Invalid Anthropic API key. Please check your .env file."
    if "429" in error or "rate_limit" in error.lower():
        return "Too many requests. Please wait a moment and try again."
    if "timeout" in error.lower() or "connection" in error.lower():
        return "Connection timeout. Please check your internet and try again."
    if "ssl" in error.lower() or "certificate" in error.lower():
        return "SSL error. This may be a network/Zscaler issue."
    return "Claude API error. Please try again in a moment."


def _get_jira_error_message(error: str) -> str:
    """
    Converts technical Jira errors into friendly messages.
    """
    if "401" in error or "403" in error:
        return "Jira authentication failed. Check your JIRA_EMAIL and JIRA_API_TOKEN in .env."
    if "404" in error:
        return "Jira project not found. Check your JIRA_PROJECT_KEY in .env."
    if "timeout" in error.lower() or "connection" in error.lower():
        return "Cannot reach Jira. Please check your internet connection."
    return f"Jira upload failed: {error}"


# ─────────────────────────────────────────
# Start server
# ─────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 AI Story Generator starting...")
    print("📌 Open http://localhost:5000 in your browser")
    #app.run(debug=True)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)