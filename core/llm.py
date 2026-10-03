from core.config import MODEL_NAME, GROQ_BASE_URL, get_groq_api_key

def llm_available():
    return bool(get_groq_api_key())

def chat(system_prompt, user_prompt, temperature=0.2):
    key = get_groq_api_key()
    if not key:
        raise RuntimeError("GROQ_API_KEY is not configured.")
    from openai import OpenAI
    client = OpenAI(api_key=key, base_url=GROQ_BASE_URL)
    response = client.chat.completions.create(
        model=MODEL_NAME,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content.strip()
