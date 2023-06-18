import os
from datetime import datetime

from flask import Flask, render_template, flash, redirect, url_for, request, abort
from flask_bootstrap import Bootstrap
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, PickleType
from sqlalchemy.ext.mutable import MutableDict
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


def cart_not_empty(func):
    def wrapper(*args, **kwargs):
        if current_user.cart['cart']:
            return func(*args, **kwargs)
        else:
            return redirect(url_for('home'))

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
    orders = relationship('Order', backref='user')
    cart = Column(MutableDict.as_mutable(PickleType), default={'cart': {}})


class Order(db.Model):
    id = Column(Integer, primary_key=True)
    ordered_at = Column(String(20), default=datetime.now().strftime('%d/%m/%Y, %H:%M:%S'))
    amount = Column(Integer, nullable=False)
    user_id = Column(Integer, ForeignKey('user.id'))
    address = Column(String(150), default={})
    cart = Column(MutableDict.as_mutable(PickleType), default={})


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
    product_list = Product.query.all()
    db.session.commit()

    return render_template('index.html', current_user=current_user, products=product_list)


@app.route('/register', methods=['GET', 'POST'])
@no_user
def register():
    if request.method == 'POST':

        form = request.form
        password = form['password']
        confirmation = form['confirm']
        user = User.query.filter_by(email=form['email']).first()
        if not user:
            if password == confirmation:
                new_user = User(name=form['name'], last_name=form['lname'], email=form['email'],
                                password=generate_password_hash(password, method="pbkdf2:sha256", salt_length=8))
                db.session.add(new_user)
                db.session.commit()
                login_user(new_user)
                return redirect(url_for('home'))
            else:
                flash('סיסמאות לא תואמות')
        else:
            flash('כבר קיים חשבון עבור אימייל זה')

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


@app.route('/add-to-cart/<string:id>', methods=['POST', 'GET'])
@login_required
def add_to_cart(id):
    product_to_add = db.session.get(Product, int(id))
    user_cart = current_user.cart

    user_cart['cart'][id] = {
        'id': product_to_add.id,
        'name': product_to_add.name,
        'desc': product_to_add.desc,
        'price': product_to_add.price,
        'img': product_to_add.img,
        'qty': user_cart['cart'][id]['qty'] + 1 if id in user_cart['cart'] and 'qty' in user_cart['cart'][id] else 1,

    }

    user_cart['cart'][id]['total'] = user_cart['cart'][id]['qty'] * user_cart['cart'][id]['price'] if id in user_cart[
        'cart'] and 'qty' in user_cart['cart'][
                                                                                                          id] else 0
    items_price = 0
    for item in user_cart['cart']:
        items_price += user_cart['cart'][item]['price'] * user_cart['cart'][item]['qty']

    user_cart['items_price'] = items_price
    current_user.cart = user_cart
    db.session.commit()

    return redirect(url_for('home'))


@app.route('/cart')
@login_required
def cart():
    if current_user.cart['cart']:
        cart_data = {'items_price': current_user.cart['items_price'],
                     'items': [x for x in current_user.cart['cart'].values()]}
        return render_template('cart.html', cart_data=cart_data)
    return render_template('cart.html', cart_data=None)


@app.route('/update/<action>', methods=['GET', 'POST'])
@login_required
def update(action):
    action = action.split('_')
    product_to_add = db.session.get(Product, int(action[0]))
    user_cart = current_user.cart

    if not action[1] == 'd':
        user_cart['cart'][action[0]] = {
            'id': product_to_add.id,
            'name': product_to_add.name,
            'desc': product_to_add.desc,
            'price': product_to_add.price,
            'img': product_to_add.img,
            'qty': user_cart['cart'][action[0]]['qty'] - 1 if user_cart['cart'][action[0]]['qty'] > 0 and action[
                1] == 's' else
            user_cart['cart'][action[0]][
                'qty'] + 1 if
            user_cart['cart'][action[0]]['qty'] < product_to_add.qty and action[1] == 'a' else
            user_cart['cart'][action[0]]['qty']

        }
        user_cart['cart'][action[0]]['total'] = user_cart['cart'][action[0]]['qty'] * user_cart['cart'][action[0]][
            'price'] if action[
                            0] in user_cart['cart'] and 'qty' in \
                        user_cart['cart'][action[
                            0]] else 0
    else:
        user_cart['cart'].pop(action[0])
    items_price = 0
    for item in user_cart['cart']:
        items_price += user_cart['cart'][item]['price'] * user_cart['cart'][item]['qty']

    user_cart['items_price'] = items_price
    current_user.cart = user_cart
    db.session.commit()
    return redirect(url_for('cart'))


@app.route('/my-orders', methods=['GET', 'POST'])
@login_required
def my_orders():
    orders = current_user.orders
    return render_template('orders.html', orders=orders, user=current_user)


@app.route('/order/<int:id>', methods=['GET', 'POST'])
@login_required
def order(id):
    single_order = db.session.get(Order, id)
    return render_template('order.html', order=single_order, user=current_user)


@app.route('/orders', methods=['GET', 'POST'])
@admin_required
@login_required
def orders():
    order_list = Order.query.all()
    return render_template('orders.html', orders=order_list, user=current_user)


@app.route('/shipping/<int:checkout>', methods=['GET', 'POST'])
@cart_not_empty
@login_required
def shipping(checkout):
    form = request.form
    cart = current_user.cart

    if request.method == "POST" and checkout == 1:
        cart['shipping'] = {'price': int(form['shipping_price']), 'shipping_info': {}}

        db.session.commit()
    elif request.method == 'POST' and checkout == 0:
        print(f'start {current_user.cart}')
        info = {'name': f"{form['name']} {form['lname']}",
                'address': f"{form['address']}, {form['city']}, {form['country']}, {form['zip']}",
                'cart': [item for item in current_user.cart['cart'].values()]}
        cart['shipping']['shipping_info'] = {'name': f"{form['name']} {form['lname']}",
                                             'address': f"{form['address']}, {form['city']}, {form['country']}, {form['zip']}"}
        current_user.cart = cart
        current_user.cart['trick'] = 0
        db.session.commit()
        print(f'end {current_user.cart}')
        print(info)
        return render_template('place-order.html', info=info, user=current_user)

    return render_template('shipping.html', user=current_user)


@app.route('/place-order', methods=['GET', 'POST'])
@cart_not_empty
@login_required
def place_order():
    if request.method == "POST":
        order_data = {'name': current_user.cart['shipping']['shipping_info']['name'],
                      'cart': [item for item in current_user.cart['cart'].values()],
                      'shipping': current_user.cart['shipping']['price'],
                      'items_price': current_user.cart['items_price']}

        order = Order(amount=current_user.cart['items_price'], cart=order_data,
                      address=current_user.cart['shipping']['shipping_info']['address'], user=current_user)
        db.session.add(order)
        print(current_user.cart)
        print(order.cart)
        current_user.cart = {'cart': {}}
        db.session.commit()

        return redirect(url_for('order', id=order.id))
    render_template('place-order.html')


if __name__ == '__main__':
    app.run(debug=True)
