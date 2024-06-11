import time
from math import exp
from decimal import Decimal
from collections import deque
from colorama import Fore, Style


# this class stores asset price observations for the price volatility calculations
class PriceObservation:
    def __init__(self, timestamp: int, price: Decimal):
        self.timestamp = timestamp
        self.price = price


class Vault:
    def __init__(self, name: str, optimal_cash_threshold: Decimal, liquidation_trigger_threshold: Decimal, window: Decimal):
        self.debug = False
        self.name = name
        self.cash = 0
        self.optimal_cash_threshold = optimal_cash_threshold # optimal threshold value after which rebalancing is possible
        self.liquidation_trigger_threshold = liquidation_trigger_threshold # threshold after which assets become liquidable
        self.token_supply = Decimal(0)
        self.assets = {} # balance of each asset in asset amount
        self.asset_liquidity_value = {} # priority over liquidations
        self.prices = {}
        self.window = window # time window for inflow, outflow and volatility calculation
        self.deposit_requests = {}
        self.withdrawal_requests = {}
        self.price_volatility = {} # storing price observations
        self.thresholds = {} # asset optimal thresholds


    # provide cash and get bestia
    def mint(self, amount: Decimal) -> Decimal:
        self.cash += amount
        self.token_supply += amount
        self.deposit_requests[time.time()] = amount
        return amount


    # give bestia and get cash
    def redeem(self, amount: Decimal) -> Decimal:
        if self.cash < amount:
            raise ValueError("Not enough cash")

        self.cash -= amount
        self.token_supply -= amount
        self.withdrawal_requests[time.time()] = amount
        return amount

    
    # whitelist an asset held by the vault
    def add_supported_asset(self, name: str, liquidity_value: Decimal, price: Decimal, threshold: Decimal):
        if name in self.assets:
            raise ValueError("Name already present")
        
        if threshold > Decimal(100):
            raise ValueError("Invalid threshold")

        self.assets[name] = Decimal(0)
        self.asset_liquidity_value[name] = liquidity_value
        self.price_volatility[name] = deque(maxlen=1000) # Limit the size to last 1000 observations
        self.price_volatility[name].append(PriceObservation(time.time(), price))
        self.prices[name] = price
        self.thresholds[name] = threshold


    def change_asset_threshold(self, asset: str, threshold: Decimal):
        if asset not in self.assets:
            raise ValueError("Asset not present")

        if threshold > Decimal(100):
            raise ValueError("Invalid threshold")

        self.thresholds[asset] = threshold


    # TBD
    # defines the added pricing when redeeming directly an asset
    def swing_pricing(self, asset: str, inflow: bool) -> Decimal:
        if (inflow):
            flow = self.get_inflow()
        else:
            flow = self.get_outflow()

        price_volatility = self.get_price_volatility(asset)
        threshold = self.get_current_asset_threshold(asset)

        # Coefficients
        a = Decimal('0.01')  # Scaling factor for flow
        b = Decimal('0.05')  # Scaling factor for price volatility
        c = Decimal('0.1')   # Exponential growth rate
        d = Decimal('0.02')  # Adjustment for deviation

        # Normalized swing factor calculation using sigmoid function
        x = flow * (1 + b * price_volatility)
        f_x = Decimal(1) / (Decimal(1) + Decimal(exp(-float(c * (x - threshold)))))

        # Final fee adjustment
        final_fee = a * x * (1 + d * f_x)

        # Ensure the fee is within 0% to 100%
        final_fee_normalized = max(0, min(1, final_fee))

        return final_fee_normalized

    # use extra cash to buy assets
    def rebalance(self):
        # First, check if rebalancing is necessary
        current_cash_ratio = self.get_current_cash_threshold()
        if current_cash_ratio <= self.optimal_cash_threshold:
            return

        # Calculate the excess cash that needs to be converted into assets
        total_value = self.get_total_value()
        desired_cash = self.optimal_cash_threshold * total_value
        excess_cash = self.cash - desired_cash

        if(self.debug):
            print(f"{Fore.BLUE}Cash to rebalance: {excess_cash}{Style.RESET_ALL}")

        # Distribute the excess cash among assets based on their liquidity value
        for asset in self.assets:
            if self.prices.get(asset, 0) == 0:
                raise ValueError(f"Invalid asset price for {asset}")
            
            # Calculate how much cash to allocate to this asset based on its liquidity share
            cash_for_asset =  excess_cash  / Decimal(self.assets.__len__())

            # Determine how many units of the asset to buy
            price_per_unit = self.prices[asset]
            quantity_to_buy = cash_for_asset / price_per_unit

            # Update asset holdings
            self.assets[asset] += quantity_to_buy
            if(self.debug):
                print(f"{Fore.BLUE}Buying {quantity_to_buy} {asset}{Style.RESET_ALL}")

        # Update cash holdings after rebalancing
        self.cash -= excess_cash
        if(self.debug):
            print(f"{Fore.BLUE}Rebalancing complete{Style.RESET_ALL}")


    def set_asset_price(self, asset: str, price: Decimal):
        self.price_volatility[asset] = deque(maxlen=1000)
        self.price_volatility[asset].append(PriceObservation(time.time(), price))
        self.prices[asset] = price

    
    def set_asset_liquidity_value(self, asset: str, value: Decimal):
        self.asset_liquidity_value[asset] = value

    
    # value of a single asset in cash terms
    def get_asset_value(self, asset: str) -> Decimal:
        if asset not in self.assets:
            raise ValueError("Invalid asset")

        if asset not in self.prices:
            raise ValueError("Invalid price")
        
        return self.prices[asset] * self.assets[asset]


    # value of all assets in cash terms
    def get_assets_value(self) -> Decimal:
        total = Decimal('0')
        for key, value in self.assets.items():
            total += self.get_asset_value(key)
        return total


    def get_inflow(self) -> Decimal:
        total = Decimal(0)
        min_time = Decimal(time.time()) - self.window
        if self.window == 0 or min_time < 0:
            raise ValueError("Invalid time window")

        for key, value in self.deposit_requests.items():
            if (key < min_time):
                pass
            else:
                total += value

        return total / self.window


    def get_outflow(self) -> Decimal:
        total = Decimal(0)
        min_time = Decimal(time.time()) - self.window
        if self.window == 0 or min_time < 0:
            raise ValueError("Invalid time window")

        for key, value in self.withdrawal_requests.items():
            if (key < min_time):
                pass
            else:
                total += value

        return total / self.window


    def get_price_volatility(self, asset: str) -> Decimal:
        current_time = Decimal(time.time())
        min_time = current_time - self.window
        relevant_prices = []

        for item in self.price_volatility[asset]:
            if item.timestamp >= min_time:
                relevant_prices.append(item.price)
        
        if len(relevant_prices) < 2:
            return Decimal('0')

        mean_price = sum(relevant_prices) / Decimal(len(relevant_prices))
        variance = sum((price - mean_price) ** 2 for price in relevant_prices) / Decimal(len(relevant_prices))
        return variance.sqrt()


    def get_current_asset_threshold(self, asset: str) -> Decimal:
        if asset not in self.thresholds:
            raise ValueError("Invalid asset")
        
        if self.get_assets_value() == 0 or self.get_asset_value(asset) == 0:
            return Decimal(0)
        
        asset_threshold = self.get_asset_value(asset) / self.get_assets_value()

        return abs(self.thresholds[asset] - asset_threshold)


    def get_total_value(self) -> Decimal:
        return self.get_assets_value() + self.cash


### user-driven liquidations ###
    def liquidate_asset(self, asset: str, amount: Decimal) -> Decimal:
        if asset not in self.assets:
            raise ValueError("Asset not supported")
        
        if asset not in self.prices:
            raise ValueError("Invalid price")
        
        if self.assets[asset] < amount:
            raise ValueError("Not enough asset amount")

        asset_value = amount * self.prices[asset]
        if self.cash >= asset_value:
            raise ValueError("No need to liquidate asset, enough cash available")

        swing_pricing_factor = self.swing_pricing(asset, amount, False)
        user_part = asset_value * (1 - swing_pricing_factor)
        protocol_part = asset_value - user_part

        if (self.debug):
            print(f"{Fore.BLUE}Liquidated {amount} {asset}, user got {user_part} and protocol got {protocol_part} with a swing pricing factor of {swing_pricing_factor}{Style.RESET_ALL}")


### protocol-driven liquidations ###
    def get_current_cash_threshold(self) -> Decimal:
        if self.get_total_value() == 0:
            return Decimal(0)
        return self.cash / self.get_total_value()


    def is_liquidable(self) -> bool:
        return self.get_current_cash_threshold() < self.liquidation_trigger_threshold


    def liquidate(self):
        if not self.is_liquidable():
            return

        # Calculate the amount needed to restore the threshold
        total_value = self.get_total_value()
        desired_cash = self.optimal_cash_threshold * total_value
        required_cash = desired_cash - self.cash

        if(self.debug):
            print(f"{Fore.RED}Need to raise: {required_cash} to restore threshold{Style.RESET_ALL}")

        # Sort assets by liquidity value in descending order
        sorted_assets = sorted(self.asset_liquidity_value.items(), key=lambda item: item[1], reverse=False)

        # Attempt to liquidate assets until the required cash amount is raised or assets are exhausted
        for asset, _ in sorted_assets:
            if self.cash >= required_cash:
                break

            # Check the current holdings and price of the asset
            current_holdings = self.assets.get(asset, 0)
            if current_holdings == 0:
                continue  # Skip if no holdings

            asset_price = self.prices.get(asset, 0)
            if asset_price == 0:
                raise ValueError(f"Invalid asset price for {asset}")

            # Calculate the maximum cash that could be obtained by liquidating this asset
            max_cash_obtainable = current_holdings * asset_price

            # Calculate the still required cash to reach the desired threshold
            still_required_cash = desired_cash - self.cash

            # Determine how much of the asset to liquidate
            if max_cash_obtainable + self.cash < desired_cash:
                # Liquidate all holdings of this asset
                self.cash += max_cash_obtainable
                self.assets[asset] = 0
                if(self.debug):
                    print(f"{Fore.RED}Liquidated all of {asset}, raised {max_cash_obtainable}{Style.RESET_ALL}")
            else:
                # Calculate exact amount of the asset to liquidate to meet the requirement
                quantity_to_sell = still_required_cash / asset_price
                self.assets[asset] -= quantity_to_sell
                actual_cash_raised = quantity_to_sell * asset_price
                self.cash += actual_cash_raised
                if(self.debug):
                    print(f"{Fore.RED}Liquidated {quantity_to_sell} of {asset}, raised {actual_cash_raised}{Style.RESET_ALL}")
        
        # Update the total value and required cash after each liquidation
        total_value = self.get_total_value()
        desired_cash = self.optimal_cash_threshold * total_value

        if(self.debug):
            if self.cash >= required_cash:
                print(f"{Fore.RED}Threshold successfully restored{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}Unable to restore threshold, all liquid assets exhausted{Style.RESET_ALL}")


    def print_status(self):
        print("-------------------------------------")
        print("| VAULT STATUS")
        print("| Vault: ", self.name)
        print("| Assets")
        for key, value in self.assets.items():
            print("| * " + key + ": ", value)
        print("| Value: ", self.get_assets_value())
        print("| Cash: ", self.cash)
        print("| Current cash threshold: ", self.get_current_cash_threshold() * 100)
        print("| Is liquidable: ", self.is_liquidable())
        print("-------------------------------------")


vault = Vault("Base", Decimal('0.2'), Decimal('0.05'), Decimal('100')) # 20% - 5%
vault.add_supported_asset("USDe", Decimal('1'), Decimal('0.998'), Decimal('0.2'))
vault.add_supported_asset("WETH", Decimal('2'), Decimal('3410'), Decimal('0.5'))
vault.add_supported_asset("WBTC", Decimal('3'), Decimal('64000'), Decimal('0.3'))
vault.print_status()
vault.mint(Decimal('10000'))
vault.rebalance()
vault.print_status()
vault.redeem(Decimal('2000'))
vault.liquidate()
vault.redeem(Decimal('1500'))
vault.liquidate()
vault.print_status()
print(vault.swing_pricing("WBTC", False))
