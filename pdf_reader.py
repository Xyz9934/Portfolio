import pypdf
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_CHAT_MODEL

# -------- Configuration --------
PDF_FILE = "book.pdf"  # Replace with your PDF filename

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# -------- Read PDF --------
book_text = ""
pdf_reader = pypdf.PdfReader(PDF_FILE)
for page in pdf_reader.pages:
    text = page.extract_text()
    if text:
        book_text += text + "\n"

print("PDF loaded successfully!")

# -------- Ask questions --------
def ask_question(question):
    # Truncate text if too long for model
    prompt_text = book_text[:4000]  # Adjust 4000 if needed
    messages = [
        {"role": "system", "content": "Explain answers in simple words."},
        {"role": "user", "content": f"{prompt_text}\n\nQuestion: {question}"}
    ]
    response = client.chat.completions.create(
        model=OPENAI_CHAT_MODEL,
        messages=messages
    )
    answer = response.choices[0].message.content
    return answer

# Example usage
while True:
    user_q = input("Ask a question about the PDF (or type 'exit'): ")
    if user_q.lower() == "exit":
        break
    print("\nAnswer:\n", ask_question(user_q), "\n")
