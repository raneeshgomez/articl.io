# Import project dependencies
from flask import Flask, render_template, flash, redirect, url_for, session, logging, request
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from passlib.hash import sha256_crypt

from functools import wraps
import datetime
import uuid
import os

from data import Articles
from registerform import RegisterForm


# Creating an instance of the Flask class
# The first argument is the name of the module or package
# This is needed so that Flask knows where to look for templates and static assets
app = Flask(__name__)
app.secret_key = os.urandom(32)

# Use a service account
cred = credentials.Certificate('utils/articlio-flask-app-bfd09e671a1a.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

# Firestore Config
fs_user_collection = db.collection('users')
fs_articles_collection = db.collection('articles')

# Assign Articles function to variable
Articles = Articles()


# Define routes

# Render home route
@app.route('/')
def home():
    return render_template('home.html')


# Render about page route
@app.route('/about')
def about():
    return render_template('about.html')


# Display all articles route
@app.route('/articles')
def articles():
    return render_template('articles.html', articles=Articles)


# Display single article Route
@app.route('/article/<article_id>/')
def article(article_id):
    return render_template('article.html', id=article_id)


# Submit Register Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm(request.form)
    if request.method == 'POST' and form.validate():
        name = form.name.data
        email = form.email.data
        username = form.username.data
        password = sha256_crypt.encrypt(str(form.password.data))

        # Query collection
        user_docs = fs_user_collection.get()
        for user_doc in user_docs:
            # Check if username is already taken
            if user_doc.get("username") == username:
                flash('User with this username already exists! Please choose another', 'danger')
                return redirect(url_for('register'))

        # Create a new document with UUID in the users collection
        new_user = fs_user_collection.document(str(uuid.uuid4()))
        # Create a new user and store it to the users collection
        new_user.set({
            'email': email,
            'name': name,
            'username': username,
            'password': password,
            'register_date': datetime.datetime.utcnow()
        })

        # Display flash message
        flash('You have successfully been registered. Have fun!', 'success')
        # Redirect to the login page
        return redirect(url_for('login'))
    return render_template('register.html', form=form)


# Submit login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Get form fields
        username = request.form['username']
        password_candidate = request.form['password']

        db_username = 'null'

        # Iterate through user documents retrieved from the database
        user_docs = fs_user_collection.get()
        for user_doc in user_docs:
            # Compare usernames
            if user_doc.get("username") == username:
                db_username = user_doc.get("username")
                # Get stored hashed password
                user_pass = user_doc.get("password")
                # Compare passwords
                if sha256_crypt.verify(password_candidate, user_pass):
                    app.logger.info('Passwords matched! Login successful')
                    # Initialize session
                    session['logged_in'] = True
                    session['username'] = db_username
                    # Display flash message
                    flash('You have successfully logged in!', 'success')
                    # Redirect to the home page
                    return redirect(url_for('dashboard'))
                else:
                    # Display flash message
                    flash('Invalid Password', 'danger')
                    return render_template('login.html')
            else:
                continue

        # Check if username matched any username in collection
        if db_username == 'null':
            # Display flash message
            flash('Username not found', 'danger')
            return render_template('login.html')

    return render_template('login.html')


# Check if user is logged in
def is_logged_in(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('Unauthorized! Please log in', 'danger')
            return redirect(url_for('login'))

    return wrapped


# Logout route
@app.route('/logout')
@is_logged_in
def logout():
    session.clear()
    flash('You are now logged out', 'success')
    return redirect('login')


# Render dashboard route
@app.route('/dashboard')
@is_logged_in
def dashboard():
    return render_template('dashboard.html')


if __name__ == '__main__':
    """ 
    Here since the application's module is being run directly, the global(module-level) variable __name__
    is set to the string "__main__".

    But if app.py was to be imported into another module, the __name__ variable would not be equal to
    "__main__", but instead it would be equal to "app" (since the name of this module is app.py).
    Therefore, the if condition here would not be satisfied and the code inside it would not run.

    """
    app.run(debug=True)
