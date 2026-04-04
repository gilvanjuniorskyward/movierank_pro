
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import requests, os

app = Flask(__name__)
app.secret_key = 'supersecret'
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('postgresql://movierankdb_user:eJI0mwxiwO6PUzzUPNehWhSj90zSW96K@dpg-d789soh4tr6s73bve6b0-a/movierankdb', 'sqlite:///db.sqlite3')

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

TMDB_API_KEY = os.getenv('TMDB_API_KEY')

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

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
@login_required
def index():
    movies = db.session.query(Movie, db.func.avg(Rating.score).label('avg')).outerjoin(Rating).group_by(Movie.id).all()
    return render_template('index.html', movies=movies)

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect('/')
        flash('Erro no login')
    return render_template('login.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        user = User(username=request.form['username'],
                    password=generate_password_hash(request.form['password']))
        db.session.add(user)
        db.session.commit()
        return redirect('/login')
    return render_template('register.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect('/login')

if __name__ == '__main__':
    db.create_all()
    app.run(debug=True)
