import os
import platform
from datetime import datetime, date
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
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
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
    from calendar import monthrange
    import datetime as dt

    today = dt.date.today()
    year = request.args.get('year', today.year, type=int)
    month = request.args.get('month', today.month, type=int)

    if month < 1:
        month = 12
        year -= 1
    elif month > 12:
        month = 1
        year += 1

    first_weekday, days_in_month = monthrange(year, month)
    # first_weekday: 0 = понедельник, 6 = воскресенье (в Python)
    # приведём к 0 = понедельник, но нам нужен первый день недели = понедельник
    first_weekday = (first_weekday) % 7  # 0 = понедельник

    events = Event.query.filter(
        db.extract('year', Event.date) == year,
        db.extract('month', Event.date) == month
    ).all()

    events_by_day = {}
    for e in events:
        events_by_day.setdefault(e.date.day, []).append(e)

    categories = Category.query.all()

    month_names = ['', 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
                   'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']

    return render_template('calendar.html',
                           year=year, month=month,
                           month_name=month_names[month],
                           first_weekday=first_weekday,
                           days_in_month=days_in_month,
                           events_by_day=events_by_day,
                           categories=categories,
                           today=today)


@app.route('/calendar/add-event', methods=['POST'])
def calendar_add_event():
    title = request.form.get('title', '').strip()
    date_str = request.form.get('date', '')
    description = request.form.get('description', '').strip()
    category_id = request.form.get('category_id', type=int)

    if title and date_str:
        try:
            event_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return redirect(url_for('calendar'))

        db.session.add(Event(
            title=title,
            date=event_date,
            description=description,
            category_id=category_id if category_id else None
        ))
        db.session.commit()
    return redirect(url_for('calendar', year=event_date.year, month=event_date.month))


@app.route('/calendar/delete-event/<int:event_id>', methods=['POST'])
def calendar_delete_event(event_id):
    event = Event.query.get_or_404(event_id)
    db.session.delete(event)
    db.session.commit()
    return redirect(url_for('calendar'))


@app.route('/calendar/categories', methods=['GET', 'POST'])
def calendar_categories():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        color = request.form.get('color', '#FF6B00')
        if name:
            db.session.add(Category(name=name, color=color))
            db.session.commit()
        return redirect(url_for('calendar_categories'))

    categories = Category.query.all()
    return render_template('calendar_categories.html', categories=categories)


@app.route('/calendar/categories/delete/<int:cat_id>', methods=['POST'])
def calendar_delete_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    db.session.delete(cat)
    db.session.commit()
    return redirect(url_for('calendar_categories'))


# --- Рецепты ---
@app.route('/recipes')
def recipes():
    return render_template('recipes.html')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
