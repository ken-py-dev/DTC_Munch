from datetime import datetime, timezone
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student')
    student_id = db.Column(db.String(20), unique=True, nullable=True)
    balance = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    orders = db.relationship('Order', backref='user', lazy='dynamic')
    favorites = db.relationship('Favorite', backref='user', lazy='dynamic',
                                cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == 'admin'


class Favorite(db.Model):
    __tablename__ = 'favorites'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    menu_item_id = db.Column(db.Integer, db.ForeignKey('menu_items.id'), nullable=False)

    __table_args__ = (db.UniqueConstraint('user_id', 'menu_item_id'),)


class Category(db.Model):
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.String(256))

    items = db.relationship('MenuItem', backref='category', lazy='dynamic')


class MenuItem(db.Model):
    __tablename__ = 'menu_items'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    image = db.Column(db.String(256), nullable=True)
    available = db.Column(db.Boolean, default=True)
    stock = db.Column(db.Integer, default=0)
    featured = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    order_items = db.relationship('OrderItem', backref='menu_item', lazy='dynamic')

    favorites = db.relationship('Favorite', backref='menu_item', lazy='dynamic',
                                cascade='all, delete-orphan')

    @property
    def image_src(self):
        if not self.image:
            return None
        if self.image.startswith(('http://', 'https://', '//')):
            return self.image
        return '/static/uploads/' + self.image

    @property
    def avg_rating(self):
        row = db.session.query(func.avg(OrderItem.rating)).filter(
            OrderItem.menu_item_id == self.id,
            OrderItem.rating.isnot(None)
        ).scalar()
        return round(row, 1) if row else None

    def is_favorited_by(self, user):
        if user.is_authenticated:
            return Favorite.query.filter_by(user_id=user.id,
                                            menu_item_id=self.id).first() is not None
        return False

    def __str__(self):
        return f'{self.name} - ${self.price:.2f}'


class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    order_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    total_amount = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(db.String(20), nullable=False, default='pending')
    payment_method = db.Column(db.String(20), default='balance')
    paid = db.Column(db.Boolean, default=False)
    invoice_ref = db.Column(db.String(20), unique=True, nullable=True)
    previous_status = db.Column(db.String(20), nullable=True)

    items = db.relationship('OrderItem', backref='order', lazy='dynamic',
                            cascade='all, delete-orphan')

    @property
    def invoice_number(self):
        return self.invoice_ref or f'INV-{self.id:04d}'


class OrderItem(db.Model):
    __tablename__ = 'order_items'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    menu_item_id = db.Column(db.Integer, db.ForeignKey('menu_items.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Float, nullable=False)
    rating = db.Column(db.Integer, nullable=True)
    review = db.Column(db.Text, nullable=True)

    def subtotal(self):
        return self.quantity * self.unit_price
