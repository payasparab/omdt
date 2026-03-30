"""Tests for the identity service."""

import pytest

from app.services import identities as id_service


@pytest.fixture(autouse=True)
def _clean():
    id_service.reload_people()
    yield
    id_service.reload_people()


class TestGetPerson:
    @pytest.mark.asyncio
    async def test_get_existing_person(self):
        person = await id_service.get_person("payas.parab")
        assert person is not None
        assert person.display_name == "Payas Parab"
        assert person.primary_email == "payas@example.com"

    @pytest.mark.asyncio
    async def test_get_missing_person(self):
        person = await id_service.get_person("nonexistent")
        assert person is None


class TestListPeople:
    @pytest.mark.asyncio
    async def test_list_returns_all(self):
        people = await id_service.list_people()
        assert len(people) >= 1
        keys = [p.person_key for p in people]
        assert "payas.parab" in keys


class TestResolveIdentity:
    @pytest.mark.asyncio
    async def test_resolve_by_email(self):
        person = await id_service.resolve_identity("payas@example.com")
        assert person is not None
        assert person.person_key == "payas.parab"

    @pytest.mark.asyncio
    async def test_resolve_by_github_username(self):
        person = await id_service.resolve_identity("payasparab")
        assert person is not None
        assert person.person_key == "payas.parab"

    @pytest.mark.asyncio
    async def test_resolve_by_linear_user_id(self):
        person = await id_service.resolve_identity("lin_user_001")
        assert person is not None
        assert person.person_key == "payas.parab"

    @pytest.mark.asyncio
    async def test_resolve_by_person_key(self):
        person = await id_service.resolve_identity("payas.parab")
        assert person is not None

    @pytest.mark.asyncio
    async def test_resolve_unknown(self):
        person = await id_service.resolve_identity("unknown@nowhere.com")
        assert person is None


class TestGetPersonRoles:
    @pytest.mark.asyncio
    async def test_get_roles(self):
        roles = await id_service.get_person_roles("payas.parab")
        assert "operator" in roles
        assert "admin" in roles

    @pytest.mark.asyncio
    async def test_get_roles_missing_person(self):
        roles = await id_service.get_person_roles("nonexistent")
        assert roles == []
