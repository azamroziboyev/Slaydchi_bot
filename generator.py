import requests
import json

API_KEY = "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"

# while True:
#     user_input = input("Ask something: ")

#     response = requests.post(
#         url="https://openrouter.ai/api/v1/chat/completions",
#         headers={
#             "Authorization": f"Bearer {API_KEY}",
#             "Content-Type": "application/json"
#         },
#         data=json.dumps({
#             "model": "deepseek/deepseek-chat",   # or any model you want
#             "messages": [
#                 {"role": "user", "content": user_input}
#             ]
#         })
#     )

#     result = response.json()
#     print("\nAI:", result["choices"][0]["message"]["content"], "\n")

def generate_thesis(prompt):
    """Call the external AI API to generate an academic paragraph for the given prompt.

    Returns a string with the generated content or a short fallback message on error.
    """
    if not API_KEY:
        return "Bu mavzuga oid qisqacha akademik monolog."
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    data = {
        "model": "deepseek/deepseek-reasoner",
        "messages": [
            {"role": "system", "content": "You write clear academic texts."},
            {"role": "user", "content": f"{prompt}"}
        ],
    }
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data), timeout=30)
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except:
        return "[Error generating paragraph — remote API unavailable]"
