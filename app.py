import os
import platform
import uuid
import requests
import re
from flask_socketio import SocketIO, emit
import eventlet
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

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- Словарь флагов ---
COUNTRY_FLAGS = {
    'россия': '🇷🇺', 'russia': '🇷🇺',
    'япония': '🇯🇵', 'japan': '🇯🇵',
    'сша': '🇺🇸', 'usa': '🇺🇸', 'соединенные штаты': '🇺🇸',
    'казахстан': '🇰🇿', 'kazakhstan': '🇰🇿',
    'украина': '🇺🇦', 'ukraine': '🇺🇦',
    'беларусь': '🇧🇾', 'belarus': '🇧🇾',
    'германия': '🇩🇪', 'germany': '🇩🇪',
    'франция': '🇫🇷', 'france': '🇫🇷',
    'великобритания': '🇬🇧', 'uk': '🇬🇧', 'англия': '🇬🇧',
    'китай': '🇨🇳', 'china': '🇨🇳',
    'корея': '🇰🇷', 'korea': '🇰🇷',
    'италия': '🇮🇹', 'italy': '🇮🇹',
    'испания': '🇪🇸', 'spain': '🇪🇸',
    'канада': '🇨🇦', 'canada': '🇨🇦',
    'турция': '🇹🇷', 'turkey': '🇹🇷',
}

# --- Модели ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    display_name = db.Column(db.String(50), nullable=False)
    nickname = db.Column(db.String(50), unique=True, nullable=True)
    password_hash = db.Column(db.String(200), nullable=False)
    avatar = db.Column(db.String(200), nullable=True)
    bio = db.Column(db.Text, default='')
    country = db.Column(db.String(50), default='')

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
    category = db.Column(db.String(20), nullable=False)
    api_id = db.Column(db.String(50), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    poster_url = db.Column(db.String(500), default='')
    description = db.Column(db.Text, default='')
    status = db.Column(db.String(20), default='want') 
    rating = db.Column(db.Integer, default=0) 
    review = db.Column(db.Text, default='')
    top_rank = db.Column(db.Integer, default=0) 
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class FriendRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sender = db.relationship('User', foreign_keys=[sender_id])
    receiver = db.relationship('User', foreign_keys=[receiver_id])

class BlockedUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    blocker_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    blocked_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    is_edited = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_messages')

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, default='')
    image_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='posts')
    likes = db.relationship('Like', backref='post', cascade='all, delete-orphan')

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except Exception:
        return None

with app.app_context():
    db.create_all()
    try:
        from sqlalchemy import text
        db.session.execute(text("ALTER TABLE user ADD COLUMN bio TEXT DEFAULT ''"))
        db.session.execute(text("ALTER TABLE user ADD COLUMN country VARCHAR(50) DEFAULT ''"))
        db.session.commit()
    except Exception:
        pass

# --- АВТОРИЗАЦИЯ ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        login_input = request.form.get('username')
        password = request.form.get('password')
        
        # Ищем либо по почте, либо по нику
        user = User.query.filter((User.username == login_input) | (User.nickname == login_input)).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Неправильный логин (почта/ник) или пароль', 'error')
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
    posts = Post.query.filter_by(user_id=current_user.id).order_by(Post.created_at.desc()).all()
    return render_template('profile.html', user=current_user, posts=posts, flags=COUNTRY_FLAGS)

@app.route('/profile/<nickname>')
@login_required
def user_profile(nickname):
    user = User.query.filter_by(nickname=nickname).first_or_404()
    posts = Post.query.filter_by(user_id=user.id).order_by(Post.created_at.desc()).all()
    return render_template('user_profile.html', user=user, posts=posts, flags=COUNTRY_FLAGS)

@app.route('/profile/settings')
@login_required
def profile_settings():
    return render_template('profile_settings.html')

@app.route('/profile/save_settings', methods=['POST'])
@login_required
def profile_save_settings():
    current_user.display_name = request.form.get('display_name', '').strip()
    current_user.country = request.form.get('country', '').strip()
    current_user.bio = request.form.get('bio', '').strip()
    db.session.commit()
    flash('Профиль успешно обновлен!', 'success')
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

# --- ПОСТЫ ---
@app.route('/post/add', methods=['POST'])
@login_required
def add_post():
    content = request.form.get('content', '').strip()
    image = request.files.get('image')
    image_url = None
    
    if image and image.filename != '':
        filename = 'post_' + str(uuid.uuid4())[:8] + '_' + secure_filename(image.filename)
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        image_url = filename

    if content or image_url:
        new_post = Post(user_id=current_user.id, content=content, image_url=image_url)
        db.session.add(new_post)
        db.session.commit()
    
    return redirect(request.referrer or url_for('profile'))

@app.route('/post/<int:post_id>/like', methods=['POST'])
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    like = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    
    if like:
        db.session.delete(like)
    else:
        db.session.add(Like(user_id=current_user.id, post_id=post_id))
        
    db.session.commit()
    return redirect(request.referrer or url_for('profile'))

# --- ГЛАВНАЯ ---
@app.route('/')
@login_required
def index(): return render_template('index.html')

# --- ОСТАЛЬНЫЕ РАЗДЕЛЫ ---
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

TMDB_TOKEN = os.environ.get("TMDB_TOKEN")
GOOGLE_BOOKS_KEY = os.environ.get("GOOGLE_BOOKS_KEY")

@app.route('/library')
@login_required
def library():
    items = LibraryItem.query.filter_by(user_id=current_user.id).order_by(LibraryItem.created_at.desc()).all()
    return render_template('library.html', items=items)

@app.route('/library/search', methods=['GET'])
@login_required
def library_search():
    query = request.args.get('q', '').strip()
    category = request.args.get('category', 'movie')
    page = request.args.get('page', 1, type=int)
    
    if not query: 
        return jsonify({'error': 'Empty query'}), 400
    
    results = []

    if category in ['movie', 'tv']:
        url = f"https://api.themoviedb.org/3/search/{category}?query={query}&language=ru-RU&page={page}"
        headers = {"accept": "application/json", "Authorization": f"Bearer {TMDB_TOKEN}"}
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                for item in response.json().get('results', [])[:10]:
                    results.append({
                        'api_id': str(item.get('id')), 
                        'title': item.get('title') or item.get('name'), 
                        'poster_url': f"https://image.tmdb.org/t/p/w500{item.get('poster_path')}" if item.get('poster_path') else '', 
                        'description': item.get('overview', '')
                    })
        except Exception as e: 
            print(f"TMDB Error: {e}")

    elif category == 'book':
        url = f"https://www.googleapis.com/books/v1/volumes?q={query}&maxResults=40&key={GOOGLE_BOOKS_KEY}"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                for item in response.json().get('items', []):
                    vol = item.get('volumeInfo', {})
                    results.append({
                        'api_id': item.get('id'), 
                        'title': vol.get('title', 'Без названия'), 
                        'poster_url': vol.get('imageLinks', {}).get('thumbnail', ''), 
                        'description': vol.get('description', '')
                    })
        except Exception as e: 
            print(f"Books Error: {e}")
        
    elif category == 'anime':
        url = "https://shikimori.one/api/graphql"
        query_str = """
        query($search: String, $page: Int, $limit: Int) {
          animes(search: $search, page: $page, limit: $limit) {
            id
            name
            russian
            description
            poster { mainUrl }
          }
        }
        """
        variables = {"search": query, "page": page, "limit": 10}
        headers = {"User-Agent": "TabibitoHub/1.0"}
        
        try:
            response = requests.post(url, json={'query': query_str, 'variables': variables}, headers=headers)
            if response.status_code == 200:
                data = response.json().get('data', {}).get('animes', [])
                for item in data:
                    title = item.get('russian') or item.get('name') or 'Без названия'
                    poster = item.get('poster', {}).get('mainUrl', '') if item.get('poster') else ''
                    desc = re.sub('<[^<]+?>', '', item.get('description', '')) if item.get('description') else ''
                    
                    results.append({
                        'api_id': str(item.get('id')), 
                        'title': title, 
                        'poster_url': poster, 
                        'description': desc
                    })
        except Exception as e: 
            print(f"Shikimori Error: {e}")

    return jsonify(results)

@app.route('/library/add', methods=['POST'])
@login_required
def library_add():
    data = request.json
    if not data: 
        return jsonify({'error': 'No data'}), 400

    if LibraryItem.query.filter_by(user_id=current_user.id, api_id=data.get('api_id'), category=data.get('category')).first():
        return jsonify({'status': 'exists'})

    db.session.add(LibraryItem(
        user_id=current_user.id, 
        category=data.get('category'), 
        api_id=data.get('api_id'), 
        title=data.get('title'), 
        poster_url=data.get('poster_url'), 
        description=data.get('description'), 
        status='want'
    ))
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
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for('library'))

@app.route('/library/<cat_code>/top10')
@login_required
def library_top10(cat_code):
    items = LibraryItem.query.filter(
        LibraryItem.user_id == current_user.id, 
        LibraryItem.category == cat_code, 
        LibraryItem.top_rank > 0
    ).order_by(LibraryItem.top_rank.asc()).all()
    return render_template('library_top10.html', items=items, cat_code=cat_code)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/recipes')
@login_required
def recipes(): 
    return render_template('recipes.html')

@app.route('/friends')
@login_required
def friends():
    my_friends = User.query.join(FriendRequest, 
        ((FriendRequest.sender_id == User.id) & (FriendRequest.receiver_id == current_user.id)) |
        ((FriendRequest.receiver_id == User.id) & (FriendRequest.sender_id == current_user.id))
    ).filter(FriendRequest.status == 'accepted').all()

    incoming_reqs = FriendRequest.query.filter_by(receiver_id=current_user.id, status='pending').all()
    outgoing_reqs = FriendRequest.query.filter_by(sender_id=current_user.id, status='pending').all()
    blocked_users = User.query.join(BlockedUser, BlockedUser.blocked_id == User.id).filter(BlockedUser.blocker_id == current_user.id).all()

    return render_template('friends.html', my_friends=my_friends, incoming_reqs=incoming_reqs, outgoing_reqs=outgoing_reqs, blocked_users=blocked_users)

@app.route('/friends/add', methods=['POST'])
@login_required
def friends_add():
    nickname = request.form.get('nickname', '').strip().replace('@', '')
    user_to_add = User.query.filter_by(nickname=nickname).first()

    if not user_to_add:
        flash('Пользователь с таким ником не найден', 'error')
    elif user_to_add.id == current_user.id:
        flash('Ты не можешь добавить самого себя', 'error')
    else:
        existing_req = FriendRequest.query.filter(
            ((FriendRequest.sender_id == current_user.id) & (FriendRequest.receiver_id == user_to_add.id)) |
            ((FriendRequest.sender_id == user_to_add.id) & (FriendRequest.receiver_id == current_user.id))
        ).first()

        if existing_req:
            flash('Заявка уже отправлена или вы уже друзья', 'error')
        else:
            db.session.add(FriendRequest(sender_id=current_user.id, receiver_id=user_to_add.id))
            db.session.commit()
            flash('Заявка в друзья отправлена!', 'success')

    return redirect(url_for('friends'))

@app.route('/friends/accept/<int:req_id>', methods=['POST'])
@login_required
def friends_accept(req_id):
    req = FriendRequest.query.get_or_404(req_id)
    if req.receiver_id == current_user.id:
        req.status = 'accepted'
        db.session.commit()
    return redirect(url_for('friends'))

@app.route('/friends/reject/<int:req_id>', methods=['POST'])
@login_required
def friends_reject(req_id):
    req = FriendRequest.query.get_or_404(req_id)
    if req.receiver_id == current_user.id or req.sender_id == current_user.id:
        db.session.delete(req)
        db.session.commit()
    return redirect(url_for('friends'))

@app.route('/friends/block/<int:user_id>', methods=['POST'])
@login_required
def friends_block(user_id):
    if user_id != current_user.id:
        FriendRequest.query.filter(
            ((FriendRequest.sender_id == current_user.id) & (FriendRequest.receiver_id == user_id)) |
            ((FriendRequest.sender_id == user_id) & (FriendRequest.receiver_id == current_user.id))
        ).delete()
        
        db.session.add(BlockedUser(blocker_id=current_user.id, blocked_id=user_id))
        db.session.commit()
        flash('Пользователь заблокирован', 'success')
    return redirect(url_for('friends'))

@app.route('/friends/unblock/<int:user_id>', methods=['POST'])
@login_required
def friends_unblock(user_id):
    block = BlockedUser.query.filter_by(blocker_id=current_user.id, blocked_id=user_id).first()
    if block:
        db.session.delete(block)
        db.session.commit()
    return redirect(url_for('friends'))

@app.route('/chat')
@login_required
def chat_list():
    messages = Message.query.filter((Message.sender_id == current_user.id) | (Message.receiver_id == current_user.id)).order_by(Message.created_at.desc()).all()
    chat_partners = {}
    for msg in messages:
        partner = msg.receiver if msg.sender_id == current_user.id else msg.sender
        if partner.id not in chat_partners:
            chat_partners[partner.id] = partner
    return render_template('chat_list.html', partners=list(chat_partners.values()))

@app.route('/chat/<nickname>')
@login_required
def chat_room(nickname):
    partner = User.query.filter_by(nickname=nickname).first_or_404()
    if partner.id == current_user.id:
        flash('Нельзя писать самому себе', 'error')
        return redirect(url_for('chat_list'))
        
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == partner.id)) |
        ((Message.sender_id == partner.id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.created_at.asc()).all()

    for m in messages:
        if m.receiver_id == current_user.id and not m.is_read:
            m.is_read = True
    db.session.commit()

    return render_template('chat_room.html', partner=partner, messages=messages)

@socketio.on('send_message')
def handle_send_message(data):
    if not current_user.is_authenticated: return
    receiver = User.query.filter_by(nickname=data['receiver']).first()
    if not receiver: return

    new_msg = Message(sender_id=current_user.id, receiver_id=receiver.id, text=data['text'])
    db.session.add(new_msg)
    db.session.commit()

    emit('receive_message', {
        'sender': current_user.nickname,
        'receiver': receiver.nickname,
        'text': data['text'],
        'time': new_msg.created_at.strftime('%H:%M')
    }, broadcast=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, debug=False, host='0.0.0.0', port=port)
