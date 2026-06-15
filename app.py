import os
import logging
from datetime import datetime
from flask import Flask, render_template
from flask_login import LoginManager
from config import Config
from models import db, User


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(name)s: %(message)s')

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.context_processor
    def inject_now():
        return {'now': datetime.utcnow}

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500

    from routes.auth import auth_bp
    from routes.menu import menu_bp
    from routes.orders import orders_bp
    from routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(menu_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(admin_bp)

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    with app.app_context():
        db.create_all()
        if not User.query.filter_by(role='admin').first():
            from models import Category, MenuItem

            admin = User(username='admin', email='admin@canteen.com',
                         role='admin', balance=0)
            admin.set_password('admin123')
            db.session.add(admin)

            student = User(username='demo', email='demo@canteen.com',
                           role='student', balance=50.0)
            student.set_password('demo123')
            db.session.add(student)

            mains = Category(name='Mains', description='Main courses')
            snacks = Category(name='Snacks', description='Light bites')
            drinks = Category(name='Drinks', description='Beverages')
            db.session.add_all([mains, snacks, drinks])
            db.session.flush()

            demo_items = [
                MenuItem(name='Chicken Rice', description='Steamed chicken with fragrant rice',
                         price=4.50, category_id=mains.id, stock=30, featured=True),
                MenuItem(name='Nasi Lemak', description='Coconut rice with sambal, egg & anchovies',
                         price=3.80, category_id=mains.id, stock=25, featured=True),
                MenuItem(name='Fried Noodles', description='Stir-fried noodles with vegetables',
                         price=3.50, category_id=mains.id, stock=20),
                MenuItem(name='Spring Rolls', description='Crispy vegetable spring rolls (4 pcs)',
                         price=2.00, category_id=snacks.id, stock=40),
                MenuItem(name='Curry Puff', description='Flaky pastry with spicy potato filling',
                         price=1.50, category_id=snacks.id, stock=35),
                MenuItem(name='Iced Lemon Tea', description='Refreshing chilled lemon tea',
                         price=1.20, category_id=drinks.id, stock=50),
                MenuItem(name='Orange Juice', description='Freshly squeezed orange juice',
                         price=2.00, category_id=drinks.id, stock=30),
                MenuItem(name='Mineral Water', description='500ml bottled water',
                         price=0.80, category_id=drinks.id, stock=100),
            ]
            db.session.add_all(demo_items)
            db.session.commit()

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000)
