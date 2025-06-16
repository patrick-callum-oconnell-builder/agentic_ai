import openai

def normalize_response(response):
    """
    Normalize a response by converting it to lowercase and handling both string and dict inputs.
    """
    if isinstance(response, dict):
        return {k.lower(): v.lower() if isinstance(v, str) else v 
                for k, v in response.items()}
    elif isinstance(response, str):
        return response.lower()
    return response

def assert_response_contains(response, expected_text):
    """
    Assert that a response contains expected text, handling both string and dict responses.
    """
    normalized_response = normalize_response(response)
    normalized_expected = normalize_response(expected_text)
    
    if isinstance(normalized_response, dict):
        # For dict responses, check if any value contains the expected text
        assert any(normalized_expected in str(v) for v in normalized_response.values()), \
            f"Expected text '{expected_text}' not found in response: {response}"
    else:
        # For string responses, check directly
        assert normalized_expected in normalized_response, \
            f"Expected text '{expected_text}' not found in response: {response}"

def llm_check_response_intent(response, intent_description, model="gpt-4o"):
    """
    Use an LLM to check if the response satisfies the intent described by intent_description.
    Returns True if the LLM says the response matches the intent, False otherwise.
    """
    prompt = f"""
You are a test assistant. Given the following response, does it satisfy the following intent?

Intent: {intent_description}

Response: {response}

Reply with only 'yes' or 'no'.
"""
    try:
        client = openai.OpenAI()
        chat_response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=5
        )
        answer = chat_response.choices[0].message.content.strip().lower()
        return answer == "yes"
    except Exception as e:
        print(f"[LLM intent check error]: {e}")
        return False 