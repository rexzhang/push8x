from typing import Any


class AuthDataGenerator:

    def __init__(
        self, accounts: list[Any], username_key: str, password_key: str
    ) -> None:
        self.accounts = iter(accounts)
        self.username_key = username_key
        self.password_key = password_key

    def __iter__(self):
        return self

    def __next__(self) -> tuple[str, str]:
        item = next(self.accounts)

        return getattr(item, self.username_key), getattr(item, self.password_key)


class AuthAbc:
    # TODO: load password with hash:xxxx
    data: dict[bytes, bytes]
    data_str: dict[str, str]

    @property
    def username_key(self) -> str:
        return "username"

    @property
    def password_key(self) -> str:
        return "password"

    def __init__(self, accounts: list[Any]) -> None:
        self.accounts = accounts
        self.data = {
            username.encode(): password.encode()
            for username, password in AuthDataGenerator(
                self.accounts, self.username_key, self.password_key
            )
        }
        self.data_str = {
            username: password
            for username, password in AuthDataGenerator(
                self.accounts, self.username_key, self.password_key
            )
        }

    def check(self, username: bytes, password: bytes) -> bool:
        print(self.data)
        return self.data.get(username, None) == password

    def check_str(self, username: str, password: str) -> bool:
        print(self.data)
        return self.data_str.get(username, None) == password
