import streamlit as st
import requests
import json
import re

# ----------------------
# PAGE CONFIG & HEADER
# ----------------------
st.set_page_config(page_title="Gemini + Jira Assistant", layout="centered")

st.markdown("""
    <style>
        .main { font-family: "Segoe UI", sans-serif; }
        h1 { font-size: 2.2rem; margin-bottom: 0.2rem; }
        .message-container {
            background-color: #f5f5f5;
            padding: 0.75rem 1rem;
            border-radius: 10px;
            margin-bottom: 1rem;
        }
        .user-msg {
            color: black;
            font-weight: 600;
        }
        .bot-msg {
            color: #444;
        }
    </style>
""", unsafe_allow_html=True)

st.title("🤖 Gemini Jira Assistant")
st.caption("Chat naturally with your Jira project using AI.")

# ----------------------
# SECRETS / CONFIG
# ----------------------
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
JIRA_BASE_URL = st.secrets["JIRA_BASE_URL"]
JIRA_EMAIL = st.secrets["JIRA_EMAIL"]
ATLASSIAN_API_TOKEN = st.secrets["ATLASSIAN_API_KEY"]
JIRA_PROJECT_KEY = st.secrets["JIRA_PROJECT_KEY"]

# ----------------------
# SESSION STATE INIT
# ----------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

# ----------------------
# FETCH JIRA ISSUES
# ----------------------
def get_all_jira_issues():
    url = f"{JIRA_BASE_URL}/rest/api/3/search"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    auth = (JIRA_EMAIL, ATLASSIAN_API_TOKEN)

    start_at = 0
    max_results = 50
    all_issues = []

    while True:
        params = {
            "jql": f"project = {JIRA_PROJECT_KEY}",
            "startAt": start_at,
            "maxResults": max_results,
            "fields": "summary,status,assignee,priority,issuetype,duedate,description,labels,parent"
        }
        response = requests.get(url, headers=headers, auth=auth, params=params)
        if response.status_code != 200:
            break

        data = response.json()
        issues = data.get("issues", [])
        all_issues.extend(issues)

        if start_at + max_results >= data.get("total", 0):
            break
        start_at += max_results

    return all_issues

# ----------------------
# FORMAT JIRA ISSUES
# ----------------------
def extract_number(summary):
    match = re.match(r"([\d.]+)", summary)
    return [int(n) for n in match.group(1).split('.')] if match else [999]

def format_issues(issues):
    issues_sorted = sorted(issues, key=lambda issue: extract_number(issue["fields"].get("summary", "")))
    formatted = []

    for issue in issues_sorted:
        key = issue.get("key", "UNKNOWN")
        fields = issue["fields"]
        summary = fields.get("summary", "No summary")
        status = fields["status"]["name"]
        assignee = fields["assignee"]["displayName"] if fields["assignee"] else "Unassigned"
        priority = fields["priority"]["name"] if fields.get("priority") else "None"
        issue_type = fields["issuetype"]["name"]
        due_date = fields.get("duedate", "No due date")
        description = fields.get("description", "No description")
        labels = ", ".join(fields.get("labels", [])) if fields.get("labels") else "No labels"

        formatted.append(
            f"- **{key}** ({issue_type}): {summary}\n"
            f"  - Status: {status}\n"
            f"  - Assignee: {assignee}\n"
            f"  - Priority: {priority}\n"
            f"  - Due: {due_date}\n"
            f"  - Labels: {labels}\n"
            f"  - Description: {'Present' if description else 'Missing'}"
        )

    return "\n\n".join(formatted)

# ----------------------
# GEMINI CALL
# ----------------------
def ask_gemini(prompt):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY
    }
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    res = requests.post(url, headers=headers, json=payload)
    try:
        return res.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception:
        return f"❌ Error: {res.text}"

# ----------------------
# ADD DESCRIPTION HELPERS
# ----------------------
def generate_description_for_issue(summary, issue_type, labels):
    label_text = ", ".join(labels) if labels else "no labels"
    prompt = (
        f"Generate a helpful Jira description for the following issue:\n\n"
        f"Title: {summary}\n"
        f"Type: {issue_type}\n"
        f"Labels: {label_text}\n\n"
        f"Keep it clear and professional. Write it like a real Jira ticket."
    )
    description = ask_gemini(prompt)
    return description if description and not description.startswith("❌") else "No description generated."

def update_jira_description(issue_key, new_description):
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    auth = (JIRA_EMAIL, ATLASSIAN_API_TOKEN)
    payload = {
        "fields": {
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": new_description}]
                    }
                ]
            }
        }
    }
    response = requests.put(url, headers=headers, auth=auth, json=payload)
    if response.status_code != 204:
        st.error(f"❌ Failed to update {issue_key}: {response.status_code} – {response.text}")
    return response.status_code == 204

# ----------------------
# DISPLAY CHAT HISTORY
# ----------------------
for msg in st.session_state.messages:
    with st.container():
        st.markdown(f"""
            <div class="message-container">
                <div class="user-msg">🧑‍💼 You: {msg['user']}</div><br>
                <div class="bot-msg">🤖 Gemini: {msg['bot']}</div>
            </div>
        """, unsafe_allow_html=True)

# ----------------------
# USER INPUT
# ----------------------
with st.form(key="chat_form", clear_on_submit=True):
    user_input = st.text_input("💬 Ask a question", placeholder="e.g., What are the overdue tasks?")
    submitted = st.form_submit_button("Send")

# ----------------------
# HANDLE RESPONSE
# ----------------------
if submitted and user_input:
    with st.spinner("🤔 Gemini is thinking..."):
        issues = get_all_jira_issues()
        if not issues:
            st.error("❌ Couldn’t fetch Jira issues.")
        else:
            # Special command: Add descriptions to missing issues
            if user_input.lower().strip() in ["add descriptions", "add descriptions to all missing issues"]:
                updated = []
                for issue in issues:
                    fields = issue["fields"]
                    description = fields.get("description")

                    # Handle both missing and empty ADF descriptions
                    is_empty = (
                        not description or
                        (isinstance(description, dict) and not description.get("content"))
                    )

                    if is_empty:
                        key = issue["key"]
                        summary = fields.get("summary", "")
                        issue_type = fields["issuetype"]["name"]
                        labels = fields.get("labels", [])

                        new_description = generate_description_for_issue(summary, issue_type, labels)
                        success = update_jira_description(key, new_description)
                        if success:
                            updated.append(key)

                result = (
                    f"✅ Added descriptions to {len(updated)} issue(s):\n" + "\n".join(f"- {k}" for k in updated)
                    if updated else
                    "🎉 All issues already have descriptions!"
                )
                st.session_state.messages.append({"user": user_input, "bot": result})
                st.rerun()

            # Normal Q&A flow
            else:
                formatted_issues = format_issues(issues)
                full_prompt = (
                    f"You are a project assistant with access to Jira project {JIRA_PROJECT_KEY}.\n\n"
                    f"Here are the Jira issues:\n\n{formatted_issues}\n\n"
                    f"The user asked: \"{user_input}\"\n\n"
                    f"Give a clear and human-like response based only on the issue data above."
                )
                answer = ask_gemini(full_prompt)
                st.session_state.messages.append({"user": user_input, "bot": answer})
                st.rerun()
