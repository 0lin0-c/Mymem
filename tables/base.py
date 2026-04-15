# 🗄️ SQLAlchemy Base 声明：所有数据模型都继承自它
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy 2.0+ Declarative Base

    所有具体的数据表模型都必须继承自此类，
    以便 SQLAlchemy 的 MetaData 能收集所有表结构。
    """
    pass
