from flask import Flask, jsonify, request, url_for
from flask_pydantic_spec import FlaskPydanticSpec, Response, Request
from pydantic_sqlalchemy import sqlalchemy_to_pydantic
from pydantic import BaseModel, Field
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
import os
import secrets
from dotenv import load_dotenv

from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError

from typing import Optional
import pymongo
import bson.json_util as json_util
import json


load_dotenv()

# Make sure database URI is set
if not os.environ.get('DATABASE_USER_URI'):
    raise RuntimeError("DATABASE_USER_URI not set")

app = Flask(__name__)
spec = FlaskPydanticSpec('FlAsK', title='API Seiva')
spec.register(app)

app.secret_key = os.getenv('SECRET_KEY', secrets.token_urlsafe())
 # Custom filter

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_USER_URI')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# Initialize mongo variables
mongodb_uri = os.getenv('MONGODB_URI')
mongodb_db = os.getenv('MONGODB_DB')
collection_log = os.getenv('MONGODB_COLLECTION_LOGS')


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    password = db.Column(db.String(60), nullable=False)
    group = db.Column(db.String(10), nullable=False, default='user')
    email = db.Column(db.String(40), nullable=False)

class Search(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    search = db.Column(db.String(40), nullable=False, unique=True)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(20), nullable=False, unique=True)

class Logs(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    datetime = db.Column(db.DateTime, nullable=False, default=datetime.now())
    description = db.Column(db.String(60), nullable=False)
    area = db.Column(db.String(60), nullable=False)
    id_ref = db.Column(db.Integer, nullable=True)

User_pydantic = sqlalchemy_to_pydantic(User)
Search_pydantic = sqlalchemy_to_pydantic(Search)
Category_pydantic = sqlalchemy_to_pydantic(Category)
Logs_pydantic = sqlalchemy_to_pydantic(Logs)


class QueryUser(BaseModel):
    id: Optional[int]
    username: Optional[str]
    group: Optional[str]
    email: Optional[str]
    password: Optional[str]

class NewUser(BaseModel):
    username: str
    password: str
    group: Optional[str]
    email: str

class UserResponse(User_pydantic):
    class Config:
        # fields = {'password': {'exclude': True}}
        pass

class Users(BaseModel):
    users: list[UserResponse]
    count: int

class Logss(BaseModel):
    logs: list[Logs_pydantic]
    count: int

class Searchs(BaseModel):
    searchs: list[Search_pydantic]
    count: int

class RequestSearch(BaseModel):
    search: str

class Categories(BaseModel):
    categories: list[Category_pydantic]
    count: int

class RequestCategory(BaseModel):
    category: str


migrate = Migrate(app, db)

@app.get('/')
def index():
    return {'homepage':'/', 'API version': 'v1', 'swagger': url_for('doc_page_swagger')}


@app.get('/users')
# @spec.validate(query=QueryUser, resp=Response(HTTP_200=Users))
@spec.validate(query=QueryUser)
def find_users():
    '''Return user list'''
    query = request.context.query
    users = User.query
    for k, v in query.dict(exclude_none=False).items():
        if v != None:
            users = users.filter(getattr(User, k)==v)
    list_users = users.all()
    return jsonify(
            Users(
                users= list_users,
                count= len(list_users)
            ).dict()
    ) , 200

@app.get('/user/<int:id>')
# @spec.validate(resp=Response(HTTP_200=UserResponse))
def find_user(id):
    '''Return user by given id'''
    user = User.query.filter_by(id = id).first()
    if not user:
        return {'message': 'User not found'}, 404
    return jsonify(UserResponse(**user.__dict__).dict()) 


def add_in_db(table, dict):
    user = table(**dict)
    db.session.add(user)
    try:
        db.session.commit()
        create_log(table, user.id, f'add in db: {user.__tablename__}:{user.id}')
        # to appear all features in __dict__:
        user.id
        return user
    except IntegrityError:
        db.session.rollback()
        return False

def update_in_db(table, id, dict):
    user = table.query.filter_by(id=id).first()
    for k, v in dict.items():
        setattr(user, k, v)
    db.session.commit()
    create_log(table, user.id, f'updated in db: {str(dict)}')
    # to appear all features in __dict__:
    user.id
    return user

def delete_in_db(table, id):
    user = table.query.filter_by(id=id).first()
    create_log(table, user.id, f'deleted from db: {table.__tablename__} id={id}')
    db.session.delete(user)
    db.session.commit()

def create_log(table, id, description):
    '''Create a new log.'''
    log = Logs(id_ref=id, description=description, area=table.__tablename__ )
    db.session.add(log)
    db.session.commit()


@app.post('/user')
@spec.validate(body=Request(NewUser))
def insert_user():
    '''Insert a new user on database'''
    new_user = request.context.body.dict(exclude_none=True)
    user = add_in_db(User, new_user)
    if not user:
        return {'message': 'User already in use'}, 404
    return jsonify(UserResponse(**user.__dict__).dict()), 201


@app.put('/user/<int:id>')
@spec.validate(body=Request(QueryUser))
def update_user(id):
    '''change user fields by user id.'''
    user = User.query.filter_by(id=id).first()
    if not user:
        return {'message': 'User not found'}, 404
    changes = request.context.body.dict(exclude_none=True)
    user = update_in_db(User, id, changes)
    return jsonify(UserResponse(**user.__dict__).dict()), 200


@app.delete('/user/<int:id>')
@spec.validate(resp=Response('HTTP_204'))
def delete_user(id):
    '''Delete user by id.'''
    user = User.query.filter_by(id=id).first()
    if not user:
        return {'message': 'User not found'}, 404
    delete_in_db(User, id)
    return jsonify({})


@app.get('/logs')
# @spec.validate(resp=Response(HTTP_200=Logss))
def find_logs():
    '''Return logs list'''
    # query = request.context.query
    logs = Logs.query.all()
    # for k, v in query.dict(exclude_none=False).items():
        # if v != None:
            # users = users.filter(getattr(User, k)==v)
    return jsonify(
            Logss(
                logs= logs,
                count= len(logs)
            ).dict()
    ) , 200


@app.post('/logs')
@spec.validate(body=Request(Logs_pydantic), resp=Response(HTTP_200=Logs_pydantic))
def insert_log():
    '''Insert a new log on database'''
    new_log = request.context.body.dict(exclude_none=True)
    log = add_in_db(Logs, new_log)
    return jsonify(Logs_pydantic(**log.__dict__).dict()), 201


@app.get('/search')
@spec.validate(resp=Response(HTTP_200=Searchs))
def find_searchs():
    '''Return a list of searchs'''
    searchs = Search.query.all()
    return jsonify(
            Searchs(
                searchs= searchs,
                count= len(searchs)
            ).dict()
    ) , 200

@app.post('/search')
@spec.validate(body=Request(RequestSearch), resp=Response(HTTP_200=Search_pydantic))
def insert_search():
    '''Insert a new search on database'''
    search = request.context.body.dict(exclude_none=True)
    new_data = add_in_db(Search, search)
    if not new_data:
        return {'message': 'Search already in use'}, 404
    return jsonify(Search_pydantic(**new_data.__dict__).dict()), 201


@app.delete('/search/<int:id>')
@spec.validate(resp=Response('HTTP_204'))
def delete_search(id):
    '''Delete Category by id.'''
    search = Search.query.filter_by(id=id).first()
    if not search:
        return {'message': 'Search not found'}, 404
    delete_in_db(Search, id)
    return jsonify({})


@app.get('/category')
@spec.validate(resp=Response(HTTP_200=Categories))
def find_gategories():
    '''Return a list of categories'''
    categories = Category.query.all()
    return jsonify(
            Categories(
                categories= categories,
                count= len(categories)
            ).dict()
    ) , 200

@app.post('/category')
@spec.validate(body=Request(RequestCategory), resp=Response(HTTP_200=Category_pydantic))
def insert_category():
    '''Insert a new category on database'''
    category = request.context.body.dict(exclude_none=True)
    new_data = add_in_db(Category, category)
    if not new_data:
        return {'message': 'Category already in use'}, 404
    return jsonify(Category_pydantic(**new_data.__dict__).dict()), 201

@app.delete('/category/<int:id>')
@spec.validate(resp=Response('HTTP_204'))
def delete_category(id):
    '''Delete Category by id.'''
    categ = Category.query.filter_by(id=id).first()
    if not categ:
        return {'message': 'Category not found'}, 404
    delete_in_db(Category, id)
    return jsonify({})

def apology(name, code):
    return {"message":name,"code":code}, code


def errorhandler(e):
    '''Handle error'''
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)

@app.get('/mongo/log')
@app.get('/mongo/log/<int:q>')
def find_mongo_log(q = 1000):
    '''Return mongo logs'''
    client = pymongo.MongoClient(mongodb_uri)
    db = client[mongodb_db]
    col = db[collection_log]

    result = col.find().sort('start_time', pymongo.DESCENDING)

    results=dict()
    for i in range(q):
        if result.alive:
            log = result.next()
            item = json.loads(json_util.dumps(log))
            # line = json.loads((item))
            results[i]=item
            # results[line["start_time"]["$date"]]=line
    return results
 

@app.get('/mongo/log/count')
def count_mongo_log():
    client = pymongo.MongoClient(mongodb_uri)
    db = client[mongodb_db]
    col = db[collection_log]

    count = col.count_documents({})
    return {"count": count}


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

if __name__ == '__main__':
    app.run(port=8000)
