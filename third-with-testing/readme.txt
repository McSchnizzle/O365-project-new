For macbook:
    start by changing to the right directory
    (on m2 macbook: /Users/paulbrown/Desktop/Coding Projects/3-18 github clone/O365-project-new/Modularized code)

    python3 -m venv venv

    source venv/bin/activate

    pip install --upgrade pip

    pip install -r requirements.txt

For WIndows:
    Below are the step‑by‑step commands you can run in Windows PowerShell to set up and run your app. Make sure you're in your project folder (the folder that contains your code, including main.py, config.py, etc.):

    Open PowerShell and navigate to your project folder:

    powershell
    Copy
    cd "C:\Path\To\Your\Project\Modularized code"
    Create a virtual environment:

        python -m venv venv
    Activate the virtual environment:
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

        .\venv\Scripts\activate
    (Your prompt should now start with (venv).)

    Install the required dependencies from requirements.txt:

    powershell
    Copy
    pip install -r requirements.txt
    Initialize your databases (if needed) and run the app:

    If you want to start fresh (deleting your existing databases and delta link), run:

    powershell
    Copy
    python main.py initialize
    Then run the normal sync and email process with:

    powershell
    Copy
    python main.py
    (Optional) If you want to run the Flask web app:

    Assuming you have an app.py file for your Flask server, run:

    powershell
    Copy
    python app.py
    Then open your browser to http://127.0.0.1:5000.

    -----------------------
    GRAPH_CLIENT_ID = 'db1311b5-c7de-4db6-a4ba-07bb8103fb77'
    GRAPH_CLIENT_SECRET = '_5x8Q~TstpFm6FHoTkhX7q5moeQ0ZsiNg4m0Xc6~'
    GRAPH_TENANT_ID = 'f2cc0c5f-9306-48fd-b5a1-edebbe80f9cf'
