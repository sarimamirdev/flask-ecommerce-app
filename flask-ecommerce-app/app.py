from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

# ============================================================================
# APPLICATION CONFIGURATION
# ============================================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'

# Force database to be created in the exact same folder
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'shopping.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)

# ============================================================================
# DATABASE MODELS
# ============================================================================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    stock_quantity = db.Column(db.Integer, default=0)
    image_filename = db.Column(db.String(200), nullable=True)
    category = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='cart_items')
    product = db.relationship('Product', backref='cart_items')


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Pending')
    shipping_address = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='orders')
    items = db.relationship('OrderItem', backref='order', cascade='all, delete-orphan')


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)

    product = db.relationship('Product')


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_cart_count(user_id):
    cart_items = CartItem.query.filter_by(user_id=user_id).all()
    return sum(item.quantity for item in cart_items)

def get_cart_total(user_id):
    cart_items = CartItem.query.filter_by(user_id=user_id).all()
    total = 0
    for item in cart_items:
        total += item.product.price * item.quantity
    return round(total, 2)

# ============================================================================
# ROUTES
# ============================================================================

@app.route('/')
def index():
    products = Product.query.limit(8).all()
    cart_count = get_cart_count(session.get('user_id')) if session.get('user_id') else 0
    return render_template('index.html', products=products, cart_count=cart_count)

@app.route('/products')
def products():
    category = request.args.get('category', '')
    search = request.args.get('search', '')
    
    query = Product.query
    if category:
        query = query.filter_by(category=category)
    if search:
        query = query.filter(Product.name.contains(search) | Product.description.contains(search))
    
    products = query.all()
    categories = db.session.query(Product.category).distinct().all()
    cart_count = get_cart_count(session.get('user_id')) if session.get('user_id') else 0
    
    return render_template('products.html', products=products, categories=categories, 
                         cart_count=cart_count, search=search, category=category)

@app.route('/product/<int:id>')
def product_detail(id):
    product = Product.query.get_or_404(id)
    cart_count = get_cart_count(session.get('user_id')) if session.get('user_id') else 0
    return render_template('product_detail.html', product=product, cart_count=cart_count)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        
        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('register'))
        
        user = User(username=username, email=email, full_name=full_name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash(f'Welcome back, {user.full_name}!', 'success')
            return redirect(url_for('products'))
        else:
            flash('Invalid username or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/cart')
def cart():
    if not session.get('user_id'):
        flash('Please login to view your cart.', 'warning')
        return redirect(url_for('login'))
    
    cart_items = CartItem.query.filter_by(user_id=session['user_id']).all()
    total = get_cart_total(session['user_id'])
    cart_count = get_cart_count(session['user_id'])
    return render_template('cart.html', cart_items=cart_items, total=total, cart_count=cart_count)

@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    if not session.get('user_id'):
        flash('Please login to add items to cart.', 'warning')
        return redirect(url_for('login'))
    
    quantity = int(request.form.get('quantity', 1))
    product = Product.query.get_or_404(product_id)
    
    if product.stock_quantity < quantity:
        flash('Not enough stock available.', 'danger')
        return redirect(url_for('product_detail', id=product_id))
    
    cart_item = CartItem.query.filter_by(user_id=session['user_id'], product_id=product_id).first()
    
    if cart_item:
        cart_item.quantity += quantity
    else:
        cart_item = CartItem(user_id=session['user_id'], product_id=product_id, quantity=quantity)
        db.session.add(cart_item)
    
    db.session.commit()
    flash(f'{product.name} added to cart!', 'success')
    return redirect(url_for('cart'))

@app.route('/update_cart/<int:item_id>', methods=['POST'])
def update_cart(item_id):
    quantity = int(request.form.get('quantity', 1))
    cart_item = CartItem.query.get_or_404(item_id)
    
    if quantity > 0:
        cart_item.quantity = quantity
    else:
        db.session.delete(cart_item)
    
    db.session.commit()
    return redirect(url_for('cart'))

@app.route('/remove_from_cart/<int:item_id>')
def remove_from_cart(item_id):
    cart_item = CartItem.query.get_or_404(item_id)
    db.session.delete(cart_item)
    db.session.commit()
    flash('Item removed from cart.', 'info')
    return redirect(url_for('cart'))

# ============================================================================
# FIXED CHECKOUT (PROCESSES ORDER, CLEARS CART, THEN SHOWS DEMO MESSAGE)
# ============================================================================

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if not session.get('user_id'):
        flash('Please login to checkout.', 'warning')
        return redirect(url_for('login'))
    
    cart_items = CartItem.query.filter_by(user_id=session['user_id']).all()
    
    if not cart_items:
        flash('Your cart is empty.', 'warning')
        return redirect(url_for('products'))
    
    total = get_cart_total(session['user_id'])
    cart_count = get_cart_count(session['user_id'])
    
    if request.method == 'POST':
        shipping_address = request.form.get('shipping_address')
        
        # 1. Create the Order
        order = Order(
            user_id=session['user_id'],
            total_amount=total,
            shipping_address=shipping_address,
            status='Pending'
        )
        db.session.add(order)
        db.session.flush()
        
        # 2. Create Order Items & Reduce Stock
        for item in cart_items:
            order_item = OrderItem(
                order_id=order.id,
                product_id=item.product_id,
                quantity=item.quantity,
                price=item.product.price
            )
            db.session.add(order_item)
            product = Product.query.get(item.product_id)
            product.stock_quantity -= item.quantity
        
        # 3. Clear the user's cart
        CartItem.query.filter_by(user_id=session['user_id']).delete()
        
        # 4. Commit all changes
        db.session.commit()
        
        # 5. Show the Demo Message!
        flash('Thank you for your purchase! This is a demo version.', 'success')
        return redirect(url_for('orders'))
    
    return render_template('checkout.html', cart_items=cart_items, total=total, cart_count=cart_count)

@app.route('/orders')
def orders():
    if not session.get('user_id'):
        flash('Please login to view your orders.', 'warning')
        return redirect(url_for('login'))
    
    # Fetches the orders you just created
    orders = Order.query.filter_by(user_id=session['user_id']).order_by(Order.created_at.desc()).all()
    cart_count = get_cart_count(session['user_id'])
    return render_template('orders.html', orders=orders, cart_count=cart_count)

# ============================================================================
# DATABASE SETUP
# ============================================================================

@app.route('/init_db')
def init_db():
    if Product.query.count() > 0:
        flash('Database already has products!', 'info')
        return redirect(url_for('products'))
    
    products = [
        Product(name='Black Hat', description='Classic black baseball cap with an adjustable strap.', price=24.99, stock_quantity=50, category='Accessories', image_filename='black_hat.png'),
        Product(name='Black Headphones', description='Premium over-ear headphones with deep bass and a comfortable fit.', price=89.99, stock_quantity=30, category='Electronics', image_filename='black_headphones.png'),
        Product(name='Black Smartwatch', description='Modern digital smartwatch with health tracking and a sleek display.', price=149.99, stock_quantity=25, category='Electronics', image_filename='black_smartwatch.png'),
        Product(name='Black Trousers', description='Stylish black cargo trousers featuring multiple utility pockets.', price=59.99, stock_quantity=40, category='Clothing', image_filename='black_trouser.png'),
        Product(name='Black Watch', description='A minimalist wristwatch with a black face and silver details.', price=45.99, stock_quantity=35, category='Accessories', image_filename='black_watch.jpg'),
        Product(name='Blue Hat', description='A stylish blue cap with a classic embroidered front.', price=29.99, stock_quantity=45, category='Accessories', image_filename='blue_hat.jpg'),
        Product(name='Blue Sneakers', description='A classic pair of blue and white sneakers with a vintage look.', price=79.99, stock_quantity=20, category='Footwear', image_filename='blue_sneaker.jpg'),
        Product(name='Blue Watch', description='A blue sports watch with a long-lasting battery and fitness tracking.', price=129.99, stock_quantity=15, category='Accessories', image_filename='blue_watch.jpg'),
        Product(name='Brown Hat', description='A solid brown baseball cap made from durable cotton.', price=24.99, stock_quantity=40, category='Accessories', image_filename='brown_hat.jpg'),
        Product(name='Brown Hoodie', description='A cozy brown hoodie with a front kangaroo pocket.', price=49.99, stock_quantity=50, category='Clothing', image_filename='brown_hoodie.jpg'),
        Product(name='Brown Sneakers', description='Stylish brown and cream sneakers with a bold street-style design.', price=69.99, stock_quantity=30, category='Footwear', image_filename='brownish_sneaker.jpg'),
        Product(name='Classic Hat', description='A classic tweed-style flat cap with a structured brim.', price=34.99, stock_quantity=25, category='Accessories', image_filename='classic_hat.jpg'),
        Product(name='Green Hoodie', description='A stylish green pullover hoodie with minimalist text on the chest.', price=54.99, stock_quantity=35, category='Clothing', image_filename='green_hoodie.jpg'),
        Product(name='Grey Trousers', description='Comfortable grey cargo trousers with multiple zippered pockets.', price=59.99, stock_quantity=40, category='Clothing', image_filename='grey_trouser.jpg'),
        Product(name='Net Hat', description='A breathable black cap with a mesh back panel.', price=19.99, stock_quantity=60, category='Accessories', image_filename='net_hat.jpg'),
        Product(name='Old Hat', description='A classic vintage-style hat with a textured finish.', price=39.99, stock_quantity=20, category='Accessories', image_filename='old_hat.jpg'),
        Product(name='Orange Watch', description='A bold orange smartwatch with a circular face and bright display.', price=199.99, stock_quantity=10, category='Electronics', image_filename='orange_watch.jpg'),
        Product(name='Red Hoodie', description='A rich red hoodie featuring expressive typography on the front.', price=49.99, stock_quantity=45, category='Clothing', image_filename='red_hoodie.jpg'),
        Product(name='RGB Headphones', description='Modern bluetooth headphones with RGB lighting on the earcups.', price=79.99, stock_quantity=25, category='Electronics', image_filename='rgb_headphone.jpg'),
        Product(name='Silver Watch', description='An elegant silver-tone metal watch with a dark blue face.', price=299.99, stock_quantity=8, category='Accessories', image_filename='silver_watch.jpg'),
        Product(name='Smartwatch', description='A premium smartwatch with a round face and sleek design.', price=109.99, stock_quantity=20, category='Electronics', image_filename='smartwatch.jpg'),
        Product(name='White Headphones', description='Stylish white headphones with a mesh headband and cushioned ears.', price=99.99, stock_quantity=20, category='Electronics', image_filename='white_headphone.jpg'),
        Product(name='White Joggers', description='Trendy white joggers with a flexible waistband and cuffed ankles.', price=49.99, stock_quantity=35, category='Clothing', image_filename='white_jogger.jpg'),
        Product(name='Zero Headphones', description='Sleek all-black headphones with a minimalist logo and soft ear padding.', price=69.99, stock_quantity=30, category='Electronics', image_filename='zero_headphone.jpg'),
    ]
    
    db.session.add_all(products)
    db.session.commit()
    
    flash(f'{len(products)} products added to database successfully!', 'success')
    return redirect(url_for('products'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print('Database created successfully!')
        print('Visit /init_db to add all products with images.')
    
    app.run(debug=True, host='127.0.0.1', port=5000)