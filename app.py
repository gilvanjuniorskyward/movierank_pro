from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import requests, os

app = Flask(__name__)
app.secret_key = 'supersecret'

# ✅ CORREÇÃO DO BANCO (certo para Render + local)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///db.sqlite3')

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

TMDB_API_KEY = os.getenv('TMDB_API_KEY')

# -------------------------
# MODELS
# -------------------------

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(200))

class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    poster = db.Column(db.String(200))

class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    movie_id = db.Column(db.Integer)
    score = db.Column(db.Integer)

# -------------------------
# LOGIN
# -------------------------

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# -------------------------
# ROTAS
# -------------------------

@app.route('/')
@login_required
def index():
    movies = db.session.query(
        Movie,
        db.func.avg(Rating.score).label('avg')
    ).outerjoin(
        Rating, Rating.movie_id == Movie.id
    ).group_by(
        Movie.id
    ).order_by(
        db.desc('avg')
    ).all()

    return render_template('index.html', movies=movies)

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()

        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('index'))

        flash('Erro no login')

    return render_template('login.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        user = User(
            username=request.form['username'],
            password=generate_password_hash(request.form['password'])
        )

        db.session.add(user)
        db.session.commit()

        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# -------------------------
# INIT DB (FUNCIONA NO RENDER)
# -------------------------

with app.app_context():
    db.create_all()

# -------------------------
# RUN LOCAL
# -------------------------

if __name__ == '__main__':
    app.run(debug=True)

#-------------------
# Busca filmes
# ---------------

def search_tmdb(query):
    url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={query}"
    return requests.get(url).json().get('results', [])

@app.route('/search', methods=['GET','POST'])
@login_required
def search():
    results = []

    if request.method == 'POST':
        results = search_tmdb(request.form['query'])

    return render_template('search.html', results=results)

@app.route('/add_movie', methods=['POST'])
@login_required
def add_movie():
    movie = Movie(
        title=request.form['title'],
        poster=request.form['poster']
    )

    db.session.add(movie)
    db.session.commit()

    return redirect('/')
