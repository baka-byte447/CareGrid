import csv
from datetime import datetime

from backend.db.database import SessionLocal
from backend.models.patient import Patient
from backend.models.bed import Bed
from backend.models.staff import Staff
from backend.models.equipment import Equipment


DATA_DIR = "data/synthetic"


def yes_no_to_bool(value):
    return value.strip().upper() == "YES"


def percentage_to_int(value):
    return int(value.strip().replace("%", ""))


def import_patients(db):
    with open(f"{DATA_DIR}/patients.csv", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            patient = Patient(
                patient_id=row["patient_id"],
                age_group=row["age_group"],
                acuity=int(row["acuity"]),
                specialty=row["specialty"],
                predicted_los=float(row["predicted_los"]),
                isolation_required=yes_no_to_bool(row["isolation_required"]),
                ventilator_required=yes_no_to_bool(row["ventilator_required"]),
                arrival_time=datetime.strptime(
                    row["arrival_time"],
                    "%Y-%m-%d %H:%M:%S"
                ),
                current_status=row["current_status"],
            )

            db.add(patient)


def import_beds(db):
    with open(f"{DATA_DIR}/beds.csv", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            bed = Bed(
                bed_id=row["bed_id"],
                bed_type=row["bed_type"],
                ward=row["ward"],
                status=row["status"],
                isolation_capable=yes_no_to_bool(row["isolation_capable"]),
            )

            db.add(bed)


def import_staff(db):
    with open(f"{DATA_DIR}/staff.csv", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            staff = Staff(
                staff_id=row["staff_id"],
                role=row["role"],
                skill_level=row["skill_level"],
                shift=row["shift"],
                workload=percentage_to_int(row["workload"]),
            )

            db.add(staff)


def import_equipment(db):
    with open(f"{DATA_DIR}/equipment.csv", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            equipment = Equipment(
                equipment_id=row["equipment_id"],
                type=row["type"],
                status=row["status"],
                location=row["location"],
            )

            db.add(equipment)


def main():

    db = SessionLocal()

    try:
        # Clear existing synthetic data
        db.query(Patient).delete()
        db.query(Bed).delete()
        db.query(Staff).delete()
        db.query(Equipment).delete()

        # Import fresh data from CSV files
        import_patients(db)
        import_beds(db)
        import_staff(db)
        import_equipment(db)

        db.commit()

        print("CSV data imported successfully.")

    except Exception as e:
        db.rollback()
        print(f"Import failed: {e}")
        raise

    finally:
        db.close()

if __name__ == "__main__":
    main()