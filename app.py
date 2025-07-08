import streamlit as st
import requests
import json

st.set_page_config(page_title="Gemini + Jira Assistant", layout="centered")
st.title("🤖 Gemini AI Jira Assistant")
st.caption("Ask anything about your Jira project")

# User input
question = st.text_input("💬 Ask your question:")

# Config
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
JIRA_BASE_URL = st.secrets["JIRA_BASE_URL"]
JIRA_EMAIL = st.secrets["JIRA_EMAIL"]
ATLASSIAN_API_TOKEN = st.secrets["ATLASSIAN_API_TOKEN"]
JIRA_PROJECT_KEY = st.secrets["JIRA_PROJECT_KEY"]

# Get Jira issues
def get_jira_issues():
    url = f"{JIRA_BASE_URL}/rest/api/3/search"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    auth = (JIRA_EMAIL, ATLASSIAN_API_TOKEN)
    jql = f"project = {JIRA_PROJECT_KEY} ORDER BY priority DESC, updated DESC"
    params = {
        "jql": jql,
        "maxResults": 10,
        "fields": "summary,status,assignee,priority"
    }
    response = requests.get(url, headers=headers, auth=auth, params=params)
    if response.status_code == 200:
        return response.json()["issues"]
    else:
        return []

def format_issues(issues):
    formatted = []
    for issue in issues:
        key = issue["key"]
        fields = issue["fields"]
        summary = fields["summary"]
        status = fields["status"]["name"]
        assignee = fields["assignee"]["displayName"] if fields["assignee"] else "Unassigned"
        priority = fields["priority"]["name"]
        formatted.append(f"- {key}: {summary} (Status: {status}, Assignee: {assignee}, Priority: {priority})")
    return "\n".join(formatted)

def ask_gemini(prompt):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
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
    except Exception as e:
        return f"Error: {res.text}"

if question:
    issues = get_jira_issues()
    if not issues:
        st.error("❌ Couldn't fetch Jira issues. Check your API keys or project key.")
    else:
        formatted_issues = format_issues(issues)
        prompt = (
            f"Here are the current Jira issues from project {JIRA_PROJECT_KEY}:\n\n"
            f"{formatted_issues}\n\n"
            f"User asked: '{question}'\n\n"
            "Please respond with helpful, prioritized guidance like an expert project assistant."
        )
        response = ask_gemini(prompt)
        st.markdown("### 🤖 Response:")
        st.info(response)
