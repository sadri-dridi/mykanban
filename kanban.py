import os

from flask import Flask
from flask import redirect, g
from flask import render_template
from flask import request, session
from flask import Flask, render_template, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from flask_login import LoginManager, UserMixin, current_user, login_user, login_required, logout_user, login_manager
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship, backref, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

project_dir = os.path.dirname(os.path.abspath(__file__))
database_file = "sqlite:///{}".format(os.path.join(project_dir, "taskdb.db"))

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = database_file
app.secret_key = "very secret"
login = LoginManager()
login.init_app(app)
login.login_view = 'login'
db = SQLAlchemy(app)

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False, unique=True)
    password = Column(String, nullable=False)  # Make sure to hash passwords before storing

    # Relationship to lists (a user has many lists)
    lists = relationship('TodoList', backref='user', lazy='dynamic')

class TodoList(db.Model):
    __tablename__ = 'todolist'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    # If there are any other attributes for a list, define them here

    # Relationship to items (this list contains many items)
    items = relationship('Item', backref='todolist', lazy='dynamic', cascade='all, delete, delete-orphan')

class Item(db.Model):
    __tablename__ = 'item'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    completed = Column(Boolean, default=False)  # True if the item is completed, False otherwise
    parent_id = Column(Integer, ForeignKey('item.id'))  # For sub-items
    list_id = Column(Integer, ForeignKey('todolist.id'), nullable=False)  # Each item belongs to a list

    # Relationship for sub-items
    children = relationship('Item',
                            backref=backref('parent', remote_side=[id]),
                            lazy='dynamic')

    # Method to add a sub-item
    def add_sub_item(self, name):
        sub_item = Item(name=name, list_id=self.list_id, parent_id=self.id)
        db.session.add(sub_item)
        return sub_item

    # Method to get all sub-items
    def get_sub_items(self):
        return Item.query.filter_by(parent_id=self.id).all()
    
# Create db
db.create_all()
db.session.commit()
login = LoginManager()
login.init_app(app)
login.login_view = 'login'

@login.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hashed_password = generate_password_hash(request.form['password'], method='sha256')
        new_user = User(username=request.form['username'], password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('home'))
        return 'Invalid username or password'
    return render_template('login.html')

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def home():
    return render_template('home.html', name=current_user.username, lists=current_user.lists)

@app.route('/list/new', methods=['POST'])
@login_required
def new_list():
    new_list = TodoList(name=request.form['name'], user=current_user)
    db.session.add(new_list)
    db.session.commit()
    return redirect(url_for('home'))

@app.route('/list/<list_id>')
@login_required
def view_list(list_id):
    todolist = TodoList.query.filter_by(id=list_id, user_id=current_user.id).first()
    if todolist is None:
        return 'No list found', 404
    
    # Prepare the tasks, ensuring they are structured hierarchically.
    # This may involve adjusting your query or organizing them before sending to the template.
    tasks = todolist.items.order_by(Item.id).all()  # Adjust as necessary for your setup

    return render_template('list.html', todolist=todolist, tasks=tasks)

@app.route('/item/new', methods=['POST'])
@login_required
def new_item():
    list_id = request.form['list_id']
    todolist = TodoList.query.filter_by(id=list_id, user_id=current_user.id).first()
    if todolist is None:
        return 'No list found', 404

    new_item = Item(name=request.form['name'], todolist=todolist)
    db.session.add(new_item)
    db.session.commit()

    # Redirect to the current page to refresh the task list
    return redirect(request.referrer)  # This redirects back to the current page


@app.route('/list/<list_id>/update', methods=['POST'])
@login_required
def update_list(list_id):
    # Fetch the list from the database
    todolist = TodoList.query.filter_by(id=list_id, user_id=current_user.id).first()
    if todolist is None:
        return 'No list found', 404

    # Update the list name from the form input
    todolist.name = request.form['name']
    db.session.commit()
    return redirect(url_for('home'))

@app.route('/list/<list_id>/delete', methods=['POST'])
@login_required
def delete_list(list_id):
    # Fetch and delete the list from the database
    todolist = TodoList.query.filter_by(id=list_id, user_id=current_user.id).first()
    if todolist is None:
        return 'No list found', 404

    # SQLAlchemy will delete all items associated with this list because of the cascade option.
    db.session.delete(todolist)
    db.session.commit()
    return redirect(url_for('home'))

@app.route('/item/<item_id>/update', methods=['POST'])
@login_required
def update_item(item_id):
    # Fetch the item from the database
    item = Item.query.filter_by(id=item_id).first()
    if item is None or item.todolist.user_id != current_user.id:
        return 'No item found', 404

    # Update item details from the form input
    item.name = request.form['name']
    # Here you can add more fields to be updated like `completed` status
    db.session.commit()
    return redirect(url_for('view_list', list_id=item.todolist.id))

@app.route('/item/<item_id>/delete', methods=['POST'])
@login_required
def delete_item(item_id):
    # Fetch and delete the item from the database
    item = Item.query.filter_by(id=item_id).first()
    if item is None or item.todolist.user_id != current_user.id:
        return 'No item found', 404

    db.session.delete(item)
    db.session.commit()
    return redirect(url_for('view_list', list_id=item.todolist.id))

@app.route('/item/<int:item_id>/add_sub_item', methods=['POST'])
@login_required
def add_sub_item(item_id):
    parent_item = Item.query.get(item_id)
    if not parent_item:
        return 'No item found', 404

    name = request.form['name']
    sub_item = parent_item.add_sub_item(name)
    db.session.commit()

    # Redirect or return response as needed
    return redirect(url_for('view_list', list_id=parent_item.list_id))

@app.route('/item/<item_id>/toggle', methods=['POST'])
@login_required
def toggle_item(item_id):
    # Fetch the item from the database
    item = Item.query.filter_by(id=item_id).first()
    if item is None or item.todolist.user_id != current_user.id:
        return 'No item found', 404

    # Toggle the completion status
    item.completed = not item.completed
    db.session.commit()
    return redirect(url_for('view_list', list_id=item.todolist.id))


if __name__ == "__main__":
    app.run(debug=True)
