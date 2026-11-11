import os
import tempfile

TMP_DIR = tempfile.mkdtemp(prefix="octopod-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{TMP_DIR}/test.db"
os.environ["SEED_DEMO"] = "false"
os.environ["AUTO_CREATE_TABLES"] = "true"
os.environ["SECRET_KEY"] = "test-secret"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.models  # noqa: F401,E402
from app.core.config import reset_settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_engine, get_sessionmaker, reset_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.employee import Employee  # noqa: E402
from app.models.reference import ShiftStatus, StaffingRequirement  # noqa: E402
from app.models.user import Role, User  # noqa: E402


@pytest.fixture(autouse=True)
def reset_database():
    from app.core.security import rate_limiter

    rate_limiter.reset()
    reset_settings()
    reset_engine()
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    reset_engine()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def seeded():
    with get_sessionmaker()() as db:
        statuses = [
            ShiftStatus(
                code="G",
                label="General",
                color="#E5E7EB",
                text_color="#111827",
                is_working=True,
                sort_order=1,
            ),
            ShiftStatus(
                code="M",
                label="Morning",
                color="#BBF7D0",
                text_color="#14532D",
                is_working=True,
                sort_order=2,
            ),
            ShiftStatus(
                code="A",
                label="Afternoon",
                color="#BFDBFE",
                text_color="#1E3A8A",
                is_working=True,
                sort_order=3,
            ),
            ShiftStatus(
                code="N",
                label="Night",
                color="#FDE68A",
                text_color="#78350F",
                is_working=True,
                sort_order=4,
            ),
            ShiftStatus(
                code="L",
                label="Leave",
                color="#FECACA",
                text_color="#7F1D1D",
                is_working=False,
                sort_order=5,
            ),
            ShiftStatus(
                code="CO",
                label="Comp-off",
                color="#FDBA74",
                text_color="#7C2D12",
                is_working=False,
                sort_order=6,
            ),
            ShiftStatus(
                code="O",
                label="Week-off",
                color="#F3F4F6",
                text_color="#374151",
                is_working=False,
                sort_order=7,
            ),
            ShiftStatus(
                code="H",
                label="Holiday",
                color="#DDD6FE",
                text_color="#4C1D95",
                is_working=False,
                sort_order=8,
            ),
        ]
        db.add_all(statuses)
        db.flush()
        status_by_code = {status.code: status for status in statuses}
        for code in ("G", "M", "A", "N"):
            db.add(
                StaffingRequirement(
                    status_id=status_by_code[code].id,
                    required_count=2,
                )
            )

        admin = User(
            email="admin@test.local",
            password_hash=hash_password("Admin123!"),
            role=Role.admin,
        )
        db.add(admin)
        employees = []
        for index in range(1, 7):
            employee = Employee(
                employee_code=f"E{index:03d}",
                full_name=f"Employee {index}",
                email=f"employee{index}@test.local",
                rotation_offset=index - 1,
                week_off_start_day=(index - 1) % 7,
            )
            db.add(employee)
            db.flush()
            db.add(
                User(
                    email=employee.email,
                    password_hash=hash_password("Employee123!"),
                    role=Role.employee,
                    employee_id=employee.id,
                )
            )
            employees.append(employee)
        db.commit()
        return {
            "admin_id": admin.id,
            "employees": [(employee.id, employee.employee_code) for employee in employees],
        }


def login_headers(client: TestClient, identifier: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"identifier": identifier, "password": password}
    )
    assert response.status_code == 200, response.text
    return {"X-CSRF-Token": response.json()["csrf_token"]}
