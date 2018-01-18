# coding: utf-8
"""
这里仅用来定义数据结构以及初始化建表，不在web中使用，且不做migrate,
若需要中途修改表结构，记得在这里添加相应字段，然后自己动手修改数据库表
一些记录:
  1. 不要用mysql的enum,因为不好迁移, 且不在严格模式时，插入错误数据不报错
  2. 要不要Field使用`constraints=[SQL("default 0")]`设定数据库的默认值：
    2.1 peewee的default是在orm转换的时候用的，不作用在数据库中
    2.2 要设置数据库default: eg:) CharField(constraints=[SQL("default ''")])
    2.3 设置或者不设置数据库default对性能几乎没有损失
    2.4 设置数据库default，能够很好的避免null，一般建议在NOT NULL时设置default
    2.5 peewee开发者任务设置数据库default后，如果更改默认值会比较复杂，所以default只作用于python端
    2.6 可以参考:https://stackoverflow.com/questions/8010036/should-mysql-columns-always-have-default-values
    2.7 这里default和constraints都设置，显式的采用default，而constraints可以避免每个insert都需要插入全部的值
"""

import datetime
import logging
import hashlib

from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
from peewee import Model, DateTimeField, IntegerField, PrimaryKeyField, \
    CharField, MySQLDatabase, BigIntegerField, ForeignKeyField, TextField,\
    BooleanField, SQL, SmallIntegerField

from utils import Constant, AttrDict, TokenError
from configs import configs
from . import app


logger = logging.getLogger(__name__)

db = MySQLDatabase(
    database=configs["mysql"]["mydb"]["DB"],
    user=configs["mysql"]["mydb"]["USER"],
    password=configs["mysql"]["mydb"]["PASSWORD"],
)

serializer = Serializer(app.config['SECRET_KEY'])


def setDefault(default):
    return [SQL("default {}".format(default))]


class BaseModel(Model):
    class Meta:
        database = db


class Permission(object):
    """权限值不是越大就越高，只是用二进制标记而已
    通过Role绑定Permission，然后User再绑定Role来完成权限控制。
    如果要精确到某个文章，再通过具体文章和用户的所属关系判断"""
    ADMIN = 1     # 0b000000000000001
    DOWNLOAD = 2  # 0b000000000000010
    VIEW = 3
    EDIT = 4
    DELETE = 5
    ADD = 6


class Role(BaseModel):
    id = PrimaryKeyField()
    name = CharField(max_length=255, unique=True, index=True)
    permission = BigIntegerField(default=0, constraints=setDefault(0))
    is_deleted = BooleanField(default=0, constraints=setDefault(0))


class User(BaseModel):
    """表名都用单数"""
    id = PrimaryKeyField()
    name = CharField(max_length=255, verbose_name="user's name",
                     index=True, unique=True)
    password = CharField(max_length=128)
    # email = CharField(max_length=128, unique=True, index=True)
    # 0表示未设置
    age = SmallIntegerField(
        default=0, constraints=setDefault(0), verbose_name="user's age")
    # 用"<3"就可以过滤出已填性别的人
    sex = SmallIntegerField(choices=AttrDict(male=1, female=2, unknown=3))
    # city = CharField(verbose_name='city for user')
    created_time = DateTimeField(default=datetime.datetime.utcnow)
    # constraints=setDefault("CURRENT_TIMESTAMP"), MySQL 5.6版本支持设置
    updated_time = DateTimeField(default=datetime.datetime.utcnow)
    role_id = BigIntegerField(verbose_name="role's primary_key")
    is_deleted = BooleanField(default=0, constraints=setDefault(0))

    class Meta:
        db_table = 'user'

    @staticmethod
    def addPermission(perm, wanted_perm):
        if User.checkPermission(perm, wanted_perm):
            return perm
        return perm + wanted_perm

    @staticmethod
    def checkPermission(perm, wanted_perm):
        return perm & wanted_perm == perm

    @staticmethod
    def can(perm, wanted_perm):
        return User.checkPermission(perm, wanted_perm) or\
            User.checkPermission(perm, Permission.ADMIN)

    @staticmethod
    def generalPassword(password):
        password = bytes(password + app.config["SECRET_KEY"], encoding='utf-8')
        hash_password = hashlib.new("md5", data=password)
        return hash_password.hexdigest()

    @staticmethod
    def verifyPassword(password, password_hash):
        return User.generalPassword(password) == password_hash

    @staticmethod
    def generalToken(data, expiration=600):
        """生成token频率不高且有效期可能不同，所以serializer实时生成"""
        s = Serializer(app.config['SECRET_KEY'], expires_in=expiration)
        return s.dumps(data)

    @staticmethod
    def verifyToken(token):
        """校验token不涉及到有效期，所以提前生成serializer"""
        try:
            data = serializer.loads(token)
        except SignatureExpired:
            raise TokenError("token已过期")  # valid token, but expired
        except Exception:
            raise TokenError("非法token")    # invalid token
        return data


class Todo(BaseModel):
    """要做的事情"""
    id = PrimaryKeyField()
    title = CharField(max_length=255, index=True)
    detail = TextField(null=True, help_text="要做的事的具体内容或步骤")
    is_completed = BooleanField(constraints=setDefault(0), default=False)
    user_id = BigIntegerField(verbose_name="user's primary_key")
    is_deleted = BooleanField(default=0, constraints=setDefault(0))

    class Meta:
        db_table = 'todo'


class S(object):
    """SQL"""

    @staticmethod
    def createTable(tables):
        db.connect()
        db.create_tables(tables)
        db.commit()

    @staticmethod
    def createAllTables():
        """要根据已有的表来更新"""
        tables = [User, Role, Todo]
        S.createTable(tables)

    is_completed = Todo.is_completed.db_column
    is_deleted = Todo.is_deleted.db_column

    user_table = User._meta.db_table
    username = User.name.db_column
    password = User.password.db_column
    age = User.age.db_column
    sex = User.sex.db_column
    created_time = User.created_time.db_column

    todo_table = Todo._meta.db_table
    title = Todo.title.db_column
    detail = Todo.detail.db_column
    user_id = Todo.user_id.db_column

    # s表示select, i表示insert
    s_username = f"select id, {username} from {user_table} where {username} = %s limit 1"
    s_password = f"select id, {password} from {user_table} where {username} = %s"
    s_alluser = f"select id, {username} from {user_table}"
    s_user_todos = f"select id, {title}, {detail}, {is_completed} from {todo_table} where {user_id} = %s and is_deleted != 1"
    s_user_todo = f"select id, {title}, {detail}, {is_completed} from {todo_table} where {user_id} = %s and {is_deleted} != 1 and id = %s"

    i_user = f"insert into {user_table} ({username}, {password}, {age}, {sex}, {created_time}) values (%s, %s, %s, %s, %s)"
    i_todo = f"insert into {todo_table} ({user_id}, {title}, {detail}) values (%s, %s, %s)"

    d_user_todo = f"delete from {todo_table} where id=%s"
