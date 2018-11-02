"""Movie Ratings."""

from jinja2 import StrictUndefined
from flask import (Flask, render_template, redirect, request, flash, session)
from flask_debugtoolbar import DebugToolbarExtension
from sqlalchemy.orm.exc import NoResultFound
from model import User, Rating, Movie, connect_to_db, db
from pprint import pprint


app = Flask(__name__)

# Required to use Flask sessions and the debug toolbar
app.secret_key = "ABC"

# Normally, if you use an undefined variable in Jinja2, it fails
# silently. This is horrible. Fix this so that, instead, it raises an
# error.
app.jinja_env.undefined = StrictUndefined


# this is the route to the homepage
@app.route('/')
def index():
    """Homepage."""

    return render_template("homepage.html")


@app.route("/register", methods=["GET"])
def register_form():
    """Display registration form."""

    return render_template("register.html")


@app.route("/register", methods=["POST"])
def register_process():
    """Process user registration and send to homepage."""

    # Get form variables
    email = request.form['email']
    password = request.form['password']
    age = int(request.form['age'])
    zipcode = request.form['zipcode']

    # check to see if user is in database,
    # if not, add new user
    # otherwise tell them a user already exists
    try:
        verify_email = User.query.filter(User.email == email).one()
        if verify_email:
            flash('A user with that email already exists!')
            return redirect("/register")
    except NoResultFound:
        new_user = User(email=email, password=password, age=age, zipcode=zipcode)
        db.session.add(new_user)
        db.session.commit()
        flash(f"User {email} added.")
        return redirect("/")


@app.route("/login", methods=["GET"])
def show_login():
    """Shows user login form"""

    return render_template("login.html")


@app.route("/login", methods=["POST"])
def verify_login():
    """Verifies user email is in database and password matches"""

    # gets email and password from form and verifies user in db
    email = request.form['email']
    password = request.form['password']
    user = User.query.filter(User.email == email).first()

    # if they are in db, add session to login, else flash message
    if user and (user.password == password):
        session['user_id'] = user.user_id
        flash('You are logged in... Prepare to be judged!')
        return redirect("/user_info?user_id=" + str(user.user_id))
    else:
        flash('Invalid email or password.')
        return redirect("/login")


@app.route("/logout")
def logout():
    """logs the current user out"""

    # removes session from browser to log out
    del session['user_id']

    flash("You are no longer being judged...")
    return redirect("/")


# queries the users from the User object and lists all users
@app.route("/users")
def user_list():
    """show list of users."""

    # this is the query using the user object
    users = User.query.all()
    return render_template("user_list.html", users=users)


# user info page gets user id from linked page
@app.route("/users/<int:user_id>")
def show_user(user_id):
    """shows individual user info"""

    # queries the user objects to find the user with matching id and grabs attributes
    user = User.query.options(db.joinedload('ratings').joinedload('movie')).get(user_id)

    return render_template("user_info.html", user=user)


# lists the movies by query
@app.route("/movies")
def movie_list():
    """Show list of movies in alphabetical order."""

    # query movies objects and lists them by title
    movies = Movie.query.order_by(Movie.title).all()

    return render_template("movie_list.html", movies=movies)


# displays individual movie information based on movie_id
@app.route("/movies/<int:movie_id>", methods=["GET"])
def show_movie(movie_id):
    """Show info about movie.

    If a user is logged in, let them add/edit a rating.
    """

    movie = Movie.query.get(movie_id)
    user_id = session.get('user_id')

    if user_id:
        user_rating = Rating.query.filter_by(
            movie_id=movie_id, user_id=user_id).first()
    else:
        user_rating = None

    # Get average rating of movie
    rating_scores = [r.score for r in movie.ratings]
    avg_rating = float(sum(rating_scores)) / len(rating_scores)

    prediction = None

    # Prediction code: only predict if the user hasn't rated it.
    if (not user_rating) and user_id:
        user = User.query.get(user_id)
        if user:
            prediction = user.predict_rating(movie)

    # Either use the prediction or their real rating
    if prediction:
        # User hasn't scored; use our prediction if we made one
        effective_rating = prediction

    elif user_rating:
        # User has already scored for real; use that
        effective_rating = user_rating.score

    else:
        # User hasn't scored, and we couldn't get a prediction
        effective_rating = None

    # Get the eye's rating, either by predicting or using real rating
    the_eye = User.query.filter_by(email="the-eye@of-judgment.com").one()
    eye_rating = Rating.query.filter_by(
        user_id=the_eye.user_id, movie_id=movie.movie_id).first()

    if eye_rating is None:
        eye_rating = the_eye.predict_rating(movie)

    else:
        eye_rating = eye_rating.score

    if eye_rating and effective_rating:
        difference = abs(eye_rating - effective_rating)

    else:
        # We couldn't get an eye rating, so we'll skip difference
        difference = None

    # Depending on how different we are from the Eye, choose a message
    BERATEMENT_MESSAGES = [
        "I suppose you don't have such bad taste after all.",
        "I regret every decision that I've ever made that has brought me" +
            " to listen to your opinion.",
        "Words fail me, as your taste in movies has clearly failed you.",
        "Did you watch this movie in an alternate universe where your taste doesn't suck?",
        "Words cannot express the awfulness of your taste."
    ]

    if difference:
        beratement = BERATEMENT_MESSAGES[int(difference)]

    else:
        beratement = None

    return render_template(
        "movie_details.html",
        movie=movie,
        user_rating=user_rating,
        average=avg_rating,
        prediction=prediction,
        eye_rating=eye_rating,
        difference=difference,
        beratement=beratement
        )


@app.route("/movies/<movie_id>", methods=["POST"])
def rate_movie(movie_id):
    """Get user info from form and add rating to database"""

    # get score from new user rating, find user in database,
    # and find if they rated the movie beore.
    score = request.form.get("score")
    user = User.query.filter(User.email == session['email']).one()
    new_rating = Rating.query.filter_by(user_id=user.user_id,
                                        movie_id=movie_id).first()

    # if user has rated movie, update score, if not, create new rating and add
    if bool(new_rating):
        new_rating.score = score
    else:
        new_rating = Rating(score=score,
                            movie_id=movie_id,
                            user_id=user.user_id)
        db.session.add(new_rating)

    db.session.commit()

    flash('You have judged this movie.')
    return redirect("/user_info?user_id=" + str(user.user_id))


if __name__ == "__main__":
    # We have to set debug=True here, since it has to be True at the
    # point that we invoke the DebugToolbarExtension
    app.debug = True
    # make sure templates, etc. are not cached in debug mode
    app.jinja_env.auto_reload = app.debug

    connect_to_db(app)

    # Use the DebugToolbar

    DebugToolbarExtension(app)

    app.run(port=5000, host='0.0.0.0')
