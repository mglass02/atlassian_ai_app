import streamlit as st
import requests
import json
import re

st.set_page_config(page_title="Gemini + Jira Assistant", layout="centered")
st.title("🤖 Gemini AI Jira Assistant")
st.caption("Ask anything about your Jira project")

# User input
question = st.text_input("💬 Ask your question:")

# Config
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
JIRA_BASE_URL = st.secrets["JIRA_BASE_URL"]
JIRA_EMAIL = st.secrets["JIRA_EMAIL"]
ATLASSIAN_API_TOKEN = st.secrets["ATLASSIAN_API_KEY"]
JIRA_PROJECT_KEY = st.secrets["JIRA_PROJECT_KEY"]

# Fetch ALL Jira issues with extended fields
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

# Sort by numerical prefix in summary (e.g. 1.2)
def extract_number(summary):
    match = re.match(r"([\d.]+)", summary)
    return [int(n) for n in match.group(1).split('.')] if match else [999]

# Format issues into a rich, multi-field string
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

# Ask Gemini
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
        return f"Error: {res.text}"

# Main interaction
if question:
    issues = get_all_jira_issues()
    if not issues:
        st.error("❌ Couldn't fetch Jira issues. Check your API keys or project key.")
    else:
        formatted_issues = format_issues(issues)
        prompt = (
            f"You are a project assistant with full access to the Jira project {JIRA_PROJECT_KEY}.\n\n"
            f"Here is the full list of issues with details:\n\n{formatted_issues}\n\n"
            f"The user asked: \"{question}\"\n\n"
            "Respond naturally. If the user asked for epics, due dates, missing fields, or classifications, use the issue data above."
        )
        response = ask_gemini(prompt)
        st.markdown("### 🤖 Response:")
        st.info(response)
