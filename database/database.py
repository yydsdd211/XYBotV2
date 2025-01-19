import datetime

from loguru import logger
from sqlalchemy import Column, String, Integer, DateTime, create_engine, JSON, Boolean
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

from utils.singleton import Singleton

Base = declarative_base()


class User(Base):
    __tablename__ = 'user'

    wxid = Column(String(20), primary_key=True, nullable=False, unique=True, index=True, autoincrement=False,
                  comment='wxid')
    points = Column(Integer, nullable=False, default=0, comment='points')
    signin_stat = Column(DateTime, nullable=False, default=datetime.datetime.fromtimestamp(0), comment='signin_stat')
    signin_days = Column(Integer, nullable=False, default=0, comment='signin_days')
    whitelist = Column(Boolean, nullable=False, default=False, comment='whitelist')
    llm_record = Column(JSON, nullable=False, default={}, comment='llm_record')


class Chatroom(Base):
    __tablename__ = 'chatroom'

    chatroom_id = Column(String(20), primary_key=True, nullable=False, unique=True, index=True, autoincrement=False,
                         comment='chatroom_id')
    members = Column(JSON, nullable=False, default=list, comment='members')
    llm_record = Column(JSON, nullable=False, default=dict, comment='llm_record')


class BotDatabase(metaclass=Singleton):
    def __init__(self):
        self.engine = create_engine('sqlite:///userdata.db')
        self.DBSession = sessionmaker(bind=self.engine)

        # 创建表
        Base.metadata.create_all(self.engine)
        logger.success("数据库初始化成功")

    # USER

    def add_points(self, wxid: str, num: int) -> bool:
        """Thread-safe point addition"""
        session = self.DBSession()
        try:
            # Use UPDATE with atomic operation
            result = session.execute(
                update(User)
                .where(User.wxid == wxid)
                .values(points=User.points + num)
            )
            if result.rowcount == 0:
                # User doesn't exist, create new
                user = User(wxid=wxid, points=num)
                session.add(user)
            logger.info(f"数据库: 用户{wxid}积分增加{num}")
            session.commit()
            return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"数据库: 用户{wxid}积分增加失败, 错误: {e}")
            return False
        finally:
            session.close()

    def set_points(self, wxid: str, num: int) -> bool:
        """Thread-safe point setting"""
        session = self.DBSession()
        try:
            result = session.execute(
                update(User)
                .where(User.wxid == wxid)
                .values(points=num)
            )
            if result.rowcount == 0:
                user = User(wxid=wxid, points=num)
                session.add(user)
            logger.info(f"数据库: 用户{wxid}积分设置为{num}")
            session.commit()
            return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"数据库: 用户{wxid}积分设置失败, 错误: {e}")
            return False
        finally:
            session.close()

    def get_points(self, wxid: str) -> int:
        """Get user points"""
        session = self.DBSession()
        try:
            user = session.query(User).filter_by(wxid=wxid).first()
            return user.points if user else 0
        finally:
            session.close()

    def get_signin_stat(self, wxid: str) -> datetime.datetime:
        """Thread-safe get user's last login time"""
        session = self.DBSession()
        try:
            # Use SELECT FOR UPDATE to prevent concurrent modifications
            user = session.query(User).filter_by(wxid=wxid) \
                .with_for_update().first()
            return user.signin_stat if user else datetime.datetime.fromtimestamp(0)
        finally:
            session.close()

    def set_signin_stat(self, wxid: str, signin_time: datetime.datetime) -> bool:
        """Thread-safe set user's signin time"""
        session = self.DBSession()
        try:
            # Use atomic UPDATE operation
            result = session.execute(
                update(User)
                .where(User.wxid == wxid)
                .values(
                    signin_stat=signin_time,
                    signin_days=User.signin_days + 1
                )
            )
            if result.rowcount == 0:
                # User doesn't exist, create new
                user = User(
                    wxid=wxid,
                    signin_stat=signin_time,
                    signin_days=1
                )
                session.add(user)
            logger.info(f"数据库: 用户{wxid}登录时间设置为{signin_time}")
            session.commit()
            return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"数据库: 用户{wxid}登录时间设置失败, 错误: {e}")
            return False
        finally:
            session.close()

    def reset_all_signin_stat(self) -> bool:
        """Reset all users' signin status"""
        session = self.DBSession()
        try:
            session.query(User).update({User.signin_stat: datetime.datetime.fromtimestamp(0)})
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"数据库: 重置所有用户登录时间失败, 错误: {e}")
            return False
        finally:
            session.close()

    def get_leaderboard(self) -> list:
        """Get points leaderboard"""
        session = self.DBSession()
        try:
            users = session.query(User).order_by(User.points.desc()).all()
            return [(user.wxid, user.points) for user in users]
        finally:
            session.close()

    def set_whitelist(self, wxid: str, stat: bool) -> bool:
        """Set user's whitelist status"""
        session = self.DBSession()
        try:
            user = session.query(User).filter_by(wxid=wxid).first()
            if not user:
                user = User(wxid=wxid)
                session.add(user)
            user.whitelist = stat
            session.commit()
            logger.info(f"数据库: 用户{wxid}白名单状态设置为{stat}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"数据库: 用户{wxid}白名单状态设置失败, 错误: {e}")
            return False
        finally:
            session.close()

    def get_whitelist(self, wxid: str) -> bool:
        """Get user's whitelist status"""
        session = self.DBSession()
        try:
            user = session.query(User).filter_by(wxid=wxid).first()
            return user.whitelist if user else False
        finally:
            session.close()

    def safe_trade_points(self, trader_wxid: str, target_wxid: str, num: int) -> bool:
        """Thread-safe points trading between users"""
        session = self.DBSession()
        try:
            # Start transaction with row-level locking
            trader = session.query(User).filter_by(wxid=trader_wxid) \
                .with_for_update().first()  # Acquire row lock
            target = session.query(User).filter_by(wxid=target_wxid) \
                .with_for_update().first()  # Acquire row lock

            if not trader:
                trader = User(wxid=trader_wxid)
                session.add(trader)
            if not target:
                target = User(wxid=target_wxid)
                session.add(target)
                session.flush()  # Ensure IDs are generated

            if trader.points >= num:
                trader.points -= num
                target.points += num
                session.commit()
                logger.info(f"数据库: 用户{trader_wxid}给用户{target_wxid}转账{num}积分")
                return True
            logger.info(f"数据库: 转账失败, 用户{trader_wxid}积分不足")
            session.rollback()
            return False
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"数据库: 转账失败, 错误: {e}")
            return False
        finally:
            session.close()

    def get_user_list(self) -> list:
        """Get list of all users"""
        session = self.DBSession()
        try:
            users = session.query(User).all()
            return [user.wxid for user in users]
        finally:
            session.close()

    def get_llm_record(self, wxid: str) -> dict:
        """Get LLM chat record for user or chatroom"""
        session = self.DBSession()
        try:
            # Check if it's a chatroom ID
            if wxid.endswith("@chatroom"):
                chatroom = session.query(Chatroom).filter_by(chatroom_id=wxid).first()
                return chatroom.llm_record if chatroom else {}
            else:
                # Regular user
                user = session.query(User).filter_by(wxid=wxid).first()
                return user.llm_record if user else {}
        finally:
            session.close()

    def save_llm_record(self, wxid: str, data: dict) -> bool:
        """Save LLM chat record for user or chatroom"""
        session = self.DBSession()
        try:
            # Check if it's a chatroom ID
            if wxid.endswith("@chatroom"):
                chatroom = session.query(Chatroom).filter_by(chatroom_id=wxid).first()
                if not chatroom:
                    chatroom = Chatroom(chatroom_id=wxid)
                    session.add(chatroom)
                chatroom.llm_record = data
            else:
                # Regular user
                user = session.query(User).filter_by(wxid=wxid).first()
                if not user:
                    user = User(wxid=wxid)
                    session.add(user)
                user.llm_record = data
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            return False
        finally:
            session.close()

    # CHATROOM

    def get_chatroom_list(self) -> list:
        """Get list of all chatrooms"""
        session = self.DBSession()
        try:
            chatrooms = session.query(Chatroom).all()
            return [chatroom.chatroom_id for chatroom in chatrooms]
        finally:
            session.close()

    def get_chatroom_members(self, chatroom_id: str) -> set:
        """Get members of a chatroom"""
        session = self.DBSession()
        try:
            chatroom = session.query(Chatroom).filter_by(chatroom_id=chatroom_id).first()
            return set(chatroom.members) if chatroom else set()
        finally:
            session.close()

    def set_chatroom_members(self, chatroom_id: str, members: set) -> bool:
        """Set members of a chatroom"""
        session = self.DBSession()
        try:
            chatroom = session.query(Chatroom).filter_by(chatroom_id=chatroom_id).first()
            if not chatroom:
                chatroom = Chatroom(chatroom_id=chatroom_id)
                session.add(chatroom)
            chatroom.members = list(members)  # Convert set to list for JSON storage
            logger.info(f"Database: Set chatroom {chatroom_id} members successfully")
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Database: Set chatroom {chatroom_id} members failed, error: {e}")
            return False
        finally:
            session.close()