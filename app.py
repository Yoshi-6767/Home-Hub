import os
import platform
import uuid
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text

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
app.config['SECRET_KEY'] = 'super-secret-home-hub-key'
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- Модели ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False) # Почта
    nickname = db.Column(db.String(50), nullable=True)               # Ник (разрешаем NULL для старых баз)
    password_hash = db.Column(db.String(200), nullable=False)

class ShoppingList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
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
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    color = db.Column(db.String(20), default='#FF6B00')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    events = db.relationship('Event', backref='category', cascade='all, delete-orphan')

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    date = db.Column(db.Date, nullable=False)
    repeat = db.Column(db.String(20), default='none')
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class NoteFolder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    notes = db.relationship('Note', backref='folder', cascade='all, delete-orphan')

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), default='Без названия')
    body = db.Column(db.Text, default='') 
    pinned = db.Column(db.Boolean, default=False)
    deleted = db.Column(db.Boolean, default=False)
    folder_id = db.Column(db.Integer, db.ForeignKey('note_folder.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SubCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    color = db.Column(db.String(20), default='#FF6B00')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subscriptions = db.relationship('Subscription', backref='category', cascade='all, delete-orphan')

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, default=0)
    period = db.Column(db.String(20), default='monthly')
    next_date = db.Column(db.Date, nullable=False)
    icon = db.Column(db.String(10), default='📦')
    notes = db.Column(db.Text, default='')
    category_id = db.Column(db.Integer, db.ForeignKey('sub_category.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except Exception:
        return None

with app.app_context():
    # 1. Создаем таблицы, если их нет
    db.create_all()
    # 2. Хитрый фикс для добавления колонки nickname в старую базу
    try:
        db.session.execute(text("ALTER TABLE user ADD COLUMN nickname VARCHAR(50) DEFAULT 'User'"))
        db.session.commit()
    except Exception:
        pass # Если колонка уже есть - ничего не делаем

# --- АВТОРИЗАЦИЯ ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Неправильный логин или пароль', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        nickname = request.form.get('nickname')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Эта почта уже занята', 'error')
        else:
            hashed = generate_password_hash(password)
            new_user = User(username=username, nickname=nickname, password_hash=hashed)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- ГЛАВНАЯ ---
@app.route('/')
@login_required
def index():
    return render_template('index.html')

# --- ПОКУПКИ ---
@app.route('/shopping')
@login_required
def shopping():
    lists = ShoppingList.query.filter_by(user_id=current_user.id).order_by(ShoppingList.created_at.desc()).all()
    return render_template('shopping.html', lists=lists)

@app.route('/shopping/create', methods=['POST'])
@login_required
def shopping_create():
    name = request.form.get('name', '').strip()
    if name:
        db.session.add(ShoppingList(name=name, user_id=current_user.id))
        db.session.commit()
    return redirect(url_for('shopping'))

@app.route('/shopping/<int:list_id>')
@login_required
def shopping_list(list_id):
    lst = ShoppingList.query.filter_by(id=list_id, user_id=current_user.id).first_or_404()
    return render_template('shopping_list.html', lst=lst)

@app.route('/shopping/<int:list_id>/add', methods=['POST'])
@login_required
def shopping_add_item(list_id):
    lst = ShoppingList.query.filter_by(id=list_id, user_id=current_user.id).first_or_404()
    name = request.form.get('name', '').strip()
    quantity = request.form.get('quantity', '').strip()
    if name:
        db.session.add(ShoppingItem(name=name, quantity=quantity, list_id=lst.id))
        db.session.commit()
    return redirect(url_for('shopping_list', list_id=list_id))

@app.route('/shopping/<int:list_id>/toggle/<int:item_id>', methods=['POST'])
@login_required
def shopping_toggle_item(list_id, item_id):
    item = ShoppingItem.query.get_or_404(item_id)
    if item.list.user_id == current_user.id:
        item.done = not item.done
        db.session.commit()
    return redirect(url_for('shopping_list', list_id=list_id))

@app.route('/shopping/<int:list_id>/delete/<int:item_id>', methods=['POST'])
@login_required
def shopping_delete_item(list_id, item_id):
    item = ShoppingItem.query.get_or_404(item_id)
    if item.list.user_id == current_user.id:
        db.session.delete(item)
        db.session.commit()
    return redirect(url_for('shopping_list', list_id=list_id))

@app.route('/shopping/<int:list_id>/delete', methods=['POST'])
@login_required
def shopping_delete_list(list_id):
    lst = ShoppingList.query.filter_by(id=list_id, user_id=current_user.id).first_or_404()
    db.session.delete(lst)
    db.session.commit()
    return redirect(url_for('shopping'))

# --- ЖЕЛАНИЯ ---
@app.route('/wishes')
@login_required
def wishes():
    wishes = Wish.query.filter_by(user_id=current_user.id).order_by(Wish.done, Wish.created_at.desc()).all()
    total = sum(w.price for w in wishes if not w.done)
    return render_template('wishes.html', wishes=wishes, total=total)

@app.route('/wishes/add', methods=['POST'])
@login_required
def wishes_add():
    name = request.form.get('name', '').strip()
    link = request.form.get('link', '').strip()
    price = request.form.get('price', '0').strip()
    priority = request.form.get('priority', 'normal')
    if name:
        try: price_val = float(price) if price else 0
        except ValueError: price_val = 0
        db.session.add(Wish(name=name, link=link, price=price_val, priority=priority, user_id=current_user.id))
        db.session.commit()
    return redirect(url_for('wishes'))

@app.route('/wishes/toggle/<int:wish_id>', methods=['POST'])
@login_required
def wishes_toggle(wish_id):
    wish = Wish.query.filter_by(id=wish_id, user_id=current_user.id).first_or_404()
    wish.done = not wish.done
    db.session.commit()
    return redirect(url_for('wishes'))

@app.route('/wishes/delete/<int:wish_id>', methods=['POST'])
@login_required
def wishes_delete(wish_id):
    wish = Wish.query.filter_by(id=wish_id, user_id=current_user.id).first_or_404()
    db.session.delete(wish)
    db.session.commit()
    return redirect(url_for('wishes'))

# --- КАЛЕНДАРЬ ---
def event_occurs_on(event, target_date):
    if event.repeat == 'none': return event.date == target_date
    if event.repeat == 'weekly': return event.date.weekday() == target_date.weekday() and event.date <= target_date
    if event.repeat == 'monthly': return event.date.day == target_date.day and event.date <= target_date
    if event.repeat == 'yearly': return (event.date.day == target_date.day and event.date.month == target_date.month and event.date <= target_date)
    return False

@app.route('/calendar')
@login_required
def calendar():
    from calendar import monthrange
    import datetime as dt
    today = dt.date.today()
    year = request.args.get('year', today.year, type=int)
    month = request.args.get('month', today.month, type=int)
    if month < 1: month = 12; year -= 1
    elif month > 12: month = 1; year += 1
    first_weekday, days_in_month = monthrange(year, month)
    first_weekday = (first_weekday) % 7
    
    all_events = Event.query.filter_by(user_id=current_user.id).all()
    events_by_day = {}
    for day in range(1, days_in_month + 1):
        target = dt.date(year, month, day)
        for e in all_events:
            if event_occurs_on(e, target):
                events_by_day.setdefault(day, []).append(e)
                
    categories = Category.query.filter_by(user_id=current_user.id).all()
    month_names = ['', 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
    return render_template('calendar.html', year=year, month=month, month_name=month_names[month], first_weekday=first_weekday, days_in_month=days_in_month, events_by_day=events_by_day, categories=categories, today=today)

@app.route('/calendar/add-event', methods=['POST'])
@login_required
def calendar_add_event():
    title = request.form.get('title', '').strip()
    date_str = request.form.get('date', '')
    description = request.form.get('description', '').strip()
    category_id = request.form.get('category_id', type=int)
    repeat = request.form.get('repeat', 'none')
    if title and date_str:
        try: event_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError: return redirect(url_for('calendar'))
        db.session.add(Event(title=title, date=event_date, description=description, repeat=repeat, category_id=category_id if category_id else None, user_id=current_user.id))
        db.session.commit()
        return redirect(url_for('calendar', year=event_date.year, month=event_date.month))
    return redirect(url_for('calendar'))

@app.route('/calendar/categories', methods=['GET', 'POST'])
@login_required
def calendar_categories():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        color = request.form.get('color', '#FF6B00')
        if name:
            db.session.add(Category(name=name, color=color, user_id=current_user.id))
            db.session.commit()
        return redirect(url_for('calendar_categories'))
    categories = Category.query.filter_by(user_id=current_user.id).all()
    return render_template('calendar_categories.html', categories=categories)

# --- ЗАМЕТКИ ---
@app.route('/notes')
@login_required
def notes():
    folder_id = request.args.get('folder_id', type=int)
    search = request.args.get('q', '').strip()
    query = Note.query.filter_by(deleted=False, user_id=current_user.id)
    if folder_id: query = query.filter_by(folder_id=folder_id)
    if search: query = query.filter(Note.title.contains(search) | Note.body.contains(search))
    notes = query.order_by(Note.pinned.desc(), Note.updated_at.desc()).all()
    folders = NoteFolder.query.filter_by(user_id=current_user.id).all()
    return render_template('notes.html', notes=notes, folders=folders, current_folder=folder_id, search=search)

@app.route('/notes/folder/create', methods=['POST'])
@login_required
def note_folder_create():
    name = request.form.get('name', '').strip()
    if name:
        db.session.add(NoteFolder(name=name, user_id=current_user.id))
        db.session.commit()
    return redirect(url_for('notes'))

@app.route('/notes/new', methods=['POST'])
@login_required
def note_new():
    folder_id = request.form.get('folder_id', type=int)
    note = Note(title='Новая заметка', body='', folder_id=folder_id if folder_id else None, user_id=current_user.id)
    db.session.add(note)
    db.session.commit()
    return redirect(url_for('note_edit', note_id=note.id))

@app.route('/notes/<int:note_id>')
@login_required
def note_edit(note_id):
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first_or_404()
    folders = NoteFolder.query.filter_by(user_id=current_user.id).all()
    return render_template('notes_edit.html', note=note, folders=folders)

@app.route('/notes/<int:note_id>/save', methods=['POST'])
@login_required
def note_save(note_id):
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first_or_404()
    data = request.json
    if data:
        note.title = data.get('title', 'Без названия')
        note.body = data.get('body', '')
        note.folder_id = data.get('folder_id') if data.get('folder_id') else None
        db.session.commit()
        return jsonify({"status": "ok", "time": datetime.now().strftime('%H:%M')})
    return jsonify({"status": "error"}), 400

@app.route('/notes/<int:note_id>/delete', methods=['POST'])
@login_required
def note_delete(note_id):
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first_or_404()
    note.deleted = True
    db.session.commit()
    return redirect(url_for('notes'))

# --- ПОДПИСКИ ---
@app.route('/subscriptions')
@login_required
def subscriptions():
    subs = Subscription.query.filter_by(user_id=current_user.id).order_by(Subscription.next_date.asc()).all()
    cats = SubCategory.query.filter_by(user_id=current_user.id).all()
    total_monthly = 0
    total_yearly = 0
    today = date.today()
    for sub in subs:
        if sub.period == 'monthly': total_monthly += sub.price; total_yearly += sub.price * 12
        elif sub.period == 'yearly': total_monthly += sub.price / 12; total_yearly += sub.price
        elif sub.period == 'weekly': total_monthly += sub.price * 4.33; total_yearly += sub.price * 52
    return render_template('subscriptions.html', subs=subs, cats=cats, total_monthly=total_monthly, total_yearly=total_yearly, today=today)

@app.route('/subscriptions/add', methods=['POST'])
@login_required
def sub_add():
    name = request.form.get('name', '').strip()
    price = request.form.get('price', '0').strip()
    period = request.form.get('period', 'monthly')
    next_date_str = request.form.get('next_date', '')
    icon = request.form.get('icon', '📦')
    category_id = request.form.get('category_id', type=int)
    if name and next_date_str:
        try:
            price_val = float(price) if price else 0
            next_date_val = datetime.strptime(next_date_str, '%Y-%m-%d').date()
            db.session.add(Subscription(name=name, price=price_val, period=period, next_date=next_date_val, icon=icon, category_id=category_id if category_id else None, user_id=current_user.id))
            db.session.commit()
        except ValueError: pass
    return redirect(url_for('subscriptions'))

@app.route('/uploads', methods=['POST'])
@login_required
def upload_file():
    if 'image' not in request.files: return jsonify({'error': 'Нет файла'}), 400
    file = request.files['image']
    if file.filename == '': return jsonify({'error': 'Пустое имя'}), 400
    if file:
        filename = str(uuid.uuid4()) + "_" + secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return jsonify({'url': f'/uploads/{filename}'})

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/recipes')
@login_required
def recipes():
    return render_template('recipes.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
