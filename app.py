import os
import platform
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

# --- Пути ---
if platform.system() == 'Windows':
    DATA_DIR = 'data'
else:
    DATA_DIR = '/data'

os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, 'homehub.db')

# --- Приложение ---
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# --- Модели ---
class ShoppingList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('ShoppingItem', backref='list', cascade='all, delete-orphan')


class ShoppingItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.String(50), default='')
    done = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    list_id = db.Column(db.Integer, db.ForeignKey('shopping_list.id'), nullable=False)


class Wish(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    link = db.Column(db.String(500), default='')
    price = db.Column(db.Float, default=0)
    priority = db.Column(db.String(20), default='normal')
    done = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


with app.app_context():
    db.create_all()


# --- Главная ---
@app.route('/')
def index():
    return render_template('index.html')


# --- Покупки ---
@app.route('/shopping')
def shopping():
    lists = ShoppingList.query.order_by(ShoppingList.created_at.desc()).all()
    return render_template('shopping.html', lists=lists)


@app.route('/shopping/create', methods=['POST'])
def shopping_create():
    name = request.form.get('name', '').strip()
    if name:
        db.session.add(ShoppingList(name=name))
        db.session.commit()
    return redirect(url_for('shopping'))


@app.route('/shopping/<int:list_id>')
def shopping_list(list_id):
    lst = ShoppingList.query.get_or_404(list_id)
    return render_template('shopping_list.html', lst=lst)


@app.route('/shopping/<int:list_id>/add', methods=['POST'])
def shopping_add_item(list_id):
    lst = ShoppingList.query.get_or_404(list_id)
    name = request.form.get('name', '').strip()
    quantity = request.form.get('quantity', '').strip()
    if name:
        db.session.add(ShoppingItem(name=name, quantity=quantity, list_id=lst.id))
        db.session.commit()
    return redirect(url_for('shopping_list', list_id=list_id))


@app.route('/shopping/<int:list_id>/toggle/<int:item_id>', methods=['POST'])
def shopping_toggle_item(list_id, item_id):
    item = ShoppingItem.query.get_or_404(item_id)
    item.done = not item.done
    db.session.commit()
    return redirect(url_for('shopping_list', list_id=list_id))


@app.route('/shopping/<int:list_id>/delete/<int:item_id>', methods=['POST'])
def shopping_delete_item(list_id, item_id):
    item = ShoppingItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for('shopping_list', list_id=list_id))


@app.route('/shopping/<int:list_id>/delete', methods=['POST'])
def shopping_delete_list(list_id):
    lst = ShoppingList.query.get_or_404(list_id)
    db.session.delete(lst)
    db.session.commit()
    return redirect(url_for('shopping'))


# --- Желания ---
@app.route('/wishes')
def wishes():
    wishes = Wish.query.order_by(Wish.done, Wish.created_at.desc()).all()
    total = sum(w.price for w in wishes if not w.done)
    return render_template('wishes.html', wishes=wishes, total=total)


@app.route('/wishes/add', methods=['POST'])
def wishes_add():
    name = request.form.get('name', '').strip()
    link = request.form.get('link', '').strip()
    price = request.form.get('price', '0').strip()
    priority = request.form.get('priority', 'normal')

    if name:
        try:
            price_val = float(price) if price else 0
        except ValueError:
            price_val = 0

        db.session.add(Wish(
            name=name,
            link=link,
            price=price_val,
            priority=priority
        ))
        db.session.commit()
    return redirect(url_for('wishes'))


@app.route('/wishes/toggle/<int:wish_id>', methods=['POST'])
def wishes_toggle(wish_id):
    wish = Wish.query.get_or_404(wish_id)
    wish.done = not wish.done
    db.session.commit()
    return redirect(url_for('wishes'))


@app.route('/wishes/delete/<int:wish_id>', methods=['POST'])
def wishes_delete(wish_id):
    wish = Wish.query.get_or_404(wish_id)
    db.session.delete(wish)
    db.session.commit()
    return redirect(url_for('wishes'))


# --- Календарь ---
@app.route('/calendar')
def calendar():
    return render_template('calendar.html')


# --- Рецепты ---
@app.route('/recipes')
def recipes():
    return render_template('recipes.html')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
