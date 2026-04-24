import datetime
import smtplib
import os
import razorpay
from email.message import EmailMessage
from flask import Flask, render_template, request, session, url_for
from flask_mysqldb import MySQL
from werkzeug.security import  check_password_hash,generate_password_hash
from datetime import datetime, timedelta
from MySQLdb.cursors import DictCursor
from collections import defaultdict
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime, timedelta
import random
import string
from flask import Response
from PIL import Image
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY") or "fallback_secret_123"

#Razorpay API Keys
import razorpay

RAZORPAY_KEY_ID = "rzp_test_SN0hso3lWNXjPI"
RAZORPAY_KEY_SECRET = "A91j95r6yDJBbWr1w81kmMCU"

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# ------------------ Mail Config ------------------
app.config['MAIL_SERVER'] = os.getenv("MAIL_SERVER")
app.config['MAIL_PORT'] = int(os.getenv("MAIL_PORT"))
app.config['MAIL_USE_TLS'] = os.getenv("MAIL_USE_TLS") == "true"
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = os.getenv("MAIL_DEFAULT_SENDER")

mail = Mail(app)


#database configuration
app.config['MYSQL_HOST'] = os.getenv("MYSQLHOST")
app.config['MYSQL_USER'] = os.getenv("MYSQLUSER")
app.config['MYSQL_PASSWORD'] = os.getenv("MYSQLPASSWORD")
app.config['MYSQL_DB'] = os.getenv("MYSQLDATABASE")
app.config['MYSQL_PORT'] = int(os.getenv("MYSQLPORT"))

mysql=MySQL(app)


#-------------FIle Managements --------------------------------
UPLOAD_FOLDER = 'static/images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
#UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

#-----------------------review config
# Configuration for review image uploads
'''
app.config['REVIEW_UPLOADS'] = 'static/review_images/'
if not os.path.exists(app.config['REVIEW_UPLOADS']):
    os.makedirs(app.config['REVIEW_UPLOADS'])
'''



def send_otp_email(to_email: str, otp: str):
    try:
        smtp_host = os.getenv('SMTP_HOST')
        smtp_port = int(os.getenv('SMTP_PORT', 587))
        smtp_user = os.getenv('SMTP_USERNAME')
        smtp_pass = os.getenv('SMTP_PASSWORD')

        subject = "OTP Reset"
        body = f"Your OTP is {otp}. Valid for 5 minutes."

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = smtp_user
        msg["To"] = to_email
        msg.set_content(body)

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        return True

    except Exception:
        return False

def resolve_user_email(cur, user_ref) -> str | None:
    ref = (user_ref or '').strip()
    if not ref:
        return None
    if '@' in ref and '.' in ref:
        return ref
    try:
        # Try by id (numeric) and email (string) both
        ref_id = None
        try:
            ref_id = int(ref)
        except Exception:
            ref_id = None
        if ref_id is not None:
            cur.execute(
                "SELECT email FROM glamfluer_registration WHERE id=%s LIMIT 1",
                (ref_id,),
            )
            u = cur.fetchone() or {}
            if u.get('email'):
                return u.get('email')
        cur.execute(
            "SELECT email FROM glamfluer_registration WHERE TRIM(LOWER(email))=TRIM(LOWER(%s)) LIMIT 1",
            (ref,),
        )
        u2 = cur.fetchone() or {}
        return u2.get('email')
    except Exception:
        return None


#----------------------------------------------------------------------------
#            Cart Recovery/status mail
#----------------------------------------------------------------------------

def send_status_email(to_email, order_number, new_status):
    """Sends real-time email when admin updates order status."""
    try:
        msg = EmailMessage()
        msg["Subject"] = f"Order #{order_number} Update - {new_status}"
        msg["From"] = os.getenv('SMTP_FROM')
        msg["To"] = to_email

        content = f"""
        Hello,

        Good news! The status of your order #{order_number} has been updated to: {new_status}.

        You can track your beauty box live here: http://127.0.0.1:5000/track_order

        Stay Glamorous,
        Team GlamFleur
        """
        msg.set_content(content)

        with smtplib.SMTP(os.getenv('SMTP_HOST'), int(os.getenv('SMTP_PORT'))) as server:
            server.starttls()
            server.login(os.getenv('SMTP_USERNAME'), os.getenv('SMTP_PASSWORD'))
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Mail Error: {e}")
        return False


def send_abandoned_cart_email(to_email, product_name):
    """Sends a reminder for items left in cart."""
    try:
        msg = EmailMessage()
        msg["Subject"] = "You left something beautiful behind! ✨"
        msg["From"] = os.getenv('SMTP_FROM')
        msg["To"] = to_email

        content = f"""
        Hi there!

        We noticed you left '{product_name}' in your GlamFleur cart. 
        It's waiting for you! 

        Use code: GLAM10 for 10% OFF if you complete your order in the next 24 hours.

        Complete Purchase: http://127.0.0.1:5000/cart

        Love,
        GlamFleur
        """
        msg.set_content(content)

        with smtplib.SMTP(os.getenv('SMTP_HOST'), int(os.getenv('SMTP_PORT'))) as server:
            server.starttls()
            server.login(os.getenv('SMTP_USERNAME'), os.getenv('SMTP_PASSWORD'))
            server.send_message(msg)
        return True
    except Exception:
        return False


def send_marketing_email(to_email, subject, message):
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = os.getenv('SMTP_FROM')
        msg["To"] = to_email

        # Professional HTML Content like the images you shared
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; border: 1px solid #eee;">
            <div style="background: #fc2779; padding: 20px; text-align: center; color: white;">
                <h1>GlamFleur</h1>
            </div>
            <div style="padding: 40px; text-align: center; line-height: 1.6;">
                <h2 style="color: #1a1c23;">{subject}</h2>
                <p>{message}</p>
                <a href="http://127.0.0.1:5000/shop" style="background: #fc2779; color: white; padding: 15px 25px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block; margin-top: 20px;">SHOP NOW</a>
            </div>
            <div style="background: #f8f8f8; padding: 20px; text-align: center; font-size: 12px; color: #888;">
                You are receiving this because you are a valued GlamFleur customer.<br>
                © 2026 GlamFleur Beauty.
            </div>
        </div>
        """
        msg.set_content(message)
        msg.add_alternative(html_content, subtype='html')

        with smtplib.SMTP(os.getenv('SMTP_HOST'), int(os.getenv('SMTP_PORT'))) as server:
            server.starttls()
            server.login(os.getenv('SMTP_USERNAME'), os.getenv('SMTP_PASSWORD'))
            server.send_message(msg)
        return True
    except Exception:
        return False



@app.route('/')
def index():

    cur = mysql.connection.cursor(DictCursor)
    is_logged_in = 'user_id' in session
    # Show only 8 products on homepage (2 rows)
    cur.execute("""
        SELECT p.id, p.product_name, p.price, p.file, p.description,
               c.category_name
        FROM glamfluer_products p
        JOIN glamfluer_categories c ON p.category_id = c.id
        WHERE p.status='Active'
        ORDER BY p.id DESC
        LIMIT 8
    """)
    homepage_products = cur.fetchall()

    # Fetch ALL products for View All modal
    cur.execute("""
        SELECT p.id, p.product_name, p.price, p.file, p.description,
               c.category_name
        FROM glamfluer_products p
        JOIN glamfluer_categories c ON p.category_id = c.id
        WHERE p.status='Active'
        ORDER BY p.id DESC
    """)
    all_products = cur.fetchall()

    # Fetch categories
    cur.execute("SELECT category_name FROM glamfluer_categories")
    categories = [row['category_name'] for row in cur.fetchall()]

    # Fetch sale products (only active)
    cur.execute("""
        SELECT id, sale_name, product_name, original_price,
               offer_percentage, sale_price, image_url
        FROM sale_products
        WHERE status='Active'
        ORDER BY id DESC
    """)
    sale_products = cur.fetchall()

    cur.execute("SELECT * FROM glamfluer_reviews WHERE status='Approved' ORDER BY created_at DESC LIMIT 6")
    live_reviews = cur.fetchall()

    cur.close()

    return render_template(
        "index.html",
        homepage_products=homepage_products,
        all_products=all_products,
        categories=categories,
        sale_products=sale_products,
        user_logged_in=is_logged_in,
        live_reviews=live_reviews
    )


@app.route('/admin_login',methods=['GET','POST'])
def admin_login():
    return render_template('admin_login.html')


@app.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():

    if request.method == "POST":
        u = request.form['txtAdminName']
        p = request.form['txtPassword']

        if (u == "admin" and p == "super"):
            session['name'] = "Tom"
            session['login'] = u
        else:
            msg = "Invalid username or password"
            return render_template("admin_login.html", message=msg)

    else:
        # If someone tries to open dashboard directly
        if 'login' not in session:
            return render_template("admin_login.html")

    # ================= DASHBOARD DATA =================
    cur = mysql.connection.cursor()

    cur.execute("SELECT SUM(amount) FROM glamfluer_orders")
    revenue = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM glamfluer_orders")
    orders = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM glamfluer_products")
    products = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM glamfluer_customers")
    customers = cur.fetchone()[0]

    cur.execute("SELECT order_number, customer_name, product_name, amount, status FROM glamfluer_orders ORDER BY id DESC LIMIT 5")
    recent_orders = cur.fetchall()

    cur.execute("""
        SELECT c.category_name, COUNT(o.id) 
        FROM glamfluer_categories c
        LEFT JOIN glamfluer_products p ON c.id = p.category_id
        LEFT JOIN glamfluer_orders o ON p.product_name = o.product_name
        GROUP BY c.category_name
        HAVING COUNT(o.id) > 0
    """)
    cat_data = cur.fetchall()

    cat_labels = [row[0] for row in cat_data]
    cat_values = [row[1] for row in cat_data]

    cur.close()

    return render_template("admin/admin_dashboard.html",
                           revenue=revenue,
                           orders=orders,
                           products=products,
                           customers=customers,
                           recent_orders=recent_orders,
                           cat_labels=cat_labels,
                           cat_values=cat_values)


@app.route('/admin_categories')
def admin_categories():
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, category_name, file, description FROM glamfluer_categories")
    categories = cur.fetchall()
    return render_template('admin/admin_categories.html', categories=categories)


from werkzeug.utils import secure_filename, redirect
import os

@app.route('/add_category', methods=['POST'])
def add_category():
    name = request.form['category_name']
    desc = request.form['description']
    file = request.files.get('fuPhoto')

    filename = None
    if file and file.filename != "":
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    cur = mysql.connection.cursor()
    cur.execute(
        "INSERT INTO glamfluer_categories (category_name,file,description) VALUES (%s,%s,%s)",
        (name, filename, desc)
    )
    mysql.connection.commit()

    categories = get_category_data()
    return render_template('admin/admin_categories.html', categories=categories)


def get_category_data():
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, category_name, file, description FROM glamfluer_categories")
    categories = cur.fetchall()
    cur.close()
    return categories



@app.route('/update_category', methods=['POST'])
def update_category():
    cid = request.form['cid']
    name = request.form['category_name']
    desc = request.form['description']
    file = request.files.get('fuPhoto')

    cur = mysql.connection.cursor()

    if file and file.filename != "":
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        cur.execute(
            "UPDATE glamfluer_categories SET category_name=%s, file=%s, description=%s WHERE id=%s",
            (name, filename, desc, cid)
        )
    else:
        cur.execute(
            "UPDATE glamfluer_categories SET category_name=%s, description=%s WHERE id=%s",
            (name, desc, cid)
        )

    mysql.connection.commit()
    categories = get_category_data()
    return render_template('admin/admin_categories.html', categories=categories)


@app.route('/delete_category/<int:id>')
def delete_category(id):
    cur = mysql.connection.cursor()

    # Delete products first
    cur.execute("DELETE FROM glamfluer_products WHERE category_id=%s", (id,))

    # Then delete category
    cur.execute("DELETE FROM glamfluer_categories WHERE id=%s", (id,))
    mysql.connection.commit()

    categories = get_category_data()
    return render_template('admin/admin_categories.html', categories=categories)


@app.route('/get_category_products')
def get_category_products():
    category_name = request.args.get('category')

    cur = mysql.connection.cursor()

    # First get category id safely
    cur.execute("""
        SELECT id FROM glamfluer_categories
        WHERE TRIM(category_name) = TRIM(%s)
    """, (category_name,))

    category = cur.fetchone()

    if not category:
        cur.close()
        return jsonify([])

    category_id = category['id']

    # Now fetch products using category_id
    cur.execute("""
        SELECT product_name, price, file
        FROM glamfluer_products
        WHERE category_id = %s
    """, (category_id,))

    products = cur.fetchall()
    cur.close()

    return jsonify(products)


from flask import jsonify


@app.route('/get_products_by_category/<category_name>')
def get_products_by_category(category_name):
    # Use DictCursor so we get {'id': 1, 'product_name': '...'} instead of (1, '...')
    cur = mysql.connection.cursor(DictCursor)

    query = """
        SELECT p.id, p.product_name, p.price, p.file, c.category_name
        FROM glamfluer_products p
        JOIN glamfluer_categories c ON p.category_id = c.id
        WHERE c.category_name = %s AND p.status = 'Active'
    """
    cur.execute(query, (category_name,))
    products = cur.fetchall()
    cur.close()

    # This sends the data in a format the 'fetch' function understands
    return jsonify(products)

from MySQLdb.cursors import DictCursor

from MySQLdb.cursors import DictCursor

@app.route("/admin_customers")
def admin_customers():
    cur = mysql.connection.cursor(DictCursor)

    cur.execute("SELECT * FROM glamfluer_customers ORDER BY created_at DESC")
    customers = cur.fetchall()

    cur.execute("SELECT COUNT(*) AS c FROM glamfluer_customers")
    total_customers = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) AS c FROM glamfluer_customers WHERE status='active'")
    active_count = cur.fetchone()["c"]
    active_pct = round((active_count / total_customers * 100), 1) if total_customers else 0

    cur.execute("SELECT SUM(total_spent) AS revenue FROM glamfluer_customers")
    raw_rev = cur.fetchone()["revenue"] or 0
    total_revenue = f"{int(raw_rev/1000)}K" if raw_rev >= 1000 else raw_rev

    avg_ltv = int(raw_rev / total_customers) if total_customers else 0

    cur.execute("SELECT COUNT(*) AS c FROM glamfluer_customers WHERE segment='VIP'")
    vip = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) AS c FROM glamfluer_customers WHERE segment='Regular'")
    regular = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) AS c FROM glamfluer_customers WHERE segment='New'")
    new = cur.fetchone()["c"]

    cur.close()

    growth_data = [120,150,180,220,260,300,340,400]

    return render_template(
        "admin/admin_customers.html",
        customers=customers,
        total_customers=total_customers,
        active_customers=active_count,
        active_pct=active_pct,
        total_revenue=total_revenue,
        avg_ltv=avg_ltv,
        vip=vip,
        regular=regular,
        new=new,
        growth=growth_data
    )

# ================= PRODUCTS DASHBOARD =================
@app.route('/admin_products')
def admin_products():
    cur = mysql.connection.cursor()

    # Get Categories
    cur.execute("SELECT id, category_name FROM glamfluer_categories")
    categories = cur.fetchall()

    # Get All Products
    cur.execute("""
        SELECT p.id, p.product_name, p.brand, p.category_id, c.category_name, 
               p.price, p.stock, p.description, 
               CASE WHEN p.stock = 0 THEN 'Out of Stock' ELSE 'In Stock' END, p.file, p.status 
        FROM glamfluer_products p 
        JOIN glamfluer_categories c ON p.category_id = c.id
        ORDER BY p.id DESC
    """)
    products = cur.fetchall()

    # DASHBOARD CALCULATIONS (The Wildcard Stats)
    cur.execute("SELECT COUNT(*) FROM glamfluer_products WHERE stock = 0")
    out_of_stock = cur.fetchone()[0]

    cur.execute("SELECT AVG(price) FROM glamfluer_products")
    avg_price_raw = cur.fetchone()[0]
    avg_price = round(avg_price_raw, 2) if avg_price_raw else 0

    cur.close()

    return render_template(
        'admin/admin_products.html',
        products=products,
        categories=categories,
        out_of_stock_count=out_of_stock,
        avg_price=avg_price
    )


# ================= ADD PRODUCT =================
@app.route('/add_product', methods=['POST'])
def add_product():
    name = request.form['product_name']
    brand = request.form['brand']
    category_id = request.form['category']
    price = request.form['price']
    stock = request.form['stock']
    description = request.form['description']
    file = request.files.get('fuPhoto')

    filename = ""
    if file and file.filename != "":
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    cur = mysql.connection.cursor()

    status = request.form.get("status", "Active")

    cur.execute("""
        INSERT INTO glamfluer_products
        (product_name, brand, category_id, price, stock, file, description, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (name, brand, category_id, price, stock, filename, description, status))

    mysql.connection.commit()
    cur.close()

    flash("New product added successfully!")
    products, categories, out_of_stock_count, avg_price = get_product_data()

    return render_template(
        'admin/admin_products.html',
        products=products,
        categories=categories,
        out_of_stock_count=out_of_stock_count,
        avg_price=avg_price
    )




def get_product_data():
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT p.id, p.product_name, p.brand, p.category_id,
               c.category_name, p.price, p.stock, p.description,
               CASE WHEN p.stock = 0 THEN 'Out of Stock' ELSE 'In Stock' END,
               p.file, p.status
        FROM glamfluer_products p
        JOIN glamfluer_categories c ON p.category_id = c.id
        ORDER BY p.id DESC
    """)
    products = cur.fetchall()

    cur.execute("SELECT * FROM glamfluer_categories")
    categories = cur.fetchall()

    out_of_stock_count = sum(1 for p in products if p[6] == 0)

    avg_price = 0
    if products:
        avg_price = sum(float(p[5]) for p in products) / len(products)

    cur.close()

    return products, categories, out_of_stock_count, round(avg_price, 2)




# ================= UPDATE PRODUCT =================
@app.route('/update_product', methods=['POST'])
def update_product():
    pid = request.form['pid']
    name = request.form['product_name']
    brand = request.form['brand']
    category_id = request.form['category']
    price = request.form['price']
    stock = request.form['stock']
    description = request.form['description']
    file = request.files.get('fuPhoto')

    cur = mysql.connection.cursor()

    status = request.form.get("status")

    if file and file.filename != "":
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        cur.execute("""
                    UPDATE glamfluer_products
                    SET product_name=%s,
                        brand=%s,
                        category_id=%s,
                        price=%s,
                        stock=%s,
                        file=%s,
                        description=%s,
                        status=%s
                    WHERE id = %s
                    """, (name, brand, category_id, price, stock, filename, description,status, pid))
    else:
        cur.execute("""
                    UPDATE glamfluer_products
                    SET product_name=%s,
                        brand=%s,
                        category_id=%s,
                        price=%s,
                        stock=%s,
                        description=%s,
                        status=%s
                    WHERE id = %s
                    """, (name, brand, category_id, price, stock, description,status, pid))

    mysql.connection.commit()
    cur.close()

    flash("Product details updated!")
    products, categories, out_of_stock_count, avg_price = get_product_data()

    return render_template(
        'admin/admin_products.html',
        products=products,
        categories=categories,
        out_of_stock_count=out_of_stock_count,
        avg_price=avg_price
    )


# ================= DELETE PRODUCT =================
@app.route('/delete_product/<int:pid>')
def delete_product(pid):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM glamfluer_products WHERE id=%s", (pid,))
    mysql.connection.commit()
    cur.close()

    flash("Product deleted from inventory.")
    products, categories, out_of_stock_count, avg_price = get_product_data()

    return render_template(
        'admin/admin_products.html',
        products=products,
        categories=categories,
        out_of_stock_count=out_of_stock_count,
        avg_price=avg_price
    )



@app.route('/admin_Revenue')
def admin_Revenue():
    from datetime import datetime, timedelta

    period = request.args.get("period", "30")
    days_map = {"7": 7, "15": 15, "30": 30, "365": 365}
    days = days_map.get(period, 30)
    start_date = datetime.now() - timedelta(days=days)

    cur = mysql.connection.cursor(DictCursor)

    # -------- TOTAL REVENUE --------
    cur.execute("""
        SELECT IFNULL(SUM(amount), 0) AS revenue
        FROM glamfluer_orders
        WHERE order_date >= %s
    """, (start_date,))
    revenue = cur.fetchone()["revenue"]

    # -------- TOTAL ORDERS --------
    cur.execute("""
        SELECT COUNT(*) AS total_orders
        FROM glamfluer_orders
        WHERE order_date >= %s
    """, (start_date,))
    total_orders = cur.fetchone()["total_orders"]

    # -------- TOTAL CUSTOMERS --------
    cur.execute("SELECT COUNT(*) AS customers FROM glamfluer_customers")
    total_customers = cur.fetchone()["customers"]

    avg_order = revenue / total_orders if total_orders > 0 else 0

    # -------- CHART DATA (DAILY REVENUE) --------
    cur.execute("""
        SELECT DATE(order_date) AS day, SUM(amount) AS daily_revenue
        FROM glamfluer_orders
        WHERE order_date >= %s
        GROUP BY DATE(order_date)
        ORDER BY day ASC
    """, (start_date,))
    chart_results = cur.fetchall()

    chart_labels = [row["day"].strftime("%d %b") for row in chart_results]
    chart_values = [float(row["daily_revenue"]) for row in chart_results]

    # -------- TOP PRODUCTS --------
    cur.execute("""
        SELECT product_name,
               COUNT(*) AS units_sold,
               SUM(amount) AS revenue
        FROM glamfluer_orders
        WHERE order_date >= %s
        GROUP BY product_name
        ORDER BY units_sold DESC
        LIMIT 5
    """, (start_date,))
    top_products = cur.fetchall()

    # -------- RECENT ORDERS --------
    cur.execute("""
        SELECT 
            order_number,
            customer_name,
            customer_email,
            amount,
            status,
            order_date
        FROM glamfluer_orders
        ORDER BY order_date DESC
        LIMIT 10
    """)

    recent_orders = cur.fetchall()

    cur.close()

    return render_template(
        "admin/admin_revenue.html",
        revenue=revenue,
        total_orders=total_orders,
        total_customers=total_customers,
        avg_order=avg_order,
        recent_orders=recent_orders,
        top_products=top_products,
        period=period,
        chart_labels=chart_labels,
        chart_values=chart_values
    )


#-------------------------------Sale------------------------------------------

@app.route('/admin_sales')
def admin_sales():
    cur = mysql.connection.cursor()
    cur.execute(
        "SELECT id, sale_name, product_name, category, original_price, offer_percentage, sale_price, start_time, end_time, image_url, status FROM sale_products ORDER BY created_at DESC")
    sales_data = cur.fetchall()
    cur.close()

    # Safe calculations
    total_sales = len(sales_data) if sales_data else 0
    total_value = sum([float(row[6]) for row in sales_data]) * 1000 if sales_data else 0
    avg_discount = sum([float(row[5]) for row in sales_data]) / total_sales if sales_data and total_sales > 0 else 0

    return render_template('admin/admin_sale.html',
                           sales=sales_data,
                           total_sales=total_sales,
                           total_value=total_value,
                           avg_discount=avg_discount)


@app.route('/add_sale', methods=['POST'])
def add_sale():
    if request.method == 'POST':
        # Get data from form
        sid = request.form.get('sid')  # For editing
        sale_name = request.form['sale_name']
        prod_name = request.form['product_name']
        category = request.form['category']
        offer = request.form['offer_percentage']
        orig_price = request.form['original_price']
        sale_price = request.form['sale_price']
        start = request.form['start_time']
        end = request.form['end_time']
        status = request.form['status']

        # Image Handling
        file = request.files.get('sale_image')
        filename = ""
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        else:
            filename = request.form.get('old_image')  # Keep old image if editing

        cur = mysql.connection.cursor()

        if sid:  # UPDATE EXISTING
            query = """UPDATE sale_products SET 
                       sale_name=%s, product_name=%s, category=%s, original_price=%s, 
                       offer_percentage=%s, sale_price=%s, start_time=%s, end_time=%s, 
                       image_url=%s, status=%s WHERE id=%s"""
            cur.execute(query,
                        (sale_name, prod_name, category, orig_price, offer, sale_price, start, end, filename, status,
                         sid))
        else:  # INSERT NEW
            query = """INSERT INTO sale_products 
                       (sale_name, product_name, category, original_price, offer_percentage, sale_price, start_time, end_time, image_url, status) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            cur.execute(query,
                        (sale_name, prod_name, category, orig_price, offer, sale_price, start, end, filename, status))

        mysql.connection.commit()
        cur.close()
        return redirect(url_for('admin_sales'))

@app.route('/delete_sale/<int:id>')
def delete_sale(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM sale_products WHERE id = %s", (id,))
    mysql.connection.commit()
    cur.close()
    return redirect(url_for('admin_sales'))


#------------------------------------Offers Page _____________________________

@app.route('/admin_offers')
def admin_offers():
    cur = mysql.connection.cursor()

    # Auto update offer status
    cur.execute(" UPDATE glamfluer_offers  SET status =      CASE     WHEN end_date < CURDATE() THEN 'expired'WHEN start_date > CURDATE() THEN 'scheduled' ELSE status       END")
    mysql.connection.commit()

    cur.execute("SELECT * FROM glamfluer_offers ORDER BY created_at DESC")
    offers = cur.fetchall()
    cur.close()

    return render_template('admin/admin_offers.html', offers=offers)

from flask import flash,request

@app.route('/admin_offers/create', methods=['POST'])
def create_offer():
    # Capture discount_value from the new form
    data = (
        request.form['title'],
        request.form['description'],
        request.form['offer_code'],
        request.form['discount_type'],
        request.form['discount_value'], # Added this
        request.form['min_purchase'],
        request.form['max_discount'],
        request.form['usage_limit'],
        request.form['start_date'],
        request.form['end_date']
    )

    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO glamfluer_offers 
        (title, description, offer_code, discount_type, discount_value, min_purchase, max_discount, usage_limit, start_date, end_date) 
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, data)
    mysql.connection.commit()
    cur.close()
    flash('Offer created successfully!')

    offers = get_offer_data()
    return render_template('admin/admin_offers.html', offers=offers)


def get_offer_data():
    cur = mysql.connection.cursor()

    cur.execute("""
        UPDATE glamfluer_offers
        SET status =
            CASE
                WHEN end_date < CURDATE() THEN 'expired'
                WHEN start_date > CURDATE() THEN 'scheduled'
                ELSE status
            END
    """)
    mysql.connection.commit()

    cur.execute("SELECT * FROM glamfluer_offers ORDER BY created_at DESC")
    offers = cur.fetchall()
    cur.close()

    return offers



@app.route('/admin_offers/update', methods=['POST'])
def update_offer():
    # Capture all fields including the hidden ID
    offer_id = request.form['offer_id']
    data = (
        request.form['title'],
        request.form['description'],
        request.form['offer_code'],
        request.form['discount_type'],
        request.form['discount_value'],
        request.form['min_purchase'],
        request.form['max_discount'],
        request.form['usage_limit'],
        request.form['start_date'],
        request.form['end_date'],
        offer_id
    )

    cur = mysql.connection.cursor()
    cur.execute("""
                UPDATE glamfluer_offers
                SET title=%s,
                    description=%s,
                    offer_code=%s,
                    discount_type=%s,
                    discount_value=%s,
                    min_purchase=%s,
                    max_discount=%s,
                    usage_limit=%s,
                    start_date=%s,
                    end_date=%s
                WHERE id = %s
                """, data)
    mysql.connection.commit()
    cur.close()

    flash('Offer updated successfully!')
    offers = get_offer_data()
    return render_template('admin/admin_offers.html', offers=offers)


@app.route('/admin_offers/toggle/<int:id>', methods=['POST'])
def toggle_offer(id):
    cur = mysql.connection.cursor()
    cur.execute("UPDATE glamfluer_offers SET status = IF(status='active','disabled','active') WHERE id=%s", (id,))
    mysql.connection.commit()
    cur.close()
    flash('Status changed!')
    offers = get_offer_data()
    return render_template('admin/admin_offers.html', offers=offers)


@app.route('/admin_offers/delete/<int:id>')
def delete_offer(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM glamfluer_offers WHERE id=%s", (id,))
    mysql.connection.commit()
    cur.close()
    flash('Offer deleted permanently!')
    offers = get_offer_data()
    return render_template('admin/admin_offers.html', offers=offers)


#-----------------ADMIN Orders



@app.route('/admin_order')
def admin_order():
    cur = mysql.connection.cursor(DictCursor)

    cur.execute("""
        SELECT 
            o.order_number,
            o.customer_name,
            o.customer_email,
            o.product_name,
            p.description,
            o.amount,
            o.file,
            o.status,
            o.order_date
        FROM glamfluer_orders o
        LEFT JOIN glamfluer_products p 
            ON o.product_name = p.product_name
        ORDER BY o.order_date DESC
    """)

    orders_raw = cur.fetchall()
    cur.close()

    grouped_orders = defaultdict(lambda: {
        'items': [],
        'total': 0,
        'name': '',
        'email': '',

        'date': '',
        'status': ''
    })

    for row in orders_raw:
        ord_num = row['order_number']

        grouped_orders[ord_num]['items'].append({
            'product_name': row['product_name'],
            'description': row['description'] if row['description'] else "No description available",
            'amount': row['amount'],
            'file': row['file']
        })

        grouped_orders[ord_num]['total'] += float(row['amount'])
        grouped_orders[ord_num]['name'] = row['customer_name']
        grouped_orders[ord_num]['email'] = row['customer_email']
        grouped_orders[ord_num]['date'] = row['order_date']
        grouped_orders[ord_num]['status'] = row['status']

    return render_template('admin/admin_orders.html', orders=grouped_orders)





@app.route('/admin_settings', methods=['GET', 'POST'])
def admin_settings():
    cur = mysql.connection.cursor(DictCursor)

    if request.method == 'POST':
        # Get data from form
        s_name = request.form.get('store_name')
        s_email = request.form.get('store_email')
        s_phone = request.form.get('store_phone')
        s_url = request.form.get('website_url')
        s_address = request.form.get('store_address')
        s_currency = request.form.get('currency')
        s_timezone = request.form.get('timezone')

        # Update Database
        cur.execute("""  UPDATE glamfluer_settings  SET store_name=%s,
                        store_email=%s,
                        store_phone=%s,
                        website_url=%s,
                        store_address=%s,
                        currency=%s,
                        timezone=%s
                    WHERE id = 1
                    """, (s_name, s_email, s_phone, s_url, s_address, s_currency, s_timezone))
        mysql.connection.commit()
        return render_template('admin/admin_settings.html')

    # GET: Fetch settings
    cur.execute("SELECT * FROM glamfluer_settings WHERE id=1")
    settings_data = cur.fetchone()
    cur.close()

    return render_template('admin/admin_settings.html', s=settings_data)


#--------------------------------------
#                    ADMIN SHIPPING
#------------------------------------
@app.route("/admin_delivery", methods=['GET', 'POST'])
def admin_delivery():
    cur = mysql.connection.cursor(DictCursor)

    if request.method == 'POST':
        order_id = request.form.get('order_id')
        new_status = request.form.get('status')
        cur.execute("UPDATE glamfluer_orders SET status = %s WHERE id = %s", (new_status, order_id))
        mysql.connection.commit()

    # JOIN with user_addresses table using address_id from orders
    query = """
        SELECT 
            o.*, 
            c.fullname, c.phone,
            ua.address_line1, ua.city, ua.state, ua.pincode
        FROM glamfluer_orders o
        LEFT JOIN glamfluer_customers c ON o.customer_email = c.email
        LEFT JOIN user_addresses ua ON o.address_id = ua.id
        ORDER BY o.order_date DESC
    """
    cur.execute(query)
    deliveries = cur.fetchall()

    # KPI logic
    cur.execute("SELECT COUNT(*) as c FROM glamfluer_orders WHERE status IN ('Placed', 'placed')")
    pending = cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) as c FROM glamfluer_orders WHERE status='on way'")
    in_transit = cur.fetchone()['c']

    cur.close()
    return render_template("admin/admin_shipping.html", deliveries=deliveries, pending=pending, in_transit=in_transit)

#







@app.route('/admin_logout')
def admin_logout():

        return render_template('index.html')


#--------------------------------User codes---------------------------------------------
@app.route('/userlogin', methods=['GET', 'POST'])
def user_login():

    if 'user' in session:
        return redirect(url_for('user_dashboard'))

    if request.method == 'POST':

        email = request.form['txtUsername'].strip()
        password = request.form['txtPassword']

        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT fullname, email, password 
            FROM glamfluer_registration 
            WHERE LOWER(email)=LOWER(%s)
        """, (email,))

        user = cur.fetchone()
        cur.close()

        # ✅ correct login
        if user and check_password_hash(user[2], password):

            session.clear()
            session['user'] = user[1]
            session['fullname'] = user[0]

            return redirect(url_for('user_dashboard'))

        # ❌ wrong login
        else:
            return render_template(
                'user_login.html',
                message="Invalid Email or Password"
            )

    return render_template('user_login.html')













@app.route('/registration', methods=['GET', 'POST'])
def registration():
    '''
    if request.method == 'POST':
        # ... your existing logic to get form data ...
        email = request.form['txtemail']
        hashed_pw = generate_password_hash(request.form['txtpassword'])

        # 1. Generate Verification Token
        token = serializer.dumps(email, salt='email-confirm')
        confirm_url = url_for('confirm_email', token=token, _external=True)

        # 2. Save User (is_verified = False)
        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO glamfluer_registration (fullname, email, password, is_verified) VALUES (%s, %s, %s, %s)",
            (fullname, email, hashed_pw, False))
        mysql.connection.commit()
        cur.close()

        # 3. Send Verification Email
        msg = Message('Verify Your GlamFleur Account', sender='noreply@glamfleur.com', recipients=[email])
        msg.body = f'Welcome to the family! Click here to verify: {confirm_url}'
        mail.send(msg)

        return render_template('registration.html', message="Check your email to verify your account!")
'''
    return render_template('registration.html')



#--------------------USer dashboard --------------



@app.route('/user_dashboard', methods=['GET','POST'])
def user_dashboard():
    if 'user' not in session:
        return redirect(url_for('user_login'))

    cur = mysql.connection.cursor(DictCursor)

    cat_id = request.args.get('cat_id')
    email = session['user']

    cur.execute("SELECT * FROM glamfluer_registration WHERE email=%s", (email,))
    user_data = cur.fetchone()

    # -------- Categories --------
    cur.execute("SELECT id, category_name FROM glamfluer_categories")
    categories = cur.fetchall()

    # -------- Fetch Products FIRST --------
    if cat_id:
        cur.execute("""
            SELECT id, product_name, brand, price, file, stock 
            FROM glamfluer_products 
            WHERE category_id = %s AND stock > 0
        """, (cat_id,))
    else:
        cur.execute("""
            SELECT id, product_name, brand, price, file, stock 
            FROM glamfluer_products 
            WHERE stock > 0
        """)

    products = cur.fetchall()

    # Convert Decimal to float
    for p in products:
        p['price'] = float(p['price'])

    # -------- Fetch Wishlist --------
    cur.execute(
        "SELECT product_name FROM glamfluer_wishlist WHERE username=%s",
        (email,)
    )
    wishlist_items = cur.fetchall()
    wishlist_names = [item['product_name'] for item in wishlist_items]

    # Mark products already in wishlist
    for product in products:
        product['in_wishlist'] = product['product_name'] in wishlist_names

    # -------- Cart Count --------
    cur.execute(
        "SELECT SUM(quantity) as total_items FROM cart WHERE customer_email = %s",
        (email,)
    )
    cart_count_data = cur.fetchone()
    cart_count = cart_count_data['total_items'] if cart_count_data['total_items'] else 0

    cur.execute("SELECT * FROM glamfluer_reviews WHERE status='Approved' ORDER BY created_at DESC LIMIT 6")
    live_reviews = cur.fetchall()
    cur.close()

    return render_template(
        'user/user_dashboard.html',
        username=email,
        fullname=session.get('fullname'),
        products=products,
        categories=categories,
        cart_count=cart_count,
        user_data=user_data,
        live_reviews=live_reviews
    )


@app.route('/wishlist')
def wishlist():
    if 'user' not in session:
        return redirect(url_for('user_login'))

    # Use DictCursor so you can access data as item.product_name in HTML
    cur = mysql.connection.cursor(DictCursor)

    # Fetch wishlist items for the logged-in user
    cur.execute("SELECT * FROM glamfluer_wishlist WHERE username = %s", (session['user'],))
    wish_items = cur.fetchall()

    # Calculate Metrics for the top banner
    total_items = len(wish_items)
    total_value = sum(item['price'] for item in wish_items) if wish_items else 0
    total_mrp = sum(item['mrp'] for item in wish_items) if wish_items else 0
    total_savings = total_mrp - total_value
    cur.close()

    return render_template(
        'user/wishlist.html',
        items=wish_items,
        stats={
            'count': total_items,
            'value': "{:,.0f}".format(total_value),
            'savings': "{:,.0f}".format(total_savings)
        },
        fullname=session.get('fullname'),
        username=session.get('user')
    )


@app.route('/add_to_wishlist/<int:product_id>', methods=['POST'])
def add_to_wishlist(product_id):
    if 'user' not in session:
        return redirect(url_for('user_login'))

    cur = mysql.connection.cursor(DictCursor)

    # Check for duplicates
    cur.execute(
        "SELECT * FROM glamfluer_wishlist WHERE username=%s AND product_name=(SELECT product_name FROM glamfluer_products WHERE id=%s)",
        (session['user'], product_id))
    if cur.fetchone():
        cur.close()
        # Returns 'exists' so the frontend still shows the popup and turns the heart pink
        return jsonify({'status': 'exists', 'message': 'Item already in wishlist! 🩷'})

    # Fetch product and insert
    cur.execute("SELECT * FROM glamfluer_products WHERE id=%s", (product_id,))
    product = cur.fetchone()

    if product:
        price = float(product['price'])
        mrp = int(price * 1.3)
        cur.execute(
            "INSERT INTO glamfluer_wishlist (username, product_name, brand, price, mrp, file) VALUES (%s, %s, %s, %s, %s, %s)",
            (session['user'], product['product_name'], product['brand'], price, mrp, product['file']))
        mysql.connection.commit()
        cur.close()
        return jsonify({'status': 'success', 'message': 'Added to Wishlist! 🩷'})

    cur.close()
    return jsonify({'status': 'error', 'message': 'Product not found'})

@app.route('/remove_from_wishlist/<int:wishlist_id>')
def remove_from_wishlist(wishlist_id):
    if 'user' not in session:
        return redirect(url_for('user_login'))

    cur = mysql.connection.cursor()
    # Delete only if the ID matches and it belongs to the logged-in user
    cur.execute("DELETE FROM glamfluer_wishlist WHERE id=%s AND username=%s", (wishlist_id, session['user']))
    mysql.connection.commit()
    cur.close()

    return redirect(url_for('wishlist'))


#----------Razorpayment process------------------------
@app.route('/create_razorpay_order', methods=['POST'])
def create_razorpay_order():

    if 'user' not in session:
        return jsonify({"error": "login required"}), 401

    email = session['user']
    cur = mysql.connection.cursor(DictCursor)

    cur.execute("SELECT * FROM cart WHERE customer_email=%s", (email,))
    cart_items = cur.fetchall()

    if not cart_items:
        cur.close()
        return jsonify({"error": "cart empty"})

    total = sum(float(item['price']) * int(item['quantity']) for item in cart_items)
    shipping = 0 if total > 499 else 70
    final_amount = total + shipping

    if final_amount < 1:
        final_amount = 1

    razorpay_order = razorpay_client.order.create({
        "amount": int(final_amount * 100),
        "currency": "INR",
        "payment_capture": 1
    })

    cur.close()

    return jsonify({
        "order_id": razorpay_order['id'],
        "amount": int(final_amount * 100),
        "key": RAZORPAY_KEY_ID
    })

#------------------------Payment verification-----------
@app.route('/verify_payment', methods=['POST'])
def verify_payment():

    if 'user' not in session:
        return jsonify({"status": "error"})

    payment_id = request.form.get('razorpay_payment_id')
    order_id = request.form.get('razorpay_order_id')
    signature = request.form.get('razorpay_signature')

    try:
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        })

        # save order
        create_order(None, "ONLINE")

        return jsonify({"status": "success"})

    except Exception as e:
        print(e)
        return jsonify({"status": "failed"})



#-------------------- --- TRACK ORDER ---
@app.route('/track_order')
def track_order():
    if 'user' not in session:
        return redirect(url_for('user_login'))

    email = session['user']
    cur = mysql.connection.cursor(DictCursor)

    cur.execute("""
        SELECT * FROM glamfluer_orders
        WHERE customer_email=%s
        ORDER BY order_date DESC
    """, (email,))
    orders_raw = cur.fetchall()

    orders_dict = {}

    for row in orders_raw:
        order_no = row['order_number']

        if order_no not in orders_dict:
            orders_dict[order_no] = {
                "id": order_no,
                "status": row['status'],
                "date": row['order_date'],
                "total_amount": 0,
                "products": []
            }

        orders_dict[order_no]["products"].append({
            "product_name": row['product_name'],
            "amount": row['amount'],
            "image": row['file']
        })

        orders_dict[order_no]["total_amount"] += float(row['amount'])

    orders = list(orders_dict.values())

    # Simple stats
    stats = {
        "Total": len(orders),
        "Delivered": sum(1 for o in orders if o["status"] == "Delivered"),
        "Shipped": sum(1 for o in orders if o["status"] == "Shipped"),
        "Pending": sum(1 for o in orders if o["status"] == "Pending" or o["status"] == "Paid")
    }

    cur.close()

    return render_template(
        "user/track_order.html",
        orders=orders,
        stats=stats
    )

#NEW ROUTE: User Side Tracking




@app.route("/offers")
def offers():
    if 'user' not in session:
        return redirect(url_for('user_login'))

    cur = mysql.connection.cursor(DictCursor)

    # Selecting from your actual table 'glamfluer_offers'
    cur.execute("SELECT * FROM glamfluer_offers WHERE status = 'active' ORDER BY id DESC")
    all_offers = cur.fetchall()

    total_active = len(all_offers)

    # Using your actual DB column 'discount_value'
    try:
        # Filter out None values before calculating max
        discounts = [int(o['discount_value']) for o in all_offers if o['discount_value'] is not None]
        max_discount = max(discounts) if discounts else 0
    except (KeyError, ValueError):
        max_discount = 0

    cur.close()

    return render_template(
        'user/offers.html',
        offers=all_offers,
        stats={
            'active': total_active,
            'max': max_discount
        },
        fullname=session.get('fullname'),
        username=session.get('user')
    )


@app.route("/addresses", methods=["GET", "POST"])
def addresses():
    if 'user' not in session:
        return redirect(url_for('user_login'))

    cur = mysql.connection.cursor(DictCursor)

    # NEW: Fetch the actual 'username' linked to the session email
    cur.execute("SELECT username FROM glamfluer_registration WHERE email = %s", (session['user'],))
    user_record = cur.fetchone()

    if not user_record:
        return "User not found", 404

    actual_username = user_record['username']

    if request.method == 'POST':
        addr_id = request.form.get('address_id')
        full_name = request.form.get('full_name')
        phone = request.form.get('phone_number')
        addr1 = request.form.get('address_line1')
        addr2 = request.form.get('address_line2')
        city = request.form.get('city')
        state = request.form.get('state')
        pincode = request.form.get('pincode')
        addr_type = request.form.get('address_type')
        is_default = 1 if request.form.get('is_default') else 0

        if is_default == 1:
            cur.execute("UPDATE user_addresses SET is_default=0 WHERE username=%s", (actual_username,))

        if addr_id and addr_id.strip():
            # UPDATE existing address
            cur.execute("""
                UPDATE user_addresses
                SET full_name=%s, phone_number=%s, address_line1=%s,
                    address_line2=%s, city=%s, state=%s,
                    pincode=%s, address_type=%s, is_default=%s
                WHERE id=%s AND username=%s
            """, (full_name, phone, addr1, addr2, city, state,
                  pincode, addr_type, is_default, addr_id, actual_username))
        else:
            # INSERT new address - Using actual_username here fixes the IntegrityError
            cur.execute("""
                INSERT INTO user_addresses
                (username, full_name, phone_number, address_line1,
                 address_line2, city, state, pincode, address_type, is_default)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (actual_username, full_name, phone, addr1,
                  addr2, city, state, pincode, addr_type, is_default))

        mysql.connection.commit()
        cur.close()
        return redirect(url_for('addresses'))

    # GET request: Fetch using the actual_username
    cur.execute("SELECT * FROM user_addresses WHERE username=%s ORDER BY is_default DESC", (actual_username,))
    user_addrs = cur.fetchall()

    # ... (rest of your count logic) ...
    cur.close()
    return render_template('user/address.html', addresses=user_addrs)


@app.route("/delete_address/<int:id>")
def delete_address(id):
    if 'user' not in session:
        return redirect(url_for('user_login'))

    cur = mysql.connection.cursor()

    # 1. Get the actual username linked to the session email
    cur.execute("SELECT username FROM glamfluer_registration WHERE email = %s", (session['user'],))
    user_record = cur.fetchone()

    if user_record:
        actual_username = user_record[0]  # Using index 0 if not using DictCursor
        # 2. Delete using the correct username
        cur.execute("DELETE FROM user_addresses WHERE id=%s AND username=%s", (id, actual_username))
        mysql.connection.commit()

    cur.close()
    return redirect(url_for('addresses'))


@app.route("/set_default_address/<int:id>")
def set_default_address(id):
    if 'user' not in session:
        return redirect(url_for('user_login'))

    cur = mysql.connection.cursor()

    # 1. Get the actual username linked to the session email
    cur.execute("SELECT username FROM glamfluer_registration WHERE email = %s", (session['user'],))
    user_record = cur.fetchone()

    if user_record:
        actual_username = user_record[0]
        # 2. Reset all to 0
        cur.execute("UPDATE user_addresses SET is_default=0 WHERE username=%s", (actual_username,))
        # 3. Set specific ID to 1
        cur.execute("UPDATE user_addresses SET is_default=1 WHERE id=%s AND username=%s", (id, actual_username))
        mysql.connection.commit()

    cur.close()
    return redirect(url_for('addresses'))

@app.route("/payments")
def payments():
    if 'user' in session:
        return render_template(
            'user/payments.html',
            username=session.get('user'),
            fullname=session.get('fullname', session.get('user'))
        )
    return render_template('index.html')


@app.route("/notifications")
def notifications():
    if 'user' in session:
        # If you have a notifications table, fetch data here.
        # For now, we are passing static data in HTML
        return render_template(
            'user/notifications.html',
            username=session.get('user'),
            fullname=session.get('fullname')
        )
    return render_template('user_login.html')
#_____________________PROFILE_---------------------

@app.route("/profile")
def profile():
    if 'user' not in session:
        return redirect(url_for('user_login'))

    user_email = session['user']
    cur = mysql.connection.cursor(DictCursor)

    # 1. Fetch Basic User Data
    cur.execute("SELECT * FROM glamfluer_registration WHERE email = %s", (user_email,))
    user_reg = cur.fetchone()

    # 2. Fetch Customer Specific Data (Wallet, Points, Referral)
    cur.execute("SELECT * FROM glamfluer_customers WHERE email = %s", (user_email,))
    customer_data = cur.fetchone()

    # 3. Calculate Real-time Points based on Order History
    # Logic: Sum of 'amount' where status is 'Paid' or 'Delivered'
    cur.execute("""
        SELECT SUM(amount) as total_spent 
        FROM glamfluer_orders 
        WHERE customer_email = %s AND status IN ('Paid', 'Delivered', 'Placed')
    """, (user_email,))
    order_stats = cur.fetchone()

    # Calculate points: 1 point per 10 Rupees
    total_spent = order_stats['total_spent'] if order_stats['total_spent'] else 0
    calculated_points = int(total_spent // 10)

    cur.close()

    if not user_reg:
        return render_template('user_login.html')

    # Combine data for the template
    return render_template(
        'user/myprofile.html',
        fullname=user_reg['fullname'],
        user_data=user_reg,
        rewards={
            "points": calculated_points,
            "wallet": customer_data['wallet_balance'] if customer_data else 0.00,
            "referral_code": customer_data['referral_code'] if customer_data else "GLAM-NEW",
            "next_reward": 500 - (calculated_points % 500)  # Points needed for next milestone
        }
    )



@app.route('/upload_profile_image', methods=['POST'])
def upload_profile_image():
    if 'user' not in session:
        return redirect(url_for('user_login'))

    if 'profile_image' not in request.files:
        return redirect(url_for('profile'))

    file = request.files['profile_image']

    if file.filename == '':
        return redirect(url_for('profile'))

    if file:
        image_data = file.read()   # 🔥 Read image as binary

        cur = mysql.connection.cursor()
        cur.execute(
            "UPDATE glamfluer_registration SET profile_file=%s WHERE email=%s",
            (image_data, session['user'])
        )
        mysql.connection.commit()
        cur.close()

    return redirect(url_for('profile'))


@app.route('/get_profile_image/<email>')
def get_profile_image(email):
    cur = mysql.connection.cursor()
    cur.execute(
        "SELECT profile_file FROM glamfluer_registration WHERE email=%s",
        (email,)
    )
    user = cur.fetchone()
    cur.close()

    if user and user[0]:

        image_data = user[0]
        image_type = imghdr.what(None, image_data)

        if image_type:
            return Response(image_data, mimetype=f'image/{image_type}')

    return ""


@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user' not in session:
        return redirect(url_for('user_login'))

    fullname = request.form['fullname']
    phone = request.form['phone']
    dob = request.form['dob']
    gender = request.form['gender']
    location = request.form['location']

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE glamfluer_registration
        SET fullname=%s, phone=%s, dob=%s, gender=%s, location=%s
        WHERE email=%s
    """, (fullname, phone, dob, gender, location, session['user']))

    mysql.connection.commit()
    cur.close()

    return redirect(url_for('profile'))


@app.context_processor
def inject_user_data():
    if 'user' in session:
        cur = mysql.connection.cursor(DictCursor)
        cur.execute("SELECT fullname, profile_file FROM glamfluer_registration WHERE email=%s", (session['user'],))
        user = cur.fetchone()
        cur.close()

        if user:
            return dict(
                fullname=user['fullname'],
                user_data=user,
                username=session['user']
            )

    return dict(fullname=None, user_data=None, username=None)


@app.route("/settings")
def settings():
    if 'user' in session:
        return render_template(
            'user/settings.html ',
            username=session.get('user'),
            fullname=session.get('fullname', session.get('user'))
        )
    return render_template('index.html')


@app.route('/user_logout')
def user_logout():
    session.clear()
    return redirect(url_for('user_login'))


from werkzeug.security import generate_password_hash
@app.route("/save", methods=['POST'])
def save():
    fn = request.form['txtfullname']
    email = request.form['txtemail']
    username = request.form['txtusername']
    password = request.form['txtpassword']
    confirm = request.form['txtconfirm']

    if password != confirm:
        return "Passwords do not match"

    hashed_password = generate_password_hash(password)
    cur = mysql.connection.cursor()

    # Insert into registration table
    cur.execute(
        """
        INSERT INTO glamfluer_registration (fullname, email, username, password)
        VALUES (%s, %s, %s, %s)
        """,
        (fn, email, username, hashed_password)
    )

    # Insert SAME USER into customers table
    cur.execute(
        """
        INSERT INTO glamfluer_customers
        (fullname, email, location, segment, orders, total_spent, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (fn, email, "Not Set", "New", 0, 0, "active")
    )

    mysql.connection.commit()
    cur.close()

    session['user'] = email
    session['fullname'] = fn

    return render_template(
        'user_login.html',
        username=email,
        fullname=fn
    )





# ----------------- CART VIEW & CHECKOUT -------------
# =====================================================================
# UPDATED CART ROUTE — adds gst_amount to template context
# =====================================================================

@app.route('/cart', methods=['GET', 'POST'])
def cart():
    if 'user' not in session:
        return redirect(url_for('user_login'))

    email = session['user']
    cur = mysql.connection.cursor(DictCursor)

    # ---------------- CART ITEMS ----------------
    cur.execute("SELECT * FROM cart WHERE customer_email=%s", (email,))
    cart_items = cur.fetchall()

    for item in cart_items:
        if 'file' in item:
            item['image'] = item['file']

    total = sum(float(item['price']) * int(item['quantity']) for item in cart_items)
    shipping = 0 if total > 499 or total == 0 else 70

    # ---------------- LIVE OFFERS ----------------
    cur.execute("""
        SELECT * FROM glamfluer_offers
        WHERE status='active'
        AND start_date <= CURDATE()
        AND end_date >= CURDATE()
        ORDER BY id DESC
    """)
    live_offers = cur.fetchall()

    discount = 0
    applied_offer = None

    if request.method == "POST" and request.form.get("apply_offer"):
        offer_id = request.form.get("offer_id")

        cur.execute("SELECT * FROM glamfluer_offers WHERE id=%s", (offer_id,))
        offer = cur.fetchone()

        if offer:
            if not offer['min_purchase'] or total >= float(offer['min_purchase']):
                if offer['discount_type'] == "percentage":
                    discount = (total * float(offer['discount_value'])) / 100
                else:
                    discount = float(offer['discount_value'])

                applied_offer = offer

    # ---- GST Calculation: 18% on (subtotal - discount) ----
    taxable_amount = total - discount
    gst_rate = 0.18  # 18%
    gst_amount = taxable_amount * gst_rate if taxable_amount > 0 else 0

    final_amount = taxable_amount + shipping + gst_amount

    # ================= FETCH ADDRESSES =================
    cur.execute(
        "SELECT username FROM glamfluer_registration WHERE email=%s",
        (email,)
    )
    user = cur.fetchone()
    username = user['username']

    cur.execute(
        "SELECT * FROM user_addresses WHERE username=%s ORDER BY is_default DESC",
        (username,)
    )
    addresses = cur.fetchall()

    cur.close()

    return render_template(
        'user/cart.html',
        cart_items=cart_items,
        total=total,
        shipping=shipping,
        discount=round(discount, 2),
        applied_offer=applied_offer,
        final_amount=round(final_amount, 2),
        gst_amount=round(gst_amount, 2),   # ← NEW: passed to template
        live_offers=live_offers,
        fullname=session.get('fullname'),
        username=email,
        addresses=addresses
    )



#-------------Cart def--------------

def generate_order_number():
    return "GF" + ''.join(random.choices(string.digits, k=8))
def create_order(address_id, payment_method):
    if 'user' not in session:
        return

    email = session['user']
    cur = mysql.connection.cursor(DictCursor)

    # Get cart items
    cur.execute("SELECT * FROM cart WHERE customer_email=%s", (email,))
    cart_items = cur.fetchall()

    if not cart_items:
        cur.close()
        return

    order_number = generate_order_number()

    # status based on payment
    status = "Pending" if payment_method == "COD" else "Paid"

    for item in cart_items:
        cur.execute("""
            INSERT INTO glamfluer_orders
            (order_number, customer_email, product_name, amount, file, status, payment_method, address_id, order_date)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW())
        """, (
            order_number,
            email,
            item['product_name'],
            float(item['price']) * int(item['quantity']),
            item.get('file'),
            status,
            payment_method,
            address_id
        ))

    # clear cart after order placed
    cur.execute("DELETE FROM cart WHERE customer_email=%s", (email,))
    mysql.connection.commit()
    cur.close()

# =====================================================================
# UPDATED place_cod_order ROUTE
# — handles both saved address selection AND new address saving to DB
# =====================================================================

@app.route('/place_cod_order', methods=['POST'])
def place_cod_order():
    if 'user' not in session:
        return redirect(url_for('user_login'))

    email = session['user']
    cur = mysql.connection.cursor(DictCursor)

    # Get username from email
    cur.execute(
        "SELECT username FROM glamfluer_registration WHERE email=%s",
        (email,)
    )
    user = cur.fetchone()
    username = user['username']

    selected_address_id = request.form.get('selected_address_id')  # saved address
    full_name  = request.form.get('full_name')                      # new address fields
    phone      = request.form.get('phone_number')

    address_id = None

    if full_name and phone and full_name.strip() and phone.strip():
        # ---- User filled in a NEW address → save it to DB (also visible in address dashboard) ----
        addr1      = request.form.get('address_line1', '')
        addr2      = request.form.get('address_line2', '')
        city       = request.form.get('city', '')
        state      = request.form.get('state', '')
        pincode    = request.form.get('pincode', '')
        addr_type  = request.form.get('address_type', 'Home')

        cur.execute("""
            INSERT INTO user_addresses
            (username, full_name, phone_number, address_line1,
             address_line2, city, state, pincode, address_type, is_default)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            username, full_name, phone, addr1,
            addr2, city, state, pincode, addr_type, 0
        ))
        mysql.connection.commit()
        address_id = cur.lastrowid

    elif selected_address_id and selected_address_id.strip():
        # ---- User selected an existing saved address ----
        address_id = int(selected_address_id)

    else:
        cur.close()
        # No address provided — redirect back with error
        return redirect(url_for('cart'))

    cur.close()

    # Place the order using the resolved address_id
    create_order(address_id, "COD")

    return redirect("/track_order")




@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    if 'user' not in session:

        if 'guest_cart' not in session:
            session['guest_cart'] = []

        session['guest_cart'].append(product_id)
        session.modified = True

        return {"status": "success", "cart_count": len(session['guest_cart'])}

    email = session['user']
    cur = mysql.connection.cursor(DictCursor)

    cur.execute("SELECT * FROM glamfluer_products WHERE id=%s", (product_id,))
    product = cur.fetchone()

    cur.execute("SELECT * FROM cart WHERE product_id=%s AND customer_email=%s", (product_id, email))
    existing = cur.fetchone()

    if existing:
        cur.execute("UPDATE cart SET quantity = quantity + 1 WHERE customer_email=%s AND product_id=%s", (email,product_id))
    else:
        cur.execute("""
            INSERT INTO cart (customer_email, product_id, product_name, brand, file, price, quantity)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (email, product['id'], product['product_name'], product['brand'], product['file'], float(product['price']), 1))

    mysql.connection.commit()

    cur.execute(""" SELECT SUM(quantity) as total_items FROM cart WHERE customer_email=%s""", (email,))
    cart_count_data = cur.fetchone()
    cart_count= cart_count_data['total_items'] if cart_count_data['total_items'] else 0

    cur.close()

    return{"status": "success", "cart_count": cart_count}





@app.route('/update_cart/<int:id>/<delta>')
def update_cart(id, delta):
    if 'user' not in session:
        return redirect(url_for('user_login'))

    try:
        change = int(delta)
    except ValueError:
        return redirect(url_for('cart'))

    cur = mysql.connection.cursor(DictCursor)

    # Get current quantity of that specific cart item
    cur.execute("""
        SELECT quantity FROM cart 
        WHERE id=%s AND customer_email=%s
    """, (id, session['user']))

    item = cur.fetchone()

    if item:
        new_qty = item['quantity'] + change

        # 🔥 IF quantity becomes 0 → DELETE that item
        if new_qty <= 0:
            cur.execute("""
                DELETE FROM cart 
                WHERE id=%s AND customer_email=%s
            """, (id, session['user']))
        else:
            # Otherwise update quantity
            cur.execute("""
                UPDATE cart 
                SET quantity=%s 
                WHERE id=%s AND customer_email=%s
            """, (new_qty, id, session['user']))

        mysql.connection.commit()

    cur.close()
    return redirect(url_for('cart'))



# --- FIX: Delete Cart Route ---
@app.route('/delete_cart_item/<int:id>')
def delete_cart_item(id):
    if 'user' not in session:
        return redirect(url_for('user_login')) # Use redirect here

    cur = mysql.connection.cursor()
    # This deletes ONLY the specific row with that ID for that specific user
    cur.execute("""
        DELETE FROM cart 
        WHERE id=%s AND customer_email=%s
    """, (id, session['user']))

    mysql.connection.commit()
    cur.close()

    # IMPORTANT: Redirect to the 'cart' function to refresh data and totals
    return redirect(url_for('cart'))

@app.route("/search_products")
def search_products():

    query = request.args.get("q", "")

    if query == "":
        return {"results": []}

    cur = mysql.connection.cursor(DictCursor)

    cur.execute("""
        SELECT p.id, p.product_name, p.price, p.file,
               c.category_name
        FROM glamfluer_products p
        JOIN glamfluer_categories c
        ON p.category_id = c.id
        WHERE p.status='Active'
        AND (
            p.product_name LIKE %s
            OR c.category_name LIKE %s
        )
        LIMIT 10
    """, (f"%{query}%", f"%{query}%"))

    results = cur.fetchall()
    cur.close()

    return {"results": results}


@app.route('/check_order', methods=['GET', 'POST'])
def check_order():
    if request.method == 'POST':
        order_id = request.form.get('order_id')
        cur = mysql.connection.cursor(DictCursor)

        # Removed LIMIT 1 to get all products in this order
        cur.execute("""
            SELECT 
                order_number,
                product_name,
                amount,
                file,
                status,
                order_date
            FROM glamfluer_orders
            WHERE order_number = %s
        """, (order_id,))

        order_items = cur.fetchall() # Get the full list
        cur.close()

        if not order_items:
            # Handle empty result (redirect or show error)
            return render_template('user/track_order.html', error="Order not found")

        # Pass the list 'order_items' and use the first item for header info
        return render_template('user/check_order.html', order_items=order_items, order=order_items[0])

    return render_template('user/track_order.html')


@app.route('/check_order/<order_id>')
def check_order_by_id(order_id):
    cur = mysql.connection.cursor(DictCursor)

    # Fetch order
    cur.execute("""
        SELECT 
            order_number,
            product_name,
            amount,
            file,
            status,
            order_date
        FROM glamfluer_orders
        WHERE order_number = %s
        LIMIT 1
    """, (order_id,))

    order = cur.fetchone()
    cur.close()

    #  If not found
    if not order:
        return "Order not found"

    return render_template('user/check_order.html', order=order)

@app.context_processor
def inject_stats():
    cur = mysql.connection.cursor(DictCursor)

    cur.execute("""
        SELECT 
            COUNT(*) as Total,
            SUM(CASE WHEN status = 'Delivered' THEN 1 ELSE 0 END) as Delivered
        FROM glamfluer_orders
    """)
    stats = cur.fetchone()

    cur.close()
    return dict(stats=stats)


@app.route('/helpcenter')
def helpcenter():

    return render_template('user/helpcenter.html')

#------------------------Invoice
#-------------------------------
@app.route('/invoice/<order_no>')
def invoice(order_no):
    if 'user' not in session:
        return redirect(url_for('user_login'))

    cur = mysql.connection.cursor(DictCursor)

    # Fetch order items
    cur.execute("""
        SELECT * FROM glamfluer_orders 
        WHERE order_number = %s AND customer_email = %s
    """, (order_no, session['user']))

    items = cur.fetchall()

    if not items:
        return "Order not found in database", 404


    # ✅ FETCH LATEST ADDRESS (NO is_default)
    cur.execute("""
        SELECT * FROM user_addresses
        WHERE username = %s
        ORDER BY id DESC
        LIMIT 1
    """, (session['user'],))

    address = cur.fetchone()


    # ---------- TOTAL CALCULATION ----------
    subtotal = sum(float(item.get('amount', 0)) for item in items)

    gst_rate = 0.18
    gst_amount = subtotal * gst_rate

    cgst = gst_amount / 2
    sgst = gst_amount / 2

    grand_total = subtotal + gst_amount

    order_info = {
        "order_no": order_no,
        "date": items[0]['order_date'],
        "status": items[0]['status'],
        "customer": session['user']
    }

    cur.close()

    return render_template(
        "user/invoice.html",
        items=items,
        order=order_info,
        subtotal=subtotal,
        cgst=cgst,
        sgst=sgst,
        gst=gst_amount,
        total=grand_total,
        address=address
    )

@app.route('/gift_cart')
def gift_cart():

    return render_template('user/gift_cart.html')


@app.route('/store_&_event')
def store_event():

  return render_template('user/store_&_event.html')


@app.route('/aboutus')
def aboutus():

    return render_template('user/aboutus.html')

@app.route('/career')
def career():

    return render_template('user/career.html')

@app.route('/authenticity')
def authenticity():

    return render_template('user/authenticity.html')

@app.route('/return_policy')
def return_policy():

    return render_template('user/return_policy.html')

@app.route('/terms_conditions')
def terms_conditions():

    return render_template('user/terms_conditions.html')

@app.route('/privacy_policy')
def privacy_policy():

    return render_template('user/privacy_policy.html')


#------------------------2FA------------------
from flask import flash, redirect, request, session, render_template, url_for
import random
from datetime import datetime, timedelta

@app.route('/forgot_password', methods=['GET','POST'])
def forgot_password():

    if request.method == "POST":
        email = request.form['email']

        cur = mysql.connection.cursor(DictCursor)
        cur.execute("""
            SELECT * FROM glamfluer_registration
            WHERE email=%s
        """,(email,))

        user = cur.fetchone()

        if not user:
            flash("Email not registered")
            return render_template("forgot_password.html")

        otp = str(random.randint(100000,999999))

        session['reset_email'] = email
        session['reset_otp'] = otp

        send_otp_email(email, otp)

        return redirect(url_for('verify_otp'))

    return render_template("forgot_password.html")

@app.route('/verify_otp', methods=['GET','POST'])
def verify_otp():

    if request.method == "POST":

        user_otp = request.form['otp']

        if 'reset_otp' not in session:
            return redirect(url_for('forgot_password'))

        if user_otp == session['reset_otp']:
            return redirect(url_for('reset_password'))
        else:
            flash("Invalid OTP")

    return render_template("verify_otp.html")


@app.route('/reset_password', methods=['GET','POST'])
def reset_password():

    if 'reset_email' not in session:
        return redirect(url_for('forgot_password'))

    if request.method == "POST":

        password = request.form['password']
        hashed = generate_password_hash(password)

        cur = mysql.connection.cursor()
        cur.execute("""
            UPDATE glamfluer_registration
            SET password=%s
            WHERE email=%s
        """,(hashed, session['reset_email']))

        mysql.connection.commit()
        cur.close()

        session.pop('reset_email',None)
        session.pop('reset_otp',None)

        flash("Password updated successfully")
        return redirect(url_for('user_login'))

    return render_template("reset_password.html")

#----------------------Payment  checkout---------------
@app.route("/checkout", methods=["POST"])
def checkout():

    if 'user' not in session:
        return redirect(url_for('user_login'))

    payment_method = request.form.get("payment_method")

    # COD
    if payment_method == "cod":
        return jsonify({"status":"cod"})

    # UPI / WALLET
    return jsonify({"status":"online"})


#----------------------------------------------------
#     CANCEL ORDER
#--------------------------------------------
@app.route('/cancel_order', methods=['POST'])
def cancel_order():

    if 'user' not in session:
        return jsonify({"status":"login required"})

    data = request.get_json()
    order_id = data.get("order_id")
    reason = data.get("reason")

    cur = mysql.connection.cursor()

    cur.execute("""
        UPDATE glamfluer_orders
        SET status='Cancelled'
        WHERE order_number=%s
        AND customer_email=%s
    """,(order_id, session['user']))

    mysql.connection.commit()
    cur.close()

    return jsonify({"status":"success"})



#-------------------------------------------
#    RETURN ORDER
#------------------------------------------

@app.route('/return_order', methods=['POST'])
def return_order():

    if 'user' not in session:
        return jsonify({"status":"login required"})

    data = request.get_json()
    order_id = data.get("order_id")
    reason = data.get("reason")

    cur = mysql.connection.cursor()

    cur.execute("""
        UPDATE glamfluer_orders
        SET status='Returned'
        WHERE order_number=%s
        AND customer_email=%s
    """,(order_id, session['user']))

    mysql.connection.commit()
    cur.close()

    return jsonify({"status":"success"})


#---------------------------------------
#              REVIEW AND RATING
#---------------------------------------
# 1. Review Submission Route
@app.route('/submit_review', methods=['POST'])
def submit_review():
    if 'user' not in session:
        return jsonify({"status": "error", "msg": "Please login to review"})

    product_name = request.form.get('product_name')
    rating = request.form.get('rating')
    review_text = request.form.get('review_text')
    customer_email = session['user']

    # Handle Image Upload
    image_name = None
    if 'review_image' in request.files:
        file = request.files['review_image']
        if file and file.filename != '':
            image_name = secure_filename(file.filename)
            # Ensure this directory exists: static/uploads/reviews
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], 'reviews', image_name))

    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO glamfluer_reviews 
        (product_name, customer_email, rating, review_text, review_image, status, is_verified) 
        VALUES (%s, %s, %s, %s, %s, 'Approved', 1)
    """, (product_name, customer_email, rating, review_text, image_name))

    mysql.connection.commit()
    cur.close()
    return jsonify({"status": "success", "msg": "Review posted live!"})


#-----------------------CART RECOVERY MAIL ROUTES -----------

@app.route('/admin/update_status', methods=['POST'])
def update_order_status():
    order_id = request.form.get('order_id')
    new_status = request.form.get('status')

    cur = mysql.connection.cursor(DictCursor)

    # 1. Get the customer email first
    cur.execute("SELECT customer_email FROM glamfluer_orders WHERE order_number=%s LIMIT 1", (order_id,))
    order_data = cur.fetchone()

    if order_data:
        # 2. Update the DB
        cur.execute("UPDATE glamfluer_orders SET status=%s WHERE order_number=%s", (new_status, order_id))
        mysql.connection.commit()

        # 3. Trigger Real-Time Notification
        send_status_email(order_data['customer_email'], order_id, new_status)

    cur.close()
    return redirect('/admin/orders')  # Change this to your admin order page


@app.route('/admin/abandoned_carts', methods=['GET'])
def view_abandoned_carts():
    cur = mysql.connection.cursor(DictCursor)

    # 1. Fetch Abandoned Carts
    cur.execute("SELECT customer_email, product_name, price, quantity FROM cart")
    carts = cur.fetchall()

    # 2. Fetch All Registered Users (for the side list)
    cur.execute("SELECT email FROM glamfluer_registration")
    all_users = cur.fetchall()

    cur.close()
    return render_template('admin/abandoned_carts.html', carts=carts, all_users=all_users)

@app.route('/admin/send_reminder', methods=['POST'])
def send_reminder():
    email = request.form.get('email')
    product = request.form.get('product')

    if send_abandoned_cart_email(email, product):
        return {"status": "success", "message": "Email sent!"}
    return {"status": "error", "message": "Failed to send"}


@app.route('/update_order_status_realtime', methods=['POST'])
def update_order_status_realtime():
    order_no = request.form.get('order_number')
    new_status = request.form.get('status')  # Arrived, Shipped, Cancelled, etc.

    cur = mysql.connection.cursor(DictCursor)

    # 1. Update the database
    cur.execute("UPDATE glamfluer_orders SET status=%s WHERE order_number=%s", (new_status, order_no))

    # 2. Fetch customer email to notify them
    cur.execute("SELECT customer_email FROM glamfluer_orders WHERE order_number=%s LIMIT 1", (order_no,))
    customer = cur.fetchone()

    mysql.connection.commit()
    cur.close()

    if customer:
        # Trigger the status email
        # send_status_email is the def we created in the previous step
        send_status_email(customer['customer_email'], order_no, new_status)

    return redirect('/admin_dashboard')  # Or wherever your admin stays


@app.route('/admin/send_miss_you', methods=['POST'])
def send_miss_you():
    email = request.form.get('email')
    subject = "We Miss You at GlamFleur! 💖"
    body = "Hi Beautiful! We haven't seen you in a while. Come check out our latest beauty arrivals!"

    if send_marketing_email(email, subject, body):
        return redirect('/admin/abandoned_carts')
    return "Error sending email"


@app.route('/admin/broadcast_offer', methods=['POST'])
def broadcast_offer():
    subject = request.form.get('subject')
    msg_body = request.form.get('message')

    cur = mysql.connection.cursor(DictCursor)
    cur.execute("SELECT email FROM glamfluer_registration")
    users = cur.fetchall()
    cur.close()

    for user in users:
        send_marketing_email(user['email'], subject, msg_body)

    return redirect('/admin/abandoned_carts')


if __name__ == "__main__":
    app.run(debug=True)

