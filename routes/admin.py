from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from models import User, MenuItem, Order, Table, Feedback, db, OrderItem
from datetime import datetime, timedelta
import json
from sqlalchemy import func

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin/dashboard')
@login_required
def dashboard():
    # Get today's date range
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    
    # Get statistics
    today_sales = db.session.query(func.sum(Order.total_amount)).filter(
        Order.user_id == current_user.id,
        Order.status == 'completed',
        Order.created_at.between(today_start, today_end)
    ).scalar() or 0.0
    
    pending_orders = Order.query.filter(
        Order.user_id == current_user.id,
        Order.status.in_(['pending', 'preparing'])
    ).count()
    
    completed_orders = Order.query.filter(
        Order.user_id == current_user.id,
        Order.status == 'completed',
        Order.created_at.between(today_start, today_end)
    ).count()
    
    # Get popular items
    popular_items = db.session.query(
        MenuItem.name,
        func.sum(OrderItem.quantity).label('total_quantity')
    ).join(OrderItem).filter(
        MenuItem.user_id == current_user.id
    ).group_by(MenuItem.id).order_by(
        func.sum(OrderItem.quantity).desc()
    ).limit(5).all()
    
    # Get recent feedback
    recent_feedback = Feedback.query.join(Order).filter(
        Order.user_id == current_user.id
    ).order_by(Feedback.created_at.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html',
                         today_sales=today_sales,
                         pending_orders=pending_orders,
                         completed_orders=completed_orders,
                         popular_items=popular_items,
                         recent_feedback=recent_feedback)

@admin_bp.route('/admin/tables', methods=['GET', 'POST'])
@login_required
def manage_tables():
    if request.method == 'POST':
        try:
            data = request.json
            table = Table(
                number=data['number'],
                capacity=data.get('capacity'),
                user_id=current_user.id
            )
            db.session.add(table)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Table added successfully'})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 400
    
    tables = Table.query.filter_by(user_id=current_user.id).all()
    return render_template('admin/tables.html', tables=tables)

@admin_bp.route('/admin/analytics')
@login_required
def analytics():
    # Get date range (default: last 7 days)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=7)
    
    # Daily sales
    daily_sales = db.session.query(
        func.date(Order.created_at).label('date'),
        func.sum(Order.total_amount).label('total')
    ).filter(
        Order.user_id == current_user.id,
        Order.status == 'completed',
        Order.created_at.between(start_date, end_date)
    ).group_by(func.date(Order.created_at)).all()
    
    # Popular categories
    popular_categories = db.session.query(
        MenuItem.category,
        func.count(OrderItem.id).label('total_orders')
    ).join(OrderItem).filter(
        MenuItem.user_id == current_user.id
    ).group_by(MenuItem.category).order_by(
        func.count(OrderItem.id).desc()
    ).all()
    
    # Average preparation time
    avg_prep_time = db.session.query(
        func.avg(MenuItem.preparation_time).label('avg_time')
    ).filter(MenuItem.user_id == current_user.id).scalar() or 0
    
    # Customer satisfaction
    satisfaction = db.session.query(
        func.avg(Feedback.rating).label('avg_rating')
    ).join(Order).filter(
        Order.user_id == current_user.id
    ).scalar() or 0
    
    return render_template('admin/analytics.html',
                         daily_sales=daily_sales,
                         popular_categories=popular_categories,
                         avg_prep_time=avg_prep_time,
                         satisfaction=satisfaction)

@admin_bp.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        try:
            data = request.form
            current_user.name = data.get('name', current_user.name)
            current_user.email = data.get('email', current_user.email)
            current_user.phone = data.get('phone', current_user.phone)
            current_user.address = data.get('address', current_user.address)
            
            if data.get('new_password'):
                current_user.set_password(data['new_password'])
            
            db.session.commit()
            return jsonify({'success': True, 'message': 'Settings updated successfully'})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 400
    
    return render_template('admin/settings.html')

def get_popular_items():
    # Get orders from the last 30 days
    start_date = datetime.utcnow() - timedelta(days=30)
    
    popular_items = db.session.query(
        MenuItem.name,
        db.func.sum(OrderItem.quantity).label('total_quantity')
    ).join(OrderItem).filter(
        Order.created_at >= start_date
    ).group_by(MenuItem.id).order_by(
        db.desc('total_quantity')
    ).limit(5).all()
    
    return popular_items

def get_sales_analytics(start_date, end_date):
    sales_data = db.session.query(
        db.func.date(Order.created_at).label('date'),
        db.func.sum(Order.total_amount).label('total_sales'),
        db.func.count(Order.id).label('order_count')
    ).filter(
        Order.created_at.between(start_date, end_date),
        Order.payment_status == 'paid'
    ).group_by(
        db.func.date(Order.created_at)
    ).all()
    
    return [{
        'date': data.date.strftime('%Y-%m-%d'),
        'total_sales': float(data.total_sales),
        'order_count': data.order_count
    } for data in sales_data]

def analyze_feedback():
    feedback_data = db.session.query(
        db.func.avg(CustomerFeedback.rating).label('avg_rating'),
        db.func.count(CustomerFeedback.id).label('total_feedback')
    ).first()
    
    return {
        'average_rating': round(float(feedback_data.avg_rating), 1) if feedback_data.avg_rating else 0,
        'total_feedback': feedback_data.total_feedback
    }

def analyze_peak_hours():
    # Analyze orders from the last 30 days
    start_date = datetime.utcnow() - timedelta(days=30)
    
    peak_hours = db.session.query(
        db.func.extract('hour', Order.created_at).label('hour'),
        db.func.count(Order.id).label('order_count')
    ).filter(
        Order.created_at >= start_date
    ).group_by(
        db.func.extract('hour', Order.created_at)
    ).order_by(
        db.desc('order_count')
    ).all()
    
    return [{
        'hour': int(data.hour),
        'order_count': data.order_count
    } for data in peak_hours] 