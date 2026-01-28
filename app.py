from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, json
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import create_engine, text, Integer, String, DateTime, Text, Column
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

# =========================
# FLASK APP
# =========================
app = Flask(__name__)
app.secret_key = 'drugai-secret-key-2025'

# =========================
# DATABASE (SQLITE)
# =========================
DATABASE_URL = "sqlite:///drugai.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # REQUIRED for SQLite + Flask
)

Session = scoped_session(sessionmaker(bind=engine))
Base = declarative_base()

@app.teardown_appcontext
def shutdown_session(exception=None):
    Session.remove()

app.jinja_env.filters['json_loads'] = json.loads

# =========================
# MODELS
# =========================
class User(UserMixin, Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    password = Column(String(200), nullable=False)
    joined = Column(DateTime, default=datetime.utcnow)

class History(Base):
    __tablename__ = 'history'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    sickness = Column(String(200))
    results = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(engine)

# =========================
# LOGIN MANAGER
# =========================
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return Session.get(User, int(user_id))   # modern SQLAlchemy-safe

# =========================
# ROUTES
# =========================
@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if Session.query(User).filter_by(username=username).first():
            flash('Username already exists', 'danger')
        elif len(password) < 6:
            flash('Password must be at least 6 characters', 'danger')
        else:
            user = User(
                username=username,
                password=generate_password_hash(password)
            )
            Session.add(user)
            Session.commit()
            flash('Registered successfully! Please login.', 'success')
            return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = Session.query(User).filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))

        flash('Invalid username or password', 'danger')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('landing'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/history')
@login_required
def history():
    searches = (
        Session.query(History)
        .filter_by(user_id=current_user.id)
        .order_by(History.timestamp.desc())
        .all()
    )
    return render_template('history.html', searches=searches)

# =========================
# API SEARCH
# =========================
@app.route('/api/search', methods=['POST'])
@login_required
def search():
    sickness = request.json.get('sickness', '').strip()
    if not sickness:
        return jsonify({"error": "Please enter a condition"}), 400

    query = text("""
        SELECT "drugName", COUNT(*) AS users, ROUND(AVG(rating),1) AS rating
        FROM prescriptions
        WHERE LOWER(condition) LIKE LOWER(:pattern)
        GROUP BY "drugName"
        HAVING COUNT(*) >= 5
        ORDER BY users DESC
        LIMIT 12
    """)

    try:
        with engine.connect() as conn:
            results = conn.execute(
                query,
                {"pattern": f"%{sickness}%"}
            ).fetchall()
    except Exception:
        return jsonify({"error": "Database error"}), 500

    if not results:
        return jsonify({"error": "No drugs found for this condition"}), 404

    total = sum(r[1] for r in results)
    drugs = [
        {
            "drug": r[0],
            "patients": int(r[1]),
            "percentage": round(r[1] / total * 100, 1),
            "rating": float(r[2])
        }
        for r in results
    ]

    # Save history
    h = History(
        user_id=current_user.id,
        sickness=sickness,
        results=json.dumps(drugs)
    )
    Session.add(h)
    Session.commit()

    return jsonify({
        "sickness": sickness.title(),
        "total_patients": total,
        "drugs": drugs
    })

# =========================
# START APP
# =========================
if __name__ == '__main__':
    print("DrugAI starting...")
    try:
        with engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM prescriptions")
            ).scalar()
            print(f"Connected! {count:,} real patient records ready.")
    except:
        print("Warning: Could not count records (table might be empty)")

    app.run(debug=True, port=5000)
