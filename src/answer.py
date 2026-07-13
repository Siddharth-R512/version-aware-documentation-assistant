from retrieve import retrieve

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI()

def generate_answer(query: str, results: list) -> str:
    context = '\n\n'.join(f"Source: {r.payload['id']}\n{r.payload['text']}" for r in results)
    system_prompt = """
You answer questions using only the provided context.
Rules:
1. If the answer is not present in the context, say "I don't know based on the provided context."
2. Do not invent facts.
"""

    user = f"""
Context:
{context}

Question:
{query}
"""
    response = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user}
        ]
    )

    return response.choices[0].message.content

if __name__=='__main__':
    queries = [
        "how do I write a validator in v2?",
        "what does orm_mode do?",
        "is an Optional field required in v2?",
        "how do I convert a model to a dict in v1?"
    ]
    # query = "how do I convert a model to a dict in v2?"
    for query in queries:
        print(f"QUESTION: {query}")
        hits = retrieve(query)
        for h in hits:
            print(f"  {h.payload['id']}  ({h.payload['version']})  {h.score:.4f}")
        response = generate_answer(query, hits)
        print(f"Answer: {response}")