from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id: int = db.Column(db.Integer, primary_key=True)
    username: str = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email: str = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash: str = db.Column(db.String(256), nullable=False)
    role: str = db.Column(db.String(20), nullable=False, default='student')
    student_id: Optional[str] = db.Column(db.String(20), unique=True, nullable=True)
    balance: Decimal = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))
    created_at: datetime = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    orders = db.relationship('Order', backref='user', lazy='dynamic')
    favorites = db.relationship('Favorite', backref='user', lazy='dynamic',
                                cascade='all, delete-orphan')

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def is_admin(self) -> bool:
        return self.role == 'admin'


class Favorite(db.Model):
    __tablename__ = 'favorites'

    id: int = db.Column(db.Integer, primary_key=True)
    user_id: int = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    menu_item_id: int = db.Column(db.Integer, db.ForeignKey('menu_items.id'), nullable=False)

    __table_args__ = (db.UniqueConstraint('user_id', 'menu_item_id'),)


class Category(db.Model):
    __tablename__ = 'categories'

    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(db.String(64), unique=True, nullable=False)
    description: Optional[str] = db.Column(db.String(256))

    items = db.relationship('MenuItem', backref='category', lazy='dynamic')


class MenuItem(db.Model):
    __tablename__ = 'menu_items'

    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(db.String(128), nullable=False)
    description: Optional[str] = db.Column(db.Text, nullable=True)
    price: Decimal = db.Column(db.Numeric(10, 2), nullable=False)
    category_id: int = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    image: Optional[str] = db.Column(db.String(256), nullable=True)
    available: bool = db.Column(db.Boolean, default=True)
    stock: int = db.Column(db.Integer, default=0)
    featured: bool = db.Column(db.Boolean, default=False)
    created_at: datetime = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    order_items = db.relationship('OrderItem', backref='menu_item', lazy='dynamic')

    favorites = db.relationship('Favorite', backref='menu_item', lazy='dynamic',
                                cascade='all, delete-orphan')

    @property
    def image_src(self) -> Optional[str]:
        if not self.image:
            return None
        if self.image.startswith(('http://', 'https://', '//')):
            return self.image
        return '/static/uploads/' + self.image

    @property
    def avg_rating(self) -> Optional[float]:
        row = db.session.query(func.avg(OrderItem.rating)).filter(
            OrderItem.menu_item_id == self.id,
            OrderItem.rating.isnot(None)
        ).scalar()
        return round(row, 1) if row else None

    def is_favorited_by(self, user: User) -> bool:
        if user.is_authenticated:
            return Favorite.query.filter_by(user_id=user.id,
                                            menu_item_id=self.id).first() is not None
        return False

    def __str__(self) -> str:
        return f'{self.name} - ₱{self.price:.2f}'


ALLOWED_STATUS_TRANSITIONS = {
    'pending': ['confirmed', 'cancel_requested'],
    'confirmed': ['preparing', 'cancel_requested'],
    'pending_payment': ['confirmed', 'cancel_requested'],
    'preparing': ['ready', 'cancel_requested'],
    'cancel_requested': ['cancelled'],
    'ready': ['completed'],
    'completed': [],
    'cancelled': [],
}


class Order(db.Model):
    __tablename__ = 'orders'

    id: int = db.Column(db.Integer, primary_key=True)
    user_id: int = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    order_date: datetime = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    total_amount: Decimal = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal('0.00'))
    status: str = db.Column(db.String(20), nullable=False, default='pending')
    payment_method: str = db.Column(db.String(20), default='balance')
    paid: bool = db.Column(db.Boolean, default=False)
    invoice_ref: Optional[str] = db.Column(db.String(20), unique=True, nullable=True)
    previous_status: Optional[str] = db.Column(db.String(20), nullable=True)

    items = db.relationship('OrderItem', backref='order', lazy='select',
                            cascade='all, delete-orphan')

    @property
    def invoice_number(self) -> str:
        return self.invoice_ref or f'INV-{self.id:04d}'


class OrderItem(db.Model):
    __tablename__ = 'order_items'

    id: int = db.Column(db.Integer, primary_key=True)
    order_id: int = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    menu_item_id: int = db.Column(db.Integer, db.ForeignKey('menu_items.id'), nullable=False)
    quantity: int = db.Column(db.Integer, nullable=False, default=1)
    unit_price: Decimal = db.Column(db.Numeric(10, 2), nullable=False)
    rating: Optional[int] = db.Column(db.Integer, nullable=True)
    review: Optional[str] = db.Column(db.Text, nullable=True)

    def subtotal(self) -> Decimal:
        return self.quantity * self.unit_price
