import os
import uuid
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, abort, current_app)
from flask_login import login_required, current_user
from models import db, User, Order, OrderItem, MenuItem, Category
from forms import MenuItemForm, CategoryForm
from sqlalchemy import exc

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
PER_PAGE = 20

ALLOWED_STATUS_TRANSITIONS = {
    'pending': ['confirmed', 'cancel_requested'],
    'confirmed': ['preparing', 'cancel_requested'],
    'preparing': ['ready', 'cancel_requested'],
    'pending_payment': ['confirmed', 'cancel_requested'],
    'cancel_requested': ['cancelled'],
    'ready': ['completed'],
    'completed': [],
    'cancelled': [],
}


def allowed_file(filename):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    return ext in current_app.config['ALLOWED_EXTENSIONS']


def save_upload(file):
    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        name = str(uuid.uuid4()) + '.' + ext
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], name)
        file.save(path)
        return name
    return None


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import func

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    def revenue_since(dt):
        return db.session.query(func.coalesce(func.sum(Order.total_amount), 0))\
            .filter(Order.order_date >= dt, Order.paid == True,
                    Order.status != 'cancelled').scalar()

    def count_since(dt, *filters):
        q = Order.query.filter(Order.order_date >= dt)
        for f in filters:
            q = q.filter(f)
        return q.count()

    total_revenue = revenue_since(datetime(2000, 1, 1, tzinfo=timezone.utc))
    today_revenue = revenue_since(today_start)
    week_revenue = revenue_since(week_start)
    month_revenue = revenue_since(month_start)

    total_users = User.query.count()
    total_items = MenuItem.query.count()
    orders_today = count_since(today_start)
    orders_total = Order.query.count()
    pending_invoices = Order.query.filter_by(paid=False).count()
    pending_orders = Order.query.filter(
        Order.status.in_(['pending', 'pending_payment', 'confirmed', 'preparing'])
    ).count()

    popular = db.session.query(
        MenuItem.name, func.sum(OrderItem.quantity).label('qty')
    ).join(OrderItem, OrderItem.menu_item_id == MenuItem.id)\
     .group_by(MenuItem.id, MenuItem.name)\
     .order_by(func.sum(OrderItem.quantity).desc())\
     .limit(5).all()

    cat_sales = db.session.query(
        Category.name, func.sum(OrderItem.quantity).label('qty'),
        func.sum(MenuItem.price * OrderItem.quantity).label('rev')
    ).select_from(OrderItem)\
     .join(MenuItem)\
     .join(Category)\
     .group_by(Category.id, Category.name)\
     .order_by(func.sum(OrderItem.quantity).desc()).all()

    balance_orders = Order.query.filter_by(payment_method='balance').count()
    manual_orders = Order.query.filter_by(payment_method='manual').count()

    status_counts = db.session.query(
        Order.status, func.count(Order.id)
    ).group_by(Order.status).all()

    new_users_30d = User.query.filter(
        User.created_at >= (now - timedelta(days=30))
    ).count()

    recent_orders = Order.query.order_by(Order.order_date.desc()).limit(5).all()

    chart_days = []
    for i in range(6, -1, -1):
        day = today_start - timedelta(days=i)
        rev = db.session.query(func.coalesce(func.sum(Order.total_amount), 0))\
            .filter(Order.order_date >= day,
                    Order.order_date < day + timedelta(days=1),
                    Order.paid == True).scalar()
        count = Order.query.filter(
            Order.order_date >= day,
            Order.order_date < day + timedelta(days=1)
        ).count()
        chart_days.append({'label': day.strftime('%a'), 'revenue': rev, 'count': count})
    max_rev = max(d['revenue'] for d in chart_days) or 1
    max_cnt = max(d['count'] for d in chart_days) or 1

    avg_ratings = db.session.query(
        MenuItem.name, func.avg(OrderItem.rating).label('avg_r'),
        func.count(OrderItem.rating).label('cnt')
    ).join(OrderItem, OrderItem.menu_item_id == MenuItem.id)\
     .filter(OrderItem.rating.isnot(None))\
     .group_by(MenuItem.id, MenuItem.name)\
     .having(func.count(OrderItem.rating) >= 1)\
     .order_by(func.avg(OrderItem.rating).desc()).limit(5).all()

    return render_template('admin/dashboard.html',
        total_users=total_users, total_items=total_items,
        orders_total=orders_total, orders_today=orders_today,
        pending_orders=pending_orders, pending_invoices=pending_invoices,
        total_revenue=total_revenue, today_revenue=today_revenue,
        week_revenue=week_revenue, month_revenue=month_revenue,
        popular=popular, cat_sales=cat_sales,
        balance_orders=balance_orders, manual_orders=manual_orders,
        status_counts=status_counts, new_users_30d=new_users_30d,
        recent_orders=recent_orders,
        chart_days=chart_days, max_rev=max_rev, max_cnt=max_cnt,
        avg_ratings=avg_ratings)


@admin_bp.route('/menu')
@login_required
@admin_required
def manage_menu():
    page = request.args.get('page', 1, type=int)
    pagination = MenuItem.query.order_by(MenuItem.name)\
                               .paginate(page=page, per_page=PER_PAGE, error_out=False)
    return render_template('admin/menu_manage.html', items=pagination.items,
                           pagination=pagination)


def resolve_category(form):
    if form.new_category.data:
        existing = Category.query.filter_by(name=form.new_category.data).first()
        if existing:
            return existing.id
        cat = Category(name=form.new_category.data)
        db.session.add(cat)
        db.session.flush()
        return cat.id
    return form.category_id.data


@admin_bp.route('/menu/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_menu_item():
    form = MenuItemForm()
    form.category_id.choices = [(c.id, c.name) for c in Category.query.all()] + [(0, '-- select --')]
    if form.validate_on_submit():
        cat_id = resolve_category(form)
        if not cat_id:
            flash('Please select or create a category.', 'error')
            return render_template('admin/menu_form.html', form=form, title='Add Item')

        filename = save_upload(request.files.get('image'))
        if not filename and form.image_url.data:
            filename = form.image_url.data

        item = MenuItem(
            name=form.name.data,
            description=form.description.data,
            price=form.price.data,
            category_id=cat_id,
            image=filename,
            available=form.available.data,
            featured=form.featured.data,
            stock=form.stock.data,
        )
        db.session.add(item)
        db.session.commit()
        flash(f'Menu item "{item.name}" added!', 'success')
        return redirect(url_for('admin.manage_menu'))
    return render_template('admin/menu_form.html', form=form, title='Add Item')


@admin_bp.route('/menu/edit/<int:item_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_menu_item(item_id):
    item = MenuItem.query.get_or_404(item_id)
    form = MenuItemForm(obj=item)
    form.category_id.choices = [(c.id, c.name) for c in Category.query.all()] + [(0, '-- select --')]
    if form.validate_on_submit():
        cat_id = resolve_category(form)
        if not cat_id:
            flash('Please select or create a category.', 'error')
            return render_template('admin/menu_form.html', form=form, title='Edit Item')

        file = request.files.get('image')
        if file and file.filename:
            filename = save_upload(file)
            if filename:
                item.image = filename
        elif form.image_url.data:
            item.image = form.image_url.data
        elif form.image.data is None:
            pass

        item.name = form.name.data
        item.description = form.description.data
        item.price = form.price.data
        item.category_id = cat_id
        item.available = form.available.data
        item.featured = form.featured.data
        item.stock = form.stock.data
        db.session.commit()
        flash(f'"{item.name}" updated!', 'success')
        return redirect(url_for('admin.manage_menu'))
    return render_template('admin/menu_form.html', form=form, title='Edit Item')


@admin_bp.route('/menu/delete/<int:item_id>', methods=['POST'])
@login_required
@admin_required
def delete_menu_item(item_id):
    item = MenuItem.query.get_or_404(item_id)
    if item.order_items.count() > 0:
        flash(f'Cannot delete "{item.name}" — it has been ordered before. '
              'Mark it unavailable instead.', 'error')
        return redirect(url_for('admin.manage_menu'))
    try:
        db.session.delete(item)
        db.session.commit()
        flash(f'"{item.name}" deleted.', 'info')
    except exc.SQLAlchemyError:
        db.session.rollback()
        flash('Error deleting item.', 'error')
    return redirect(url_for('admin.manage_menu'))


@admin_bp.route('/menu/toggle-featured/<int:item_id>', methods=['POST'])
@login_required
@admin_required
def toggle_featured(item_id):
    item = MenuItem.query.get_or_404(item_id)
    item.featured = not item.featured
    db.session.commit()
    flash(f'"{item.name}" {"featured" if item.featured else "unfeatured"}.', 'success')
    return redirect(url_for('admin.manage_menu'))


@admin_bp.route('/categories')
@login_required
@admin_required
def manage_categories():
    categories = Category.query.order_by(Category.name).all()
    return render_template('admin/categories.html', categories=categories)


@admin_bp.route('/categories/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_category():
    form = CategoryForm()
    if form.validate_on_submit():
        cat = Category(name=form.name.data, description=form.description.data)
        db.session.add(cat)
        db.session.commit()
        flash(f'Category "{cat.name}" created!', 'success')
        return redirect(url_for('admin.manage_categories'))
    return render_template('admin/category_form.html', form=form, title='Add Category')


@admin_bp.route('/categories/edit/<int:cat_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    form = CategoryForm(obj=cat)
    if form.validate_on_submit():
        cat.name = form.name.data
        cat.description = form.description.data
        db.session.commit()
        flash(f'Category "{cat.name}" updated!', 'success')
        return redirect(url_for('admin.manage_categories'))
    return render_template('admin/category_form.html', form=form, title='Edit Category')


@admin_bp.route('/categories/delete/<int:cat_id>', methods=['POST'])
@login_required
@admin_required
def delete_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    if cat.items.count() > 0:
        flash(f'Cannot delete "{cat.name}" — it has menu items. Move or delete items first.',
              'error')
        return redirect(url_for('admin.manage_categories'))
    try:
        db.session.delete(cat)
        db.session.commit()
        flash(f'Category "{cat.name}" deleted.', 'info')
    except exc.SQLAlchemyError:
        db.session.rollback()
        flash('Error deleting category.', 'error')
    return redirect(url_for('admin.manage_categories'))


@admin_bp.route('/orders')
@login_required
@admin_required
def manage_orders():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status')
    query = Order.query.order_by(Order.order_date.desc())
    if status_filter:
        query = query.filter_by(status=status_filter)
    pagination = query.paginate(page=page, per_page=PER_PAGE, error_out=False)
    return render_template('admin/orders_manage.html', orders=pagination.items,
                           pagination=pagination, status_filter=status_filter)


@admin_bp.route('/orders/update-status/<int:order_id>', methods=['POST'])
@login_required
@admin_required
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    allowed = ALLOWED_STATUS_TRANSITIONS.get(order.status, [])
    if new_status not in allowed:
        flash(f'Cannot change order #{order.id} from "{order.status}" to "{new_status}".',
              'error')
        return redirect(url_for('admin.manage_orders'))
    order.status = new_status
    db.session.commit()
    flash(f'Order #{order.id} status updated to "{new_status}".', 'success')
    return redirect(url_for('admin.manage_orders'))


@admin_bp.route('/orders/approve-cancel/<int:order_id>', methods=['POST'])
@login_required
@admin_required
def approve_cancel(order_id):
    order = Order.query.get_or_404(order_id)
    if order.status != 'cancel_requested':
        flash(f'Order #{order.id} is not awaiting cancellation.', 'error')
        return redirect(url_for('admin.manage_orders'))
    try:
        order.status = 'cancelled'
        for oi in order.items:
            item = MenuItem.query.get(oi.menu_item_id)
            if item:
                item.stock += oi.quantity
        if order.payment_method == 'balance' and order.paid:
            current_user.balance += order.total_amount
        order.previous_status = None
        db.session.commit()
        flash(f'Order #{order.id} cancelled and refunded.', 'success')
    except exc.SQLAlchemyError:
        db.session.rollback()
        flash('Error approving cancellation.', 'error')
    return redirect(url_for('admin.manage_orders'))


@admin_bp.route('/orders/reject-cancel/<int:order_id>', methods=['POST'])
@login_required
@admin_required
def reject_cancel(order_id):
    order = Order.query.get_or_404(order_id)
    if order.status != 'cancel_requested':
        flash(f'Order #{order.id} is not awaiting cancellation.', 'error')
        return redirect(url_for('admin.manage_orders'))
    if not order.previous_status:
        flash(f'Cannot restore order #{order.id}: previous status unknown.', 'error')
        return redirect(url_for('admin.manage_orders'))
    order.status = order.previous_status
    order.previous_status = None
    db.session.commit()
    flash(f'Cancellation rejected. Order #{order.id} restored to "{order.status}".', 'success')
    return redirect(url_for('admin.manage_orders'))


@admin_bp.route('/invoices')
@login_required
@admin_required
def manage_invoices():
    page = request.args.get('page', 1, type=int)
    paid_filter = request.args.get('paid')
    query = Order.query.order_by(Order.order_date.desc())
    if paid_filter == '0':
        query = query.filter_by(paid=False)
    elif paid_filter == '1':
        query = query.filter_by(paid=True)
    pagination = query.paginate(page=page, per_page=PER_PAGE, error_out=False)
    unpaid_count = Order.query.filter_by(paid=False).count()
    return render_template('admin/invoices.html', orders=pagination.items,
                           pagination=pagination, unpaid_count=unpaid_count,
                           paid_filter=paid_filter)


@admin_bp.route('/invoices/toggle-paid/<int:order_id>', methods=['POST'])
@login_required
@admin_required
def toggle_paid(order_id):
    order = Order.query.get_or_404(order_id)
    order.paid = not order.paid
    if order.paid and order.status == 'pending_payment':
        order.status = 'confirmed'
    flash(f'Invoice {order.invoice_number} marked as {"paid" if order.paid else "unpaid"}.',
          'success')
    db.session.commit()
    return redirect(url_for('admin.manage_invoices'))


@admin_bp.route('/users')
@login_required
@admin_required
def manage_users():
    page = request.args.get('page', 1, type=int)
    pagination = User.query.order_by(User.username)\
                           .paginate(page=page, per_page=PER_PAGE, error_out=False)
    return render_template('admin/users.html', users=pagination.items,
                           pagination=pagination)


@admin_bp.route('/users/topup/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def topup_balance(user_id):
    user = User.query.get_or_404(user_id)
    amount = request.form.get('amount', type=float)
    if amount and 0 < amount <= 10000:
        user.balance += amount
        db.session.commit()
        current_app.logger.info(
            f'Admin {current_user.id} topped up user {user.id} ({user.username}) '
            f'by ${amount:.2f}. New balance: ${user.balance:.2f}'
        )
        flash(f'Added ${amount:.2f} to {user.username}\'s balance.', 'success')
    else:
        flash('Enter an amount between $0.01 and $10,000.', 'error')
    return redirect(url_for('admin.manage_users'))
