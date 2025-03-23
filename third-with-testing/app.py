# app.py
from flask import Flask, render_template_string
from sync_email import build_html_email

app = Flask(__name__)

@app.route('/')
def home():
    html_content = build_html_email()
    return render_template_string(html_content)

if __name__ == '__main__':
    app.run(debug=True)
