# Import project dependencies
from flask import Flask, render_template, flash, redirect, url_for, session, logging, request
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from passlib.hash import sha256_crypt

from functools import wraps
import datetime
import uuid

from registerform import RegisterForm
from articleform import ArticleForm


# Creating an instance of the Flask class
# The first argument is the name of the module or package
# This is needed so that Flask knows where to look for templates and static assets
app = Flask(__name__)
app.secret_key = '4rticl1os3cr3t'

# Use a service account
cred = credentials.Certificate('utils/articlio-flask-app-bfd09e671a1a.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

# Firestore Config
fs_user_collection = db.collection('users')
fs_articles_collection = db.collection('articles')


# Define routes

# Render home route
@app.route('/')
def home():
    title = 'Welcome'
    return render_template('home.html', title=title)


# Render about page route
@app.route('/about')
def about():
    title = 'About'
    return render_template('about.html', title=title)


# Display all articles route
@app.route('/articles')
def articles():
    title = 'Articles'
    db_articles = fs_articles_collection.get()
    if db_articles is None:
        msg = 'No articles found'
        return render_template('articles.html', msg=msg, title=title)
    else:
        return render_template('articles.html', articles=db_articles, title=title)


# Display single article Route
@app.route('/articles/<article_id>/')
def article(article_id):
    title = 'View Article'
    db_articles = fs_articles_collection.get()
    for db_article in db_articles:
        if db_article.id == article_id:
            return render_template('article.html', article=db_article, title=title)
    return render_template('article.html', title=title)


# Submit Register Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    title = 'Register'
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
    return render_template('register.html', form=form, title=title)


# Submit login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    title = 'Login'
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
                    session['name'] = user_doc.get("name")
                    session['userid'] = user_doc.id
                    # Display flash message
                    flash('You have successfully logged in!', 'success')
                    # Redirect to the home page
                    return redirect(url_for('dashboard'))
                else:
                    # Display flash message
                    flash('Invalid Password', 'danger')
                    return render_template('login.html', title=title)
            else:
                continue

        # Check if username matched any username in collection
        if db_username == 'null':
            # Display flash message
            flash('Username not found', 'danger')
            return render_template('login.html', title=title)

    return render_template('login.html', title=title)


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
@app.route('/users/dashboard')
@is_logged_in
def dashboard():
    title = 'My Dashboard'
    user_articles = []
    db_articles = fs_articles_collection.get()
    # Verify if the variable is set
    if db_articles is None:
        msg = 'No articles found'
        return render_template('dashboard.html', msg=msg, title=title)
    else:
        for db_article in db_articles:
            # Get only the articles that belong to the current user session
            if db_article.get("user_id") == session['userid']:
                user_articles.append(db_article)
        return render_template('dashboard.html', articles=user_articles, title=title)


# Add article route
@app.route('/users/articles', methods=['GET', 'POST'])
@is_logged_in
def add_article():
    title = 'Add Article'
    form = ArticleForm(request.form)
    if request.method == 'POST' and form.validate():
        title = form.title.data
        body = form.body.data

        # Create a new document with UUID in the articles collection
        new_article = fs_articles_collection.document(str(uuid.uuid4()))
        # Create a new article document and store it to the articles collection
        new_article.set({
            'user_id': session['userid'],
            'article_id': new_article.id,
            'title': title,
            'body': body,
            'author': session['name'],
            'posted_date': datetime.datetime.utcnow()
        })

        # Display flash message
        flash('Your article has been successfully posted!', 'success')
        # Redirect to the dashboard page
        return redirect(url_for('dashboard'))
    return render_template('add_article.html', form=form, title=title)


# Edit article route
@app.route('/users/articles/<string:article_id>/', methods=['GET', 'POST', 'DELETE'])
@is_logged_in
def edit_article(article_id):
    title = 'Edit Article'
    form = ArticleForm(request.form)

    # Get the article correponding to the passed article_id and fill the fields with the title and body
    db_article = fs_articles_collection.document(article_id).get()
    form.title.data = db_article.get("title")
    form.body.data = db_article.get("body")

    if request.method == 'POST' and form.validate():
        title = request.form['title']
        body = request.form['body']

        # Update the article document and store it to the articles collection
        db_article = fs_articles_collection.document(article_id)
        db_article.update({
            'title': title,
            'body': body
        })

        # Display flash message
        flash('Your article has been updated!', 'success')
        # Redirect to the dashboard page
        return redirect(url_for('dashboard'))
    elif request.method == 'DELETE':
        fs_articles_collection.document(article_id).delete()
        # Display flash message
        flash('Article has been deleted', 'success')
        return redirect(url_for('dashboard'))
    return render_template('edit_article.html', form=form, title=title)


if __name__ == '__main__':
    """ 
    Here since the application's module is being run directly, the global(module-level) variable __name__
    is set to the string "__main__".

    But if app.py was to be imported into another module, the __name__ variable would not be equal to
    "__main__", but instead it would be equal to "app" (since the name of this module is app.py).
    Therefore, the if condition here would not be satisfied and the code inside it would not run.

    """
    app.run(debug=True)
