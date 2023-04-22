import os
from datetime import datetime

from flask import Flask, render_template, flash, redirect, url_for, request, abort
from flask_bootstrap import Bootstrap
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, PickleType
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///online-store.db'
app.config['SECRET_KEY'] = 'something_secret'
db = SQLAlchemy(app)
Bootstrap(app)

login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def admin_required(func):
    def wrapper(*args, **kwargs):
        if current_user.is_authenticated and current_user.is_admin:
            return func(*args, **kwargs)
        else:
            return abort(403)

    wrapper.__name__ = func.__name__
    return wrapper


def no_user(func):
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return func(*args, **kwargs)
        else:
            return home()

    wrapper.__name__ = func.__name__
    return wrapper


class User(db.Model, UserMixin):
    id = Column(Integer, primary_key=True)
    is_admin = Column(Boolean, default=False)
    name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    email = Column(String(100), nullable=False, unique=True)
    password = Column(String(100), nullable=False)
    orders = relationship('Order', backref='users')
    cart = Column(PickleType)


order_product = db.Table('order_product',
                         Column('order_id', Integer, ForeignKey('order.id')),
                         Column('product_id', Integer, ForeignKey('product.id'))
                         )


class Order(db.Model):
    id = Column(Integer, primary_key=True)
    ordered_at = Column(String(20), default=datetime.now().strftime('%d/%m/%Y, %H:%M:%S'))
    amount = Column(Integer, nullable=False)
    user_id = Column(Integer, ForeignKey('user.id'))
    products = relationship('Product', secondary=order_product, backref='orders')


class Product(db.Model):
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, default="שם...")
    desc = Column(String(300), nullable=False, default="תיאור...")
    qty = Column(Integer, default=0)
    price = Column(Integer, default=0)
    price_off = Column(Integer, default=0)
    img = Column(String(200))


with app.app_context():
    db.create_all()


@app.route('/', methods=['GET', 'POST'])
def home():
    products = Product.query.all()
    return render_template('index.html', current_user=current_user, products=products)


@app.route('/register', methods=['GET', 'POST'])
@no_user
def register():
    if request.method == 'POST':

        form = request.form
        password = form['password']
        confirmation = form['confirm']
        if password == confirmation:
            new_user = User(name=form['name'], last_name=form['lname'], email=form['email'],
                            password=generate_password_hash(password, method="pbkdf2:sha256", salt_length=8))
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('home'))
        else:
            flash('סיסמאות לא תואמות')
    return render_template('register.html', current_user=current_user)


@app.route('/signin', methods=['GET', 'POST'])
@no_user
def signin():
    if request.method == 'POST':
        form = request.form
        user = User.query.filter_by(email=form['email']).first()
        if user and check_password_hash(user.password, form['password']):
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash('סיסמה או אימייל לא נכונים')

    return render_template('signin.html', current_user=current_user)


@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    if current_user:
        logout_user()
    return redirect(url_for('home'))


@app.route('/product/<id>', methods=['GET'])
def product(id):
    prod = db.session.get(Product, int(id))
    return render_template('product.html', product=prod)


@app.route('/products')
@admin_required
@login_required
def products():
    product_list = Product.query.all()
    return render_template('products.html', products=product_list)


@app.route('/add-product', methods=['POST', 'GET'])
@admin_required
@login_required
def add_product():
    if request.method == 'POST':
        product = Product()
        db.session.add(product)
        db.session.commit()
    return redirect(url_for('products'))


@app.route('/edit-product/<id>', methods=['GET', 'POST'])
@admin_required
@login_required
def edit_product(id):
    product = db.session.get(Product, int(id))
    if request.method == 'POST':
        form = request.form
        product.name = form['name']
        product.desc = form['desc']
        product.price = form['price']
        product.price_off = form['price_off']
        product.qty = form['qty']
        file = request.files['img']
        if file:
            file.save(os.path.join("static/images", secure_filename(file.filename)))
            product.img = file.filename
        db.session.commit()
        return redirect(url_for('products'))
    return render_template('edit-product.html', product=product)


@app.route('/delete-product/<id>', methods=['GET', 'POST'])
@admin_required
@login_required
def delete_product(id):
    product = db.session.get(Product, int(id))
    if product:
        db.session.delete(product)
        db.session.commit()
    return redirect(url_for('products'))


@app.route('/users', methods=['GET', 'POST'])
@admin_required
@login_required
def users():
    user_list = User.query.all()
    return render_template('users.html', users=user_list)


@app.route('/add-to-cart/<id>', methods=['POST', 'GET'])
def add_to_cart(id):
    product_to_add = db.session.get(Product, int(id))
    if not current_user.cart:
        current_user.cart = {
            str(product_to_add.id): {'name': product_to_add.name, 'price': product_to_add.price, 'qty': 1}}
    else:
        cart = current_user.cart[str(id)]
        current_user.cart = {
            str(product_to_add.id): {'name': product_to_add.name, 'price': product_to_add.price,
                                     'qty': cart['qty'] + 1}}

    db.session.commit()

    return redirect(url_for('home'))


@app.route('/my-orders', methods=['GET', 'POST'])
@login_required
def my_orders():
    order_list = Order.query.all()
    return render_template('orders.html', orders=order_list, user=current_user)


@app.route('/orders', methods=['GET', 'POST'])
@admin_required
@login_required
def orders():
    order_user = []
    order_list = Order.query.all()
    for order in order_list:
        order_user.append([order, current_user])

    return render_template('orders.html', orders=order_user)


if __name__ == '__main__':
    app.run(debug=True)
