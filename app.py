from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/shopping')
def shopping():
    return render_template('shopping.html')

@app.route('/wishes')
def wishes():
    return render_template('wishes.html')

@app.route('/calendar')
def calendar():
    return render_template('calendar.html')

@app.route('/recipes')
def recipes():
    return render_template('recipes.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)