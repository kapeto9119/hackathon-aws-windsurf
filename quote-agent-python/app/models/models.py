from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Table, Boolean, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base
import uuid

# Association table for parts in quotes
quote_parts = Table(
    'quote_parts',
    Base.metadata,
    Column('quote_id', Integer, ForeignKey('quotes.id'), primary_key=True),
    Column('part_id', Integer, ForeignKey('parts.id'), primary_key=True)
)

# Association table for parts in calls
call_parts = Table(
    'call_parts',
    Base.metadata,
    Column('call_id', Integer, ForeignKey('calls.id'), primary_key=True),
    Column('part_id', Integer, ForeignKey('parts.id'), primary_key=True)
)

class Customer(Base):
    """
    Customer model
    """
    __tablename__ = 'customers'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    phone = Column(String(20), unique=True)
    email = Column(String(100))
    address = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    calls = relationship("Call", back_populates="customer")
    orders = relationship("Order", back_populates="customer")
    
    def __repr__(self):
        return f"<Customer(id={self.id}, name='{self.name}', phone='{self.phone}')>"

class Manufacturer(Base):
    """
    Manufacturer model
    """
    __tablename__ = 'manufacturers'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    phone = Column(String(20))
    email = Column(String(100))
    specialties = Column(JSON)  # Store as JSON array
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    quotes = relationship("Quote", back_populates="manufacturer")
    
    def __repr__(self):
        return f"<Manufacturer(id={self.id}, name='{self.name}')>"

class Part(Base):
    """
    Part model
    """
    __tablename__ = 'parts'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    description = Column(Text)
    category = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    quotes = relationship("Quote", secondary=quote_parts, back_populates="parts")
    calls = relationship("Call", secondary=call_parts, back_populates="parts")
    
    def __repr__(self):
        return f"<Part(id={self.id}, name='{self.name}', category='{self.category}')>"

class Call(Base):
    """
    Call model
    """
    __tablename__ = 'calls'
    
    id = Column(Integer, primary_key=True)
    call_sid = Column(String(50), unique=True)  # Twilio Call SID
    customer_id = Column(Integer, ForeignKey('customers.id'))
    direction = Column(String(20))  # inbound or outbound
    status = Column(String(20))  # in-progress, completed, failed
    duration = Column(Integer)  # in seconds
    recording_url = Column(String(255))
    conversation_data = Column(JSON)  # Store conversation data as JSON
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customer = relationship("Customer", back_populates="calls")
    parts = relationship("Part", secondary=call_parts, back_populates="calls")
    
    def __repr__(self):
        return f"<Call(id={self.id}, call_sid='{self.call_sid}', status='{self.status}')>"

class Quote(Base):
    """
    Quote model
    """
    __tablename__ = 'quotes'
    
    id = Column(Integer, primary_key=True)
    manufacturer_id = Column(Integer, ForeignKey('manufacturers.id'))
    price = Column(Float)
    eta = Column(Integer)  # in days
    is_best_quote = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    manufacturer = relationship("Manufacturer", back_populates="quotes")
    parts = relationship("Part", secondary=quote_parts, back_populates="quotes")
    orders = relationship("Order", back_populates="quote")
    
    def __repr__(self):
        return f"<Quote(id={self.id}, manufacturer_id={self.manufacturer_id}, price={self.price}, eta={self.eta})>"

class Order(Base):
    """
    Order model
    """
    __tablename__ = 'orders'
    
    id = Column(Integer, primary_key=True)
    order_number = Column(String(50), unique=True, default=lambda: f"ORD-{uuid.uuid4().hex[:8].upper()}")
    customer_id = Column(Integer, ForeignKey('customers.id'))
    quote_id = Column(Integer, ForeignKey('quotes.id'))
    status = Column(String(20))  # pending, confirmed, shipped, delivered
    email_sent = Column(Boolean, default=False)
    callback_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customer = relationship("Customer", back_populates="orders")
    quote = relationship("Quote", back_populates="orders")
    
    def __repr__(self):
        return f"<Order(id={self.id}, order_number='{self.order_number}', status='{self.status}')>"
