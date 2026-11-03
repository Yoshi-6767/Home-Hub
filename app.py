import os
import platform
import uuid
import requests
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

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
app.config['SECRET_KEY'] = 'super-secret-tabibito-hub-key'
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
    username = db.Column(db.String(50), unique=True, nullable=False)
    display_name = db.Column(db.String(50), nullable=False)
    nickname = db.Column(db.String(50), nullable=True)
    password_hash = db.Column(db.String(200), nullable=False)
    avatar = db.Column(db.String(200), nullable=True)

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
    color = db.Column(db.String(20), default='#E53935')
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
    color = db.Column(db.String(20), default='#E53935')
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

class LibraryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.Column(db.String(20), nullable=False) # 'movie', 'tv', 'anime', 'book', 'game'
    api_id = db.Column(db.String(50), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    poster_url = db.Column(db.String(500), default='')
    description = db.Column(db.Text, default='')
    status = db.Column(db.String(20), default='want') 
    rating = db.Column(db.Integer, default=0) 
    review = db.Column(db.Text, default='')
    top_rank = db.Column(db.Integer, default=0) 
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except Exception:
        return None

with app.app_context():
    db.create_all()

# --- АВТОРИЗАЦИЯ ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password_hash, request.form.get('password')):
            login_user(user)
            return redirect(url_for('index'))
        flash('Неправильный логин или пароль', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        nickname = request.form.get('nickname')
        if User.query.filter_by(username=username).first(): flash('Почта занята', 'error')
        elif User.query.filter_by(nickname=nickname).first(): flash('Ник занят', 'error')
        else:
            new_user = User(username=username, display_name=request.form.get('display_name'), nickname=nickname, password_hash=generate_password_hash(request.form.get('password')))
            db.session.add(new_user); db.session.commit(); login_user(new_user)
            return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- ПРОФИЛЬ ---
@app.route('/profile')
@login_required
def profile():
    purchases_count = ShoppingItem.query.join(ShoppingList).filter(ShoppingList.user_id == current_user.id, ShoppingItem.done == True).count()
    notes_count = Note.query.filter_by(user_id=current_user.id, deleted=False).count()
    events_count = Event.query.filter_by(user_id=current_user.id).count()
    subs_sum = sum(sub.price for sub in Subscription.query.filter_by(user_id=current_user.id).all() if sub.period == 'monthly')
    return render_template('profile.html', purchases_count=purchases_count, notes_count=notes_count, events_count=events_count, subs_sum=subs_sum)

@app.route('/profile/update', methods=['POST'])
@login_required
def profile_update():
    if request.form.get('display_name', '').strip():
        current_user.display_name = request.form.get('display_name').strip()
        db.session.commit(); flash('Имя изменено!', 'success')
    return redirect(url_for('profile'))

@app.route('/profile/upload-avatar', methods=['POST'])
@login_required
def upload_avatar():
    if 'avatar' in request.files:
        file = request.files['avatar']
        if file.filename != '':
            filename = 'avatar_' + str(current_user.id) + '_' + str(uuid.uuid4())[:8] + '_' + secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            current_user.avatar = filename; db.session.commit()
    return redirect(url_for('profile'))

# --- ГЛАВНАЯ ---
@app.route('/')
@login_required
def index(): return render_template('index.html')

# --- ПОКУПКИ ---
@app.route('/shopping')
@login_required
def shopping(): return render_template('shopping.html', lists=ShoppingList.query.filter_by(user_id=current_user.id).order_by(ShoppingList.created_at.desc()).all())

@app.route('/shopping/create', methods=['POST'])
@login_required
def shopping_create():
    name = request.form.get('name', '').strip()
    if name: db.session.add(ShoppingList(name=name, user_id=current_user.id)); db.session.commit()
    return redirect(url_for('shopping'))

@app.route('/shopping/<int:list_id>')
@login_required
def shopping_list(list_id): return render_template('shopping_list.html', lst=ShoppingList.query.filter_by(id=list_id, user_id=current_user.id).first_or_404())

@app.route('/shopping/<int:list_id>/add', methods=['POST'])
@login_required
def shopping_add_item(list_id):
    lst = ShoppingList.query.filter_by(id=list_id, user_id=current_user.id).first_or_404()
    name = request.form.get('name', '').strip()
    if name: db.session.add(ShoppingItem(name=name, quantity=request.form.get('quantity', '').strip(), list_id=lst.id)); db.session.commit()
    return redirect(url_for('shopping_list', list_id=list_id))

@app.route('/shopping/<int:list_id>/toggle/<int:item_id>', methods=['POST'])
@login_required
def shopping_toggle_item(list_id, item_id):
    item = ShoppingItem.query.get_or_404(item_id)
    if item.list.user_id == current_user.id: item.done = not item.done; db.session.commit()
    return redirect(url_for('shopping_list', list_id=list_id))

@app.route('/shopping/<int:list_id>/delete/<int:item_id>', methods=['POST'])
@login_required
def shopping_delete_item(list_id, item_id):
    item = ShoppingItem.query.get_or_404(item_id)
    if item.list.user_id == current_user.id: db.session.delete(item); db.session.commit()
    return redirect(url_for('shopping_list', list_id=list_id))

@app.route('/shopping/<int:list_id>/delete', methods=['POST'])
@login_required
def shopping_delete_list(list_id):
    lst = ShoppingList.query.filter_by(id=list_id, user_id=current_user.id).first_or_404()
    db.session.delete(lst); db.session.commit()
    return redirect(url_for('shopping'))

# --- ЖЕЛАНИЯ ---
@app.route('/wishes')
@login_required
def wishes():
    wishes = Wish.query.filter_by(user_id=current_user.id).order_by(Wish.done, Wish.created_at.desc()).all()
    return render_template('wishes.html', wishes=wishes, total=sum(w.price for w in wishes if not w.done))

@app.route('/wishes/add', methods=['POST'])
@login_required
def wishes_add():
    name = request.form.get('name', '').strip()
    if name:
        try: price_val = float(request.form.get('price', '0')) if request.form.get('price') else 0
        except ValueError: price_val = 0
        db.session.add(Wish(name=name, link=request.form.get('link', '').strip(), price=price_val, priority=request.form.get('priority', 'normal'), user_id=current_user.id))
        db.session.commit()
    return redirect(url_for('wishes'))

@app.route('/wishes/toggle/<int:wish_id>', methods=['POST'])
@login_required
def wishes_toggle(wish_id):
    wish = Wish.query.filter_by(id=wish_id, user_id=current_user.id).first_or_404(); wish.done = not wish.done; db.session.commit()
    return redirect(url_for('wishes'))

@app.route('/wishes/delete/<int:wish_id>', methods=['POST'])
@login_required
def wishes_delete(wish_id):
    wish = Wish.query.filter_by(id=wish_id, user_id=current_user.id).first_or_404(); db.session.delete(wish); db.session.commit()
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
    
    all_events = Event.query.filter_by(user_id=current_user.id).all()
    events_by_day = {}
    for day in range(1, days_in_month + 1):
        target = dt.date(year, month, day)
        for e in all_events:
            if event_occurs_on(e, target): events_by_day.setdefault(day, []).append(e)
                
    month_names = ['', 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
    return render_template('calendar.html', year=year, month=month, month_name=month_names[month], first_weekday=first_weekday%7, days_in_month=days_in_month, events_by_day=events_by_day, categories=Category.query.filter_by(user_id=current_user.id).all(), today=today)

@app.route('/calendar/add-event', methods=['POST'])
@login_required
def calendar_add_event():
    title = request.form.get('title', '').strip()
    date_str = request.form.get('date', '')
    if title and date_str:
        try: event_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError: return redirect(url_for('calendar'))
        db.session.add(Event(title=title, date=event_date, description=request.form.get('description', '').strip(), repeat=request.form.get('repeat', 'none'), category_id=request.form.get('category_id', type=int), user_id=current_user.id))
        db.session.commit()
        return redirect(url_for('calendar', year=event_date.year, month=event_date.month))
    return redirect(url_for('calendar'))

@app.route('/calendar/categories', methods=['GET', 'POST'])
@login_required
def calendar_categories():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if name: db.session.add(Category(name=name, color=request.form.get('color', '#E53935'), user_id=current_user.id)); db.session.commit()
        return redirect(url_for('calendar_categories'))
    return render_template('calendar_categories.html', categories=Category.query.filter_by(user_id=current_user.id).all())

# --- ЗАМЕТКИ ---
@app.route('/notes')
@login_required
def notes():
    folder_id = request.args.get('folder_id', type=int)
    search = request.args.get('q', '').strip()
    query = Note.query.filter_by(deleted=False, user_id=current_user.id)
    if folder_id: query = query.filter_by(folder_id=folder_id)
    if search: query = query.filter(Note.title.contains(search) | Note.body.contains(search))
    return render_template('notes.html', notes=query.order_by(Note.pinned.desc(), Note.updated_at.desc()).all(), folders=NoteFolder.query.filter_by(user_id=current_user.id).all(), current_folder=folder_id, search=search)

@app.route('/notes/folder/create', methods=['POST'])
@login_required
def note_folder_create():
    name = request.form.get('name', '').strip()
    if name: db.session.add(NoteFolder(name=name, user_id=current_user.id)); db.session.commit()
    return redirect(url_for('notes'))

@app.route('/notes/new', methods=['POST'])
@login_required
def note_new():
    note = Note(title='Новая заметка', body='', folder_id=request.form.get('folder_id', type=int), user_id=current_user.id)
    db.session.add(note); db.session.commit()
    return redirect(url_for('note_edit', note_id=note.id))

@app.route('/notes/<int:note_id>')
@login_required
def note_edit(note_id): return render_template('notes_edit.html', note=Note.query.filter_by(id=note_id, user_id=current_user.id).first_or_404(), folders=NoteFolder.query.filter_by(user_id=current_user.id).all())

@app.route('/notes/<int:note_id>/save', methods=['POST'])
@login_required
def note_save(note_id):
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first_or_404()
    data = request.json
    if data:
        note.title = data.get('title', 'Без названия'); note.body = data.get('body', ''); note.folder_id = data.get('folder_id') if data.get('folder_id') else None
        db.session.commit()
        return jsonify({"status": "ok", "time": datetime.now().strftime('%H:%M')})
    return jsonify({"status": "error"}), 400

@app.route('/notes/<int:note_id>/delete', methods=['POST'])
@login_required
def note_delete(note_id):
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first_or_404(); note.deleted = True; db.session.commit()
    return redirect(url_for('notes'))

# --- ПОДПИСКИ ---
@app.route('/subscriptions')
@login_required
def subscriptions():
    subs = Subscription.query.filter_by(user_id=current_user.id).order_by(Subscription.next_date.asc()).all()
    total_monthly = sum(sub.price if sub.period == 'monthly' else (sub.price / 12 if sub.period == 'yearly' else sub.price * 4.33) for sub in subs)
    total_yearly = sum((sub.price * 12) if sub.period == 'monthly' else (sub.price if sub.period == 'yearly' else sub.price * 52) for sub in subs)
    return render_template('subscriptions.html', subs=subs, cats=SubCategory.query.filter_by(user_id=current_user.id).all(), total_monthly=total_monthly, total_yearly=total_yearly, today=date.today())

@app.route('/subscriptions/add', methods=['POST'])
@login_required
def sub_add():
    name = request.form.get('name', '').strip()
    date_str = request.form.get('next_date', '')
    if name and date_str:
        try: price_val = float(request.form.get('price', '0')) if request.form.get('price') else 0; next_date_val = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError: return redirect(url_for('subscriptions'))
        db.session.add(Subscription(name=name, price=price_val, period=request.form.get('period', 'monthly'), next_date=next_date_val, icon=request.form.get('icon', '📦'), category_id=request.form.get('category_id', type=int), user_id=current_user.id))
        db.session.commit()
    return redirect(url_for('subscriptions'))

# --- БИБЛИОТЕКА (Общая страница) ---
TMDB_TOKEN = os.environ.get("TMDB_TOKEN")

@app.route('/library/search', methods=['GET'])
@login_required
def library_search():
    query = request.args.get('q', '').strip()
    category = request.args.get('category', 'movie')
    
    if not query: return jsonify({'error': 'Empty query'}), 400
    results = []

    if category in ['movie', 'tv']:
        url = f"https://api.themoviedb.org/3/search/{category}?query={query}&language=ru-RU"
        headers = {"accept": "application/json", "Authorization": f"Bearer {TMDB_TOKEN}"}
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                for item in response.json().get('results', [])[:10]:
                    results.append({'api_id': str(item.get('id')), 'title': item.get('title') or item.get('name'), 'poster_url': f"https://image.tmdb.org/t/p/w500{item.get('poster_path')}" if item.get('poster_path') else '', 'description': item.get('overview', '')})
        except Exception: pass

    elif category == 'book':
        url = f"https://www.googleapis.com/books/v1/volumes?q={query}&maxResults=10"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                for item in response.json().get('items', []):
                    vol = item.get('volumeInfo', {})
                    results.append({'api_id': item.get('id'), 'title': vol.get('title'), 'poster_url': vol.get('imageLinks', {}).get('thumbnail', ''), 'description': vol.get('description', '')})
        except Exception: pass
        
    elif category == 'anime':
        # Jikan API (MyAnimeList) - без токена
        url = f"https://api.jikan.moe/v4/anime?q={query}&limit=10"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                for item in response.json().get('data', []):
                    results.append({'api_id': str(item.get('mal_id')), 'title': item.get('title'), 'poster_url': item.get('images', {}).get('jpg', {}).get('image_url', ''), 'description': item.get('synopsis', '')})
        except Exception: pass

    return jsonify(results)

@app.route('/library/add', methods=['POST'])
@login_required
def library_add():
    data = request.json
    if not data: return jsonify({'error': 'No data'}), 400

    if LibraryItem.query.filter_by(user_id=current_user.id, api_id=data.get('api_id'), category=data.get('category')).first():
        return jsonify({'status': 'exists'})

    db.session.add(LibraryItem(user_id=current_user.id, category=data.get('category'), api_id=data.get('api_id'), title=data.get('title'), poster_url=data.get('poster_url'), description=data.get('description'), status='want'))
    db.session.commit()
    return jsonify({'status': 'ok'})

@app.route('/library/item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def library_item(item_id):
    item = LibraryItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    if request.method == 'POST':
        item.status = request.form.get('status', 'want')
        item.rating = int(request.form.get('rating', 0))
        item.review = request.form.get('review', '')
        item.top_rank = int(request.form.get('top_rank', 0))
        db.session.commit()
        flash('Изменения сохранены!', 'success')
        return redirect(url_for('library_item', item_id=item.id))
    return render_template('library_item.html', item=item)

@app.route('/library/item/<int:item_id>/delete', methods=['POST'])
@login_required
def library_item_delete(item_id):
    item = LibraryItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    db.session.delete(item); db.session.commit()
    return redirect(url_for('library'))

@app.route('/library/<cat_code>/top10')
@login_required
def library_top10(cat_code):
    return render_template('library_top10.html', items=LibraryItem.query.filter_by(user_id=current_user.id, category=cat_code).order_by(LibraryItem.top_rank.asc()).all(), cat_code=cat_code)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/recipes')
@login_required
def recipes(): return render_template('recipes.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
