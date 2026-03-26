import os
import pymysql
from flask import Flask, render_template, request, redirect, url_for, session, flash
from functools import wraps
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'isi_dakar_2026_key')


# --- CONNEXION RDS ---
def get_db_connection():
    try:
        return pymysql.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASS'),
            database=os.getenv('DB_NAME'),
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False
        )
    except pymysql.MySQLError as e:
        print(f"❌ Erreur RDS : {e}")
        return None


# --- AUTHENTIFICATION ---
EMPLOYEES = {"admin": "IsiAdmin2026", "amadou.tall": "Isibank2026"}


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')

        if role == 'employer' and EMPLOYEES.get(username) == password:
            session.update({'logged_in': True, 'role': 'employer', 'user': username})
            return redirect(url_for('index'))

        elif role == 'client':
            conn = get_db_connection()
            if conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM users WHERE fullname=%s AND password=%s", (username, password))
                    user = cur.fetchone()
                    if user:
                        session.update({'logged_in': True, 'role': 'client', 'user': username})
                        conn.close()
                        return redirect(url_for('client_dashboard'))
                conn.close()

        flash("Identifiants ou rôle incorrects", "danger")
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# --- INTERFACES ---

@app.route('/')
@login_required
def index():
    if session.get('role') != 'employer':
        return redirect(url_for('client_dashboard'))
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users ORDER BY id DESC")
            accounts = cur.fetchall()
        return render_template('index.html', accounts=accounts)
    finally:
        conn.close()


@app.route('/client_dashboard')
@login_required
def client_dashboard():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE fullname = %s", (session['user'],))
            user_data = cur.fetchone()
            cur.execute("SELECT * FROM transactions WHERE sender_fullname = %s ORDER BY timestamp DESC",
                        (session['user'],))
            txs = cur.fetchall()
        return render_template('client_dashboard.html', user=user_data, transactions=txs)
    finally:
        conn.close()


# --- ACTIONS ---

@app.route('/add_account', methods=['POST'])
@login_required
def add_account():
    if session.get('role') != 'employer': return "Interdit", 403
    f, e, a, b, p = request.form.get('fullname'), request.form.get('email'), request.form.get(
        'account_number'), request.form.get('balance', 0), request.form.get('password', '1234')
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (fullname, email, account_number, balance, password) VALUES (%s, %s, %s, %s, %s)",
                (f, e, a, b, p))
        conn.commit()
        flash("Compte créé avec succès !", "success")
    except Exception as err:
        conn.rollback()
        flash(f"Erreur : {err}", "danger")
    finally:
        conn.close()
    return redirect(url_for('index'))


@app.route('/transfer', methods=['POST'])
@login_required
def transfer():
    receiver_acc = request.form.get('receiver_account')
    amount = float(request.form.get('amount'))
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if session.get('role') == 'client':
                cur.execute("SELECT id, fullname, balance FROM users WHERE fullname=%s FOR UPDATE", (session['user'],))
            else:
                cur.execute("SELECT id, fullname, balance FROM users WHERE id=%s FOR UPDATE",
                            (request.form.get('sender_id'),))

            sender = cur.fetchone()
            if not sender or sender['balance'] < amount:
                flash("Solde insuffisant !", "danger")
                return redirect(url_for('index' if session['role'] == 'employer' else 'client_dashboard'))

            cur.execute("UPDATE users SET balance = balance - %s WHERE id = %s", (amount, sender['id']))
            cur.execute("UPDATE users SET balance = balance + %s WHERE account_number = %s", (amount, receiver_acc))

            if cur.rowcount == 0: raise Exception("Compte destinataire introuvable.")

            cur.execute("INSERT INTO transactions (sender_fullname, receiver_account, amount) VALUES (%s, %s, %s)",
                        (sender['fullname'], receiver_acc, amount))
        conn.commit()
        flash("Virement effectué !", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Erreur : {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for('index' if session['role'] == 'employer' else 'client_dashboard'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)