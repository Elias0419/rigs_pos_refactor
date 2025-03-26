import logging

logging_configured = False

def setup_logging():
    global logging_configured
    if not logging_configured:

        logger.setLevel(logging.DEBUG)

        fh = logging.FileHandler('rigs_pos.log')
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)',
                                      datefmt='%m/%d/%Y %H:%M:%S')
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        formatter_console = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)')
        ch.setFormatter(formatter_console)
        logger.addHandler(ch)

        logger.propagate = False

        logging_configured = True


logger = logging.getLogger('rigs_pos')

import inspect
import json
import os
import random
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta

from kivy.clock import Clock
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image

from kivymd.app import MDApp
from kivymd.toast import toast
from kivymd.uix.boxlayout import BoxLayout, MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDIconButton, MDRaisedButton
from kivymd.uix.gridlayout import GridLayout, MDGridLayout
from kivymd.uix.label import MDLabel

from barcode.upc import UniversalProductCodeA as upc_a

from barcode_scanner import BarcodeScanner
from button_handlers import ButtonHandler
from database_manager import DatabaseManager
from distributor_manager import DistPopup, DistView
from history_manager import HistoryPopup, HistoryView, OrderDetailsPopup
from inventory_manager import InventoryManagementRow, InventoryManagementView
from label_printer import LabelPrinter, LabelPrintingView
from open_cash_drawer import open_cash_drawer
from order_manager import OrderManager
from popups import Calculator, FinancialSummaryWidget, PopupManager
from receipt_printer import ReceiptPrinter

def log_caller_info(depth=1):
    stack = inspect.stack()

    if depth < len(stack):
        caller_frame = stack[depth]
        file_name = caller_frame.filename
        line_number = caller_frame.lineno
        function_name = caller_frame.function
        logger.warn(f"Called from {file_name}, line {line_number}, in {function_name}")

class Utilities:
    def __init__(self, ref):
        self.app = ref
        self.clock_in_file = ""
        self.popup_manager = PopupManager(None)
        self.font = "images/VarelaRound-Regular.ttf"
        self.screen_brightness = 75

    def adjust_screen_brightness(self, direction):
        if self.screen_brightness < 20:
            logger.info("Brightness is below minimum, setting to minimum of 20")
            self.set_brightness(20)
            return
        elif self.screen_brightness > 80:
            logger.info("Brightness is above maximum, setting to maximum of 80")
            self.set_brightness(80)
            return

        if direction == "down":
            if self.screen_brightness == 20:
                logger.info("Brightness is already at minimum")
            else:
                new_value = max(self.screen_brightness - 10, 20)
                self.set_brightness(new_value)
        elif direction == "up":
            if self.screen_brightness == 80:
                logger.info("Brightness is already at maximum")
            else:
                new_value = min(self.screen_brightness + 10, 80)
                self.set_brightness(new_value)

    def set_brightness(self, value):
        self.screen_brightness = value
        command = ["sudo", "ddccontrol", "-r", "0x10", "-w", str(value), "dev:/dev/i2c-3"]
        try:
            subprocess.Popen(command)
        except subprocess.CalledProcessError:
            logger.warn(f"[Utilities] failed to set brightness\n{e}")




    def check_if_update_was_applied(self):
        try:
            os.remove('update_applied')
            return True
        except FileNotFoundError:
            return False

    def get_update_details(self):
        update_details = []
        try:

            with open('update/update_details', 'r') as f:
                for line in f:
                    update_details.append(line)
            os.remove('update/update_details')
            return update_details
        except:
            pass
        return None

    def initialize_global_variables(self):
        # self.app.admin = False
        self.app.pin_store = "pin_store.json"
        self.app.attendance_log = "attendance_log.json"
        self.app.entered_pin = ""
        self.app.is_guard_screen_displayed = False
        self.app.is_lock_screen_displayed = False
        self.app.disable_lock_screen = False
        self.app.override_tap_time = 0
        self.app.click = 0
        self.app.current_context = "main"
        self.app.theme_cls.theme_style = "Dark"
        self.app.theme_cls.primary_palette = "Brown"
        self.app.selected_categories = []

    def instantiate_modules(self):
        try:
            self.initialize_receipt_printer()
        except: # TODO: Something other than log the error
            logger.info("Receipt Printer was not initialized 1")
        self.app.barcode_scanner = BarcodeScanner(self.app)
        try:
            self.app.db_manager = DatabaseManager("/home/rigs/rigs_pos/db/inventory.db", self.app)
        except:
            self.app.db_manager = DatabaseManager("/home/x/work/python/rigs_pos/db/inventory.db", self.app)
        finally: # TODO: Something other than log the error
            logger.info("Receipt Printer was not initialized (in finally block)")
        self.app.financial_summary = FinancialSummaryWidget(self.app)
        self.app.order_manager = OrderManager(self.app)
        self.app.history_manager = HistoryView(self.app)
        # self.app.order_history_popup = OrderManager(self.app)
        self.app.history_popup = HistoryPopup()
        self.app.inventory_manager = InventoryManagementView()
        self.app.inventory_row = InventoryManagementRow()
        self.app.label_printer = LabelPrinter(self.app)
        self.app.label_manager = LabelPrintingView(self.app)
        self.app.pin_reset_timer = ReusableTimer(5.0, self.reset_pin)
        self.app.calculator = Calculator()
        self.app.dist_manager = DistView(self.app)
        self.app.dist_popup = DistPopup()
        self.app.button_handler = ButtonHandler(self.app)
        self.app.popup_manager = PopupManager(self.app)
        # self.app.wrapper = Wrapper()
        self.app.categories = self.initialize_categories()
        self.app.barcode_cache = self.initialize_barcode_cache()
        self.app.inventory_cache = self.initialize_inventory_cache()

    def initialize_receipt_printer(self):
        try:
            self.app.receipt_printer = ReceiptPrinter(

                self.app, "/home/rigs/rigs_pos/receipt_printer_config.yaml"
            )
        except:
            self.app.receipt_printer = ReceiptPrinter(

                self.app, "/home/x/work/python/rigs_pos/receipt_printer_config.yaml"
            )


    def initialize_barcode_cache(self):

        all_items = self.app.db_manager.get_all_items()
        barcode_cache = {}
        # print(len(barcode_cache))
        for item in all_items:
            barcode = item[0]
            if barcode not in barcode_cache:
                barcode_cache[barcode] = {"items": [item], "is_dupe": False}
            else:
                barcode_cache[barcode]["items"].append(item)
                barcode_cache[barcode]["is_dupe"] = True
        # print(len(barcode_cache))
        return barcode_cache

    def initialize_inventory_cache(self):
        inventory = self.app.db_manager.get_all_items()
        return inventory

    def update_inventory_cache(self):
        inventory = self.app.db_manager.get_all_items()
        self.app.inventory_cache = inventory

    def update_barcode_cache(self, item_details):
        barcode = item_details["barcode"]
        if barcode not in self.app.barcode_cache:
            self.app.barcode_cache[barcode] = {
                "items": [item_details],
                "is_dupe": False,
            }
        else:
            self.app.barcode_cache[barcode]["items"].append(item_details)
            self.app.barcode_cache[barcode]["is_dupe"] = True

    def initialize_categories(self):
        categories = [
            "Cdb",
            "Rig",
            "Nails",
            "Tubes",
            "Hand Pipes",
            "Chillum",
            "Ecig",
            "Butane",
            "Torch",
            "Toro",
            "Slides H",
            "Quartz",
            "Vaporizers",
            "Lighter",
            "9mm Thick",
            "Cleaning",
            "Edible",
            "Bubbler",
            "Sherlock",
            "Spoon",
            "Silicone",
            "Scales",
            "Slides",
            "Imported Glass",
            "Ash Catcher",
            "Soft Glass",
            "Vaporizers",
            "Pendant",
            "Smoker Accessory",
            "Ecig Accessories",
            "Happy Fruit",
            "Concentrate Accessories",
            "Conc. Devices, Atomizers",
            "Erigs And Accessory",
            "Mods Batteries Kits",
        ]
        return categories

    def store_user_details(self, name, pin, admin):
        user_details = {"name": name, "pin": pin, "admin": admin}
        temp_file_path = self.app.pin_store + ".tmp"
        final_file_path = self.app.pin_store

        try:
            if os.path.exists(final_file_path):
                with open(final_file_path, "r") as file:
                    try:
                        data = json.load(file)
                    except json.JSONDecodeError:
                        data = []
            else:
                data = []

            data.append(user_details)

            with open(temp_file_path, "w") as file:
                json.dump(data, file, indent=4)

            os.replace(temp_file_path, final_file_path)

        except Exception as e:
            logger.warn(f"[Utilities]: store_user_details\n {e}")
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    def validate_pin(self, entered_pin):
        if not os.path.exists(self.app.pin_store):
            self.store_user_details("default", entered_pin, False)
            return {"name": "default", "admin": False}, True
        with open(self.app.pin_store, "r") as file:
            users = json.load(file)
            for user in users:
                if user["pin"] == entered_pin:
                    return {"name": user["name"], "admin": user["admin"]}, True
        return False

    def time_until_end_of_shift(self):
        now = datetime.now()
        end_of_shift = datetime(now.year, now.month, now.day, 23)
        if now.hour >= 23:
            end_of_shift += timedelta(days=1)
        seconds_until_end = (end_of_shift - now).total_seconds()
        return seconds_until_end

    # def time_until_end_of_shift(self): # testing
    #
    #     hour = 11
    #     minute = 3
    #     now = datetime.now()
    #     end_of_shift = datetime(now.year, now.month, now.day, hour, minute)
    #
    #     if now >= end_of_shift:
    #         end_of_shift += timedelta(days=1)
    #
    #     seconds_until_end = (end_of_shift - now).total_seconds()
    #     return seconds_until_end

    def read_formatted_clock_in_time(self, clock_in_file):
        if os.path.exists(clock_in_file):
            with open(clock_in_file, "r") as file:
                data = json.load(file)
                clock_in_iso = data.get("clock_in", "")
                if clock_in_iso:
                    clock_in_time = datetime.fromisoformat(clock_in_iso)
                    return clock_in_time.strftime("%I:%M %p")
        return ""

    def clock_in(self, entered_pin):
        user_details, authenticated = self.validate_pin(entered_pin)
        if not authenticated:
            return False

        if os.path.exists(self.clock_in_file):
            return

        session_id = str(uuid.uuid4())
        today_str = datetime.now().strftime("%Y-%m-%d")
        prod_file = f"/home/rigs/rigs_pos/{user_details['name']}-{today_str}-{session_id}.json"
        dev_file = f"/home/x/work/python/rigs_pos/{user_details['name']}-{today_str}-{session_id}.json"

        clock_in_successful = False

        try:
            with open(prod_file, "w") as file:
                json.dump(
                    {"clock_in": datetime.now().isoformat(), "session_id": session_id},
                    file,
                )
            self.clock_in_file = prod_file
            clock_in_successful = True
        except FileNotFoundError:
            try:
                with open(dev_file, "w") as file:
                    json.dump(
                        {"clock_in": datetime.now().isoformat(), "session_id": session_id},
                        file,
                    )
                self.clock_in_file = dev_file
                clock_in_successful = True
            except FileNotFoundError:
                logger.warn("[Utilities] clock_in: skipping clock in")

        if not clock_in_successful:
            return False

        self.app.logged_in_user = user_details
        self.update_attendance_log(
            user_details["name"],
            session_id=session_id,
            clock_in=True,
        )
        log_in_time = self.read_formatted_clock_in_time(self.clock_in_file)
        self.time_clock.text = f"Logged in as {user_details['name']}\n[u]Tap here to log out[/u]"
        self.clock_out_event = Clock.schedule_once(
            self.auto_clock_out, self.time_until_end_of_shift()
    )

    def clock_out(self, timestamp=None, auto=False):
        if hasattr(self, "clock_out_event"):
            self.clock_out_event.cancel()
        if os.path.exists(self.clock_in_file):
            session_id = self.extract_session_id(self.clock_in_file)
            os.remove(self.clock_in_file)
            self.update_attendance_log(
                name=self.app.logged_in_user["name"],
                session_id=session_id,
                clock_out=True,
            )
        current_user = self.app.logged_in_user["name"]
        self.app.logged_in_user["name"] = "nobody"
        self.app.admin = False
        try:
            self.app.popup_manager.clock_out_popup.dismiss()
        except:
            pass
        timestamp = timestamp or datetime.now().isoformat()
        self.trigger_guard_and_lock(
            clock_out=True, current_user=current_user, timestamp=timestamp, auto=auto
        )

    def auto_clock_out(self, dt):
        logger.warn(f"called auto clock out\nclock in file: {self.clock_in_file}")
        if os.path.exists(self.clock_in_file):
            logger.warn("path exists")
            session_id = self.extract_session_id(self.clock_in_file)
            os.remove(self.clock_in_file)

            midnight = datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            ) + timedelta(days=1)
            formatted_midnight = midnight.isoformat()
            self.update_attendance_log(
                #self.app.attendance_log,
                name=self.app.logged_in_user["name"],
                session_id=session_id,
                #"auto",
                timestamp=formatted_midnight,
                clock_out=True,

            )

        timestamp = datetime.now().isoformat()
        self.app.utilities.trigger_guard_and_lock(
            auto_clock_out=True, timestamp=timestamp
        )

    def update_attendance_log(
        self, name, session_id, timestamp=None, clock_in=False, clock_out=False
    ):
        log_caller_info(depth=2)
        logger.warn(f"update_attendance_log called with: name={name}, session_id={session_id}, timestamp={timestamp}, clock_in={clock_in}, clock_out={clock_out}")
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        if clock_in:
            self.app.db_manager.insert_attendance_log_entry(name, session_id, timestamp)
        elif clock_out:
            self.app.db_manager.update_attendance_log_entry(session_id, timestamp)
    # def update_attendance_log(
    #     self, log_file, user_name, action, session_id, auto=False, timestamp=None
    # ):
    #     if timestamp is None:
    #         timestamp = datetime.now().isoformat()
    #
    #     entry = {
    #         "name": user_name,
    #         "timestamp": timestamp,
    #         "action": action if not auto else "auto",
    #         "session_id": session_id,
    #     }
    #     if not os.path.exists(log_file):
    #         with open(log_file, "w") as file:
    #             json.dump([entry], file, indent=4)
    #     else:
    #         with open(log_file, "r+") as file:
    #             log = json.load(file)
    #             log.append(entry)
    #             file.seek(0)
    #             json.dump(log, file, indent=4)

    def delete_session_from_log(self, session_id):
        try:
            with open(self.app.attendance_log, "r+") as file:
                log = json.load(file)

                updated_log = [
                    entry for entry in log if entry["session_id"] != session_id
                ]

                file.seek(0)
                file.truncate()
                json.dump(updated_log, file, indent=4)
        except Exception as e:
            logger.warn(f"Utilities: delete_session_from_log\n{e}")

    def extract_session_id(self, filename):
        with open(filename, "r") as file:
            data = json.load(file)
        return data["session_id"]

    def load_attendance_data(self):

        data = self.app.db_manager.retrieve_attendence_log_entries()
        return data

    def organize_sessions(self, data):
        sessions = {}
        for entry in data:
            session_id, user, clock_in, clock_out = (
                entry[0],
                entry[1],
                entry[2],
                entry[3],
            )

            if user not in sessions:
                sessions[user] = {}

            if session_id not in sessions[user]:
                sessions[user][session_id] = {
                    "clock_in": None,
                    "clock_out": None,
                    "session_id": session_id,
                }

            if clock_in:
                sessions[user][session_id]["clock_in"] = clock_in
            if clock_out:
                sessions[user][session_id]["clock_out"] = clock_out

        return sessions

    def format_sessions_for_display(self, sessions):
        formatted_data = []
        for user, user_sessions in sessions.items():
            for session_id, session_details in user_sessions.items():
                if session_details["clock_out"]:
                    clock_in_time = datetime.fromisoformat(session_details["clock_in"])
                    clock_out_time = datetime.fromisoformat(
                        session_details["clock_out"]
                    )
                    duration = clock_out_time - clock_in_time
                    hours, remainder = divmod(duration.total_seconds(), 3600)
                    minutes = remainder // 60
                    formatted_session = {
                        "date": clock_in_time.strftime("%m/%d/%Y"),
                        "name": user,
                        "clock_in": clock_in_time.strftime("%H:%M"),
                        "clock_out": clock_out_time.strftime("%H:%M"),
                        "hours": int(hours),
                        "minutes": int(minutes),
                        "session_id": session_id,
                    }
                    formatted_data.append(formatted_session)
        return formatted_data

    # def display_attendance_log(self): # testing
    #     data = self.load_attendance_data()
    #     sessions = self.organize_sessions(data)
    #     display_data = self.format_sessions_for_display(sessions)
    #     for line in display_data:
    #         print(line)

    def reset_pin_timer(self):
        logger.warn("reset_pin_timer", self.app.pin_reset_timer)
        if self.app.pin_reset_timer is not None:
            self.app.pin_reset_timer.stop()

        self.app.pin_reset_timer.start()

    def reset_pin(self, dt=None):
        # print(
        #     f"reset pin\n{self.app.entered_pin}\n{self.app.popup_manager.pin_input.text}"
        # )

        def update_ui(dt):
            self.app.entered_pin = ""
            if self.app.popup_manager.pin_input is not None:
                self.app.popup_manager.pin_input.text = ""

        Clock.schedule_once(update_ui)

    def calculate_common_amounts(self, total):
        amounts = []
        for base in [1, 5, 10, 20, 50, 100]:
            amount = total - (total % base) + base
            if amount not in amounts and amount >= total:
                amounts.append(amount)
        return amounts

    def update_clock(self, *args):
        current_time = time.strftime("%l:%M %p")
        current_date = time.strftime("%A, %B %d, %Y")

        formatted_time = f"[size=36][b]{current_time}[/b][/size]"
        formatted_date = f"[size=26]{current_date}[/size]"
        self.app.clock_label.font_name = self.font
        self.app.clock_label.text = f"{formatted_time}\n{formatted_date}\n"

        # self.app.clock_label.color = self.get_text_color()

    def update_lockscreen_clock(self, *args):

        self.app.popup_manager.clock_label.text = time.strftime("%I:%M %p")
        self.app.popup_manager.clock_label.color = self.get_text_color()

    def get_text_color(self):
        if self.app.theme_cls.theme_style == "Dark":
            return (1, 1, 1, 1)
        else:
            return (0, 0, 0, 1)

    def reset_to_main_context(self, instance):
        self.app.current_context = "main"
        try:
            self.app.inventory_manager.detach_from_parent()
            self.app.label_manager.detach_from_parent()
        except Exception as e:
            logger.warn(e)

    def create_md_raised_button(

        self,
        text,
        on_press_action,
        size_hint=(None, None),
        font_style="Body1",
        height=50,
    ):
        button = MDRaisedButton(
            text=text,
            on_press=on_press_action,
            size_hint=size_hint,
            font_style=font_style,
            height=height,
        )
        return button

    def dismiss_popups(self, *popups):
        for popup_attr in popups:
            if hasattr(self, popup_attr):
                try:
                    popup = getattr(self, popup_attr)
                    if popup._is_open:
                        popup.dismiss()
                except Exception as e:
                    logger.warn(e)

    def update_display(self):
        self.app.order_layout.clear_widgets()

        for item_id, item_info in self.app.order_manager.items.items():
            item_name = item_info["name"]
            price = item_info["price"]
            item_quantity = item_info["quantity"]
            item_total_price = item_info["total_price"]
            item_discount = item_info.get("discount", {"amount": 0, "percent": False})
            price_times_quantity = price * item_quantity

            if type(item_total_price) is float:

                if item_quantity > 1:
                    if float(item_discount["amount"]) > 0:
                        item_display_text = f"{item_name}"
                        price_display_text = f"${price_times_quantity:.2f} - {float(item_discount['amount']):.2f}\n = ${item_total_price:.2f}"
                        quantity_display_text = f"{item_quantity}"
                    else:
                        item_display_text = f"{item_name}"
                        price_display_text = f"${item_total_price:.2f}"
                        quantity_display_text = f"{item_quantity}"
                else:
                    if float(item_discount["amount"]) > 0:
                        item_display_text = f"{item_name}"
                        price_display_text = f"${price_times_quantity:.2f} - {float(item_discount['amount']):.2f}\n = ${item_total_price:.2f}"
                        quantity_display_text = ""
                    else:
                        item_display_text = f"{item_name}"
                        price_display_text = f"${item_total_price:.2f}"
                        quantity_display_text = ""
            else:
                return
            blue_line = MDBoxLayout(size_hint_x=1, size_hint_y=None, height=1)
            blue_line.md_bg_color = (0.56, 0.56, 1, 1)
            blue_line2 = MDBoxLayout(size_hint_x=1, size_hint_y=None, height=1)
            blue_line2.md_bg_color = (0.56, 0.56, 1, 1)
            blue_line3 = MDBoxLayout(size_hint_x=1, size_hint_y=None, height=1)
            blue_line3.md_bg_color = (0.56, 0.56, 1, 1)
            item_layout = GridLayout(
                orientation="lr-tb", cols=3, rows=2, size_hint=(1, 1)
            )
            item_label_container = BoxLayout(size_hint_x=None, width=550)
            item_label = MDLabel(text=f"[size=20]{item_display_text}[/size]")
            item_label_container.add_widget(item_label)

            spacer = MDLabel(size_hint_x=1)
            # item_layout.add_widget(spacer)
            price_label_container = BoxLayout(size_hint_x=None, width=150)
            price_label = MDLabel(
                text=f"[size=20]{price_display_text}[/size]", halign="right"
            )
            price_label_container.add_widget(price_label)

            quantity_label_container = BoxLayout(size_hint_x=None, width=50)
            quantity_label = MDLabel(text=f"[size=20]{quantity_display_text}[/size]")
            quantity_label_container.add_widget(quantity_label)

            item_layout.add_widget(item_label_container)
            item_layout.add_widget(quantity_label_container)
            item_layout.add_widget(price_label_container)
            item_layout.add_widget(blue_line)
            item_layout.add_widget(blue_line2)
            item_layout.add_widget(blue_line3)

            item_button = MDFlatButton(size_hint=(1, 1))
            item_button.add_widget(item_layout)
            item_button.bind(
                on_press=lambda x, item_button=item_button, item_id=item_id: self.app.popup_manager.show_item_details_popup(
                    item_id, item_button
                )
            )

            self.app.order_layout.add_widget(item_button)
            # self.app.order_layout.add_widget(blue_line)

    def update_financial_summary(self):
        subtotal = self.app.order_manager.subtotal
        total_with_tax = self.app.order_manager.calculate_total_with_tax()
        tax = self.app.order_manager.tax_amount
        discount = self.app.order_manager.order_discount

        self.app.financial_summary_widget.update_summary(
            subtotal, tax, total_with_tax, discount
        )
        Clock.schedule_once(self.app.financial_summary.update_mirror_image, 0.1)

    def manual_override(self, instance):

        current_time = time.time()

        if current_time - self.app.override_tap_time < 0.5:
            sys.exit(42)

        self.app.override_tap_time = current_time

    def set_primary_palette(self, color_name):
        self.app.theme_cls.primary_palette = color_name
        self.save_settings()

    def toggle_dark_mode(self):
        if self.app.theme_cls.theme_style == "Dark":
            self.app.theme_cls.theme_style = "Light"
        else:
            self.app.theme_cls.theme_style = "Dark"
        self.save_settings()

    def on_add_or_bypass_choice(self, choice_text, barcode):
        if choice_text == "Add Custom Item":
            self.app.popup_manager.show_custom_item_popup(barcode)
        elif choice_text == "Add to Database":
            self.app.popup_manager.show_add_to_database_popup(barcode)

    def check_dual_pane_mode(self):
        flag_file_path = "dual_pane_mode.flag"
        if os.path.exists(flag_file_path):
            self.dual_pane_mode = True
            os.remove(flag_file_path)

    def create_main_layout(self, dual_pane_mode=False):

        if dual_pane_mode:
            dual_pane_layout = GridLayout(orientation="lr-tb", cols=2)
        self.main_layout = GridLayout(
            cols=1, spacing=5, orientation="lr-tb", row_default_height=60
        )

        self.top_area_layout = GridLayout(
            cols=4, rows=1, orientation="lr-tb", row_default_height=60, size_hint_x=0.92
        )
        right_area_layout = GridLayout(rows=2, orientation="tb-lr", padding=50)
        self.app.order_layout = GridLayout(
            orientation="tb-lr",
            cols=2,
            rows=10,
            spacing=5,
            row_default_height=60,
            row_force_default=True,
            size_hint_x=1 / 2,
        )
        self.clock_layout = self.create_clock_layout()
        self.top_area_layout.add_widget(self.clock_layout)

        self.center_container = GridLayout(
            rows=2, orientation="tb-lr", size_hint_y=0.01, size_hint_x=0.4
        )
        trash_icon_container = MDBoxLayout(size_hint_y=None, height=100)
        _blank = BoxLayout(size_hint_y=0.9)
        self.app.trash_icon = MDIconButton(
            icon="trash-can",
            pos_hint={"top": 0.75, "right": 0},
            on_press=lambda x: self.confirm_clear_order(),
        )
        trash_icon_container.add_widget(self.app.trash_icon)
        print_icon_container = MDBoxLayout(size_hint_y=None, height=100)

        self.app.print_icon = MDIconButton(
            icon="printer",
            pos_hint={"top": 0.75, "right": 0},
            on_press=lambda x: self.print_draft_receipt(),
        )
        print_icon_container.add_widget(self.app.print_icon)

        calc_icon_container = MDBoxLayout(size_hint_y=None, height=100)

        self.app.calc_icon = MDIconButton(
            icon="calculator",
            pos_hint={"top": 0.75, "right": 0},
            on_press=lambda x: self.app.calculator.show_calculator_popup(),
        )
        calc_icon_container.add_widget(self.app.calc_icon)

        save_icon_container = MDBoxLayout(size_hint_y=None, height=100)
        # _blank = BoxLayout(size_hint_y=0.9)
        self.app.save_icon = MDIconButton(
            icon="content-save",
            pos_hint={"top": 0.90, "right": 0},
            on_press=lambda x: self.app.financial_summary.save_order(),
        )
        save_icon_container.add_widget(self.app.save_icon)
        top_center_container = MDBoxLayout(orientation="vertical", size_hint_y=0.2)
        # center_container.add_widget(trash_icon_container)
        self.time_clock = MDFlatButton(
            text="",
            size_hint_y=0.2,
            on_press=lambda x: self.app.popup_manager.open_clock_out_popup(),
        )
        time_clock_container = GridLayout(orientation="lr-tb", cols=2)
        _blank2 = MDBoxLayout(size_hint_y=0.8)
        clock_icon = MDIconButton(
            icon="clock",
            pos_hint={"top": 1},
            on_press=lambda x: self.app.popup_manager.open_clock_out_popup(),
        )

        brightness_plus_container = MDBoxLayout(size_hint_y=None, height=100)
        # _blank = BoxLayout(size_hint_y=0.9)
        self.app.brightness_plus_icon = MDIconButton(
            icon="plus",
            # pos_hint={"top": 0.75, "right": 0},
            on_press=lambda x: self.adjust_screen_brightness(direction="up"),
        )
        brightness_plus_container.add_widget(self.app.brightness_plus_icon)

        brightness_minus_container = MDBoxLayout(size_hint_y=None, height=100)
        # _blank = BoxLayout(size_hint_y=0.9)
        self.app.brightness_minus_icon = MDIconButton(
            icon="minus",
            # pos_hint={"top": 0.75, "right": 0},
            on_press=lambda x: self.adjust_screen_brightness(direction="down"),
        )
        brightness_minus_container.add_widget(self.app.brightness_minus_icon)

        time_clock_container.add_widget(self.time_clock)
        # time_clock_container.add_widget(clock_icon)
        top_center_container.add_widget(time_clock_container)
        top_center_container.add_widget(_blank2)
        # self.center_container.add_widget(self.mirror_image)
        self.center_container.add_widget(top_center_container)
        self.center_container.add_widget(_blank)
        self.top_area_layout.add_widget(self.center_container)

        right_area_layout.add_widget(self.app.order_layout)

        financial_button = self.create_financial_layout()
        financial_layout = MDGridLayout(size_hint_y=0.2, orientation="lr-tb", cols=2)
        financial_layout.add_widget(MDLabel(size_hint_x=0.4))
        financial_layout.add_widget(financial_button)
        right_area_layout.add_widget(financial_layout)
        self.top_area_layout.add_widget(right_area_layout)
        sidebar = BoxLayout(orientation="vertical", size_hint_x=0.07)
        lock_icon = MDIconButton(
            icon="lock", on_press=lambda x: self.trigger_guard_and_lock(trigger=True)
        )
        self.cost_overlay_icon = MDButtonLabel(
            on_press=lambda x: self.app.popup_manager.show_cost_overlay(),
            text="",
            halign="center",
        )

        sidebar.add_widget(trash_icon_container)
        sidebar.add_widget(save_icon_container)
        sidebar.add_widget(print_icon_container)
        sidebar.add_widget(brightness_plus_container)
        sidebar.add_widget(brightness_minus_container)

        sidebar.add_widget(self.cost_overlay_icon)
        sidebar.add_widget(MDBoxLayout())
        sidebar.add_widget(calc_icon_container)
        sidebar.add_widget(lock_icon)
        # sidebar.add_widget(trash_icon)
        self.top_area_layout.add_widget(sidebar)
        self.main_layout.add_widget(self.top_area_layout)
        # main_layout.add_widget(sidebar)
        button_layout = GridLayout(
            cols=5,
            spacing=20,
            padding=20,
            size_hint_y=0.1,
            size_hint_x=1,
            orientation="lr-tb",
        )

        btn_pay = MDFlatButton(
            text="[b][size=40]PAY[/b][/size]",
            on_press=self.app.button_handler.on_button_press,
            padding=(8, 8),
            font_name=self.font,
            font_style="H6",
            size_hint_x=None,
            _min_width=225,
            # _min_height=100,
            # line_color="white",
        )

        btn_custom_item = MDFlatButton(
            text="[b][size=40]CUSTOM[/b][/size]",
            on_press=self.app.button_handler.on_button_press,
            padding=(8, 8),
            font_name=self.font,
            font_style="H6",
            size_hint_x=None,
            _min_width=225,
            # _min_height=100,
            # line_color="white",
        )

        btn_inventory = MDFlatButton(
            text="[b][size=40]SEARCH[/b][/size]",
            on_press=self.app.button_handler.on_button_press,
            padding=(8, 8),
            font_name=self.font,
            font_style="H6",
            size_hint_x=None,
            _min_width=225,
            # _min_height=100,
            # line_color="white",
        )

        btn_tools = MDFlatButton(
            text="[b][size=40]TOOLS[/b][/size]",
            on_press=self.app.button_handler.on_button_press,
            # on_press=lambda x: self.app.db_manager.retrieve_attendence_log_entries(),
            padding=(8, 8),
            font_style="H1",
            font_name=self.font,
            size_hint_x=None,
            _min_width=225,
            # _min_height=100,
            # line_color="white",
        )
        _blank3 = MDBoxLayout(size_hint_x=None, width=500)
        button_layout.add_widget(_blank3)
        button_layout.add_widget(btn_pay)
        button_layout.add_widget(btn_custom_item)
        button_layout.add_widget(btn_inventory)
        button_layout.add_widget(btn_tools)
        self.main_layout.add_widget(button_layout)

        Clock.schedule_interval(self.check_inactivity, 10)
        Clock.schedule_interval(self.app.barcode_scanner.check_for_scanned_barcode, 0.1)

        self.base_layout = FloatLayout()
        try:
            bg_image = Image(source="images/test.jpg", fit_mode="fill")
            self.base_layout.add_widget(bg_image)

        except Exception as e:
            logger.warn(e)
            with self.base_layout.canvas.before:
                Color(0.78, 0.78, 0.78, 1)
                self.rect = Rectangle(
                    size=self.base_layout.size, pos=self.base_layout.pos
                )

            def update_rect(instance, value):
                instance.rect.size = instance.size
                instance.rect.pos = instance.pos

            self.base_layout.bind(size=update_rect, pos=update_rect)

        self.base_layout.add_widget(self.main_layout)
        if dual_pane_mode:
            blank_layout = self.app.popup_manager.show_lock_screen(dual_pane=True)
            dual_pane_layout.add_widget(self.base_layout)
            dual_pane_layout.add_widget(blank_layout)
            return dual_pane_layout
        else:
            return self.base_layout

    def create_clock_layout(self):

        self.clock_layout = GridLayout(
            orientation="tb-lr",
            rows=6,
            size_hint_x=0.75,
            size_hint_y=1,
            padding=(60, 0, 0, -10),
        )
        mirror_image_container = MDBoxLayout(size_hint=(None, 0.1), width=200)
        self.mirror_image = Image(source="cropped_mirror_snapshot.png")
        mirror_image_container.add_widget(self.mirror_image)
        top_container = BoxLayout(orientation="vertical", size_hint_y=0.1, padding=10)
        saved_orders_container = MDBoxLayout(
            size_hint_y=1, orientation="vertical", spacing=20, padding=(0, 0, 0, 100)
        )
        self.saved_order_title_container = MDBoxLayout(orientation="vertical")
        self.saved_order_title = MDLabel(
            text="", adaptive_height=False, size_hint_y=None, height=50
        )
        self.saved_order_divider = MDBoxLayout(
            size_hint_x=0.5, size_hint_y=None, height=1, md_bg_color=(0, 0, 0, 0)
        )
        self.saved_order_title_container.add_widget(self.saved_order_title)
        self.saved_order_title_container.add_widget(self.saved_order_divider)

        self.saved_order_button1 = MDFlatButton(
            text="",
            on_press=lambda x: self.do_nothing(),
            md_bg_color=(0, 0, 0, 0),
            size_hint=(0.75, None),
            _min_height=50,
            _no_ripple_effect=True,
        )
        self.saved_order_button1_label = MDLabel(text="", halign="left")
        self.saved_order_button1.add_widget(self.saved_order_button1_label)
        self.saved_order_button2 = MDFlatButton(
            text="",
            on_press=lambda x: self.do_nothing(),
            md_bg_color=(0, 0, 0, 0),
            size_hint=(0.75, None),
            _min_height=50,
            _no_ripple_effect=True,
        )
        self.saved_order_button2_label = MDLabel(text="", halign="left")
        self.saved_order_button2.add_widget(self.saved_order_button2_label)

        self.saved_order_button3 = MDFlatButton(
            text="",
            on_press=lambda x: self.do_nothing(),
            md_bg_color=(0, 0, 0, 0),
            size_hint=(0.75, None),
            _min_height=50,
            _no_ripple_effect=True,
        )
        self.saved_order_button3_label = MDLabel(text="", halign="left")
        self.saved_order_button3.add_widget(self.saved_order_button3_label)
        self.saved_order_button4 = MDFlatButton(
            text="",
            on_press=lambda x: self.do_nothing(),
            md_bg_color=(0, 0, 0, 0),
            size_hint=(0.75, None),
            _min_height=50,
            _no_ripple_effect=True,
        )
        self.saved_order_button4_label = MDLabel(text="", halign="left")
        self.saved_order_button4.add_widget(self.saved_order_button4_label)
        self.saved_order_button5 = MDFlatButton(
            text="",
            on_press=lambda x: self.do_nothing(),
            md_bg_color=(0, 0, 0, 0),
            size_hint=(0.75, None),
            _min_height=50,
            _no_ripple_effect=True,
        )
        self.saved_order_button5_label = MDLabel(text="", halign="left")
        self.saved_order_button5.add_widget(self.saved_order_button5_label)
        saved_orders_container.add_widget(self.saved_order_title_container)
        # saved_orders_container.add_widget(self.saved_order_divider)
        saved_orders_container.add_widget(self.saved_order_button1)
        saved_orders_container.add_widget(self.saved_order_button2)
        saved_orders_container.add_widget(self.saved_order_button3)
        saved_orders_container.add_widget(self.saved_order_button4)
        saved_orders_container.add_widget(self.saved_order_button5)
        logo_container = BoxLayout(size_hint_y=0.2, padding=(-250, 0, 0, -150))
        logo = ImageButton(source="images/rigs_logo_test.png")
        logo_container.add_widget(logo)

        register_text = MDLabel(
            text="Cash Register",
            size_hint_y=None,
            font_style="H6",
            height=50,
            font_name=self.font,
            # valign="bottom",
            # halign="center",
        )
        blank_space = MDLabel(
            text="", size_hint_y=1, height=450, valign="top", halign="center"
        )
        clock_container = BoxLayout(size_hint_y=0.2, padding=(-40, 0, 0, -100))
        self.app.clock_label = MDLabel(
            # font_name=self.font,
            text="",
            size_hint_y=None,
            # font_style="H6",
            height=150,
            size_hint_x=1,
            color=self.get_text_color(),
            # markup=True,
            # valign="bottom",
            halign="left",
            # pos_hint={"left": 0.1}

        )
        clock_container.add_widget(self.app.clock_label)
        line_container = MDBoxLayout(
            orientation="horizontal",
            height=1,
            size_hint_y=None,
        )
        blue_line = MDBoxLayout(size_hint_x=0.4)
        blue_line.md_bg_color = (0.56, 0.56, 1, 1)
        blank_line = MDBoxLayout(size_hint_x=0.2)
        blank_line.md_bg_color = (0, 0, 0, 0)
        blank_line2 = MDBoxLayout(size_hint_x=0.2)
        blank_line2.md_bg_color = (0, 0, 0, 0)
        line_container.add_widget(blue_line)
        line_container.add_widget(blank_line)

        line_container.add_widget(blank_line2)
        dual_button_container = MDBoxLayout(padding=10, size_hint_y=None, height=50)
        self.dual_button = MDFlatButton(
            text="",
            # pos_hint={"right": 1},
            on_press=lambda x: self.maximize_dual_popup(),
        )
        dual_button_container.add_widget(self.dual_button)
        top_container.add_widget(register_text)
        top_container.add_widget(line_container)
        self.clock_layout.add_widget(top_container)
        self.clock_layout.add_widget(dual_button_container)
        self.clock_layout.add_widget(mirror_image_container)
        self.clock_layout.add_widget(saved_orders_container)
        self.app.financial_summary.add_saved_orders_to_clock_layout()
        self.clock_layout.add_widget(clock_container)
        self.clock_layout.add_widget(logo_container)

        Clock.schedule_interval(self.update_clock, 1)

        return self.clock_layout

    def print_draft_receipt(self):
        order_details = self.app.order_manager.get_order_details()
        self.app.receipt_printer.print_receipt(order_details, draft=True)

    def modify_clock_layout_for_dual_pane_mode(self):
        self.dual_button.text = f"[b][size=20]Go Back To Dual Pane Mode[/b][/size]"

    def do_nothing(self):
        pass

    def maximize_dual_popup(self):
        try:
            self.app.popup_manager.maximize_dual_popup()
        except:
            pass

    def create_financial_layout(self):
        financial_layout = GridLayout(cols=1, size_hint_x=1 / 3)

        self.app.financial_summary_widget = FinancialSummaryWidget(self)
        financial_layout.add_widget(self.app.financial_summary_widget)

        return financial_layout

    def clear_order_widget(self):
        if self.app.click == 0:
            self.app.click += 1
            self.app.clear_order.text = "Tap to Clear Order"
        elif self.app.click == 1:
            self.app.order_manager.clear_order()
            self.update_display()
            self.update_financial_summary()
            self.app.clear_order.text = f"[size=30]X[/size]"
            self.app.click = 0
        Clock.unschedule(self.reset)
        Clock.schedule_interval(self.reset, 3)

    def confirm_clear_order(self):
        if self.app.click == 0:
            self.app.click += 1

            toast("Tap again to clear order")

            self.app.trash_icon.icon = "trash-can"
            self.app.trash_icon.icon_color = "red"
            Clock.unschedule(self.reset_confirmation)
            Clock.schedule_once(self.reset_confirmation, 3)
        else:
            self.perform_clear_order()

    def perform_clear_order(self):
        self.app.order_manager.clear_order()
        self.update_display()
        self.update_financial_summary()

        self.app.trash_icon.icon = "trash-can-outline"
        self.click = 0

    def reset_confirmation(self, dt):

        self.app.trash_icon.icon = "trash-can-outline"
        self.click = 0

    def dismiss_guard_popup(self):

        self.app.popup_manager.guard_popup.dismiss()
        # self.turn_on_monitor()

    def close_item_popup(self):
        self.dismiss_popups("item_popup")

    def dismiss_add_discount_popup(self):
        self.dismiss_popups("discount_popup")

    def dismiss_bypass_popup(self, instance, barcode):
        self.app.on_add_or_bypass_choice(instance.text, barcode)
        # self.dismiss_popups('popup')

    def close_add_to_database_popup(self):
        self.app.popup_manager.add_to_db_popup.dismiss()

    def on_cash_cancel(self, instance):
        self.app.popup_manager.cash_popup.dismiss()

    def on_adjust_price_cancel(self, instance):
        self.app.popup_manager.adjust_price_popup.dismiss()

    def on_custom_item_cancel(self, instance):
        self.app.popup_manager.custom_item_popup.dismiss()
        self.app.popup_manager.cash_input.text = ""

    def on_custom_cash_cancel(self, instance):
        self.app.popup_manager.custom_cash_popup.dismiss()

    def on_change_done(self, instance):
        self.app.popup_manager.change_popup.dismiss()
        self.app.popup_manager.show_payment_confirmation_popup()
        self.app.popup_manager.make_change_dismiss_event.cancel()

    def split_cancel(self):
        self.app.popup_manager.dismiss_popups("split_payment_numeric_popup")
        self.app.popup_manager.finalize_order_popup.open()

    def split_on_cash_cancel(self):
        self.app.popup_manager.dismiss_popups("split_cash_popup")
        self.app.popup_manager.finalize_order_popup.open()

    def on_split_custom_cash_cancel(self, instance):
        self.app.popup_manager.dismiss_popups("split_custom_cash_popup")

    def trigger_guard_and_lock(
        self,
        trigger=False,
        clock_out=False,
        auto_clock_out=False,
        current_user=None,
        timestamp="",
        auto=False,
    ):
        if clock_out:
            self.app.is_lock_screen_displayed = False
            self.app.disable_lock_screen = False
        if auto_clock_out:
            try:
                self.app.popup_manager.lock_popup.dismiss()
            except:
                pass
            try:
                self.app.popup_manager.guard_popup.dismiss()
            except:
                pass
            self.app.is_lock_screen_displayed = False
            self.app.is_guard_screen_displayed = False
            self.clock_out(timestamp=timestamp, auto=True)
        if current_user is None and self.app.logged_in_user != "nobody":
            current_user = self.app.logged_in_user["name"]
        if trigger:
            self.app.disable_lock_screen = False
            try:
                self.app.popup_manager.lock_popup.dismiss()
            except:
                pass
            self.app.is_lock_screen_displayed = False
            self.app.popup_manager.show_lock_screen()
            self.app.is_lock_screen_displayed = True
        elif (
            not self.app.is_guard_screen_displayed
            and not self.app.is_lock_screen_displayed
        ):
            self.app.popup_manager.show_lock_screen(
                clock_out=clock_out,
                current_user=current_user,
                auto=auto,
                timestamp=timestamp,
            )
            self.app.popup_manager.show_guard_screen()
            self.app.is_lock_screen_displayed = True
            self.app.is_guard_screen_displayed = True
        elif (
            self.app.is_lock_screen_displayed and not self.app.is_guard_screen_displayed
        ):
            self.app.popup_manager.show_guard_screen()
            self.app.is_guard_screen_displayed = True

        elif (
            self.app.is_guard_screen_displayed and not self.app.is_lock_screen_displayed
        ):
            self.app.popup_manager.show_lock_screen()
            self.app.is_lock_screen_displayed = True

    def reboot(self, instance):
        try:
            subprocess.run(["systemctl", "reboot"])
        except Exception as e:
            logger.warn(e)

    def save_settings(self):
        settings = {
            "primary_palette": self.app.theme_cls.primary_palette,
            "theme_style": self.app.theme_cls.theme_style,
        }
        with open("settings.json", "w") as f:
            json.dump(settings, f)

    def load_settings(self):
        try:
            with open("settings.json", "r") as f:
                settings = json.load(f)

                self.app.theme_cls.primary_palette = settings.get(
                    "primary_palette", "Brown"
                )
                self.app.theme_cls.theme_style = settings.get("theme_style", "Light")

                # # check for emergency reboot flag
                # if settings.get("emergency_reboot", True):
                #     self.handle_emergency_reboot()

        except FileNotFoundError as e:
            logger.warn(e)

    def turn_on_monitor(self):
        try:
            subprocess.run(
                ["xrandr", "--output", "HDMI-1", "--brightness", "1"], check=True
            )
        except Exception as e:
            logger.warn(e)

    def check_inactivity(self, *args):
        try:
            idle_time = int(subprocess.check_output(["xprintidle"]).strip())
            # if idle_time > 6000:  # debug
            if idle_time > 600000:  # 10 minutes
                self.trigger_guard_and_lock()
            # if idle_time > 660000:  #debug
            if idle_time > 3600000:  # 1 hour
                subprocess.run(["xset", "dpms", "force", "off"])

        except Exception as e:
            logger.warn(f"Exception in check_inactivity\n{e}")

    def clear_split_numeric_input(self):
        self.app.popup_manager.split_payment_numeric_cash_input.text = ""

    def handle_split_input(self, amount, method):
        if not amount.strip():
            pass
        else:
            try:
                amount = float(amount)
                self.on_split_payment_confirm(amount=amount, method=method)
            except ValueError as e:
                logger.warn(e)

    def on_split_payment_confirm(self, amount, method):
        amount = float(f"{amount:.2f}")

        self.app.popup_manager.split_payment_info["total_paid"] += amount
        self.app.popup_manager.split_payment_info["remaining_amount"] -= amount
        self.app.popup_manager.split_payment_info["payments"].append(
            {"method": method, "amount": amount}
        )

        if method == "Cash":

            self.app.popup_manager.show_split_cash_popup(amount)
            self.app.popup_manager.split_payment_numeric_popup.dismiss()
        elif method == "Debit":
            self.app.popup_manager.show_split_card_confirm(amount, method)
            self.app.popup_manager.split_payment_numeric_popup.dismiss()
        elif method == "Credit":
            self.app.popup_manager.show_split_card_confirm(amount, method)
            self.app.popup_manager.split_payment_numeric_popup.dismiss()

    def split_cash_continue(self, instance):
        tolerance = 0.001
        self.app.popup_manager.dismiss_popups(
            "split_cash_popup", "split_cash_confirm_popup", "split_change_popup"
        )

        if (
            abs(self.app.popup_manager.split_payment_info["remaining_amount"])
            <= tolerance
        ):
            self.finalize_split_payment()
        else:
            self.app.popup_manager.show_split_payment_numeric_popup(
                subsequent_payment=True
            )

    def split_card_continue(self, amount, method):

        tolerance = 0.001
        self.app.popup_manager.dismiss_popups("split_card_confirm_popup")

        if (
            abs(self.app.popup_manager.split_payment_info["remaining_amount"])
            <= tolerance
        ):
            self.finalize_split_payment()
        else:
            self.app.popup_manager.show_split_payment_numeric_popup(
                subsequent_payment=True
            )

    def finalize_split_payment(self):
        self.app.order_manager.set_payment_method("Split")
        self.app.popup_manager.show_payment_confirmation_popup()

    def split_on_custom_cash_confirm(self, amount):

        self.app.popup_manager.split_custom_cash_popup.dismiss()
        input_amount = float(self.app.popup_manager.split_custom_cash_input.text)

        amount = float(amount)

        if input_amount > amount:

            open_cash_drawer()
            change = float(self.app.popup_manager.split_custom_cash_input.text) - amount

            self.app.popup_manager.split_cash_make_change(change, amount)
        else:

            open_cash_drawer()
            self.app.popup_manager.show_split_cash_confirm(amount)

    def split_on_cash_confirm(self, amount):
        self.app.popup_manager.split_cash_popup.dismiss()
        if float(self.app.popup_manager.split_cash_input.text) > amount:
            open_cash_drawer()
            change = float(self.app.popup_manager.split_cash_input.text) - amount

            self.app.popup_manager.split_cash_make_change(change, amount)
        else:

            open_cash_drawer()
            self.app.popup_manager.show_split_cash_confirm(amount)

    def indicate_incorrect_pin(self, layout):
        original_color = layout.background_color
        layout.background_color = [1, 0, 0, 1]
        Clock.schedule_once(
            lambda dt: setattr(layout, "background_color", original_color), 0.5
        )

    # elif instance.text == "TEST": TODO
    #     print("test button")
    #     eel_thread = threading.Thread(target=self.start_eel)
    #     eel_thread.daemon = True
    #     eel_thread.start()

    def dismiss_single_discount_popup(self):
        self.app.popup_manager.discount_item_popup.dismiss()
        self.app.popup_manager.item_popup.dismiss()
        try:
            self.app.popup_manager.discount_amount_input.text = ""
        except:
            pass
        try:
            self.app.popup_manager.discount_popup.dismiss()
        except:
            pass

    def dismiss_entire_discount_popup(self):
        try:
            self.app.popup_manager.custom_discount_order_amount_input.text = ""
        except:
            pass
        self.app.popup_manager.custom_discount_order_popup.dismiss()

    def dismiss_discount_order_popup(self):
        self.app.popup_manager.discount_order_popup.dismiss()
        self.app.financial_summary.order_mod_popup.dismiss()

    def update_confirm_and_close(
        self,
        barcode_input,
        name_input,
        price_input,
        cost_input,
        sku_input,
        category_input,
        popup,
    ):
        self.app.inventory_row.update_item_in_database(
            barcode_input,
            name_input,
            price_input,
            cost_input,
            sku_input,
            category_input,
        )
        self.update_inventory_cache()
        self.app.inventory_manager.refresh_inventory()
        popup.dismiss()

    def inventory_item_confirm_and_close(
        self,
        barcode_input,
        name_input,
        price_input,
        cost_input,
        sku_input,
        category_input,
        popup,
        query=None,
    ):
        try:
            int(barcode_input.text)
        except ValueError as e:
            logger.warn("[Utilities]\n inventory_item_confirm_and_close no barcode")
            self.app.popup_manager.catch_label_printer_missing_barcode()
            return

        if len(name_input.text) > 0:

            self.app.inventory_manager.add_item_to_database(
                barcode_input,
                name_input,
                price_input,
                cost_input,
                sku_input,
                category_input,
            )
            self.app.inventory_manager.refresh_inventory(query=query)
            self.app.popup_manager.inventory_item_popup.dismiss()

    def set_generated_barcode(self, barcode_input):
        unique_barcode = self.generate_unique_barcode()
        self.app.popup_manager.barcode_input.text = unique_barcode

    def generate_unique_barcode(self):
        while True:
            new_barcode = str(
                upc_a(
                    str(random.randint(100000000000, 999999999999)), writer=None
                ).get_fullcode()
            )

            if not self.app.db_manager.barcode_exists(new_barcode):
                return new_barcode

    def apply_categories(self):
        categories_str = ", ".join(self.app.popup_manager.selected_categories)
        self.app.popup_manager.add_to_db_category_input.text = categories_str
        self.app.popup_manager.category_button_popup.dismiss()

    def apply_categories_inv(self):
        categories_str = ", ".join(self.app.popup_manager.selected_categories_inv)
        self.app.popup_manager.add_to_db_category_input_inv.text = categories_str
        self.app.popup_manager.category_button_popup_inv.dismiss()

    def apply_categories_row(self):
        categories_str = ", ".join(self.app.popup_manager.selected_categories_row)
        self.app.popup_manager.add_to_db_category_input_row.text = categories_str
        self.app.popup_manager.category_button_popup_row.dismiss()

    def toggle_category_selection(self, is_active, category):
        if is_active:
            if category not in self.app.popup_manager.selected_categories:
                self.app.popup_manager.selected_categories.append(category)
        else:
            if category in self.app.popup_manager.selected_categories:
                self.app.popup_manager.selected_categories.remove(category)

    def toggle_category_selection_row(self, is_active, category):
        if is_active:
            if category not in self.app.popup_manager.selected_categories_row:
                self.app.popup_manager.selected_categories_row.append(category)

        else:
            if category in self.app.popup_manager.selected_categories_row:
                self.app.popup_manager.selected_categories_row.append(category)

    def toggle_category_selection_inv(self, is_active, category):
        if is_active:
            if category not in self.app.popup_manager.selected_categories_inv:
                self.app.popup_manager.selected_categories_inv.append(category)

        else:
            if category in self.app.popup_manager.selected_categories_inv:
                self.app.popup_manager.selected_categories_inv.append(category)

    def show_add_item_popup(self, scanned_barcode):
        self.barcode = scanned_barcode
        self.app.popup_manager.inventory_item_popup()

    def open_inventory_manager_row(self, instance):
        self.app.current_context = "inventory_item"
        self.app.popup_manager.inventory_item_popup_row(instance)

    def update_apply_categories(self):
        categories_str = ", ".join(self.update_selected_categories)
        self.update_category_input.text = categories_str
        self.update_category_button_popup.dismiss()

    def update_toggle_category_selection(self, instance, category):
        if category in self.update_selected_categories:
            self.update_selected_categories.remove(category)
            instance.text = category
        else:
            self.update_selected_categories.append(category)
            instance.text = f"{category}\n (Selected)"

    # def launch_tetris(self):
    #     subprocess.Popen(['/home/rigs/0/bin/python', 'games/tetris.py'])

    # def reboot(self):
    #     print("reboot")
    #     sys.exit(43)
    #     # try:
    #     #     subprocess.run(["systemctl", "reboot"])
    #     # except Exception as e:
    #     #     print(e)
    #
    # @eel.expose
    # @staticmethod
    # def get_order_history_for_eel():
    #     db_manager = DatabaseManager("db/inventory.db")
    #     order_history = db_manager.get_order_history()
    #     formatted_data = [
    #         {
    #             "order_id": order[0],
    #             "items": order[1],
    #             "total": order[2],
    #             "tax": order[3],
    #             "discount": order[4],
    #             "total_with_tax": order[5],
    #             "timestamp": order[6],
    #             "payment_method": order[7],
    #             "amount_tendered": order[8],
    #             "change_given": order[9],
    #         }
    #         for order in order_history
    #     ]
    #     return formatted_data
    #
    # def start_eel(self):
    #     eel.init("web")
    #     print("start eel")
    #     eel.start("index.html")
    #
    # def handle_emergency_reboot(self):
    #     print("handle_emergency_reboot")
    #     with open("settings.json", "r+") as f:
    #         settings = json.load(f)
    #         settings["emergency_reboot"] = False
    #         f.seek(0)
    #         json.dump(settings, f)
    #         f.truncate()
    #     self.app.popup_manager.unrecoverable_error()

    # def check_inactivity(self, *args):
    #     try:
    #         bus = dbus.SessionBus()
    #         screensaver_proxy = bus.get_object(
    #             "org.freedesktop.ScreenSaver", "/org/freedesktop/ScreenSaver"
    #         )
    #         screensaver_interface = dbus.Interface(
    #             screensaver_proxy, dbus_interface="org.freedesktop.ScreenSaver"
    #         )
    #         idle_time = screensaver_interface.GetSessionIdleTime()
    #
    #         hours, remainder = divmod(idle_time, 3600000)
    #         minutes, seconds = divmod(remainder, 60000)
    #         seconds //= 1000
    #
    #         human_readable_time = f"{hours}h:{minutes}m:{seconds}s"
    #
    #         if idle_time > 600000:  # 10 minutes
    #             # if idle_time > 10000: # 10 secs
    #
    #             self.trigger_guard_and_lock(trigger=False)
    #
    #     except Exception as e:
    #         print(f"Exception in check_inactivity\n{e}")
    #         pass
    #
    # old version of main buttons
    #         # btn_pay = self.create_md_raised_button(
    #     f"[b][size=40]Pay[/b][/size]",
    #     self.app.button_handler.on_button_press,
    #     (8, 8),
    #     "H6",
    # )
    #
    # btn_custom_item = self.create_md_raised_button(
    #     f"[b][size=40]Custom[/b][/size]",
    #     self.app.button_handler.on_button_press,
    #     (8, 8),
    #     "H6",
    # )
    # btn_inventory = self.create_md_raised_button(
    #     f"[b][size=40]Search[/b][/size]",
    #     # lambda x: self.app.popup_manager.maximize_dual_popup(),
    #     self.app.button_handler.on_button_press,
    #     # lambda x: self.app.popup_manager.show_lock_screen(),
    #     (8, 8),
    #     "H6",
    # )
    # btn_tools = self.create_md_raised_button(
    #     f"[b][size=40]Tools[/b][/size]",
    #     self.app.button_handler.on_button_press,
    #     # lambda x: self.app.popup_manager.show_notes_widget(),
    #     # lambda x: self.app.popup_manager.show_cost_overlay(),
    #     # lambda x: self.modify_clock_layout_for_dual_pane_mode(),
    #     # lambda x: self.app.popup_manager.show_dual_inventory_and_label_managers(),
    #     # lambda x: self.enable_dual_pane_mode(),
    #     # lambda x: self.store_user_details("noob","1111",False),
    #     # lambda x: self.app.popup_manager.show_lock_screen(),
    #     # lambda x: self.popup_manager.show_add_or_bypass_popup("132414144141"),
    #     # lambda x: sys.exit(42),
    #     # lambda x: self.app.financial_summary.update_mirror_image(),
    #     (8, 8),
    #     "H6",
    # )


class ReusableTimer:
    def __init__(self, interval, function, *args, **kwargs):
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.timer = None

    def _run(self):
        self.function(*self.args, **self.kwargs)
        self.timer = None

    def start(self):
        if self.timer is not None:
            self.stop()
        self.timer = threading.Timer(self.interval, self._run)
        self.timer.start()

    def stop(self):
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None

    def reset(self):
        self.start()


class ImageButton(ButtonBehavior, Image):
    def __init__(self, **kwargs):
        super(ImageButton, self).__init__(**kwargs)
        self.register_event_type("on_double_tap")
        self.last_tap_time = None
        self.double_tap_time = 0.25
        self.app = MDApp.get_running_app()

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            current_time = Clock.get_time()
            if (
                self.last_tap_time
                and current_time - self.last_tap_time < self.double_tap_time
            ):
                self.dispatch("on_double_tap")
                self.last_tap_time = None
            else:
                self.last_tap_time = current_time
            return True
        return super(ImageButton, self).on_touch_down(touch)

    def on_double_tap(self, *args):
        self.launch_tetris()

    def launch_tetris(self):
        try:
            subprocess.Popen(
                ["/home/rigs/0/bin/python", "games/tetris.py", self.app.logged_in_user]
            )
        except Exception as e:
            print(e)
        # subprocess.Popen(["python", "games/tetris.py", self.app.logged_in_user])


class MDButtonLabel(ButtonBehavior, MDLabel):
    def __init__(self, **kwargs):
        self.on_touch_down_callback = kwargs.pop("on_touch_down_callback", None)
        super().__init__(**kwargs)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if self.on_touch_down_callback:
                self.on_touch_down_callback()
        return super().on_touch_down(touch)
