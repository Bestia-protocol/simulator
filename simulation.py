from enum import Enum
import random
import time
from decimal import Decimal
from typing import Dict
from faker import Faker
from colorama import Fore, Style
from vault import Vault
from utils import generate_random_decimal


class Action(Enum):
    NOTHING = 0
    MINT = 1
    REDEEM = 2


class User():
    def __init__(self, vault: Vault, name: str, cash: Decimal):
        self.vault = vault
        self.name = name
        self.cash = cash
        self.usdb = Decimal('0')


    def nothing(self):
        return


    def mint(self):
        amount = generate_random_decimal(0, self.cash)
        self.cash -= amount
        self.usdb += self.vault.mint(amount)
        print(f"{Fore.GREEN}{self.name} minted {amount} USDb{Style.RESET_ALL}")


    def redeem(self):
        amount = generate_random_decimal(0, self.usdb)
        try:
            self.usdb -= self.vault.redeem(amount)
            self.cash += amount
            print(f"{Fore.MAGENTA}{self.name} Redeemed {amount} USDb{Style.RESET_ALL}")
        except:
            print(f"{Fore.BLACK}{self.name} can't redeem {amount}USDb{Style.RESET_ALL}")

def generate_users(n, vault):
    fake = Faker()
    users = []
    for _ in range(n):
        name = fake.user_name()
        amount = generate_random_decimal(1, 1000000)
        user = User(vault, name, amount)
        users.append(user)
    return users


def main():
    print("--------- Starting Bestia Simulator ---------")
    vault = Vault("Vault", Decimal('0.2'), Decimal('0.05')) # 20% - 5%
    vault.add_supported_asset("USDe", Decimal('1'), Decimal('0.998'))
    vault.add_supported_asset("WETH", Decimal('2'), Decimal('3410'))
    vault.add_supported_asset("WBTC", Decimal('3'), Decimal('64000'))

    users = generate_users(10, vault)
    try:
        while True:
            for user in users:
                action = random.choice(list(Action))
                getattr(user, action.name.lower())()
                vault.rebalance()
                vault.liquidate()

            random_asset = random.choice(list(vault.assets.keys()))
            base_ratio = vault.prices[random_asset]
            lower_bound = base_ratio * Decimal('0.5')
            upper_bound = base_ratio * Decimal('1.5')
            new_price = generate_random_decimal(lower_bound, upper_bound)
            vault.set_asset_price(random_asset, new_price)
            print(f"Changed {random_asset} price to {new_price}")

            random.shuffle(users)
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n--------- Exiting Bestia Simulator ---------")


if __name__ == "__main__":
    main()
