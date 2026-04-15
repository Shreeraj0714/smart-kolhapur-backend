import google.generativeai as genai

genai.configure(api_key="YOUR_API_KEY_HERE")

model = genai.GenerativeModel("gemini-pro")

def analyze_issue(text):
    prompt = f"""
    You are a Smart City AI.

    Analyze the complaint and return:
    Category, Priority, Suggestion.

    Complaint: {text}
    """

    response = model.generate_content(prompt)
    return response.text