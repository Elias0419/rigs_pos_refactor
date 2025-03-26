import uuid
import json
import os
from open_cash_drawer import open_cash_drawer

import logging
logger = logging.getLogger('rigs_pos')

class OrderManager:
    _instance = None
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(OrderManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, ref, tax_rate=0.07):
        if not hasattr(self, "_init"):

            self.items = {}
            self.total = 0.0
            self.subtotal = 0.0
            self.tax_amount = 0.0
            self.change_given = 0.0
            self.order_discount = 0.0
            self.amount_tendered = 0.0
            self.tax_rate = tax_rate
            self.payment_method = None
            self._total_with_tax = None
            self.order_id = str(uuid.uuid4())
            self.saved_orders_dir = "saved_orders"
            self.app = ref

            if not os.path.exists(self.saved_orders_dir):
                os.makedirs(self.saved_orders_dir)

            self._init = True

    def _update_total_with_tax(self):
        self.tax_amount = self.total * self.tax_rate
        self._total_with_tax = self.total + self.tax_amount

    def calculate_total_with_tax(self):
        self._update_total_with_tax()
        return self._total_with_tax

    def update_tax_amount(self):
        self.tax_amount = max(self.total * self.tax_rate, 0)
        # print(self.tax_amount)
        return self.tax_amount

    def recalculate_order_totals(self, remove=False):
        if remove:
            self.subtotal = sum(
                float(item["total_price"]) for item in self.items.values()
            )

        self.order_discount = sum(
            float(item.get("discount", {}).get("amount", "0"))
            for item in self.items.values()
        )

        self.total = max(self.subtotal - self.order_discount, 0)

        self.update_tax_amount()
        self._update_total_with_tax()

    # def get_item_id(self, item_name, item_price):
    #     if item_name == "Custom Item":
    #         item_id = str(uuid.uuid4())
    #         return item_id
    #     else:
    #         item_details = self.app.db_manager.get_item_details(name=item_name, price=item_price)
    #         print(item_details)
    #         item_id = item_details["item_id"]
    #
    #         return item_id

    def add_item(self, item_name, item_price, custom_item=False, item_id=None):
        # if custom_item:
        #     item_id = item_id
        # else:
        #     item_id = self.get_item_id(item_name, item_price)

        existing_item = next(
            (
                key
                for key, value in self.items.items()
                if value["name"] == item_name and value["price"] == item_price
            ),
            None,
        )

        if existing_item:
            self.items[existing_item]["quantity"] += 1
            self.items[existing_item]["total_price"] += item_price
        else:
            self.items[item_id] = {
                "name": item_name,
                "price": item_price,
                "quantity": 1,
                "total_price": item_price,
                "discount": {"amount": 0, "percent": False},
            }

        self.total += item_price
        self.subtotal += item_price
        self._update_total_with_tax()
        # print(self.items)

    def remove_item(self, item_name):

        item_to_remove = next(
            (key for key, value in self.items.items() if value["name"] == item_name),
            None,
        )
        if item_to_remove:

            item_discount_amount = float(
                self.items[item_to_remove].get("discount", {}).get("amount", "0")
            )
            removed_item_total = (
                self.items[item_to_remove]["total_price"] - item_discount_amount
            )
            self.subtotal -= removed_item_total
            del self.items[item_to_remove]
            self.recalculate_order_discount()
            self.recalculate_order_totals(remove=True)

    def recalculate_order_discount(self):

        self.order_discount = sum(
            float(item.get("discount", {}).get("amount", "0"))
            for item in self.items.values()
        )

    def get_order_details(self):
        return {
            "order_id": self.order_id,
            "items": self.items,
            "subtotal": self.subtotal,
            "total": self.total,
            "tax_rate": self.tax_rate,
            "tax_amount": self.tax_amount,
            "total_with_tax": self._total_with_tax,
            "discount": self.order_discount,
            "payment_method": self.payment_method,
            "amount_tendered": self.amount_tendered,
            "change_given": self.change_given,
        }

    def clear_order(self):
        self.items = {}
        self.total = 0.0
        self._total_with_tax = None
        self.order_id = str(uuid.uuid4())
        self.order_discount = 0.0
        self.tax_amount = 0.0
        self.subtotal = 0.0
        self.payment_method = None
        self.amount_tendered = 0.0
        self.change_given = 0.0

    def save_order_to_disk(self):
        if not os.path.exists(self.saved_orders_dir):
            os.makedirs(self.saved_orders_dir)

        order_details = self.get_order_details()
        order_filename = f"order_{self.order_id}.json"

        filepath = os.path.join(self.saved_orders_dir, order_filename)

        with open(filepath, "w") as file:
            json.dump(order_details, file)

    def delete_order_from_disk(self, order):
        order_id = order["order_id"]
        order_filename = f"order_{order_id}.json"
        full_path = os.path.join(self.saved_orders_dir, order_filename)
        try:
            os.remove(full_path)
        except Exception as e:
            logger.info(f"[Order Manager] Expected error in delete_order_from_disk\n{e}")

    def load_order_from_disk(self, order):
        order_id = order["order_id"]
        order_filename = f"order_{order_id}.json"
        full_path = os.path.join(self.saved_orders_dir, order_filename)

        try:
            with open(full_path, "r") as file:
                order_data = json.load(file)
        except Exception as e:
            logger.warn(f"[Order Manager] load_order_from_disk\n{e}")
        try:
            self.order_id = order_data["order_id"]
            self.items = order_data["items"]
            self.subtotal = order_data["subtotal"]
            self.total = order_data["total"]
            self.tax_rate = order_data["tax_rate"]
            self.tax_amount = order_data["tax_amount"]
            self._total_with_tax = order_data["total_with_tax"]
            self.order_discount = order_data["discount"]
            self.payment_method = order_data["payment_method"]
            self.amount_tendered = order_data["amount_tendered"]
            self.change_given = order_data["change_given"]
            self.app.utilities.update_display()
            self.app.utilities.update_financial_summary()
            return True
        except Exception as e:
            logger.warn(e)

    def list_all_saved_orders(self):
        all_order_details = []
        for file_name in os.listdir(self.saved_orders_dir):
            if file_name.startswith("order_") and file_name.endswith(".json"):
                full_path = os.path.join(self.saved_orders_dir, file_name)

                try:
                    with open(full_path, "r") as file:
                        order_data = json.load(file)
                        item_names = [
                            item["name"] for item in order_data["items"].values()
                        ]
                        order_dict = {
                            "order_id": order_data["order_id"],
                            "items": item_names,
                        }
                        all_order_details.append(order_dict)
                except Exception as e:
                    logger.warn(f"[Order Manager] Error reading order file {file_name}\n{e}")

        return all_order_details

    def adjust_item_quantity(self, item_id, adjustment):
        if item_id in self.items:
            item = self.items[item_id]
            original_quantity = item["quantity"]
            new_quantity = max(original_quantity + adjustment, 1)
            discount_data = item.get("discount", {"amount": 0, "percent": False})
            discount_amount = float(discount_data["amount"])
            if discount_data["percent"]:
                per_item_discount = item["price"] * discount_amount / 100
            else:
                per_item_discount = discount_amount / original_quantity

            total_discount_for_new_quantity = per_item_discount * new_quantity
            item["discount"] = {
                "amount": total_discount_for_new_quantity,
                "percent": discount_data["percent"],
            }

            single_item_price = float(item["price"])
            item["quantity"] = new_quantity
            item["total_price"] = (
                single_item_price * new_quantity - total_discount_for_new_quantity
            )

            self.recalculate_order_totals(remove=True)

    def adjust_order_to_target_total(self, target_total_with_tax):
        if target_total_with_tax != "":
            adjusted_subtotal = target_total_with_tax / (1 + self.tax_rate)
            discount = self.subtotal - adjusted_subtotal

            if discount < 0 or discount > self.subtotal:
                return False

            self.order_discount = discount
            self.total = max(self.subtotal - self.order_discount, 0)
            self.update_tax_amount()
            self._update_total_with_tax()

            return True

    def add_discount(self, discount_amount, percent=False):
        discount_amount = float(discount_amount)
        if percent:
            discount = self.subtotal * (discount_amount / 100)
            self.order_discount += discount

        else:
            self.order_discount += min(discount_amount, self.subtotal)
        self.total = max(self.subtotal - self.order_discount, 0)
        self.update_tax_amount()
        self._update_total_with_tax()

    def set_payment_method(self, method):
        self.payment_method = method

    def set_payment_details(self, amount_tendered=None, change=None):
        self.amount_tendered = amount_tendered if amount_tendered is not None else 0.0
        self.change_given = change if change is not None else 0.0

    def add_custom_item(self, instance, name="Custom Item", price=0.00):

        # price = self.app.popup_manager.cash_input.text
        item_id = str(uuid.uuid4())
        try:
            price = float(price)
        except Exception as e:
            logger.warn("Exception in add custom item order_manager.py,", e)
            return
        # try:
        custom_item_name = name
        try:
            self.add_item(custom_item_name, price, custom_item=True, item_id=item_id)
        except Exception as e:
            logger.warn("Exception in add custom item order_manager.py,", e)
        try:
            self.app.utilities.update_display()
            self.app.utilities.update_financial_summary()
            self.app.popup_manager.custom_item_popup.dismiss()
            self.app.popup_manager.cash_input.text = ""
        except Exception as e:
            logger.warn(f"[Order Manager]: add_custom_item\n{e}")
            pass

    def finalize_order(self):
        order_details = self.get_order_details()

        order_summary = f"[size=18][b]Order Summary:[/b][/size]\n\n"

        for item_id, item_details in order_details["items"].items():
            item_name = item_details["name"]
            quantity = item_details["quantity"]
            total_price_for_item = item_details["total_price"]

            try:
                total_price_float = float(total_price_for_item)
            except ValueError as e:
                logger.warn(e)
                continue

            order_summary += self.create_order_summary_item(
                item_name, quantity, total_price_float
            )

        order_summary += f"\nSubtotal: ${order_details['subtotal']:.2f}"
        order_summary += f"\nTax: ${order_details['tax_amount']:.2f}"
        if order_details["discount"] > 0:
            order_summary += f"\nDiscount: ${order_details['discount']:.2f}"
        order_summary += (
            f"\n\n[size=20]Total: [b]${order_details['total_with_tax']:.2f}[/b][/size]"
        )

        self.app.popup_manager.show_order_popup(order_summary)

    def create_order_summary_item(self, item_name, quantity, total_price):
        return f"[b]{item_name}[/b] x{quantity} ${total_price:.2f}\n"

    def remove_order_discount(self):
        if float(self.order_discount) > 0:
            self.order_discount = 0

            self.subtotal = sum(
                item["price"] * item["quantity"] - float(item["discount"].get("amount", 0))
                for item in self.items.values()
            )

            self.total = max(self.subtotal, 0)
            self.update_tax_amount()
            self._update_total_with_tax()
            self.recalculate_order_discount()
            self.app.utilities.update_display()
            self.app.utilities.update_financial_summary()

    def remove_single_item_discount(self, item_id):
        if item_id in self.items:
            item = self.items[item_id]
            item_price = float(item["price"])
            item_quantity = int(item["quantity"])
            item["discount"] = {"amount": 0, "percent": False}
            item["total_price"] = max(item_price * item_quantity, 0)
            self.recalculate_order_totals(remove=True)
            self.app.utilities.update_display()
            self.app.utilities.update_financial_summary()
            self.app.popup_manager.item_popup.dismiss()

    def discount_single_item(self, discount_amount, item_id="", percent=False):
        try:
            logger.warn("discount_single_item %s", item_id)
            if item_id in self.items:
                item = self.items[item_id]

                item_price = float(item["price"])
                discount_amount = float(discount_amount)
                item_quantity = int(item["quantity"])

                if percent:
                    if discount_amount >= 100:
                        discount_value = item_price
                    else:
                        discount_value = item_price * discount_amount / 100
                else:
                    if discount_amount >= item_price * item_quantity:
                        discount_value = item_price * item_quantity
                    else:
                        discount_value = discount_amount

                discount_value = float(discount_value)

                item["discount"] = {"amount": str(discount_value), "percent": percent}
                item["total_price"] = max(
                    item_price * item_quantity - discount_value, 0
                )

                self.recalculate_order_totals()

            self.app.utilities.update_display()
            self.app.utilities.update_financial_summary()
            try:
                self.app.popup_manager.discount_amount_input.text = ""
            except:
                pass
            self.app.popup_manager.discount_item_popup.dismiss()
            try:
                self.app.popup_manager.discount_popup.dismiss()
            except:
                pass
            self.app.popup_manager.item_popup.dismiss()
        except:
            pass

    def discount_entire_order(self, discount_amount, percent=False):
        if discount_amount != "":
            try:
                discount_amount = float(discount_amount)
            except ValueError as e:
                logger.warn(f"Order Manager: discount_entire_order\nexception converting to a float\n{e}")

            if percent:
                discount_value = self.subtotal * discount_amount / 100
            else:
                discount_value = discount_amount

            discount_value = min(discount_value, self.subtotal)

            self.order_discount += discount_value
            self.total = max(self.subtotal - self.order_discount, 0)
            try:
                self.update_tax_amount()
                self._update_total_with_tax()
                self.app.utilities.update_display()
                self.app.utilities.update_financial_summary()
            except Exception as e:
                logger.warn(f"[Order Manager]: discount_entire_order\n exception updating totals\n{e}")
            try:
                self.app.popup_manager.custom_discount_order_amount_input.text = ""
            except AttributeError:
                logger.info("[Order Manager]: discount_entire_order\nExpected error popup_manager.custom_discount_order_amount_input.text is None")
            try:
                self.app.popup_manager.discount_order_popup.dismiss()
            except AttributeError:
                logger.info("[Order Manager]: discount_entire_order\nExpected error popup_manager.discount_order_popup is None")
            try:
                self.app.popup_manager.custom_discount_order_popup.dismiss()
            except AttributeError:
                logger.info("[Order Manager]: discount_entire_order\nExpected error popup_manager.custom_discount_order_popup is None")
            self.app.financial_summary.order_mod_popup.dismiss()

    def add_adjusted_price_item(self):
        target_amount = self.app.popup_manager.adjust_price_cash_input.text
        try:
            target_amount = float(target_amount)
        except ValueError as e:
            logger.warn(e)

        self.adjust_order_to_target_total(target_amount)
        self.app.utilities.update_display()
        self.app.utilities.update_financial_summary()
        self.app.popup_manager.adjust_price_popup.dismiss()
        self.app.financial_summary.order_mod_popup.dismiss()

    def remove_item_in(self, item_name, item_price):
        self.remove_item(item_name)
        self.app.utilities.update_display()
        self.app.utilities.update_financial_summary()
        self.app.popup_manager.item_popup.dismiss()

    def adjust_item_quantity_in(self, item_id, item_button, adjustment):
        self.adjust_item_quantity(item_id, adjustment)
        # self.app.popup_manager.item_popup.dismiss()
        # self.app.popup_manager.show_item_details_popup(item_id, item_button)
        self.app.utilities.update_display()
        self.app.utilities.update_financial_summary()

    def handle_credit_payment(self):
        open_cash_drawer()
        self.set_payment_method("Credit")
        self.app.popup_manager.show_payment_confirmation_popup()

    def handle_debit_payment(self):
        open_cash_drawer()
        self.set_payment_method("Debit")
        self.app.popup_manager.show_payment_confirmation_popup()

    def on_cash_confirm(self, instance):
        amount_tendered = float(self.app.popup_manager.cash_payment_input.text)
        total_with_tax = self.app.order_manager.calculate_total_with_tax()
        change = amount_tendered - total_with_tax
        if hasattr(self.app.popup_manager, "cash_popup"):
            self.app.popup_manager.cash_popup.dismiss()
        if hasattr(self.app.popup_manager, "custom_cash_popup"):
            self.app.popup_manager.custom_cash_popup.dismiss()
        open_cash_drawer()
        self.set_payment_method("Cash")
        self.set_payment_details(amount_tendered, change)
        self.app.popup_manager.show_make_change_popup(change)

    def on_custom_cash_confirm(self, instance):
        amount_tendered = float(self.app.popup_manager.custom_cash_input.text)
        total_with_tax = self.app.order_manager.calculate_total_with_tax()
        change = amount_tendered - total_with_tax
        if hasattr(self.app.popup_manager, "cash_popup"):
            self.app.popup_manager.cash_popup.dismiss()
        if hasattr(self.app.popup_manager, "custom_cash_popup"):
            self.app.popup_manager.custom_cash_popup.dismiss()
        open_cash_drawer()
        self.set_payment_method("Cash")
        self.set_payment_details(amount_tendered, change)
        self.app.popup_manager.show_make_change_popup(change)
