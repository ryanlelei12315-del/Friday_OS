from memory.database import Base
from memory.database import engine

def initialize_memory():
    Base.metadata.create_all(bind=engine)