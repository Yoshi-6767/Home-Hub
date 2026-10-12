import os
import json
import uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

DATA_DIR = '/data'
SHOPPING_FILE = os.path.join(DATA_DIR, 'shopping.json')


def load_shopping():
    if not os.path.exists(SHOPPING_FILE):
        return {"lists": []}
    with open(SHOPPING_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_shopping(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SHOPPING_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def find_list(data, list_id):
    for lst in data["lists"]:
        if lst["id"] == list_id:
            return lst
    return None


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/shopping')
def shopping():
    data = load_shopping()
    return render_template('shopping.html', lists=data["lists"])


@app.route('/shopping/create', methods=['POST'])
def shopping_create():
    name = request.form.get('name', '').strip()
    if name:
        data = load_shopping()
        data["lists"].append({
            "id": str(uuid.uuid4())[:8],
            "name": name,
            "items": []
        })
        save_shopping(data)
    return redirect(url_for('shopping'))


@app.route('/shopping/<list_id>')
def shopping_list(list_id):
    data = load_shopping()
    lst = find_list(data, list_id)
    if not lst:
        return redirect(url_for('shopping'))
    return render_template('shopping_list.html', lst=lst)


@app.route('/shopping/<list_id>/add', methods=['POST'])
def shopping_add_item(list_id):
    name = request.form.get('name', '').strip()
    quantity = request.form.get('quantity', '').strip()
    if name:
        data = load_shopping()
        lst = find_list(data, list_id)
        if lst:
            lst["items"].append({
                "id": str(uuid.uuid4())[:8],
                "name": name,
                "quantity": quantity,
                "done": False,
                "created_at": datetime.now().strftime('%Y-%m-%d')
            })
            save_shopping(data)
    return redirect(url_for('shopping_list', list_id=list_id))


@app.route('/shopping/<list_id>/toggle/<item_id>', methods=['POST'])
def shopping_toggle_item(list_id, item_id):
    data = load_shopping()
    lst = find_list(data, list_id)
    if lst:
        for item in lst["items"]:
            if item["id"] == item_id:
                item["done"] = not item["done"]
                break
        save_shopping(data)
    return redirect(url_for('shopping_list', list_id=list_id))


@app.route('/shopping/<list_id>/delete/<item_id>', methods=['POST'])
def shopping_delete_item(list_id, item_id):
    data = load_shopping()
    lst = find_list(data, list_id)
    if lst:
        lst["items"] = [i for i in lst["items"] if i["id"] != item_id]
        save_shopping(data)
    return redirect(url_for('shopping_list', list_id=list_id))


@app.route('/shopping/<list_id>/delete', methods=['POST'])
def shopping_delete_list(list_id):
    data = load_shopping()
    data["lists"] = [l for l in data["lists"] if l["id"] != list_id]
    save_shopping(data)
    return redirect(url_for('shopping'))


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
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
