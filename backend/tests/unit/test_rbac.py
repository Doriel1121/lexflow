from app.core.dependencies import RoleChecker
from app.db.models.user import User, UserRole
from fastapi import HTTPException


def make_user(role: UserRole, superuser: bool = False):
    return User(
        id=1,
        email="x@example.com",
        hashed_password="hash",
        full_name="X",
        is_active=True,
        is_superuser=superuser,
        role=role,
    )


def test_role_checker_allows_allowed_role():
    checker = RoleChecker([UserRole.LAWYER, UserRole.ASSISTANT])
    user = make_user(UserRole.LAWYER)
    assert checker(user) is user


def test_role_checker_rejects_disallowed_role():
    checker = RoleChecker([UserRole.ADMIN])
    user = make_user(UserRole.VIEWER)
    try:
        checker(user)
        assert False, "Expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 403


def test_role_checker_superuser_bypass():
    checker = RoleChecker([])  # no roles permitted normally
    superu = make_user(UserRole.VIEWER, superuser=True)
    assert checker(superu) is superu
