from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func
from sqlalchemy.orm import joinedload
import requests, os

app = Flask(__name__)
app.secret_key = 'supersecret'

# ✅ Banco
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
    trailer = db.Column(db.String(200))  # 🔥 cache


class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), index=True)
    movie_id = db.Column(db.Integer, db.ForeignKey('movie.id'), index=True)

    score = db.Column(db.Integer)
    comment = db.Column(db.String(300))

    user = db.relationship('User')


class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, index=True)
    movie_id = db.Column(db.Integer, index=True)


# -------------------------
# LOGIN
# -------------------------

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# -------------------------
# TRAILER (COM CACHE)
# -------------------------

def get_trailer(movie):
    # 🔥 se já tem trailer salvo → não chama API
    if movie.trailer:
        return movie.trailer

    url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={movie.title}"
    data = requests.get(url).json()

    if data.get('results'):
        movie_id = data['results'][0]['id']

        videos_url = f"https://api.themoviedb.org/3/movie/{movie_id}/videos?api_key={TMDB_API_KEY}"
        videos = requests.get(videos_url).json()

        for v in videos.get('results', []):
            if v['type'] == 'Trailer' and v['site'] == 'YouTube':
                movie.trailer = f"https://www.youtube.com/embed/{v['key']}"
                db.session.commit()
                return movie.trailer

    return None


# -------------------------
# HOME (OTIMIZADA)
# -------------------------

@app.route('/')
@login_required
def index():

    # 🔥 query otimizada
    movies = db.session.query(
        Movie,
        func.avg(Rating.score).label('avg')
    ).outerjoin(Rating).group_by(Movie.id).order_by(func.avg(Rating.score).desc()).all()

    # 🔥 evita N+1
    ratings = Rating.query.options(joinedload(Rating.user)).all()

    ratings_by_movie = {}
    for r in ratings:
        ratings_by_movie.setdefault(r.movie_id, []).append(r)

    # 🔥 trailer com cache
    trailers = {}
    for m, _ in movies:
        trailers[m.id] = get_trailer(m)

    # 🔥 favoritos
    fav_ids = {
        f.movie_id for f in Favorite.query.filter_by(user_id=current_user.id).all()
    }

    # 🔥 gráfico
    labels = [m.title for m, _ in movies]
    values = [round(avg or 0, 2) for _, avg in movies]

    return render_template(
        'index.html',
        movies=movies,
        ratings_by_movie=ratings_by_movie,
        trailers=trailers,
        favorites=fav_ids,
        labels=labels,
        values=values
    )


# -------------------------
# LOGIN / REGISTER
# -------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()

        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('index'))

        flash('Erro no login')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
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
# SEARCH
# -------------------------

def search_tmdb(query):
    url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={query}"
    return requests.get(url).json().get('results', [])


@app.route('/search', methods=['GET', 'POST'])
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

    return redirect(url_for('index'))


# -------------------------
# RATE
# -------------------------

@app.route('/rate/<int:id>', methods=['POST'])
@login_required
def rate(id):

    score = int(request.form['score'])
    comment = request.form.get('comment')

    existing = Rating.query.filter_by(
        user_id=current_user.id,
        movie_id=id
    ).first()

    if existing:
        existing.score = score
        existing.comment = comment
    else:
        db.session.add(Rating(
            user_id=current_user.id,
            movie_id=id,
            score=score,
            comment=comment
        ))

    db.session.commit()

    flash("✅ Avaliação enviada com sucesso!")
    return redirect(url_for('index'))


# -------------------------
# FAVORITE
# -------------------------

@app.route('/favorite/<int:id>')
@login_required
def favorite(id):
    existing = Favorite.query.filter_by(
        user_id=current_user.id,
        movie_id=id
    ).first()

    if existing:
        db.session.delete(existing)
    else:
        db.session.add(Favorite(user_id=current_user.id, movie_id=id))

    db.session.commit()
    return redirect(url_for('index'))


# -------------------------
# FAVORITOS PAGE
# -------------------------

@app.route('/favorites')
@login_required
def favorites_page():
    fav_ids = [f.movie_id for f in Favorite.query.filter_by(user_id=current_user.id).all()]
    movies = Movie.query.filter(Movie.id.in_(fav_ids)).all()

    return render_template('favorites.html', movies=movies)


# -------------------------
# RECOMENDAÇÕES
# -------------------------

@app.route('/recommendations')
@login_required
def recommendations():

    user_ratings = Rating.query.filter_by(user_id=current_user.id).all()

    high_rated_ids = [r.movie_id for r in user_ratings if r.score >= 8]

    if not high_rated_ids:
        return render_template('recommendations.html', movies=[])

    liked_movies = Movie.query.filter(Movie.id.in_(high_rated_ids)).all()

    recommendations = []

    for movie in liked_movies:
        results = search_tmdb(movie.title)
        recommendations.extend(results[:2])

    return render_template('recommendations.html', movies=recommendations)


# -------------------------
# INIT DB
# -------------------------

with app.app_context():
    db.create_all()
    


# -------------------------
# RUN
# -------------------------

if __name__ == '__main__':
    app.run(debug=True)
