from decimal import Decimal
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, session, current_app)
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from models import db, Order, OrderItem, MenuItem, Favorite, ALLOWED_STATUS_TRANSITIONS
from sqlalchemy import exc

orders_bp = Blueprint('orders', __name__, url_prefix='/orders')


@orders_bp.route('/cart')
def view_cart():
    cart = session.get('cart', {})
    cart_items = []
    total = Decimal('0')
    removed = []
    for item_id, qty in cart.items():
        try:
            item = MenuItem.query.get(int(item_id))
        except (ValueError, TypeError):
            removed.append(item_id)
            continue
        if not item:
            removed.append(item_id)
            continue
        subtotal = item.price * qty
        cart_items.append({'item': item, 'quantity': qty, 'subtotal': subtotal})
        total += subtotal
    if removed:
        for r in removed:
            cart.pop(str(r), None)
        session['cart'] = cart
        flash('Some items were removed from your cart because they are no longer available.', 'info')
    return render_template('orders/cart.html', cart_items=cart_items, total=total)


@orders_bp.route('/add-to-cart/<int:item_id>', methods=['POST'])
def add_to_cart(item_id):
    item = MenuItem.query.get_or_404(item_id)
    if not item.available or item.stock <= 0:
        flash('Item is not available.', 'error')
        return redirect(url_for('menu.index'))

    qty = request.form.get('quantity', 1, type=int)
    qty = max(1, min(qty, current_app.config['MAX_CART_QTY'], item.stock))

    cart = session.get('cart', {})
    current_qty = cart.get(str(item_id), 0)
    new_qty = current_qty + qty
    if new_qty > current_app.config['MAX_CART_QTY']:
        max_qty = current_app.config['MAX_CART_QTY']
        flash(f'Maximum {max_qty} per item allowed.', 'error')
        return redirect(url_for('menu.index'))
    if new_qty > item.stock:
        flash(f'Only {item.stock} available.', 'error')
        return redirect(url_for('menu.index'))

    cart[str(item_id)] = new_qty
    session['cart'] = cart
    flash(f'{qty}x {item.name} added to cart!', 'success')
    return redirect(url_for('menu.index'))


@orders_bp.route('/update-cart', methods=['POST'])
def update_cart():
    item_id = request.form.get('item_id')
    quantity = request.form.get('quantity', type=int)
    cart = session.get('cart', {})
    if quantity and quantity > 0:
        quantity = min(quantity, current_app.config['MAX_CART_QTY'])
        cart[str(item_id)] = quantity
    else:
        cart.pop(str(item_id), None)
    session['cart'] = cart
    return redirect(url_for('orders.view_cart'))


@orders_bp.route('/checkout', methods=['POST'])
@login_required
def checkout():
    cart = session.get('cart', {})
    if not cart:
        flash('Your cart is empty.', 'error')
        return redirect(url_for('orders.view_cart'))

    payment_method = request.form.get('payment_method', 'balance')

    total = Decimal('0')
    order_items_data = []

    for item_id, qty in cart.items():
        item = MenuItem.query.get(int(item_id))
        if not item or not item.available:
            flash(f'Item {item.name if item else "unknown"} is unavailable.', 'error')
            return redirect(url_for('orders.view_cart'))
        if item.stock < qty:
            flash(f'Not enough stock for {item.name}. Available: {item.stock}', 'error')
            return redirect(url_for('orders.view_cart'))
        order_items_data.append((item, qty))
        total += item.price * qty

    if payment_method == 'balance':
        if current_user.balance < total:
            flash(f'Insufficient balance. Need ₱{total:.2f}, have ₱{current_user.balance:.2f}.',
                  'error')
            return redirect(url_for('orders.view_cart'))
        paid = True
        status = 'confirmed'
    else:
        paid = False
        status = 'pending_payment'

    try:
        order = Order(
            user_id=current_user.id,
            total_amount=total,
            status=status,
            payment_method=payment_method,
            paid=paid,
        )
        db.session.add(order)
        db.session.flush()

        order.invoice_ref = f'INV-{order.id:04d}'
        db.session.flush()

        for item, qty in order_items_data:
            oi = OrderItem(order_id=order.id, menu_item_id=item.id,
                           quantity=qty, unit_price=item.price)
            item.stock -= qty
            db.session.add(oi)

        if payment_method == 'balance':
            current_user.balance -= total

        db.session.commit()
    except exc.SQLAlchemyError:
        db.session.rollback()
        flash('An error occurred while placing your order. Please try again.', 'error')
        return redirect(url_for('orders.view_cart'))

    session.pop('cart', None)
    flash(f'Invoice {order.invoice_number} created! Total: ₱{total:.2f}', 'success')
    return redirect(url_for('orders.invoice', order_id=order.id))


@orders_bp.route('/invoice/<int:order_id>')
@login_required
def invoice(order_id):
    order = Order.query.options(
        joinedload(Order.user),
        joinedload(Order.items).joinedload(OrderItem.menu_item)
    ).get_or_404(order_id)
    if order.user_id != current_user.id and not current_user.is_admin():
        flash('You can only view your own invoices.', 'error')
        return redirect(url_for('orders.history'))
    return render_template('orders/invoice.html', order=order)


@orders_bp.route('/cancel/<int:order_id>', methods=['POST'])
@login_required
def cancel_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        flash('You can only cancel your own orders.', 'error')
        return redirect(url_for('orders.history'))

    allowed = ALLOWED_STATUS_TRANSITIONS.get(order.status, [])
    if 'cancel_requested' not in allowed:
        flash(f'Order #{order.id} cannot be cancelled (status: {order.status}).', 'error')
        return redirect(url_for('orders.history'))

    try:
        order.previous_status = order.status
        order.status = 'cancel_requested'
        db.session.commit()
        flash(f'Cancellation requested for Order #{order.id}. Awaiting admin approval.', 'success')
    except exc.SQLAlchemyError:
        db.session.rollback()
        flash('An error occurred while requesting cancellation.', 'error')

    return redirect(url_for('orders.history'))


@orders_bp.route('/rate', methods=['POST'])
@login_required
def rate_item():
    oi_id = request.form.get('order_item_id', type=int)
    rating = request.form.get('rating', type=int)
    review = request.form.get('review', '').strip()

    oi = OrderItem.query.get_or_404(oi_id)
    order = oi.order
    if order.user_id != current_user.id:
        flash('You can only rate your own orders.', 'error')
        return redirect(url_for('orders.history'))
    if order.status != 'completed':
        flash('You can only rate completed orders.', 'error')
        return redirect(url_for('orders.history'))
    if rating and 1 <= rating <= 5:
        oi.rating = rating
        oi.review = review or None
        db.session.commit()
        flash('Rating submitted!', 'success')
    else:
        flash('Please select a rating between 1 and 5.', 'error')

    return redirect(url_for('orders.history'))


@orders_bp.route('/favorite/<int:item_id>', methods=['POST'])
@login_required
def toggle_favorite(item_id):
    item = MenuItem.query.get_or_404(item_id)
    fav = Favorite.query.filter_by(user_id=current_user.id,
                                   menu_item_id=item_id).first()
    if fav:
        db.session.delete(fav)
        db.session.commit()
        flash(f'{item.name} removed from favorites.', 'info')
    else:
        fav = Favorite(user_id=current_user.id, menu_item_id=item_id)
        db.session.add(fav)
        db.session.commit()
        flash(f'{item.name} added to favorites!', 'success')
    return redirect(request.referrer or url_for('menu.index'))


@orders_bp.route('/history')
@login_required
def history():
    page = request.args.get('page', 1, type=int)
    pagination = Order.query.options(
        joinedload(Order.items).joinedload(OrderItem.menu_item)
    ).filter_by(user_id=current_user.id)\
     .order_by(Order.order_date.desc())\
     .paginate(page=page, per_page=20, error_out=False)
    return render_template('orders/history.html', orders=pagination.items,
                           pagination=pagination)
