from sqlalchemy import BigInteger, String, Boolean, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from database import Base

class GuildConfig(Base):
    __tablename__ = "guild_config"
    
    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticket_category_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    transcript_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    log_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    mod_log_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    message_log_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    member_log_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    voice_log_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    
    log_message_edits: Mapped[bool] = mapped_column(Boolean, default=True)
    log_message_deletions: Mapped[bool] = mapped_column(Boolean, default=True)
    log_member_joins: Mapped[bool] = mapped_column(Boolean, default=True)
    log_member_leaves: Mapped[bool] = mapped_column(Boolean, default=True)
    log_voice_updates: Mapped[bool] = mapped_column(Boolean, default=True)
    
    automod_invite_links: Mapped[bool] = mapped_column(Boolean, default=False)
    
    mod_role_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    admin_role_id: Mapped[int] = mapped_column(BigInteger, nullable=True)

class TicketReason(Base):
    __tablename__ = "ticket_reasons"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger)
    label: Mapped[str] = mapped_column(String(100))
    category_id: Mapped[int] = mapped_column(BigInteger)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    emoji: Mapped[str] = mapped_column(String(50), nullable=True)
    # required_roles is BIGINT[] in postgres, SQLAlchemy needs an adaptation
    # For now we'll skip complex types or use pickletype/json if needed
    # required_roles: Mapped[list] = mapped_column(JSON, nullable=True) 

class WordFilter(Base):
    __tablename__ = "word_filters"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger)
    phrase: Mapped[str] = mapped_column(Text)
class Ticket(Base):
    __tablename__ = "tickets"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger)
    channel_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    owner_id: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20))
    transcript_text: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text) # Using Text for simplicity or DateTime
