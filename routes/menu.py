from flask import Blueprint, render_template, request
from flask_login import current_user
from models import db, MenuItem, Category

menu_bp = Blueprint('menu', __name__)


@menu_bp.route('/')
def index():
    categories = Category.query.all()
    selected_category = request.args.get('category', type=int)
    search = request.args.get('q', '').strip()
    featured_only = request.args.get('featured', type=int)

    query = MenuItem.query.filter_by(available=True)

    if selected_category:
        query = query.filter_by(category_id=selected_category)

    if featured_only:
        query = query.filter_by(featured=True)

    if search:
        like = f'%{search}%'
        query = query.filter(
            db.or_(MenuItem.name.ilike(like), MenuItem.description.ilike(like))
        )

    items = query.all()

    if current_user.is_authenticated:
        fav_ids = {f.menu_item_id for f in current_user.favorites}
        items.sort(key=lambda i: (i.id not in fav_ids, i.featured and 0 or 1, i.name))
    else:
        items.sort(key=lambda i: (not i.featured, i.name))

    return render_template('menu/menu.html', items=items, categories=categories,
                           selected_category=selected_category, search=search,
                           featured_only=featured_only)
