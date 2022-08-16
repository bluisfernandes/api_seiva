from logging import exception
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
    datetime = db.Column(db.DateTime, nullable=False, default=datetime.now())
    description = db.Column(db.String(60), nullable=False)
    area = db.Column(db.String(60), nullable=False)
    id_ref = db.Column(db.Integer, nullable=True)

User_pydantic = sqlalchemy_to_pydantic(User)
Pesquisa_pydantic = sqlalchemy_to_pydantic(Pesquisa)
Categoria_pydantic = sqlalchemy_to_pydantic(Categoria)
Logs_pydantic = sqlalchemy_to_pydantic(Logs)


class QueryUser(BaseModel):
    id: Optional[int]
    username: Optional[str]
    group: Optional[str]
    email: Optional[str]

class NewUser(BaseModel):
    username: str
    password: str
    group: Optional[str]
    email: str

class UserResponse(User_pydantic):
    class Config:
        fields = {'password': {'exclude': True}}

class Users(BaseModel):
    users: list[UserResponse]
    count: int

class Logss(BaseModel):
    logs: list[Logs_pydantic]
    count: int

class Pesquisas(BaseModel):
    pesquisa: list[Pesquisa_pydantic]
    count: int

class RequestPesquisa(BaseModel):
    pesquisa: str

class Categorias(BaseModel):
    categoria: list[Categoria_pydantic]
    count: int

class RequestCategoria(BaseModel):
    categoria: str


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
def busca_pessoa(id):
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
    except IntegrityError as e:
        db.session.rollback()
        print(f"ERROR! {e}")
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
    create_log(table, user.id, f'deleted from db: {table.__tablename__} id:{id}')
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
def deleta_pessoa(id):
    '''Delete user by id.'''
    user = User.query.filter_by(id=id).first()
    if not user:
        return {'message': 'User not found'}, 404
    delete_in_db(User, id)
    return jsonify({})


@app.get('/logs')
@spec.validate(resp=Response(HTTP_200=Logss))
# @spec.validate(query=QueryUser)
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


@app.get('/pesquisas')
@spec.validate(resp=Response(HTTP_200=Pesquisas))
def find_pesquisas():
    '''Return a list os pesquisas'''
    pesquisas = Pesquisa.query.all()
    return jsonify(
            Pesquisas(
                pesquisa= pesquisas,
                count= len(pesquisas)
            ).dict()
    ) , 200

@app.post('/pesquisa')
@spec.validate(body=Request(RequestPesquisa), resp=Response(HTTP_200=Pesquisa_pydantic))
def insert_pesquisa():
    '''Insert a new log on database'''
    pesquisa = request.context.body.dict(exclude_none=True)
    new_data = add_in_db(Pesquisa, pesquisa)
    return jsonify(Pesquisa_pydantic(**new_data.__dict__).dict()), 201

@app.get('/categorias')
@spec.validate(resp=Response(HTTP_200=Categorias))
def find_gategorias():
    '''Return a list of categorias'''
    categorias = Categoria.query.all()
    return jsonify(
            Categorias(
                categoria= categorias,
                count= len(categorias)
            ).dict()
    ) , 200

@app.post('/categoria')
@spec.validate(body=Request(RequestCategoria), resp=Response(HTTP_200=Categoria_pydantic))
def insert_categoria():
    '''Insert a new categoria on database'''
    categoria = request.context.body.dict(exclude_none=True)
    new_data = add_in_db(Categoria, categoria)
    return jsonify(Categoria_pydantic(**new_data.__dict__).dict()), 201
