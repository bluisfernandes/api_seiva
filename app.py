from flask import Flask, jsonify, request, url_for
from flask_pydantic_spec import FlaskPydanticSpec, Response, Request
from pydantic_sqlalchemy import sqlalchemy_to_pydantic
from pydantic import BaseModel, Field
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
import os
import secrets
from dotenv import load_dotenv

from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError

from typing import Optional


load_dotenv()

# Make sure database URI is set
if not os.environ.get('DATABASE_USER_URI'):
    raise RuntimeError("DATABASE_USER_URI not set")

app = Flask(__name__)
spec = FlaskPydanticSpec('FlAsK', title='Estudo API')
spec.register(app)

app.secret_key = os.getenv('SECRET_KEY', secrets.token_urlsafe())
 # Custom filter

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_USER_URI')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    password = db.Column(db.String(60), nullable=False)
    group = db.Column(db.String(10), nullable=False, default='user')
    email = db.Column(db.String(40), nullable=False)

class Pesquisa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pesquisa = db.Column(db.String(40), nullable=False, unique=True)

class Categoria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    categoria = db.Column(db.String(20), nullable=False, unique=True)

class Logs(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    datetime = db.Column(db.String(20), nullable=False)
    job = db.Column(db.String(60), nullable=False)
    area = db.Column(db.String(60), nullable=False)

User_pydantic = sqlalchemy_to_pydantic(User)
Pesquisa_pydantic = sqlalchemy_to_pydantic(Pesquisa)
Categoria_pydantic = sqlalchemy_to_pydantic(Categoria)
Logs_pydantic = sqlalchemy_to_pydantic(Logs)


class QueryUser(BaseModel):
    id: Optional[int]
    username: Optional[str]
    group: Optional[str]
    email: Optional[str]

class Users(BaseModel):
    users: list[User_pydantic]
    count: int


migrate = Migrate(app, db)

@app.get('/')
def index():
    return {'homepage':'/', 'API version': 'v1', 'swagger': url_for('doc_page_swagger')}


@app.get('/users')
@spec.validate(query=QueryUser, resp=Response(HTTP_200=Users))
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
    ) 

@app.get('/user/<int:id>')
@spec.validate(resp=Response(HTTP_200=Users))
def busca_pessoa(id):
    '''Retorn user by given id'''
    try:
        user = User.query.filter_by(id = id).all()
    except IndexError:
        return {'message': 'User not found'}, 404
    print(user[0])
    list_users = user
    return jsonify(
            Users(
                users= list_users,
                count= len(list_users)
            ).dict()
    ) 


@app.post('/pessoas')
@spec.validate(body=Request(User_pydantic), resp=Response(HTTP_201=User_pydantic))
def insere_pessoa():
    '''Insere uma pessoa no banco de dados'''
    person = request.context.body.dict()
    database.insert(person)
    return person


@app.put('/pessoas/<int:id>')
@spec.validate(body=Request(User_pydantic), resp=Response(HTTP_200=User_pydantic))
def altera_pessoa(id):
    '''Altera a pessoa pelo numero do id.'''
    body = request.context.body.dict()
    database.update(body, Query().id == id)
    return jsonify(body)


@app.delete('/pessoas/<int:id>')
@spec.validate(resp=Response('HTTP_204'))
def deleta_pessoa(id):
    '''Deleta a pessoa pelo numero do id.'''
    database.remove(Query().id == id)
    return jsonify({})

