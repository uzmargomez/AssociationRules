from main import app

def start_app():
    app.run(
        host='localhost',
        port='5000',
        debug=True,
    )