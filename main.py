from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from flask_gravatar import Gravatar
import os
# Import your forms from the forms.py
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_KEY')
ckeditor = CKEditor(app)
Bootstrap5(app)

# TODO: Configure Flask-Login
login_manager=LoginManager()
login_manager.init_app(app)

gravatar=Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

@login_manager.user_loader #Tells Flask-Login: Use the function below whenever you need to load a logged-in user.
def load_user(user_id): #lask-Login automatically passes the logged-in user's ID to this function
    return db.get_or_404(User,user_id) #Looks for the user with that ID in the User table. If found returns the User object else 404 error.


def admin_only(f):
    @wraps(f)
    def decorator_function(*args,**kwargs):
        if current_user.id !=1:
            return abort(403)
        return f(*args,**kwargs)
    return decorator_function

# CREATE DATABASE
class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DB_URI", "sqlite:///posts.db")
db = SQLAlchemy(model_class=Base)
db.init_app(app)


# TODO: Create a User table for all your registered users. 
#Create a User class that is a database table and has login features
class User(UserMixin,db.Model): # UserMixin Adds ready-made login features for Flask-Login, such asis_authenticated, is_active, is_anonymous, get_id().db.Model tells SQLAlchemy that this class represents a database table.
    __tablename__="users" # specifies the name of the table in the database, Here, the table will be created as users.
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    email:Mapped[str]=mapped_column(String(200),unique=True)
    password:Mapped[str]=mapped_column(String(150))
    name:Mapped[str]=mapped_column(String(120))
    #This will act like a List of BlogPost objects attached to each User. 
    #The "author" refers to the author property in the BlogPost class.
    # Creates a relationship between the User and BlogPost tables.
    # One User can write many BlogPosts.
    # SQLAlchemy creates a new property called "posts" inside every User object.
    # So we can access all blogs of a user by writing: user.posts
    posts=relationship("BlogPost",back_populates="author")
    comments=relationship("Comment",back_populates="comment_author")


# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Create Foreign Key, "users.id" the users refers to the tablename of User.
    author_id:Mapped[int]=mapped_column(Integer,db.ForeignKey("users.id"))
    # Create reference to the User object. The "posts" refers to the posts property in the User class.
   
    author=relationship("User",back_populates="posts")
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    comments=relationship("Comment",back_populates="parent_post")



class Comment(db.Model):
    __tablename__="comments"
    id: Mapped[int]=mapped_column(Integer,primary_key=True) 
    author_id:Mapped[int]=mapped_column(Integer,db.ForeignKey("users.id"))
    comment_author=relationship("User",back_populates="comments")
    post_id:Mapped[int]=mapped_column(Integer,db.ForeignKey("blog_posts.id"))
    parent_post=relationship("BlogPost",back_populates="comments")
    text:Mapped[str]=mapped_column(Text,nullable=False)

with app.app_context():
    db.create_all()


# TODO: Use Werkzeug to hash the user's password when creating a new user.
@app.route('/register', methods=["GET","POST"])
def register():
    form=RegisterForm()
    if form.validate_on_submit():
        # form.password.data gets the validated password from the WTForms PasswordField.
        # Since validate_on_submit() has already checked the form, it's better than request.form.get(). 
        hash_and_salted_password=generate_password_hash(form.password.data,method='pbkdf2:sha256',salt_length=7)
        email=form.email.data
        result=db.session.execute(db.select(User).where(User.email==email))
        user=result.scalar()
        if user:
            flash("You've already registered, login instead!")
            return redirect(url_for('login'))
        new_user=User(name=form.name.data,password=hash_and_salted_password,email=email)
        db.session.add(new_user)
        db.session.commit()
        #This line will authenticate the user with Flask-Login
        login_user(new_user)
        return redirect(url_for('get_all_posts'))
    return render_template("register.html",form=form, current_user=current_user)


# TODO: Retrieve a user from the database based on their email. 
@app.route('/login', methods=["GET","POST"])
def login():
    form=LoginForm()
    if form.validate_on_submit():
        email=form.email.data
        password=form.password.data
        result=db.session.execute(db.select(User).where(User.email==email))
        user=result.scalar()
        if not user:
            flash("your email does not exist, please try different one! ")
            redirect(url_for('login'))
        elif not check_password_hash(user.password,password):
            flash("password is incorrect, please try again!")
            return redirect(url_for('login'))
        else:
            login_user(user)
            return redirect(url_for('get_all_posts'))
    return render_template("login.html",form=form, current_user=current_user)


@app.route('/logout')
def logout():
    print("Before:", current_user.is_authenticated)
    logout_user()
    print("After:", current_user.is_authenticated)
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    print("Home:", current_user.is_authenticated)
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts,current_user=current_user)


# TODO: Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>",methods=["GET","POST"])
def show_post(post_id):
    requested_post = db.get_or_404(BlogPost, post_id)
    comment_form=CommentForm()
    if comment_form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for('login'))
        new_comment=Comment(text=comment_form.comment_text.data,comment_author=current_user,parent_post=requested_post )
        db.session.add(new_comment)
        db.session.commit()
    return render_template("post.html", post=requested_post,form=comment_form,current_user=current_user)


# TODO: Use a decorator so only an admin user can create a new post
@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


# TODO: Use a decorator so only an admin user can edit a post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


# TODO: Use a decorator so only an admin user can delete a post
@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


if __name__ == "__main__":
    app.run(debug=False, port=5002)
