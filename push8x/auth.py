from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class AuthDataItem:
    password_str: str
    password_bytes: bytes
    ext: dict[str, Any]


class AuthDataGenerator:

    def __init__(
        self, accounts: list[Any], username_key: str, password_key: str
    ) -> None:
        self.accounts = iter(accounts)
        self.username_key = username_key
        self.password_key = password_key

    def __iter__(self):
        return self

    def __next__(self) -> tuple[str, AuthDataItem]:
        item = next(self.accounts)

        ext = asdict(item)
        username = ext.pop(self.username_key)
        password = ext.pop(self.password_key)

        return username, AuthDataItem(
            password_str=password, password_bytes=password.encode(), ext=ext
        )


class AuthAbc:
    # TODO: load password with hash:xxxx
    accounts: list[Any]
    data_bytes: dict[bytes, AuthDataItem]
    data_str: dict[str, AuthDataItem]

    @property
    def username_key(self) -> str:
        return "username"

    @property
    def password_key(self) -> str:
        return "password"

    def __init__(self, accounts: list[Any]) -> None:
        self.accounts = accounts
        self.data_bytes = {
            username.encode(): auth_data_item
            for username, auth_data_item in AuthDataGenerator(
                self.accounts, self.username_key, self.password_key
            )
        }
        self.data_str = {
            username: auth_data_item
            for username, auth_data_item in AuthDataGenerator(
                self.accounts, self.username_key, self.password_key
            )
        }

    def check(self, username: bytes, password: bytes) -> tuple[bool, dict[str, Any]]:
        auth_data_item = self.data_bytes.get(username, None)
        if auth_data_item is None:
            return False, {}

        if auth_data_item.password_bytes == password:
            return True, auth_data_item.ext

        return False, auth_data_item.ext

    def check_str(self, username: str, password: str) -> tuple[bool, dict[str, Any]]:
        auth_data_item = self.data_str.get(username, None)
        if auth_data_item is None:
            return False, {}

        if auth_data_item.password_str == password:
            return True, auth_data_item.ext

        return False, auth_data_item.ext
