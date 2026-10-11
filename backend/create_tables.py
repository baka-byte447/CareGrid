from backend.db.database import Base, engine

# Import all models so SQLAlchemy knows about them
from backend.models.patient import Patient
from backend.models.bed import Bed
from backend.models.staff import Staff
from backend.models.equipment import Equipment


Base.metadata.create_all(bind=engine)

print("All database tables created successfully.")