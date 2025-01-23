# ----------- #

# 这个脚本是用来把XYBotV1的数据库迁移到XYBotV2的数据库

# 使用方法：
# python3 database_migrater.py -v1-path XYBotV1数据库路径 -v2-path 数据库输出路径

# ----------- #

import argparse
import datetime
import sqlite3

from sqlalchemy import Column, String, Integer, DateTime, JSON, Boolean
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase


# 定义V2数据库模型
class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'user'

    wxid = Column(String(20), primary_key=True, nullable=False, unique=True, index=True)
    points = Column(Integer, nullable=False, default=0)
    signin_stat = Column(DateTime, nullable=False, default=datetime.datetime.fromtimestamp(0))
    signin_streak = Column(Integer, nullable=False, default=0)
    whitelist = Column(Boolean, nullable=False, default=False)
    llm_thread_id = Column(JSON, nullable=False, default="")


class Chatroom(Base):
    __tablename__ = 'chatroom'

    chatroom_id = Column(String(20), primary_key=True, nullable=False, unique=True, index=True, autoincrement=False,
                         comment='chatroom_id')
    members = Column(JSON, nullable=False, default=list, comment='members')
    llm_thread_id = Column(JSON, nullable=False, default=lambda: {}, comment='llm_thread_id')


def migrate_database(v1_path: str, v2_path: str):
    """
    从V1数据库迁移数据到V2数据库
    :param v1_path: V1 SQLite数据库文件路径
    :param v2_path: V2 SQLite数据库文件路径
    """
    try:
        # 连接V1数据库
        print(f"正在连接V1数据库: {v1_path}")
        v1_conn = sqlite3.connect(v1_path)
        v1_cursor = v1_conn.cursor()

        # 连接V2数据库
        print(f"正在连接V2数据库: {v2_path}")
        engine = create_engine(f"sqlite:///{v2_path}")
        Base.metadata.create_all(engine)  # 创建表
        Session = sessionmaker(bind=engine)
        session = Session()

        # 获取V1数据
        v1_cursor.execute("SELECT WXID, POINTS FROM USERDATA")
        user_data = v1_cursor.fetchall()

        # 迁移数据
        success_count = 0
        fail_count = 0

        for wxid, points in user_data:
            try:
                # 创建新用户记录
                new_user = User(
                    wxid=wxid,
                    points=points
                )
                session.merge(new_user)  # 使用merge代替add，避免主键冲突
                success_count += 1
                print(f"成功迁移用户 {wxid} 的积分: {points}")
            except Exception as e:
                fail_count += 1
                print(f"迁移用户 {wxid} 失败: {e}")

        # 提交事务
        session.commit()
        print(f"数据迁移完成！成功: {success_count} 条, 失败: {fail_count} 条")

    except sqlite3.Error as e:
        print(f"SQLite错误: {e}")
    except Exception as e:
        print(f"迁移过程出错: {e}")
        if 'session' in locals():
            session.rollback()
    finally:
        if 'v1_conn' in locals():
            v1_conn.close()
        if 'session' in locals():
            session.close()


def main():
    parser = argparse.ArgumentParser(description='从V1数据库迁移数据到V2数据库')
    parser.add_argument('-v1-path', required=True, help='V1数据库文件路径 (例如: ./v1_database.db)')
    parser.add_argument('-v2-path', required=True, help='V2数据库文件路径 (例如: ./v2_database.db)')

    args = parser.parse_args()
    migrate_database(args.v1_path, args.v2_path)  # 修改这里的参数名


if __name__ == "__main__":
    main()
