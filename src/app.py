import os
import pymysql
import random
from flask import Flask, render_template, request, redirect, url_for, session, flash
from functools import wraps
from datetime import datetime
from dotenv import load_dotenv

# Chargement des variables d'environnement
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'isi_dakar_secret_key_2026')


# --- CONFIGURATION DE LA CONNEXION DB ---
def get_db_connection():
    ssl_cert_path = './global-bundle.pem'
    ssl_config = {'ca': ssl_cert_path} if os.path.exists(ssl_cert_path) else None
    try:
        conn = pymysql.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASS'),
            database=os.getenv('DB_NAME'),
            cursorclass=pymysql.cursors.DictCursor,
            ssl=ssl_config,
            connect_timeout=10
        )
        return conn
    except Exception as e:
        print(f"❌ ERREUR CONNEXION DB : {e}")
        return None


# --- PROTECTION DES PAGES ---
def login_required(role=None):
    def wrapper(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user' not in session:
                return redirect(url_for('login'))
            if role and session.get('role') != role:
                flash("Accès non autorisé.", "danger")
                return redirect(url_for('home'))
            return f(*args, **kwargs)
        return decorated
    return wrapper


# --- ROUTES D'AUTHENTIFICATION ---
@app.route('/')
def home():
    if 'role' in session:
        if session['role'] == 'employer': return redirect(url_for('staff_dashboard'))
        if session['role'] == 'admin': return redirect(url_for('admin_dashboard'))
        return redirect(url_for('client_dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_saisi = request.form.get('username')
        password_saisi = request.form.get('password')
        role_saisi = request.form.get('role')
        conn = get_db_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, fullname, password, role FROM users WHERE username=%s", (username_saisi,))
                res = cur.fetchone()
                if res and res['role'] == role_saisi and res['password'] == password_saisi:
                    session['user'] = res['fullname']
                    session['client_id'] = res['id']
                    session['role'] = res['role']

                    if res['role'] == 'employer': return redirect(url_for('staff_dashboard'))
                    if res['role'] == 'admin': return redirect(url_for('admin_dashboard'))
                    return redirect(url_for('client_dashboard'))

                flash("Identifiants ou rôle incorrects.", "danger")
            conn.close()
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# --- ESPACE PERSONNEL (STAFF) ---
@app.route('/staff')
@login_required(role='employer')
def staff_dashboard():
    conn = get_db_connection()
    accounts = []
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, fullname, account_number, balance FROM users WHERE role='client'")
            accounts = cur.fetchall()
        conn.close()
    return render_template('staff_interface.html', accounts=accounts)


# --- ESPACE ADMINISTRATEUR (HQ) ---
@app.route('/admin')
@login_required(role='admin')
def admin_dashboard():
    conn = get_db_connection()
    stats = {'b': 0, 'c': 0}
    logs = []
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT SUM(balance) as total_b, COUNT(id) as total_c FROM users WHERE role='client'")
            res = cur.fetchone()
            if res:
                stats = {'b': res['total_b'] or 0, 'c': res['total_c']}
            try:
                cur.execute("SELECT * FROM transactions ORDER BY timestamp DESC LIMIT 10")
                logs = cur.fetchall()
            except:
                logs = []
        conn.close()
    return render_template('index.html', stats=stats, logs=logs)


# --- ESPACE CLIENT ---
@app.route('/client')
@login_required(role='client')
def client_dashboard():
    conn = get_db_connection()
    user_data = None
    transactions = []
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE id=%s", (session['client_id'],))
            user_data = cur.fetchone()
            try:
                cur.execute(
                    "SELECT amount, receiver_account, timestamp FROM transactions WHERE sender_fullname=%s ORDER BY timestamp DESC",
                    (user_data['fullname'],))
                transactions = cur.fetchall()
            except:
                transactions = []
        conn.close()
    return render_template('client_dashboard.html', user=user_data, transactions=transactions)


# --- ACTIONS CLIENT (Redéfini pour corriger l'erreur BuildError) ---
@app.route('/client/transfer', methods=['POST'])
@login_required(role='client')
def client_transfer():
    flash("Le service de virement est temporairement indisponible.", "warning")
    return redirect(url_for('client_dashboard'))


@app.route('/client/mobile-deposit', methods=['POST'])
@login_required(role='client')
def client_mobile_deposit():
    amount = request.form.get('amount')
    flash(f"Demande de dépôt de {amount} XOF envoyée.", "info")
    return redirect(url_for('client_dashboard'))


# --- ACTIONS STAFF & API ---
@app.route('/staff/register', methods=['POST'])
@login_required(role='employer')
def staff_register():
    fullname = request.form.get('fullname')
    email = request.form.get('email')
    acc_num = f"ISI-{random.randint(100000, 999999)}"
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (fullname, username, password, role, balance, account_number) VALUES (%s, %s, '1234', 'client', 0, %s)",
                (fullname, email, acc_num))
            conn.commit()
            flash(f"Compte {acc_num} créé", "success")
        conn.close()
    return redirect(url_for('staff_dashboard'))


@app.route('/staff/transaction', methods=['POST'])
@login_required(role='employer')
def staff_transaction():
    client_id = request.form.get('client_id')
    amount = int(request.form.get('amount'))
    type_op = request.form.get('type')
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            sql = "UPDATE users SET balance = balance + %s WHERE id = %s" if type_op == 'deposit' else "UPDATE users SET balance = balance - %s WHERE id = %s"
            cur.execute(sql, (amount, client_id))
            conn.commit()
            flash("Transaction réussie", "success")
        conn.close()
    return redirect(url_for('staff_dashboard'))


@app.route('/api/enrolment', methods=['POST'])
def field_enrolment():
    fullname = request.form.get('fullname')
    flash(f"Enrôlement de {fullname} reçu.", "success")
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)