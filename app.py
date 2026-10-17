import os
import platform
import uuid
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

# --- Пути ---
if platform.system() == 'Windows':
    DATA_DIR = 'data'
else:
    DATA_DIR = '/data'

os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, 'homehub.db')
UPLOAD_FOLDER = os.path.join(DATA_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Приложение ---
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
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

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    color = db.Column(db.String(20), default='#FF6B00')
    events = db.relationship('Event', backref='category', cascade='all, delete-orphan')

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    date = db.Column(db.Date, nullable=False)
    repeat = db.Column(db.String(20), default='none')
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class NoteFolder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    notes = db.relationship('Note', backref='folder', cascade='all, delete-orphan')

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), default='Без названия')
    body = db.Column(db.Text, default='') 
    pinned = db.Column(db.Boolean, default=False)
    deleted = db.Column(db.Boolean, default=False)
    folder_id = db.Column(db.Integer, db.ForeignKey('note_folder.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# --- НОВЫЕ МОДЕЛИ ДЛЯ ПОДПИСОК ---
class SubCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    color = db.Column(db.String(20), default='#FF6B00')
    subscriptions = db.relationship('Subscription', backref='category', cascade='all, delete-orphan')

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, default=0)
    period = db.Column(db.String(20), default='monthly') # weekly, monthly, yearly
    next_date = db.Column(db.Date, nullable=False)
    icon = db.Column(db.String(10), default='📦') # Эмодзи иконка
    notes = db.Column(db.Text, default='')
    category_id = db.Column(db.Integer, db.ForeignKey('sub_category.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


with app.app_context():
    db.create_all()


# --- Главная ---
@app.route('/')
def index():
    return render_template('index.html')

# ... [Тут идут все твои старые маршруты для Покупок, Желаний, Календаря и Заметок без изменений] ...
# Чтобы не спамить, я скрыл их, но В ТВОЕМ ФАЙЛЕ ОНИ ДОЛЖНЫ БЫТЬ. 
# Скопируй свои старые маршруты, если удалял. Или скажи мне, я скину их снова.

# --- ПОДПИСКИ ---
@app.route('/subscriptions')
def subscriptions():
    subs = Subscription.query.order_by(Subscription.next_date.asc()).all()
    cats = SubCategory.query.all()
    
    # Подсчет месячной и годовой стоимости
    total_monthly = 0
    total_yearly = 0
    today = date.today()

    for sub in subs:
        if sub.period == 'monthly':
            total_monthly += sub.price
            total_yearly += sub.price * 12
        elif sub.period == 'yearly':
            total_monthly += sub.price / 12
            total_yearly += sub.price
        elif sub.period == 'weekly':
            total_monthly += sub.price * 4.33
            total_yearly += sub.price * 52

    return render_template('subscriptions.html', subs=subs, cats=cats, 
                           total_monthly=total_monthly, total_yearly=total_yearly, today=today)

@app.route('/subscriptions/category/create', methods=['POST'])
def sub_category_create():
    name = request.form.get('name', '').strip()
    color = request.form.get('color', '#FF6B00')
    if name:
        db.session.add(SubCategory(name=name, color=color))
        db.session.commit()
    return redirect(url_for('subscriptions'))

@app.route('/subscriptions/add', methods=['POST'])
def sub_add():
    name = request.form.get('name', '').strip()
    price = request.form.get('price', '0').strip()
    period = request.form.get('period', 'monthly')
    next_date_str = request.form.get('next_date', '')
    icon = request.form.get('icon', '📦')
    category_id = request.form.get('category_id', type=int)
    notes = request.form.get('notes', '').strip()

    if name and next_date_str:
        try:
            price_val = float(price) if price else 0
            next_date_val = datetime.strptime(next_date_str, '%Y-%m-%d').date()
            
            db.session.add(Subscription(
                name=name, price=price_val, period=period, next_date=next_date_val,
                icon=icon, notes=notes, category_id=category_id if category_id else None
            ))
            db.session.commit()
        except ValueError:
            pass # Ошибка формата даты
    return redirect(url_for('subscriptions'))

@app.route('/subscriptions/delete/<int:sub_id>', methods=['POST'])
def sub_delete(sub_id):
    sub = Subscription.query.get_or_404(sub_id)
    db.session.delete(sub)
    db.session.commit()
    return redirect(url_for('subscriptions'))

# --- ЗАГЛУШКИ ---
@app.route('/recipes')
def recipes():
    return render_template('recipes.html')

@app.route('/reset-db-for-subs')
def reset_db():
    db.drop_all()
    db.create_all()
    return "База сброшена! Подписки готовы."

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
