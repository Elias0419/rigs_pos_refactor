import json
import os
import time
import uuid
from datetime import datetime

from kivy.clock import Clock
from kivy.properties import ColorProperty
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.utils import get_color_from_hex

from kivymd.color_definitions import palette
from kivymd.toast import toast
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.card import MDCard
from kivymd.uix.floatlayout import MDFloatLayout
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.selectioncontrol import MDCheckbox
from kivymd.uix.textfield import MDTextField

from PIL import Image as PILImage

from inventory_manager import InventoryManagementView, InventoryView
from open_cash_drawer import open_cash_drawer

import logging
logger = logging.getLogger('rigs_pos')


class PopupManager:
    def __init__(self, ref):
        self.app = ref


    def show_update_notification_popup(self, update_details):
        update_details_string = ''
        for line in update_details:
            update_details_string += line
        layout=BoxLayout()
        button = MDFlatButton(text="OK", on_release=self.dismiss_update_notification_popup)
        text=MDLabel(text=update_details_string, halign="center")
        layout.add_widget(text)
        layout.add_widget(button)
        self.update_notification_popup=Popup(content=layout, size_hint=(0.5,0.5), title="Update Applied", overlay_color=(0,0,0,0), separator_height=0)
        self.update_notification_popup.open()

    def dismiss_update_notification_popup(self, _):
        try:
            self.update_notification_popup.dismiss()
        except AttributeError as e:
            logger.info("[PopupManager: Expected error in dismiss_update_notification_popup]\n", e)

    def show_notes_widget(self):
        self.notes_dir = "/home/rigs/rigs_pos/notes"
        os.makedirs(self.notes_dir, exist_ok=True)
        layout = MDBoxLayout(
            size_hint=(1, 1), orientation="vertical", spacing=10, padding=10
        )
        scroll_view = ScrollView(size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True)
        self.top_level_notes_container = MDBoxLayout(
            orientation="vertical",
            size_hint_y=None,
            adaptive_height=True,
            spacing=10,
            padding=10,
        )
        scroll_view.add_widget(self.top_level_notes_container)
        button_container = MDBoxLayout(size_hint_x=1, size_hint_y=None, height=100)
        button = MDFlatButton(
            text="Add Topic",
            on_press=lambda x: self.add_topic(),
            size_hint_x=0.1,
            line_color="white",
            _min_height=100,
            _min_width=100,
        )
        button_container.add_widget(MDBoxLayout(size_hint_x=0.9))
        button_container.add_widget(button)
        layout.add_widget(scroll_view)
        layout.add_widget(button_container)
        popup = Popup(
            title="Notes",
            content=layout,
            size_hint=(None, 0.8),
            width=900,
            pos_hint={"center_x": 0.7},
            overlay_color=(0, 0, 0, 0),
            separator_height=0,
        )
        popup.open()
        self.populate_top_level_notes()

    def populate_top_level_notes(self):
        note_files = []
        for file_name in os.listdir(self.notes_dir):
            if file_name.endswith(".json"):
                full_path = os.path.join(self.notes_dir, file_name)
                with open(full_path, "r", encoding="utf-8") as file:
                    content = json.load(file)

                if self.app.admin or not content.get("admin", False):
                    note_files.append((content["last_modified"], file_name, content))
        note_files.sort(reverse=True, key=lambda x: x[0])
        for last_modified, file_name, content in note_files:

            note_id = file_name.replace(".json", "")

            note_button = MDFlatButton(
                line_color="white",
                line_width=0.2,
                text=content["name"],
                size_hint_x=None,
                size_hint_y=None,
                height=50,
                _min_width=800,
                on_press=lambda x, nid=note_id, name=content["name"], admin=content[
                    "admin"
                ]: self.show_note_details(
                    self.notes_dir, note_id=nid, name=name, admin=admin
                ),
            )
            self.top_level_notes_container.add_widget(note_button)
        self.update_notes_container_height()

    def save_note_content(self, note_id, content):
        content["last_modified"] = datetime.now().isoformat()
        with open(os.path.join(self.notes_dir, f"{note_id}.json"), "w") as file:
            json.dump(content, file)

    def add_topic(self):

        layout = MDBoxLayout(orientation="vertical", spacing=10, padding=10)
        text_input = TextInput(
            multiline=False, size_hint_x=1, size_hint_y=None, height=50
        )
        bottom_layout = MDBoxLayout()
        admin_checkbox = CustomCheckbox(size_hint_x=None, width=50)
        admin_question = MDLabel(text="Admin only?", size_hint_x=None, width=100)
        confirm_button = MDFlatButton(
            text="Confirm",
            on_press=lambda x: self.add_to_top_level_notes(
                text_input.text, admin_checkbox.active
            ),
            _min_height=75,
            _min_width=125,
            line_color="white",
        )
        layout.add_widget(text_input)
        bottom_layout.add_widget(confirm_button)
        bottom_layout.add_widget(MDBoxLayout(size_hint_x=None, width=400))
        if self.app.admin:
            bottom_layout.add_widget(admin_question)
            bottom_layout.add_widget(admin_checkbox)
        layout.add_widget(bottom_layout)
        self.add_topic_popup = FocusPopup(
            size_hint=(0.4, 0.2),
            title="Add Topic",
            content=layout,
            pos_hint={"center_x": 0.7, "center_y": 0.2},
            overlay_color=(0, 0, 0, 0),
            separator_height=0,
        )
        self.add_topic_popup.focus_on_textinput(text_input)
        self.add_topic_popup.open()

    def add_to_top_level_notes(self, text, admin):
        note_id = self.create_note(text, body="", admin=admin)
        self.top_level_notes_container.add_widget(
            MDFlatButton(
                line_color="white",
                line_width=0.2,
                text=text,
                size_hint_x=None,
                size_hint_y=None,
                height=50,
                _min_width=800,
                on_press=lambda x: self.show_note_details(
                    self.notes_dir, note_id, name=text, admin=admin
                ),
            )
        )
        self.add_topic_popup.dismiss()
        self.update_notes_container_height()

    def update_notes_container_height(self):
        total_height = sum(
            child.height for child in self.top_level_notes_container.children
        )
        self.top_level_notes_container.height = total_height

    def show_note_details(self, notes_dir, note_id, name, admin):
        layout = BoxLayout(size_hint=(1, 1), orientation="vertical")
        card = MDCard(size_hint=(1, 1))
        text_input = AutoSaveTextInput(
            notes_dir=notes_dir, note_id=note_id, name=name, admin=admin
        )
        content = text_input.load_note_content()
        text_input.text = content["body"]
        card.add_widget(text_input)
        layout.add_widget(card)
        if admin:
            popup = Popup(
                content=layout,
                title=f"{name} (Admin Only)",
                size_hint=(0.4, 0.8),
                pos_hint={"center_x": 0.25},
                overlay_color=(0, 0, 0, 0),
                separator_height=0,
            )
        else:
            popup = Popup(
                content=layout,
                title=name,
                size_hint=(0.4, 0.8),
                pos_hint={"center_x": 0.25},
                overlay_color=(0, 0, 0, 0),
                separator_height=0,
            )
        popup.open()

    def create_note(self, name, body="", admin=False):
        note_id = str(uuid.uuid4())

        last_modified = datetime.now().isoformat()

        self.save_note_content(
            note_id,
            {
                "name": name,
                "body": body,
                "last_modified": last_modified,
                "admin": admin,
            },
        )
        return note_id

    # def save_note_content(self, note_id, content):
    #     with open(os.path.join(self.notes_dir, f"{note_id}.json"), "w") as file:
    #         json.dump(content, file)
    #
    # def load_note_content(self, note_id):
    #     try:
    #         with open(os.path.join(self.notes_dir, f"{note_id}.json"), "r") as file:
    #             return json.load(file)
    #     except FileNotFoundError:
    #         return {"name": "", "body": ""}

    def show_cost_overlay(self):
        order_count = self.app.order_manager.get_order_details()
        if len(order_count["items"]) == 0:
            temp_layout = MDBoxLayout(orientation="vertical")
            temp_message = MDLabel(
                text=f'This is a test of the "Advanced Discount" feature.\nThe current order is empty so there is nothing here.\n'
            )
            temp_button = Button(
                text="Dismiss", on_press=lambda x: self.temp_popup.dismiss()
            )
            temp_layout.add_widget(temp_message)
            temp_layout.add_widget(temp_button)
            self.temp_popup = Popup(content=temp_layout, size_hint=(0.4, 0.4))
            self.temp_popup.open()
        else:
            order_details_with_cost = self.add_costs_to_order_details()
            total_cost = round(self.calculate_total_cost(order_details_with_cost), 2)
            total_price = round(self.calculate_total_price(order_details_with_cost), 2)
            total_profit = round(total_price - total_cost, 2)

            layout = MDBoxLayout(orientation="vertical")
            card = MDCard(orientation="vertical")
            inner_layout = MDGridLayout(orientation="tb-lr", rows=11)
            header = MDGridLayout(
                orientation="lr-tb",
                cols=11,
                padding=5,
                spacing=5,
                size_hint_y=None,
                height=50,
            )

            header.add_widget(MDLabel(text="", size_hint_x=0.3))
            header.add_widget(MDLabel(text="Price", size_hint_x=0.075, halign="center"))
            header.add_widget(MDLabel(text="Cost", size_hint_x=0.075, halign="center"))
            header.add_widget(
                MDLabel(text="Profit", size_hint_x=0.075, halign="center")
            )
            header.add_widget(
                MDLabel(text="Quantity", size_hint_x=0.075, halign="center")
            )
            header.add_widget(
                MDLabel(text="Total Price", size_hint_x=0.075, halign="center")
            )
            header.add_widget(
                MDLabel(text="Total Cost", size_hint_x=0.075, halign="center")
            )
            header.add_widget(
                MDLabel(text="Total Profit", size_hint_x=0.075, halign="center")
            )
            header.add_widget(MDLabel(text="", size_hint_x=None, width=100))
            header.add_widget(
                MDLabel(text="Discount", size_hint_x=0.075, halign="center")
            )
            header.add_widget(MDLabel(text="", size_hint_x=None, width=20))
            inner_layout.add_widget(header)

            footer = MDGridLayout(
                size_hint_y=0.1, cols=3, orientation="lr-tb", padding=5, spacing=5
            )
            total_price_label = MDLabel(
                text=f"Total Price: {total_price}", size_hint_x=0.33, halign="center"
            )
            total_cost_label = MDLabel(
                text=f"Total Cost: {total_cost}", size_hint_x=0.33, halign="center"
            )
            total_profit_label = MDLabel(
                text=f"Total Profit: {total_profit}", size_hint_x=0.33, halign="center"
            )
            footer.add_widget(total_price_label)
            footer.add_widget(total_cost_label)
            footer.add_widget(total_profit_label)

            item_totals = {"total_prices": [], "total_costs": [], "total_profits": []}

            def update_footer():
                total_price = sum(item_totals["total_prices"])
                total_cost = sum(item_totals["total_costs"])
                total_profit = sum(item_totals["total_profits"])

                total_price_label.text = f"Total Price: {round(total_price, 2)}"
                total_cost_label.text = f"Total Cost: {round(total_cost, 2)}"
                total_profit_label.text = f"Total Profit: {round(total_profit, 2)}"

            def set_item(
                discount,
                item_index,
                item_data,
                discount_button,
                discount_type_button,
                total_price_text,
                total_profit_text,
            ):

                discount_value = float(discount)
                discount_type = discount_type_button.text

                if discount_type == "%":
                    discount_amount = (item_data["price"] * item_data["quantity"]) * (
                        discount_value / 100
                    )
                else:
                    discount_amount = discount_value

                new_total_price = (
                    item_data["price"] * item_data["quantity"]
                ) - discount_amount
                new_profit = new_total_price - (
                    item_data["cost"] * item_data["quantity"]
                )

                total_price_text.text = str(round(new_total_price, 2))
                total_profit_text.text = str(round(new_profit, 2))
                discount_button.text = str(discount_value)

                item_totals["total_prices"][item_index] = new_total_price
                item_totals["total_costs"][item_index] = (
                    item_data["cost"] * item_data["quantity"]
                )
                item_totals["total_profits"][item_index] = new_profit

                update_footer()

            def create_menu_item(
                discount,
                item_index,
                item_data,
                discount_button,
                discount_type_button,
                total_price_text,
                total_profit_text,
            ):
                return {
                    "text": str(discount),
                    "viewclass": "OneLineListItem",
                    "on_release": lambda: set_item(
                        discount,
                        item_index,
                        item_data,
                        discount_button,
                        discount_type_button,
                        total_price_text,
                        total_profit_text,
                    ),
                }

            def create_menu_item_type(i, item_index, discount_button):
                return {
                    "text": str(i),
                    "viewclass": "OneLineListItem",
                    "on_release": lambda: self.set_discount_type(discount_button, i),
                }

            for item_index, (item_id, item_data) in enumerate(
                order_details_with_cost["items"].items()
            ):
                item_layout = MDGridLayout(
                    orientation="lr-tb",
                    cols=11,
                    padding=5,
                    spacing=5,
                    size_hint_y=None,
                    height=50,
                )
                item_price = round(item_data["price"], 2)
                item_cost = round(item_data["cost"], 2)
                item_quantity = item_data["quantity"]
                item_name = item_data["name"]

                item_profit = round(item_price - item_cost, 2)
                price_x_quantity = round(item_price * item_quantity, 2)
                cost_x_quantity = round(item_cost * item_quantity, 2)
                profit_x_quantity = round(item_profit * item_quantity, 2)

                name_text = MDLabel(text=item_name, size_hint_x=0.3)
                price_text = MDLabel(
                    text=str(item_price), size_hint_x=0.075, halign="center"
                )
                cost_text = MDLabel(
                    text=str(item_cost), size_hint_x=0.075, halign="center"
                )
                profit_text = MDLabel(
                    text=str(item_profit), size_hint_x=0.075, halign="center"
                )
                quantity_text = MDLabel(
                    text=str(item_quantity), size_hint_x=0.075, halign="center"
                )
                total_price_text = MDLabel(
                    text=str(price_x_quantity), size_hint_x=0.075, halign="center"
                )
                total_cost_text = MDLabel(
                    text=str(cost_x_quantity), size_hint_x=0.075, halign="center"
                )
                total_profit_text = MDLabel(
                    text=str(profit_x_quantity), size_hint_x=0.075, halign="center"
                )
                item_discount_text = MDLabel(
                    text="", size_hint_x=0.075, halign="center"
                )

                self.discount_button = MDRaisedButton(text="0", pos_hint={"top": 1})
                self.discount_type_button = MDRaisedButton(text="%")

                menu_items = [
                    create_menu_item(
                        i,
                        item_index,
                        item_data,
                        self.discount_button,
                        self.discount_type_button,
                        total_price_text,
                        total_profit_text,
                    )
                    for i in [0, 5, 10, 15, 20, 25, 50]
                ]

                self.discount_dropdown = MDDropdownMenu(
                    items=menu_items,
                    caller=self.discount_button,
                    width_mult=4,
                )
                self.discount_button.bind(
                    on_release=lambda x, dd=self.discount_dropdown: dd.open()
                )
                menu_items_type = [
                    create_menu_item_type(
                        i,
                        item_index,
                        self.discount_type_button,
                    )
                    for i in ["%", "$"]
                ]

                self.discount_type_dropdown = MDDropdownMenu(
                    items=menu_items_type,
                    caller=self.discount_type_button,
                    width_mult=4,
                )
                self.discount_type_button.bind(
                    on_release=lambda x, dd=self.discount_type_dropdown: dd.open()
                )

                item_layout.add_widget(name_text)
                item_layout.add_widget(price_text)
                item_layout.add_widget(cost_text)
                item_layout.add_widget(profit_text)
                item_layout.add_widget(quantity_text)
                item_layout.add_widget(total_price_text)
                item_layout.add_widget(total_cost_text)
                item_layout.add_widget(total_profit_text)
                item_layout.add_widget(item_discount_text)
                item_layout.add_widget(self.discount_button)
                item_layout.add_widget(self.discount_type_button)

                inner_layout.add_widget(item_layout)

                item_totals["total_prices"].append(price_x_quantity)
                item_totals["total_costs"].append(cost_x_quantity)
                item_totals["total_profits"].append(profit_x_quantity)

            update_footer()

            card.add_widget(inner_layout)
            layout.add_widget(card)
            layout.add_widget(footer)
            popup = Popup(
                size_hint=(0.8, 0.8),
                content=layout,
                overlay_color=(0, 0, 0, 0),
                separator_height=0,
                title="",
            )
            popup.open()

    def set_discount(self, button, text):
        button.text = text
        self.discount_dropdown.dismiss()

    def set_discount_type(self, button, text):
        button.text = text
        self.discount_type_dropdown.dismiss()

    def calculate_total_cost(self, order_details):
        total_cost = 0
        for item_data in order_details["items"].values():
            total_cost += item_data["quantity"] * item_data["cost"]
        return total_cost

    def calculate_total_price(self, order_details):
        total_price = 0
        for item_data in order_details["items"].values():
            total_price += item_data["quantity"] * item_data["price"]
        return total_price

    def get_cost_from_db(self, order_details):
        costs = {}
        item_quantities = {
            item_id: item_data["quantity"]
            for item_id, item_data in order_details["items"].items()
        }
        for item_id, quantity in item_quantities.items():
            item_details = self.app.db_manager.get_item_details(item_id)
            cost = item_details["cost"]
            costs[item_id] = {"quantity": quantity, "cost": cost}
        return costs

    def add_costs_to_order_details(self):
        order_details = self.app.order_manager.get_order_details()
        costs = self.get_cost_from_db(order_details)
        for item_id, item_data in order_details["items"].items():
            if item_id in costs:
                item_data["cost"] = costs[item_id]["cost"]
        return order_details

    def open_clock_out_popup(self):
        if self.app.logged_in_user == "nobody":
            return

        data = self.app.utilities.load_attendance_data()
        open_session = None

        for entry in reversed(data):

            if entry[1] == self.app.logged_in_user["name"] and entry[3] == None:
                open_session = entry
                break
            elif entry[3] is not None:
                break
        if open_session:
            clock_in_time = datetime.fromisoformat(open_session[2])
            clock_out_time = datetime.now()
            duration = clock_out_time - clock_in_time
            hours, remainder = divmod(duration.total_seconds(), 3600)
            minutes = remainder // 60
            session_info = f"{self.app.logged_in_user['name']}: {clock_in_time.strftime('%H:%M')} - {clock_out_time.strftime('%H:%M')}; {int(hours)}h {int(minutes)}m"
        else:
            session_info = "No open session found."

        layout = MDBoxLayout(orientation="vertical")
        card = MDCard()
        if open_session:
            self.clock_out_message = MDLabel(
                text=f"I'll add the time entry\n\n[b][size=20]{session_info}[/size][/b]\n\nto the time sheet and log you out.\n\nIs that what you want to do?\n\n",
                halign="center",
            )
        else:
            self.clock_out_message = MDLabel(text=f"{session_info}")
        card.add_widget(self.clock_out_message)
        layout.add_widget(card)

        button_layout = MDGridLayout(cols=2, size_hint_y=0.2)
        confirm_button = MDFlatButton(
            text="Confirm",
            size_hint=(1, 1),
            on_press=lambda x: self.app.utilities.clock_out() if open_session else None,
        )
        cancel_button = MDFlatButton(
            text="Cancel",
            size_hint=(1, 1),
            on_press=lambda x: self.clock_out_popup.dismiss(),
        )
        button_layout.add_widget(confirm_button)
        button_layout.add_widget(cancel_button)
        layout.add_widget(button_layout)
        self.clock_out_popup = Popup(
            content=layout,
            title="Clock Out",
            size_hint=(0.4, 0.4),
            separator_height=0,
            overlay_color=(0, 0, 0, 0),
            pos_hint={"top": 1},
        )
        self.clock_out_popup.open()

    def show_attendence_log(self, filter=False, filter_name=None):
        data = self.app.utilities.load_attendance_data()
        users = self.read_names_from_json()
        sessions = self.app.utilities.organize_sessions(data)
        display_data = self.app.utilities.format_sessions_for_display(sessions)
        container = GridLayout(orientation="tb-lr", rows=3)
        header = GridLayout(
            orientation="lr-tb",
            cols=9,
            size_hint_y=None,
            height=40,
            padding=10,
            spacing=10,
        )
        label1 = MDLabel(text="Cash", halign="center", size_hint_x=None, width=100)
        label2 = MDLabel(text="DD", halign="center", size_hint_x=None, width=100)
        label3 = MDLabel(text="Delete", halign="center", size_hint_x=None, width=100)
        for i in range(4):
            globals()[f"_blank{i}"] = MDLabel()
            header.add_widget(globals()[f"_blank{i}"])
        header.add_widget(label1)
        header.add_widget(label2)
        header.add_widget(label3)
        _2blank = MDLabel(size_hint_x=None, width=60)
        _2blank2 = MDLabel(size_hint_x=None, width=100)
        header.add_widget(_2blank)
        header.add_widget(_2blank2)
        footer = MDBoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=60,
            spacing=10,
            padding=10,
        )

        layout = MDBoxLayout(
            orientation="vertical", size_hint_y=None, spacing=10, padding=10
        )
        layout.bind(minimum_height=layout.setter("height"))

        def update_display(user):
            layout.clear_widgets()
            filtered_data = [
                session for session in display_data if session["name"] == user
            ]
            for session in reversed(filtered_data):
                h_layout = GridLayout(
                    orientation="lr-tb", cols=10, size_hint_y=None, height=40
                )

                name_label = MDLabel(text=session["name"])
                date_label = MDLabel(text=session["date"])
                time_label = MDLabel(
                    text=f"{session['clock_in']} - {session['clock_out']}"
                )
                hours_label = MDLabel(text=f"{session['hours']}h {session['minutes']}m")

                cash_checkbox = CustomCheckbox(
                    size_hint_x=None, width=100, _no_ripple_effect=True
                )
                dd_checkbox = CustomCheckbox(
                    size_hint_x=None, width=100, _no_ripple_effect=True
                )
                delete_checkbox = CustomCheckbox(
                    size_hint_x=None, width=100, _no_ripple_effect=True
                )

                notes_button = Button(text="Notes", size_hint_x=None, width=60)
                notes = ""  # TODO
                complete_button = Button(
                    text="Complete",
                    on_press=lambda x, session=session, cash_checkbox=cash_checkbox, dd_checkbox=dd_checkbox, delete_checkbox=delete_checkbox: self.handle_time_sheet_complete(
                        session_id=session["session_id"],
                        date=session["date"],
                        name=session["name"],
                        clock_in=session["clock_in"],
                        clock_out=session["clock_out"],
                        hours=session["hours"],
                        minutes=session["minutes"],
                        cash=cash_checkbox.active,
                        dd=dd_checkbox.active,
                        delete=delete_checkbox.active,
                        notes=notes,
                    ),
                    size_hint_x=None,
                    width=100,
                )

                h_layout.add_widget(name_label)
                h_layout.add_widget(date_label)
                h_layout.add_widget(time_label)
                h_layout.add_widget(hours_label)
                h_layout.add_widget(cash_checkbox)
                h_layout.add_widget(dd_checkbox)
                h_layout.add_widget(delete_checkbox)
                h_layout.add_widget(notes_button)
                h_layout.add_widget(MDLabel(size_hint_x=None, width=20))
                h_layout.add_widget(complete_button)
                layout.add_widget(h_layout)

        for user in users:
            button = MDRaisedButton(
                text=str(user), _min_width=150, _min_height=50, size_hint_y=1
            )
            button.bind(on_press=lambda x, user=user: update_display(user))
            footer.add_widget(button)

        scroll_view = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        scroll_view.add_widget(layout)
        container.add_widget(header)
        container.add_widget(scroll_view)
        container.add_widget(footer)
        self.attendence_log_popup = Popup(
            title="Attendance Log",
            content=container,
            size_hint=(0.9, 0.9),
            overlay_color=(0, 0, 0, 0),
            separator_height=0.5,
        )
        self.attendence_log_popup.open()
        if filter:
            update_display(filter_name)

    def read_names_from_json(self):
        try:
            with open(self.app.pin_store, "r") as file:
                data = json.load(file)
            return [item["name"] for item in data]
        except:
            return []

    def handle_time_sheet_complete(
        self,
        session_id,
        date,
        name,
        clock_in,
        clock_out,
        hours,
        minutes,
        cash,
        dd,
        delete,
        notes,
    ):
        if delete:
            self.open_delete_session_popup(
                session_id, date, name, clock_in, clock_out, hours, minutes, cash, dd
            )
        else:
            self.open_submit_session_popup(
                session_id,
                date,
                name,
                clock_in,
                clock_out,
                hours,
                minutes,
                cash,
                dd,
                notes,
            )

    def open_submit_session_popup(
        self,
        session_id,
        date,
        name,
        clock_in,
        clock_out,
        hours,
        minutes,
        cash,
        dd,
        notes,
    ):
        layout = MDBoxLayout(orientation="vertical")
        card = MDCard()
        text = MDLabel(
            text=f"{name}\n{date}\n{clock_in}-{clock_out}\n\nAdded to the Payment History Database!",
            halign="center",
        )
        button_layout = GridLayout(
            orientation="lr-tb", cols=1, size_hint_y=None, height=60
        )
        dismiss_button = MDFlatButton(
            text="Dismiss",
            size_hint=(1, 1),
            on_press=lambda x: self.submit_session_popup.dismiss(),
        )

        button_layout.add_widget(dismiss_button)
        # button_layout.add_widget(spacer)
        # button_layout.add_widget(cancel_button)
        card.add_widget(text)
        layout.add_widget(card)
        layout.add_widget(button_layout)
        self.submit_session_popup = Popup(
            title="",
            overlay_color=(0, 0, 0, 0),
            separator_height=0,
            content=layout,
            size_hint=(0.4, 0.25),
            on_dismiss=lambda x: self.on_time_sheet_confirm(
                session_id,
                date,
                name,
                clock_in,
                clock_out,
                hours,
                minutes,
                cash,
                dd,
                notes,
            ),
        )
        self.submit_session_popup.open()

    def open_delete_session_popup(
        self, session_id, date, name, clock_in, clock_out, hours, minutes, cash, dd
    ):
        layout = MDBoxLayout(orientation="vertical")
        card = MDCard()
        text = MDLabel(
            text=f"I'm going to delete the user session\n{session_id}\n{name}\n{date}\n{clock_in}-{clock_out}\n\nIf you want to save it to the payment history database instead, go back and uncheck 'delete'",
            halign="center",
        )
        button_layout = GridLayout(
            orientation="lr-tb", cols=3, size_hint_y=None, height=60
        )
        delete_button = MDFlatButton(
            text="Confirm Deletion",
            size_hint=(1, 1),
            on_press=lambda x: self.delete_session(session_id, name, delete=True),
        )
        spacer = MDLabel(size_hint_x=None, width=500, size_hint_y=1)
        cancel_button = MDFlatButton(
            text="Go Back",
            size_hint=(1, 1),
            on_press=lambda x: self.delete_session_popup.dismiss(),
        )
        button_layout.add_widget(delete_button)
        button_layout.add_widget(spacer)
        button_layout.add_widget(cancel_button)
        card.add_widget(text)
        layout.add_widget(card)
        layout.add_widget(button_layout)
        self.delete_session_popup = Popup(
            title="",
            overlay_color=(0, 0, 0, 0),
            separator_height=0,
            content=layout,
            size_hint=(0.4, 0.25),
        )
        self.delete_session_popup.open()

    def on_time_sheet_confirm(
        self,
        session_id,
        date,
        name,
        clock_in,
        clock_out,
        hours,
        minutes,
        cash,
        dd,
        notes,
    ):
        self.app.db_manager.add_session_to_payment_history(
            session_id, date, name, clock_in, clock_out, hours, minutes, cash, dd, notes
        )
        self.delete_session(session_id, name)
        # self.attendence_log_popup.dismiss()
        # self.show_attendence_log(filter=True, filter_name=name)

    def delete_session(self, session_id, name, delete=False):
        self.app.db_manager.delete_attendance_log_entry(session_id)
        if delete:
            self.delete_session_popup.dismiss()
        self.attendence_log_popup.dismiss()
        self.show_attendence_log(filter=True, filter_name=name)

    def show_add_user_popup(self):
        layout = MDBoxLayout(orientation="vertical")
        name_input = TextInput(hint_text="Name")
        pin_input = TextInput(hint_text="PIN (4 Digits)")
        button_layout = GridLayout(orientation="lr-tb", cols=2)
        buttons_container = MDBoxLayout(orientation="horizontal", size_hint_x=0.7)
        checkbox_container = MDBoxLayout(orientation="horizontal", size_hint_x=0.3)
        confirm_button = MDFlatButton(
            text="Confirm",
            on_press=lambda x: self.on_add_user_confirm(
                name_input.text, pin_input.text, self.admin_checkbox.active
            ),
            size_hint_x=1,
        )
        cancel_button = MDFlatButton(
            text="Cancel",
            size_hint_x=1,
            on_press=lambda x: self.add_user_popup.dismiss(),
        )
        buttons_container.add_widget(confirm_button)
        buttons_container.add_widget(cancel_button)
        admin_label = MDLabel(text="Admin?", size_hint_x=0.1)
        self.admin_checkbox = CustomCheckbox(_no_ripple_effect=True, size_hint_x=0.1)
        checkbox_container.add_widget(admin_label)
        checkbox_container.add_widget(self.admin_checkbox)
        button_layout.add_widget(buttons_container)
        button_layout.add_widget(checkbox_container)
        # button_layout.add_widget(admin_label)
        # button_layout.add_widget(admin_checkbox)
        layout.add_widget(name_input)
        layout.add_widget(pin_input)
        layout.add_widget(button_layout)
        self.add_user_popup = Popup(
            content=layout,
            title="Add User",
            overlay_color=(0, 0, 0, 0),
            separator_height=0,
            size_hint=(0.2, 0.2),
        )
        self.add_user_popup.open()

    def on_add_user_confirm(self, name, pin, admin):
        self.app.utilities.store_user_details(name, pin, admin)
        self.add_user_popup.dismiss()
        toast(f"Added {name}")

    def create_category_popup(self):
        self.selected_categories = []
        categories = self.app.utilities.initialize_categories()
        main_layout = GridLayout(orientation="lr-tb", cols=1, rows=2)
        layout = GridLayout(
            orientation="lr-tb", spacing=5, size_hint=(1, 1), rows=10, cols=5
        )

        layout.bind(minimum_height=layout.setter("height"))

        for category in categories:
            layout.add_widget(self.create_category_item(category))
        main_layout.add_widget(layout)
        button_layout = GridLayout(
            orientation="lr-tb", spacing=5, cols=2, rows=2, size_hint=(1, 0.2)
        )
        confirm_button = MDRaisedButton(
            text="Confirm",
            on_release=lambda instance: self.app.utilities.apply_categories(),
            size_hint=(0.2, 1),
        )

        cancel_button = MDRaisedButton(
            text="Cancel",
            on_release=lambda instance: self.category_button_popup.dismiss(),
            size_hint=(0.2, 1),
        )
        button_layout.add_widget(confirm_button)
        button_layout.add_widget(cancel_button)
        main_layout.add_widget(button_layout)
        self.category_button_popup = Popup(content=main_layout, size_hint=(0.8, 0.8))
        # self.category_button_popup_inv.open()

        return self.category_button_popup

    def open_update_category_button_popup(self):
        self.selected_categories_row = []
        categories = self.app.utilities.initialize_categories()
        main_layout = GridLayout(orientation="lr-tb", cols=1, rows=2)
        layout = GridLayout(
            orientation="lr-tb", spacing=5, size_hint=(1, 1), rows=10, cols=5
        )

        layout.bind(minimum_height=layout.setter("height"))

        for category in categories:
            layout.add_widget(self.create_category_item_row(category))
        main_layout.add_widget(layout)
        button_layout = GridLayout(
            orientation="lr-tb", spacing=5, cols=2, rows=2, size_hint=(1, 0.2)
        )
        confirm_button = MDRaisedButton(
            text="Confirm",
            on_release=lambda instance: self.app.utilities.apply_categories_row(),
            size_hint=(0.2, 1),
        )
        cancel_button = MDRaisedButton(
            text="Cancel",
            on_release=lambda instance: self.category_button_popup_row.dismiss(),
            size_hint=(0.2, 1),
        )
        button_layout.add_widget(confirm_button)
        button_layout.add_widget(cancel_button)
        main_layout.add_widget(button_layout)
        self.category_button_popup_row = Popup(
            content=main_layout, size_hint=(0.8, 0.8)
        )
        self.category_button_popup_row.open()

    def open_category_button_popup_inv(self):
        self.selected_categories_inv = []
        categories = self.app.utilities.initialize_categories()
        main_layout = GridLayout(orientation="lr-tb", cols=1, rows=2)
        layout = GridLayout(
            orientation="lr-tb", spacing=5, size_hint=(1, 1), rows=10, cols=5
        )

        layout.bind(minimum_height=layout.setter("height"))

        for category in categories:
            layout.add_widget(self.create_category_item_inv(category))
        main_layout.add_widget(layout)
        button_layout = GridLayout(
            orientation="lr-tb", spacing=5, cols=2, rows=2, size_hint=(1, 0.2)
        )
        confirm_button = MDRaisedButton(
            text="Confirm",
            on_release=lambda instance: self.app.utilities.apply_categories_inv(),
            size_hint=(0.2, 1),
        )
        cancel_button = MDRaisedButton(
            text="Cancel",
            on_release=lambda instance: self.category_button_popup_inv.dismiss(),
            size_hint=(0.2, 1),
        )
        button_layout.add_widget(confirm_button)
        button_layout.add_widget(cancel_button)
        main_layout.add_widget(button_layout)
        self.category_button_popup_inv = Popup(
            content=main_layout, size_hint=(0.8, 0.8)
        )
        self.category_button_popup_inv.open()

    def create_category_item(self, category):
        checkbox = MDCheckbox(size_hint=(None, None), size=(48, 48))
        checkbox.bind(
            active=lambda instance, is_active, cat=category: self.app.utilities.toggle_category_selection(
                is_active, cat
            )
        )

        container = TouchableMDBoxLayout(
            orientation="horizontal", size_hint_y=None, height=40, checkbox=checkbox
        )
        label = MDLabel(text=category, size_hint_y=None, height=40)

        container.add_widget(checkbox)
        container.add_widget(label)

        return container

    def create_category_item_inv(self, category):
        checkbox = MDCheckbox(size_hint=(None, None), size=(48, 48))
        checkbox.bind(
            active=lambda instance, is_active, cat=category: self.app.utilities.toggle_category_selection_inv(
                is_active, cat
            )
        )
        container = TouchableMDBoxLayout(
            orientation="horizontal", size_hint_y=None, height=40, checkbox=checkbox
        )

        label = MDLabel(text=category, size_hint_y=None, height=40)
        container.add_widget(checkbox)
        container.add_widget(label)
        return container

    def create_category_item_row(self, category):
        checkbox = MDCheckbox(size_hint=(None, None), size=(48, 48))
        checkbox.bind(
            active=lambda instance, is_active, cat=category: self.app.utilities.toggle_category_selection_row(
                is_active, cat
            )
        )
        container = TouchableMDBoxLayout(
            orientation="horizontal", size_hint_y=None, height=40, checkbox=checkbox
        )

        label = MDLabel(text=category, size_hint_y=None, height=40)
        container.add_widget(checkbox)
        container.add_widget(label)
        return container

    def open_category_button_popup(self):
        category_button_popup = self.create_category_popup()
        category_button_popup.open()

    def inventory_item_popup_row(self, instance):

        content = BoxLayout(orientation="vertical", size_hint_y=1, padding=10)
        name_layout = BoxLayout(orientation="horizontal", size_hint_y=0.2)
        name_input = TextInput(text=instance.name, font_size=20)
        name_layout.add_widget(Label(text="Name", size_hint_x=0.2))
        name_layout.add_widget(name_input)
        barcode_layout = BoxLayout(orientation="horizontal", size_hint_y=0.2)

        self.item_barcode_input = TextInput(
            input_filter="int",
            text=instance.barcode if instance.barcode else "",
            font_size=20,
        )
        barcode_layout.add_widget(Label(text="Barcode", size_hint_x=0.2))
        barcode_layout.add_widget(self.item_barcode_input)

        price_layout = BoxLayout(orientation="horizontal", size_hint_y=0.2)
        price_input = TextInput(input_filter="float", text=instance.price, font_size=20)
        price_layout.add_widget(Label(text="Price", size_hint_x=0.2))
        price_layout.add_widget(price_input)

        cost_layout = BoxLayout(orientation="horizontal", size_hint_y=0.2)
        cost_input = TextInput(text=instance.cost, input_filter="float", font_size=20)
        cost_layout.add_widget(Label(text="Cost", size_hint_x=0.2))
        cost_layout.add_widget(cost_input)

        sku_layout = BoxLayout(orientation="horizontal", size_hint_y=0.2)
        sku_input = TextInput(text=instance.sku, font_size=20)
        sku_layout.add_widget(Label(text="SKU", size_hint_x=0.2))
        sku_layout.add_widget(sku_input)

        category_layout = BoxLayout(orientation="horizontal", size_hint_y=0.2)
        self.add_to_db_category_input_row = TextInput(
            text=instance.category, disabled=True, font_size=20
        )
        category_layout.add_widget(Label(text="Categories", size_hint_x=0.2))
        category_layout.add_widget(self.add_to_db_category_input_row)

        content.add_widget(name_layout)
        content.add_widget(barcode_layout)
        content.add_widget(price_layout)
        content.add_widget(cost_layout)
        content.add_widget(sku_layout)
        content.add_widget(category_layout)

        button_layout = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            size_hint_x=1,
            height=100,
            spacing=10,
            padding=10,
        )

        update_details_button = MDRaisedButton(
            text="[b][size=20]Update Details[/b][/size]",
            size_hint=(0.2, 1),
            on_press=lambda x: self.app.utilities.update_confirm_and_close(
                self.item_barcode_input.text,
                name_input.text,
                price_input.text,
                cost_input.text,
                sku_input.text,
                self.add_to_db_category_input_row.text,
                self.inventory_item_update_popup,
            ),
        )

        categories_button = MDRaisedButton(
            text="[b][size=20]Categories[/b][/size]",
            size_hint=(0.2, 1),
            on_press=lambda x: self.open_update_category_button_popup(),
        )

        close_button = MDRaisedButton(
            text="[b][size=20]Close[/b][/size]",
            size_hint=(0.2, 1),
            on_press=lambda x: self.inventory_item_update_popup.dismiss(),
        )

        delete_button = MDFlatButton(
            text="Delete Item",
            md_bg_color="grey",
            on_press=lambda x: self.open_delete_item_popup(
                barcode=self.item_barcode_input.text,
                name=name_input.text,
                price=price_input.text,
                admin=True,
            ),
        )
        _blank = MDBoxLayout(size_hint=(1, 1))
        button_layout.add_widget(update_details_button)
        button_layout.add_widget(categories_button)
        button_layout.add_widget(close_button)
        button_layout.add_widget(_blank)
        if self.app.admin:
            button_layout.add_widget(delete_button)

        content.add_widget(button_layout)

        self.inventory_item_update_popup = Popup(
            title="Item details",
            # pos_hint={"top": 1},
            content=content,
            size_hint=(0.8, 0.6),
            on_dismiss=lambda x: self.app.inventory_manager.reset_inventory_context(),
        )
        self.inventory_item_update_popup.open()

    def open_delete_item_popup(self, barcode="", name="", price=0, admin=False):
        if admin:
            layout = MDBoxLayout(orientation="vertical")
            label = MDLabel(text=f"Permanently Delete\n{name}\nfrom the inventory?")
            container = MDCard()
            container.add_widget(label)
            layout.add_widget(container)
            btn_layout = MDBoxLayout(orientation="horizontal", size_hint_y=0.2)
            confirm_button = MDFlatButton(
                text="Confirm",
                on_press=lambda x: self.delete_item(barcode, name, price),
                size_hint=(1, 1),
            )
            _blank = MDBoxLayout(size_hint=(1, 1))
            cancel_button = MDFlatButton(
                text="Cancel",
                on_press=lambda x: self.delete_item_popup.dismiss(),
                size_hint=(1, 1),
            )
            btn_layout.add_widget(confirm_button)
            btn_layout.add_widget(_blank)
            btn_layout.add_widget(cancel_button)
            layout.add_widget(btn_layout)
            self.delete_item_popup = Popup(content=layout, size_hint=(0.4, 0.4))
            self.delete_item_popup.open()
        else:
            self.do_nothing()

    def delete_item(self, barcode="", name="", price=0):

        item_details = self.app.db_manager.get_item_details(
            barcode=barcode, name=name, price=price
        )
        item_id = item_details["item_id"]

        self.app.db_manager.delete_item(item_id)
        self.delete_item_popup.dismiss()
        self.inventory_item_update_popup.dismiss()
        self.app.inventory_manager.refresh_inventory()

    def show_add_to_database_popup(self, barcode, categories=None):
        content = BoxLayout(orientation="vertical", padding=10)
        name_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        name_input = TextInput()
        name_layout.add_widget(Label(text="Name", size_hint_x=0.2))
        name_layout.add_widget(name_input)
        barcode_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        barcode_input = TextInput(input_filter="int", text=barcode if barcode else "")
        barcode_layout.add_widget(Label(text="Barcode", size_hint_x=0.2))
        barcode_layout.add_widget(barcode_input)

        price_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        price_input = TextInput(input_filter="float")
        price_layout.add_widget(Label(text="Price", size_hint_x=0.2))
        price_layout.add_widget(price_input)

        cost_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        cost_input = TextInput(input_filter="float")
        cost_layout.add_widget(Label(text="Cost", size_hint_x=0.2))
        cost_layout.add_widget(cost_input)

        sku_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        sku_input = TextInput()
        sku_layout.add_widget(Label(text="SKU", size_hint_x=0.2))
        sku_layout.add_widget(sku_input)

        category_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        self.add_to_db_category_input = TextInput(disabled=True)
        category_layout.add_widget(Label(text="Categories", size_hint_x=0.2))
        category_layout.add_widget(self.add_to_db_category_input)

        content.add_widget(name_layout)
        content.add_widget(barcode_layout)
        content.add_widget(price_layout)
        content.add_widget(cost_layout)
        content.add_widget(sku_layout)
        content.add_widget(category_layout)

        button_layout = BoxLayout(
            orientation="horizontal", size_hint_y=None, height="50dp", spacing=10
        )

        button_layout.add_widget(
            MDRaisedButton(
                text="Confirm",
                on_press=lambda _: self.app.db_manager.add_item_to_database(
                    barcode_input.text,
                    name_input.text,
                    price_input.text,
                    cost_input.text,
                    sku_input.text,
                    self.add_to_db_category_input.text,
                ),
            )
        )

        button_layout.add_widget(
            MDRaisedButton(
                text="Close", on_press=lambda x: self.add_to_db_popup.dismiss()
            )
        )
        button_layout.add_widget(
            MDRaisedButton(
                text="Categories", on_press=lambda x: self.open_category_button_popup()
            )
        )

        content.add_widget(button_layout)

        self.add_to_db_popup = Popup(
            title="Item details",
            pos_hint={"top": 1},
            content=content,
            size_hint=(0.8, 0.4),
        )
        self.add_to_db_popup.open()

    def show_add_or_bypass_popup(self, barcode):

        popup_layout = BoxLayout(orientation="vertical", spacing=5)
        self.barcode_label = Label(text=f"Barcode: {barcode} ")
        popup_layout.add_widget(self.barcode_label)
        button_layout = BoxLayout(orientation="horizontal", spacing=5)

        def on_button_press(instance, option):
            self.app.utilities.on_add_or_bypass_choice(option, barcode)
            self.add_or_bypass_popup.dismiss()

        for option in ["Add Custom Item", "Add to Database"]:
            btn = MDRaisedButton(
                text=option,
                on_release=lambda instance, opt=option: on_button_press(instance, opt),
                size_hint=(0.5, 0.4),
            )
            button_layout.add_widget(btn)

        popup_layout.add_widget(button_layout)

        self.add_or_bypass_popup = Popup(
            title="Item Not Found", content=popup_layout, size_hint=(0.6, 0.4)
        )
        self.add_or_bypass_popup.open()

    def show_item_details_popup(self, item_id, item_button):

        item_info = self.app.order_manager.items.get(item_id)
        if item_info:
            item_name = item_info["name"]
            item_quantity = item_info["quantity"]
            item_price = item_info["total_price"]
            original_price = item_price / item_quantity
            item_discount = item_info.get("discount", {"amount": 0, "percent": False})
        item_popup_layout = GridLayout(
            rows=3, cols=3, orientation="lr-tb", size_hint=(1, 1), spacing=5, padding=10
        )
        # details_layout = BoxLayout(orientation="vertical", size_hint=(1, 1))
        _blank = BoxLayout(
            size_hint=(1, 1),
        )
        # _blank2 = BoxLayout(
        #     size_hint=(1, 1),
        # )
        #
        # details_text = MDLabel(
        #     text=f"[size=20]{item_name}\n\n${original_price} x {item_quantity} = ${item_price:.2f}[/size]",
        #     size_hint=(1, 1),
        #     halign="center",
        # )
        # details_button = MDFlatButton(
        #     text="",
        #     size_hint=(1, 1),
        #     md_bg_color="grey",
        #     on_press=lambda x: self.inventory_item_short_details(item_id),
        # )
        # details_button.add_widget(details_text)
        # details_layout.add_widget(details_button)

        minus_container = AnchorLayout(anchor_x="center", anchor_y="center")
        minus_button = MDFlatButton(
            text=f"[size=100]-[/size]",
            on_press=lambda x: self.app.order_manager.adjust_item_quantity_in(
                item_id, item_button, -1
            ),
        )
        minus_container.add_widget(minus_button)

        # quantity_container = AnchorLayout(anchor_x="center", anchor_y="center")
        # quantity_label = MDLabel(
        #     text=f"[size=30]{str(item_quantity)}[/size]",
        #     halign="center",
        #     valign="center",
        # )
        # quantity_container.add_widget(quantity_label)

        plus_container = AnchorLayout(anchor_x="center", anchor_y="center")
        plus_button = MDFlatButton(
            text=f"[size=75]+[/size]",
            on_press=lambda x: self.app.order_manager.adjust_item_quantity_in(
                item_id, item_button, 1
            ),
        )
        plus_container.add_widget(plus_button)

        dicount_button_layout = BoxLayout(
            orientation="horizontal",
            size_hint=(1, 1),
        )
        if float(item_discount["amount"]) > 0:
            dicount_button_layout.add_widget(
                self.app.utilities.create_md_raised_button(
                    f"[b][size=20]Remove Discount[/size][/b]",
                    lambda x, item_id=item_id: self.app.order_manager.remove_single_item_discount(
                        item_id
                    ),
                    # self.add_discount_popup,
                    (1, 0.8),
                )
            )

        else:
            dicount_button_layout.add_widget(
                self.app.utilities.create_md_raised_button(
                    f"[b][size=20]Add Discount[/size][/b]",
                    lambda x, item_id=item_id: self.open_add_discount_popup(item_id),
                    # self.add_discount_popup,
                    (1, 0.8),
                )
            )

        remove_button_layout = BoxLayout(
            orientation="horizontal",
            size_hint=(1, 1),
        )

        remove_button_layout.add_widget(
            self.app.utilities.create_md_raised_button(
                f"[b][size=20]Remove Item[/size][/b]",
                lambda x: self.app.order_manager.remove_item_in(item_name, item_price),
                (1, 0.8),
            )
        )

        cancel_button_layout = BoxLayout(
            orientation="horizontal",
            size_hint=(1, 1),
        )
        cancel_button_layout.add_widget(
            Button(
                text="Close",
                size_hint=(1, 0.8),
                on_press=lambda x: self.close_item_popup(),
            )
        )

        # item_popup_layout.add_widget(_blank)
        # item_popup_layout.add_widget(details_layout)
        # item_popup_layout.add_widget(_blank2)
        item_popup_layout.add_widget(minus_container)
        item_popup_layout.add_widget(_blank)
        # item_popup_layout.add_widget(quantity_container)
        item_popup_layout.add_widget(plus_container)
        item_popup_layout.add_widget(dicount_button_layout)
        item_popup_layout.add_widget(remove_button_layout)
        item_popup_layout.add_widget(cancel_button_layout)

        button_x, button_y = item_button.to_window(*item_button.pos)
        button_height = item_button.height

        popup_x = button_x / self.app.root.width
        popup_y = (button_y + button_height) / self.app.root.height

        self.item_popup = Popup(
            title="",
            content=item_popup_layout,
            size_hint=(0.4, 0.2),
            # background="images/transparent.png",
            background_color=(0, 0, 0, 0.5),
            separator_height=0,
            overlay_color=(0, 0, 0, 0),
            pos_hint={"x": popup_x, "top": popup_y},
        )
        self.item_popup.open()

    def inventory_item_short_details(self, item_id):

        item_details = self.app.db_manager.get_item_details(item_id=item_id)
        layout = BoxLayout(orientation="vertical")
        content = MDLabel(
            text=f"{item_details['name']}\nPrice: {item_details['price']}\nCost: {item_details['cost']}\n{item_details['sku']}"
        )
        popup = Popup(content=layout, size_hint=(0.2, 0.4))
        button = Button(text="Dismiss", on_press=lambda x: popup.dismiss())
        layout.add_widget(content)
        layout.add_widget(button)
        popup.open()

    def close_item_popup(self):
        if self.item_popup:
            self.item_popup.dismiss()

    def open_add_discount_popup(self, item_id):
        self.add_discount_popup(item_id)

    def handle_discount_toggle(self, percent):
        if percent:
            self.percent_toggle.line_color = "white"
            self.percent_toggle.text = "[size=48][b]%[/b][/size]"
            self.amount_toggle.text = "[size=18]$[/size]"
            self.amount_toggle.line_color = (0, 0, 0, 0)
            self.current_item_discount_type = "percent"
        else:
            self.amount_toggle.line_color = "white"
            self.amount_toggle.text = "[size=48][b]$[/b][/size]"
            self.percent_toggle.text = "[size=18]%[/size]"
            self.percent_toggle.line_color = (0, 0, 0, 0)
            self.current_item_discount_type = "amount"

    def apply_item_discount(self, value, discount_type, item_id):
        percent = discount_type == "percent"
        self.app.order_manager.discount_single_item(
            discount_amount=value, percent=percent, item_id=item_id
        )

    def custom_add_item_discount_popup(self, item_id, instance=None):

        discount_popup_layout = BoxLayout(orientation="vertical", spacing=10)

        self.discount_amount_input = TextInput(
            text="",
            # disabled=True,
            multiline=False,
            input_filter="float",
            font_size=30,
            size_hint_y=None,
            height=50,
        )
        self.discount_popup = self.create_focus_popup(
            title="Add Discount",
            content=discount_popup_layout,
            size_hint=(0.2, 0.4),
            textinput=self.discount_amount_input,
        )
        discount_popup_layout.add_widget(self.discount_amount_input)

        keypad_layout = GridLayout(cols=3, spacing=10)

        numeric_buttons = [
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "",
            "0",
            "",
        ]
        for button in numeric_buttons:

            if button == "":
                blank_space = Label(size_hint=(0.8, 0.8))
                keypad_layout.add_widget(blank_space)
            else:
                btn = Button(
                    text=button,
                    on_press=self.app.button_handler.on_add_discount_numeric_button_press,
                    size_hint=(0.8, 0.8),
                )
                keypad_layout.add_widget(btn)

        amount_button = self.app.utilities.create_md_raised_button(
            "Amount",
            lambda x: self.app.order_manager.discount_single_item(
                discount_amount=self.discount_amount_input.text,
                item_id=item_id,
            ),
            (0.8, 0.8),
        )
        percent_button = self.app.utilities.create_md_raised_button(
            "Percent",
            lambda x: self.app.order_manager.discount_single_item(
                discount_amount=self.discount_amount_input.text,
                percent=True,
                item_id=item_id,
            ),
            (0.8, 0.8),
        )

        cancel_button = Button(
            text="Cancel",
            on_press=lambda x: self.app.utilities.dismiss_single_discount_popup(),
            size_hint=(0.8, 0.8),
        )

        keypad_layout.add_widget(amount_button)
        keypad_layout.add_widget(percent_button)
        keypad_layout.add_widget(cancel_button)
        discount_popup_layout.add_widget(keypad_layout)

        self.discount_popup.open()

    def custom_add_order_discount_popup(self):

        custom_discount_order_popup_layout = BoxLayout(
            orientation="vertical", spacing=10
        )
        self.custom_discount_order_popup = Popup(
            title="Add Discount",
            content=custom_discount_order_popup_layout,
            size_hint=(0.8, 0.8),
        )
        self.custom_discount_order_amount_input = TextInput(
            text="",
            disabled=True,
            multiline=False,
            input_filter="float",
            font_size=30,
            size_hint_y=None,
            height=50,
        )
        custom_discount_order_popup_layout.add_widget(
            self.custom_discount_order_amount_input
        )

        keypad_layout = GridLayout(cols=3, spacing=10)

        numeric_buttons = [
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "",
            "0",
            "",
        ]
        for button in numeric_buttons:

            if button == "":
                blank_space = Label(size_hint=(0.8, 0.8))
                keypad_layout.add_widget(blank_space)
            else:
                btn = Button(
                    text=button,
                    on_press=self.app.button_handler.on_add_order_discount_numeric_button_press,
                    size_hint=(0.8, 0.8),
                )
                keypad_layout.add_widget(btn)

        amount_button = self.app.utilities.create_md_raised_button(
            "Amount",
            lambda x: self.app.order_manager.discount_entire_order(
                discount_amount=self.custom_discount_order_amount_input.text
            ),
            size_hint=(0.8, 0.8),
        )
        percent_button = self.app.utilities.create_md_raised_button(
            "Percent",
            lambda x: self.app.order_manager.discount_entire_order(
                discount_amount=self.custom_discount_order_amount_input.text,
                percent=True,
            ),
            size_hint=(0.8, 0.8),
        )

        cancel_button = Button(
            text="Cancel",
            on_press=lambda x: self.app.utilities.dismiss_entire_discount_popup(),
            size_hint=(0.8, 0.8),
        )

        keypad_layout.add_widget(amount_button)
        keypad_layout.add_widget(percent_button)
        keypad_layout.add_widget(cancel_button)
        custom_discount_order_popup_layout.add_widget(keypad_layout)

        self.custom_discount_order_popup.open()

    def add_discount_popup(self, item_id, instance=None):
        # print("add_discount_popup", item_id)
        self.current_item_discount_type = "percent"
        discount_item_popup_layout = GridLayout(
            orientation="tb-lr", spacing=5, cols=1, rows=3
        )
        self.discount_item_popup = Popup(
            title="Add Discount",
            content=discount_item_popup_layout,
            size_hint=(0.2, 0.6),
        )

        toggle_container = MDGridLayout(orientation="lr-tb", cols=2, size_hint_y=0.2)
        self.percent_toggle = MDFlatButton(
            text="[size=48][b]%[/b][/size]",
            size_hint=(1, 1),
            line_color="white",
            on_press=lambda x: self.handle_discount_toggle(percent=True),
        )
        self.amount_toggle = MDFlatButton(
            text="[size=18]$[/size]",
            size_hint=(1, 1),
            on_press=lambda x: self.handle_discount_toggle(percent=False),
        )
        toggle_container.add_widget(self.percent_toggle)
        # if self.app.admin:
        #     toggle_container.add_widget(self.amount_toggle)
        # if self.app.admin:
        #     discounts = [5, 10, 15, 20, 30, 40, 50, 100]
        # else:
        #     discounts = [5, 10, 15]
        toggle_container.add_widget(self.amount_toggle) # revert
        discounts = [5, 10, 15, 20, 30, 40, 50, 100] # revert
        discount_item_layout = GridLayout(orientation="lr-tb", cols=2, spacing=10)
        for discount in discounts:
            discount_button = MDFlatButton(
                md_bg_color=(0.5, 0.5, 0.5, 0.25),
                text=f"[b][size=28]{str(discount)}[/b][/size]",
                size_hint=(1, 1),
                on_press=lambda x, d=discount: self.apply_item_discount(
                    d, self.current_item_discount_type, item_id
                ),
            )
            discount_item_layout.add_widget(discount_button)

        button_layout = GridLayout(
            orientation="lr-tb", spacing=5, cols=2, rows=1, size_hint_y=0.2
        )
        custom_button = Button(
            text="Custom",
            on_press=lambda x: self.custom_add_item_discount_popup(item_id=item_id),
        )
        cancel_button = Button(
            text="Cancel",
            on_press=lambda x: self.app.utilities.dismiss_single_discount_popup(),
        )
        # if self.app.admin:
        #     button_layout.add_widget(custom_button)
        button_layout.add_widget(custom_button) # revert
        button_layout.add_widget(cancel_button)
        discount_item_popup_layout.add_widget(toggle_container)
        discount_item_popup_layout.add_widget(discount_item_layout)
        discount_item_popup_layout.add_widget(button_layout)

        self.discount_item_popup.open()

    def add_order_discount_popup(self):
        self.current_discount_type = "percent"
        discount_order_popup_layout = GridLayout(
            orientation="tb-lr", spacing=5, cols=1, rows=3
        )
        self.discount_order_popup = Popup(
            title="Add Discount",
            content=discount_order_popup_layout,
            size_hint=(0.2, 0.6),
        )

        toggle_container = MDGridLayout(orientation="lr-tb", cols=2, size_hint_y=0.2)
        self.percent_toggle = MDFlatButton(
            text="[size=48][b]%[/b][/size]",
            size_hint=(1, 1),
            line_color="white",
            on_press=lambda x: self.handle_order_discount_toggle(percent=True),
        )
        # if self.app.admin: # revert
        self.amount_toggle = MDFlatButton(
            text="[size=18]$[/size]",
            size_hint=(1, 1),
            on_press=lambda x: self.handle_order_discount_toggle(percent=False),
        )
        toggle_container.add_widget(self.percent_toggle)
        toggle_container.add_widget(self.amount_toggle)


        # if self.app.admin:
        #     discounts = [5, 10, 15, 20, 30, 40, 50, 100]
        # else:
        #     discounts = [5, 10, 15]
        discounts = [5, 10, 15, 20, 30, 40, 50, 100] # revert
        discount_layout = GridLayout(orientation="lr-tb", cols=2, spacing=10)
        for discount in discounts:
            discount_button = MDFlatButton(
                md_bg_color=(0.5, 0.5, 0.5, 0.25),
                text=f"[b][size=28]{str(discount)}[/b][/size]",
                size_hint=(1, 1),
                on_press=lambda x, d=discount: self.apply_discount(d),
            )
            discount_layout.add_widget(discount_button)

        button_layout = GridLayout(
            orientation="lr-tb", spacing=5, cols=2, rows=1, size_hint_y=0.2
        )
        # if self.app.admin: # revert
        custom_button = Button(
            text="Custom",
            on_press=lambda x: self.custom_add_order_discount_popup(),
        )
        button_layout.add_widget(custom_button)
        cancel_button = Button(
            text="Cancel",
            on_press=lambda x: self.app.utilities.dismiss_discount_order_popup(),
        )
        button_layout.add_widget(cancel_button)
        discount_order_popup_layout.add_widget(toggle_container)
        discount_order_popup_layout.add_widget(discount_layout)
        discount_order_popup_layout.add_widget(button_layout)

        self.discount_order_popup.open()

    def handle_order_discount_toggle(self, percent):
        if percent:
            self.percent_toggle.line_color = "white"
            self.percent_toggle.text = "[size=48][b]%[/b][/size]"
            self.amount_toggle.text = "[size=18]$[/size]"
            self.amount_toggle.line_color = (0, 0, 0, 0)
            self.current_discount_type = "percent"
        else:
            self.amount_toggle.line_color = "white"
            self.amount_toggle.text = "[size=48][b]$[/b][/size]"
            self.percent_toggle.text = "[size=18]%[/size]"
            self.percent_toggle.line_color = (0, 0, 0, 0)
            self.current_discount_type = "amount"

    def apply_discount(self, value, military=False):
        if military:
            self.current_discount_type = "percent"
        percent = self.current_discount_type == "percent"
        self.app.order_manager.discount_entire_order(
            discount_amount=value, percent=percent
        )

    def show_theme_change_popup(self):
        layout = GridLayout(cols=4, rows=8, orientation="lr-tb")

        button_layout = GridLayout(
            cols=4, rows=8, orientation="lr-tb", spacing=5, size_hint=(1, 0.4)
        )
        button_layout.bind(minimum_height=button_layout.setter("height"))

        for color in palette:
            button = self.app.utilities.create_md_raised_button(
                color,
                lambda x, col=color: self.app.utilities.set_primary_palette(col),
                (0.8, 0.8),
            )

            button_layout.add_widget(button)

        dark_btn = MDRaisedButton(
            text="Dark Mode",
            size_hint=(0.8, 0.8),
            md_bg_color=(0, 0, 0, 1),
            on_release=lambda x, col=color: self.app.utilities.toggle_dark_mode(),
        )
        button_layout.add_widget(dark_btn)
        layout.add_widget(button_layout)

        self.theme_change_popup = Popup(
            title="",
            content=layout,
            size_hint=(0.6, 0.6),
            background="images/transparent.png",
            background_color=(0, 0, 0, 0),
            separator_height=0,
        )
        self.theme_change_popup.open()

    def show_system_popup(self):
        float_layout = FloatLayout()

        system_buttons = ["Change Theme", "Reboot System", "Restart App", "TEST"]

        for index, tool in enumerate(system_buttons):
            btn = MDRaisedButton(
                text=tool,
                size_hint=(1, 0.15),
                pos_hint={"center_x": 0.5, "center_y": 1 - 0.2 * index},
                on_press=self.app.button_handler.on_system_button_press,
            )
            float_layout.add_widget(btn)

        self.system_popup = Popup(
            content=float_layout,
            size_hint=(0.2, 0.6),
            title="",
            background="images/transparent.png",
            background_color=(0, 0, 0, 0),
            separator_height=0,
        )
        self.system_popup.open()

    def show_label_printing_view(self, dual_pane_mode=False):
        if hasattr(self, "label_printing_view") and self.label_printing_view.parent:
            self.label_printing_view.parent.remove_widget(self.label_printing_view)

        inventory = self.app.inventory_cache
        self.label_printing_view = self.app.label_manager

        if dual_pane_mode:
            self.app.label_manager.dual_pane_mode = True
            # try:
            self.label_printing_view.show_inventory_for_label_printing(
                inventory, dual_pane_mode=True
            )
            container = MDGridLayout(orientation="tb-lr", rows=4, size_hint_x=0.6)
            button_container = MDBoxLayout(
                size_hint_y=0.05, orientation="horizontal", spacing=10, padding=5
            )
            self.view_container = MDBoxLayout(size_hint_y=0.42)
            self.queue_container = MDBoxLayout(size_hint_y=0.48)
            self.print_queue_embed = self.app.label_manager.show_print_queue(embed=True)
            self.queue_container.add_widget(self.print_queue_embed)
            button = MDFlatButton(
                text="Go Back to Cash Register",
                md_bg_color="grey",
                size_hint=(1, 1),
                _no_ripple_effect=True,
                on_press=lambda x: self.minimize_dual_popup(),
            )
            button2 = MDFlatButton(
                text="Exit Dual Pane Mode",
                md_bg_color="grey",
                size_hint=(1, 1),
                _no_ripple_effect=True,
                on_press=lambda x: self.exit_dual_pane_mode(),
            )
            button_container.add_widget(button)
            button_container.add_widget(button2)
            if self.label_printing_view.parent:
                self.label_printing_view.parent.remove_widget(self.label_printing_view)
            self.view_container.add_widget(self.label_printing_view)
            divider = MDBoxLayout(size_hint_y=None, height=1, md_bg_color="blue")
            container.add_widget(self.view_container)
            container.add_widget(divider)
            container.add_widget(self.queue_container)
            container.add_widget(button_container)
            return container
        # except Exception as e:
        #     print(f"expected error in popup manager show_label_printing_view\n{e}")
        else:
            self.app.label_manager.dual_pane_mode = False
            self.label_printing_view.show_inventory_for_label_printing(
                inventory, dual_pane_mode=False
            )
            self.app.current_context = "label"

            self.label_printing_popup = Popup(
                title="Label Printing",
                content=self.label_printing_view,
                size_hint=(0.9, 0.9),
            )
            self.label_printing_popup.bind(
                on_dismiss=self.app.utilities.reset_to_main_context
            )
            self.label_printing_popup.open()

    def exit_dual_pane_mode(self):
        try:
            self.overlay_popup.dismiss()
            self.dual_popup.dismiss()
            self.app.utilities.dual_button.text = ""
            self.app.current_context = "main"
        except Exception as e:
            logger.info(f"[PopupManager: Expected error in exit_dual_pane_mode\n{e}]")

    def toggle_active_pane(self):
        if self.overlay_popup.pos_hint == {"right": 1}:
            self.overlay_popup.dismiss()
            self.toggle_overlay_popup(pane="left")
            self.app.current_context = "label"
        else:
            self.overlay_popup.dismiss()
            self.toggle_overlay_popup(pane="right")
            self.app.current_context = "inventory"

    def toggle_overlay_popup(self, pane="right"):
        # container = MDBoxLayout()
        layout = MDFlatButton(
            size_hint=(1, 1),
            md_bg_color="grey",
            _no_ripple_effect=True,
            opacity=0.75,
            on_press=lambda x: self.toggle_active_pane(),
        )
        # container.add_widget(layout)
        if pane == "right":

            self.overlay_popup = NonModalPopup(
                content=layout,
                title="",
                size_hint_x=0.605,
                pos_hint={"right": 1},
                background="images/transparent.png",
                background_color=(0, 0, 0, 0),
                separator_height=0,
                overlay_color=(0, 0, 0, 0),
                auto_dismiss=False,
            )
            self.overlay_popup.open()
        else:
            self.overlay_popup = NonModalPopup(
                content=layout,
                title="",
                size_hint_x=0.405,
                pos_hint={"x": 0.0, "y": 0},
                background="images/transparent.png",
                background_color=(0, 0, 0, 0),
                separator_height=0,
                overlay_color=(0, 0, 0, 0),
                auto_dismiss=False,
            )
            self.overlay_popup.open()

    def minimize_dual_popup(self):
        self.dual_popup.opacity = 0
        self.dual_popup.disabled = True
        self.overlay_popup.dismiss()
        self.app.current_context = "main"
        self.app.utilities.modify_clock_layout_for_dual_pane_mode()

    def maximize_dual_popup(self):
        self.dual_popup.opacity = 1
        self.dual_popup.disabled = False
        self.toggle_overlay_popup()
        self.app.current_context = "inventory"

    def show_dual_inventory_and_label_managers(self, toggle="inventory"):
        self.app.current_context = "inventory"

        if hasattr(self, "label_printing_view") and self.label_printing_view.parent:
            self.label_printing_view.parent.remove_widget(self.label_printing_view)

        if (
            hasattr(self, "inventory_management_view")
            and self.inventory_management_view.parent
        ):
            self.inventory_management_view.parent.remove_widget(
                self.inventory_management_view
            )
        self.dual_layout = GridLayout(orientation="lr-tb", cols=3, size_hint=(1, 1))
        if toggle == "inventory":
            # try:
            inv_layout = self.show_inventory_management_view(dual_pane_mode=True)

            self.dual_label_layout = self.show_label_printing_view(dual_pane_mode=True)

            divider = MDBoxLayout(
                orientation="vertical",
                size_hint_x=None,
                width=1,
                size_hint_y=1,
                md_bg_color="blue",
            )
            self.dual_layout.add_widget(inv_layout)
            self.dual_layout.add_widget(divider)
            self.dual_layout.add_widget(self.dual_label_layout)
            self.dual_popup = ConditionalModalPopup(
                content=self.dual_layout,
                overlay_color=(0, 0, 0, 0),
                auto_dismiss=False,
                title="Inventory Manager" + " " * 275 + "Label Printer",
            )
            self.dual_popup.open()
            self.toggle_overlay_popup()
            # except Exception as e:
            #     print(f"[popups]\nshow_dual_inventory_and_label_managers\n{e}")

    def show_inventory_management_view(self, dual_pane_mode=False):
        if (
            hasattr(self, "inventory_management_view")
            and self.inventory_management_view.parent
        ):
            self.inventory_management_view.parent.remove_widget(
                self.inventory_management_view
            )

        self.inventory_management_view = InventoryManagementView()
        inventory = self.app.db_manager.get_all_items()
        self.inventory_management_view.show_inventory_for_manager(inventory)

        if dual_pane_mode:
            self.inventory_management_view.size_hint_x = 0.4
            return self.inventory_management_view
        else:
            self.app.current_context = "inventory"
            self.inventory_management_view_popup = Popup(
                title="Inventory Management",
                content=self.inventory_management_view,
                size_hint=(0.9, 0.9),
            )
            self.inventory_management_view_popup.bind(
                on_dismiss=self.on_inventory_manager_dismiss
            )
            self.inventory_management_view_popup.open()

    def on_inventory_manager_dismiss(self, instance):
        self.app.utilities.reset_to_main_context(instance)
        self.app.inventory_manager.detach_from_parent()
        self.inventory_management_view.ids.inv_search_input.text = ""

    def show_adjust_price_popup(self):
        self.adjust_price_popup_layout = BoxLayout(
            orientation="vertical", spacing=5, padding=5
        )

        self.adjust_price_cash_input = TextInput(
            text="",
            hint_text="Enter Target Amount",
            multiline=False,
            input_filter="float",
            font_size=30,
            size_hint_y=None,
            height=50,
        )

        self.adjust_price_popup = self.create_focus_popup(
            title="Adjust Payment",
            content=self.adjust_price_popup_layout,
            size_hint=(0.2, 0.4),
            on_dismiss=lambda x: setattr(self.adjust_price_cash_input, "text", ""),
            textinput=self.adjust_price_cash_input,
        )

        self.adjust_price_popup_layout.add_widget(self.adjust_price_cash_input)

        keypad_layout = GridLayout(cols=3, spacing=10)
        numeric_buttons = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "<-"]

        for button in numeric_buttons:
            if button == "":
                btn = MDFlatButton(size_hint=(0.8, 0.8), md_bg_color=(0, 0, 0, 0))
            elif button == "<-":
                btn = MDFlatButton(
                    text=f"[b][size=20]{button}[/size][/b]",
                    size_hint=(0.8, 0.8),
                    md_bg_color=[0.7, 0.7, 0.7, 1],
                    on_press=lambda x: self.handle_backspace(
                        self.adjust_price_cash_input
                    ),
                )
            else:
                btn = MDFlatButton(
                    text=f"[b][size=20]{button}[/size][/b]",
                    size_hint=(0.8, 0.8),
                    md_bg_color=[0.7, 0.7, 0.7, 1],
                    on_press=self.app.button_handler.on_adjust_price_numeric_button_press,
                )

            keypad_layout.add_widget(btn)

        buttons_layout = GridLayout(cols=2, size_hint_y=1 / 7, spacing=5)
        confirm_button = self.app.utilities.create_md_raised_button(
            "Confirm",
            lambda x: self.app.order_manager.add_adjusted_price_item(),
            (0.8, 0.8),
        )

        cancel_button = self.app.utilities.create_md_raised_button(
            "Cancel",
            lambda x: self.adjust_price_popup.dismiss(),
            (0.8, 0.8),
        )

        buttons_layout.add_widget(confirm_button)
        buttons_layout.add_widget(cancel_button)

        self.adjust_price_popup_layout.add_widget(keypad_layout)
        self.adjust_price_popup_layout.add_widget(buttons_layout)

        self.adjust_price_popup.open()
        # return self.adjust_price_popup

    def handle_backspace(self, input_field):
        current_input = input_field.text.replace(".", "").lstrip("0")

        if current_input:
            new_input = str(int(current_input) // 10).zfill(2)
        else:
            new_input = "00"

        cents = int(new_input)
        dollars = cents // 100
        remaining_cents = cents % 100

        input_field.text = f"{dollars}.{remaining_cents:02d}"

    def show_guard_screen(self):
        if not self.app.is_guard_screen_displayed:
            guard_layout = BoxLayout(orientation="vertical")

            clock_label = Label(size_hint_y=0.1, font_size=50, bold=True)

            def update_time(*args):
                clock_label.text = datetime.now().strftime("%I:%M %p")

            Clock.schedule_interval(update_time, 1)

            guard_image = Image(source="images/rigs_logo_scaled.png")

            guard_layout.add_widget(guard_image)
            guard_layout.add_widget(clock_label)

            self.guard_popup = Popup(
                title="",
                content=guard_layout,
                size_hint=(1, 1),
                auto_dismiss=False,
                background_color=(0, 0, 0, 0),
                separator_height=0,
                overlay_color=(0.1, 0.1, 0.1, 1),
            )
            self.guard_popup.bind(
                on_touch_down=lambda x, touch: self.app.utilities.dismiss_guard_popup()
            )

            self.guard_popup.bind(
                on_dismiss=lambda x: setattr(
                    self.app, "is_guard_screen_displayed", False
                )
            )

            self.guard_popup.open()
            update_time()

    def show_lock_screen(
        self, clock_out=False, current_user=None, auto=False, timestamp=None
    ):
        #print(clock_out, current_user, auto, timestamp)
        #if clock_out and current_user is not None:
            #print("condtion\n\nTEST")
        if self.app.disable_lock_screen:
            self.do_nothing(None)
        else:
            if not self.app.is_lock_screen_displayed:

                lock_layout = MDGridLayout(
                    orientation="lr-tb", cols=2, size_hint=(1, 1)
                )
                left_side_layout = MDGridLayout(orientation="lr-tb", cols=2, rows=2)
                lock_button_layout_container = MDBoxLayout(spacing=5, padding=10)
                # lock_button_layout = MDGridLayout(orientation="lr-tb",cols=3, rows=4, size_hint=(0.5, 1))
                self.lockscreen_keypad_layout = GridLayout(
                    cols=3, rows=4, spacing=10, padding=10, size_hint=(0.1, 1)
                )

                numeric_buttons = [
                    "1",
                    "2",
                    "3",
                    "4",
                    "5",
                    "6",
                    "7",
                    "8",
                    "9",
                    "0",
                    "Reset",
                    " ",
                ]

                for button in numeric_buttons:
                    if button != " ":
                        btn = MDFlatButton(
                            text=f"[b][size=28]{button}[/size][/b]",
                            # color=(1, 1, 1, 1),
                            size_hint=(0.8, 0.8),
                            _no_ripple_effect=True,
                            on_press=lambda x, button=button: self.app.button_handler.on_lock_screen_button_press(
                                instance=x, button_text=button
                            ),
                        )
                        self.lockscreen_keypad_layout.add_widget(btn)

                    else:
                        btn_2 = Button(
                            size_hint=(0.8, 0.8),
                            opacity=0,
                            background_color=(0, 0, 0, 0),
                        )
                        btn_2.bind(on_press=self.app.utilities.manual_override)
                        self.lockscreen_keypad_layout.add_widget(btn_2)
                right_side_layout = self.create_right_side_layout()

                # lock_button_layout.add_widget(self.lockscreen_keypad_layout)
                lock_button_layout_container.add_widget(self.lockscreen_keypad_layout)
                clock_layout = self.create_clock_layout()
                self.clock_out_info = MDLabel(text="")
                _blank = MDBoxLayout()
                _blank2 = MDBoxLayout()
                _blank3 = MDBoxLayout()

                def format_timestamp(timestamp):
                    return datetime.strptime(
                        timestamp, "%Y-%m-%dT%H:%M:%S.%f"
                    ).strftime("%m/%d/%Y\n%I:%M %p")

                if timestamp:
                    human_readable_timestamp = format_timestamp(timestamp)
                if clock_out and auto:
                    self.clock_out_info.text = (
                        f"Automatically logged out.\n\nPrevious user:\n{current_user}"
                    )
                elif clock_out:
                    self.clock_out_info.text = f"Logged out.\n\nPrevious session:\n{current_user}\n{human_readable_timestamp}"
                left_side_layout.add_widget(self.clock_out_info)
                left_side_layout.add_widget(clock_layout)
                left_side_layout.add_widget(_blank2)
                left_side_layout.add_widget(lock_button_layout_container)
                lock_layout.add_widget(left_side_layout)
                # lock_layout.add_widget(self.pin_input)
                # lock_layout.add_widget(checkbox_layout)
                lock_layout.add_widget(right_side_layout)
                self.lock_popup = Popup(
                    title="",
                    content=lock_layout,
                    size_hint=(1, 1),
                    auto_dismiss=False,
                    # background_color=(0.78, 0.78, 0.78, 0),
                    overlay_color=(0.25, 0.25, 0.25, 1),
                    separator_height=0,
                )

                self.lock_popup.bind(
                    on_dismiss=lambda instance: setattr(
                        self.app, "is_lock_screen_displayed", False
                    )
                )

                self.lock_popup.open()

    def flash_buttons_red(self):  # move to utils

        for btn in self.lockscreen_keypad_layout.children:
            original_background = btn.background_normal
            btn.background_normal = "red_background.png"

            Clock.schedule_once(
                lambda dt, btn=btn, original=original_background: setattr(
                    btn, "background_normal", original
                ),
                0.5,
            )

    def create_clock_layout(self):
        clock_layout = MDBoxLayout(orientation="vertical")
        image = Image(source="images/rigs_logo_scaled.png")
        container = MDBoxLayout()
        clock_container = MDBoxLayout(orientation="vertical", padding=100)
        self.clock_label = MDLabel(
            text="",
            size_hint_y=None,
            font_style="H4",
            height=80,
            color=self.app.utilities.get_text_color(),
            halign="center",
        )

        Clock.schedule_interval(self.app.utilities.update_lockscreen_clock, 1)
        clock_container.add_widget(image)
        clock_container.add_widget(self.clock_label)

        container.add_widget(clock_container)
        clock_layout.add_widget(container)
        return clock_layout

    def create_right_side_layout(self):  # not a popup - to utils

        self.pin_input = MDLabel(
            text="",
            size_hint_y=None,
            font_style="H4",
            height=80,
            color=self.app.utilities.get_text_color(),
            halign="center",
        )
        right_side_layout = BoxLayout(orientation="vertical", size_hint_x=0.5)
        self.disable_lock_screen_checkbox = MDCheckbox(
            size_hint=(None, None), size=("48dp", "48dp")
        )
        disable_lock_screen_label = Label(
            text="Disable Lock Screen", size_hint=(None, None), size=("200dp", "48dp")
        )

        checkbox_layout = BoxLayout(
            orientation="horizontal", size_hint=(1, None), height="48dp"
        )
        checkbox_layout.add_widget(self.disable_lock_screen_checkbox)
        checkbox_layout.add_widget(disable_lock_screen_label)
        image_path = "images/rigs_logo_scaled.png"
        if os.path.exists(image_path):
            img = Image(source=image_path, size_hint=(1, 0.75))
        else:

            img = Label(text="", size_hint=(1, 0.75), halign="center")

        # right_side_layout.add_widget(img)
        right_side_layout.add_widget(self.pin_input)
        # right_side_layout.add_widget(self.clock_label)
        right_side_layout.add_widget(checkbox_layout)
        return right_side_layout

    def show_inventory(self):

        inventory = self.app.inventory_cache
        inventory_view = InventoryView(order_manager=self.app.order_manager)
        inventory_view.show_inventory(inventory)
        self.inventory_popup = self.create_focus_popup(
            title="",
            content=inventory_view,
            textinput=inventory_view.ids.inventory_search_input,
            size_hint=(0.6, 0.8),
            #pos_hint={"top": 1},
            overlay_color=(0, 0, 0, 0),
            separator_height=0,
        )
        self.inventory_popup.open()

    def show_tools_popup(self):
        tools_popup_md_bg_color = (0.25, 0.25, 0.25, 0.75)
        # float_layout = FloatLayout()
        float_layout = GridLayout(
            orientation="tb-lr", size_hint=(1, 1), rows=10, spacing=10
        )
        tool_buttons = [
            "Notes",
            "Label Printer",
            "Inventory",
            "Dual Pane",
            "Open Register",
        ]

        if self.app.admin:
            tool_buttons.insert(0, "Admin")
            tool_buttons.insert(1, "System")

        for index, tool in enumerate(tool_buttons):

            btn = MDFlatButton(
                text=f"[b][size=20]{tool}[/b][/size]",
                size_hint_y=None,
                _min_height=75,
                _min_width=200,
                md_bg_color=tools_popup_md_bg_color,
                on_press=self.app.button_handler.on_tool_button_press,
                _no_ripple_effect=True,
            )
            float_layout.add_widget(btn)
        if self.app.admin:
            self.tools_popup = Popup(
                content=float_layout,
                size_hint=(0.2, 0.8),
                title="",
                background="images/transparent.png",
                background_color=(0, 0, 0, 0),
                separator_height=0,
                pos_hint={"center_x": 0.77, "center_y": 0.275},
                overlay_color=(0, 0, 0, 0),
                # pos_hint={"top":1}
            )
        else:
            self.tools_popup = Popup(
                content=float_layout,
                size_hint=(0.2, 0.8),
                title="",
                background="images/transparent.png",
                background_color=(0, 0, 0, 0),
                separator_height=0,
                pos_hint={"center_x": 0.77, "center_y": 0.125},
                overlay_color=(0, 0, 0, 0),
                # pos_hint={"top":1}
            )
        self.tools_popup.open()

    def show_admin_popup(self):

        float_layout = GridLayout(
            orientation="tb-lr", size_hint=(1, 1), rows=10, spacing=10
        )
        admin_buttons = [
            "Reporting",
            "Time Sheets",
            "Users",
        ]

        for index, entry in enumerate(admin_buttons):

            btn = MDFlatButton(
                text=f"[b][size=20]{entry}[/b][/size]",
                size_hint_y=None,
                _min_height=75,
                _min_width=200,
                on_press=self.app.button_handler.on_admin_button_press,
                md_bg_color=(0.5, 0.5, 0.5, 0.25),
                _no_ripple_effect=True,
            )
            float_layout.add_widget(btn)

        self.admin_popup = Popup(
            content=float_layout,
            size_hint=(0.2, 0.8),
            title="",
            background="images/transparent.png",
            background_color=(0, 0, 0, 0),
            separator_height=0,
            pos_hint={"center_x": 0.75, "center_y": 0.22},
            overlay_color=(0, 0, 0, 0),
            # pos_hint={"top":1}
        )
        self.admin_popup.open()

    def show_custom_item_popup(self, barcode="01234567890"):

        self.custom_item_popup_layout = BoxLayout(
            orientation="vertical", spacing=5, padding=5
        )
        self.cash_input = TextInput(
            text="",
            hint_text="Enter Price",
            multiline=False,
            input_filter="float",
            font_size=30,
            size_hint_y=None,
            height=50,
        )
        self.custom_item_name_input = TextInput(
            text="Custom Item",
            hint_text="Enter Name",
            multiline=False,
            font_size=30,
            size_hint_y=None,
            height=50,
        )
        self.custom_item_popup_layout.add_widget(self.custom_item_name_input)
        self.custom_item_popup_layout.add_widget(self.cash_input)

        keypad_layout = GridLayout(cols=3, spacing=10)

        numeric_buttons = [
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "0",
        ]
        for button in numeric_buttons:
            btn = Button(
                text=button,
                on_press=self.app.button_handler.on_numeric_button_press,
                size_hint=(0.8, 0.8),
                font_size=30,
            )
            keypad_layout.add_widget(btn)

        confirm_button = self.app.utilities.create_md_raised_button(
            "[size=20][b]Confirm[/b][/size]",
            lambda x: self.app.order_manager.add_custom_item(
                x, name=self.custom_item_name_input.text, price=self.cash_input.text
            ),
            (0.8, 0.8),
        )

        cancel_button = Button(
            text="Cancel",
            on_press=self.app.utilities.on_custom_item_cancel,
            size_hint=(0.8, 0.8),
        )

        keypad_layout.add_widget(confirm_button)
        keypad_layout.add_widget(cancel_button)

        self.custom_item_popup_layout.add_widget(keypad_layout)
        self.custom_item_popup = FocusPopup(
            title="",
            content=self.custom_item_popup_layout,
            size_hint=(0.4, 0.6),
            on_dismiss=lambda x: setattr(self.cash_input, "text", ""),
            overlay_color=(0, 0, 0, 0),
            separator_height=0,
        )
        self.custom_item_popup.focus_on_textinput(self.cash_input)
        self.custom_item_popup.open()

    def show_order_popup(self, order_summary):

        order_details = self.app.order_manager.get_order_details()
        popup_layout = GridLayout(
            orientation="tb-lr", spacing=5, padding=5, cols=2, rows=2
        )

        items_layout = GridLayout(orientation="lr-tb", size_hint_y=1, rows=20, cols=2)

        for item_id, item_details in order_details["items"].items():
            item_text = f"{item_details['quantity']}x {item_details['name']}"
            item_price = f"${item_details['total_price']:.2f}"
            item_label = MDLabel(
                text=item_text,
                halign="left",
                size_hint_x=7 / 8,
                size_hint_y=None,
                height=40,
            )
            price_label = MDLabel(
                text=item_price,
                halign="right",
                size_hint_x=1 / 8,
                size_hint_y=None,
                height=40,
            )
            items_layout.add_widget(item_label)
            items_layout.add_widget(price_label)

        totals_container = AnchorLayout(anchor_x="right", size_hint_y=0.1)
        totals_layout = GridLayout(orientation="tb-lr", rows=4)
        subtotal_label = MDLabel(
            text=f"Subtotal: ${order_details['subtotal']:.2f}", halign="right"
        )
        tax_label = MDLabel(
            text=f"Tax: ${order_details['tax_amount']:.2f}", halign="right"
        )
        total_label = MDLabel(
            text=f"[size=25]Total: [b]${order_details['total_with_tax']:.2f}[/b][/size]",
            halign="right",
        )

        totals_layout.add_widget(subtotal_label)
        if order_details["discount"] > 0:
            discount_label = MDLabel(
                text=f"Discount: -${order_details['discount']:.2f}", halign="right"
            )
            totals_layout.add_widget(discount_label)
        else:
            _blank = MDLabel(text="", size_hint_y=None, height=1)
            totals_layout.add_widget(_blank)

        totals_layout.add_widget(tax_label)
        totals_layout.add_widget(total_label)
        totals_container.add_widget(totals_layout)
        # items_and_totals_layout.add_widget(totals_layout)
        popup_layout.add_widget(items_layout)
        popup_layout.add_widget(totals_container)
        buttons_layout_top = GridLayout(
            orientation="tb-lr",
            spacing=5,
            padding=5,
            cols=1,
            rows=3,
            size_hint_x=1 / 3,
            size_hint_y=3 / 5,
        )
        buttons_layout_bottom = GridLayout(
            orientation="tb-lr",
            spacing=5,
            padding=5,
            cols=1,
            rows=3,
            size_hint_x=1 / 3,
            size_hint_y=2 / 5,
        )
        btn_pay_cash = self.app.utilities.create_md_raised_button(
            f"[b][size=20]Pay Cash[/b][/size]",
            self.app.button_handler.on_payment_button_press,
            (0.8, 1),
        )

        btn_pay_credit = self.app.utilities.create_md_raised_button(
            f"[b][size=20]Pay Credit[/b][/size]",
            self.app.button_handler.on_payment_button_press,
            (0.8, 1),
        )
        btn_pay_debit = self.app.utilities.create_md_raised_button(
            f"[b][size=20]Pay Debit[/b][/size]",
            self.app.button_handler.on_payment_button_press,
            (0.8, 1),
        )

        btn_pay_split = self.app.utilities.create_md_raised_button(
            f"[b][size=20]Split[/b][/size]",
            self.app.button_handler.on_payment_button_press,
            (0.8, 1),
        )

        btn_cancel = Button(
            text="Cancel",
            on_press=self.app.button_handler.on_payment_button_press,
            size_hint=(0.8, 1),
        )
        buttons_layout_top.add_widget(btn_pay_cash)
        buttons_layout_top.add_widget(btn_pay_debit)
        buttons_layout_top.add_widget(btn_pay_credit)
        buttons_layout_bottom.add_widget(btn_pay_split)
        buttons_layout_bottom.add_widget(btn_cancel)
        popup_layout.add_widget(buttons_layout_top)
        popup_layout.add_widget(buttons_layout_bottom)

        self.finalize_order_popup = Popup(
            title=f"Finalize Order - {order_details['order_id']}",
            content=popup_layout,
            size_hint=(0.4, 0.6),
            overlay_color=(0, 0, 0, 0),
            separator_color="white",
            separator_height=0.5,
            title_align="center",
        )
        self.finalize_order_popup.open()

    def show_cash_payment_popup(self):
        total_with_tax = self.app.order_manager.calculate_total_with_tax()
        common_amounts = self.app.utilities.calculate_common_amounts(total_with_tax)

        self.cash_popup_layout = BoxLayout(orientation="vertical", spacing=10)
        self.cash_payment_input = MoneyInput(
            text=f"{total_with_tax:.2f}",
            disabled=True,
            input_type="number",
            multiline=False,
            input_filter="float",
            font_size=30,
            size_hint_y=0.2,
            size_hint_x=0.3,
            height=50,
        )
        self.cash_popup_layout.add_widget(self.cash_payment_input)

        keypad_layout = GridLayout(cols=2, spacing=5)
        other_buttons = BoxLayout(
            orientation="horizontal",
            spacing=5,
            size_hint=(1, 0.4),
        )

        placeholder_amounts = [0] * 5
        for i, amount in enumerate(placeholder_amounts):
            btn_text = (
                f"[b][size=20]${common_amounts[i]:.2f}[/size][/b]"
                if i < len(common_amounts)
                else "-"
            )
            btn = MarkupButton(
                text=btn_text, on_press=self.app.button_handler.on_preset_amount_press
            )
            btn.disabled = i >= len(common_amounts)
            keypad_layout.add_widget(btn)

        custom_cash_button = MDFlatButton(
            text=f"[b][size=20]Custom[/size][/b]",
            on_press=self.open_custom_cash_popup,
            size_hint=(0.4, 0.8),
            md_bg_color="grey",
        )

        confirm_button = self.app.utilities.create_md_raised_button(
            f"[b][size=20]Confirm[/size][/b]",
            self.app.order_manager.on_cash_confirm,
            (0.4, 0.8),
        )

        cancel_button = MDFlatButton(
            text=f"[b][size=20]Cancel[/size][/b]",
            on_press=self.app.utilities.on_cash_cancel,
            size_hint=(0.4, 0.8),
            md_bg_color="grey",
        )

        other_buttons.add_widget(confirm_button)
        other_buttons.add_widget(cancel_button)
        other_buttons.add_widget(custom_cash_button)

        self.cash_popup_layout.add_widget(keypad_layout)
        self.cash_popup_layout.add_widget(other_buttons)
        self.cash_popup = Popup(
            title="Amount Tendered",
            content=self.cash_popup_layout,
            size_hint=(0.4, 0.6),
            overlay_color=(0, 0, 0, 0),
        )
        self.cash_popup.open()

    def open_custom_cash_popup(self, instance):
        self.custom_cash_popup_layout = BoxLayout(orientation="vertical", spacing=10)
        self.custom_cash_input = TextInput(
            text="",
            multiline=False,
            input_filter="float",
            font_size=30,
            size_hint_y=None,
            height=50,
        )
        self.custom_cash_popup_layout.add_widget(self.custom_cash_input)

        keypad_layout = GridLayout(cols=3, spacing=10)

        numeric_buttons = [
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "0",
        ]
        for button in numeric_buttons:
            btn = Button(
                text=button,
                on_press=self.app.button_handler.on_custom_cash_numeric_button_press,
                size_hint=(0.8, 0.8),
                font_size=30,
            )
            keypad_layout.add_widget(btn)

        confirm_button = self.app.utilities.create_md_raised_button(
            "Confirm",
            lambda instance: self.app.order_manager.on_custom_cash_confirm(instance),
            (0.8, 0.8),
        )

        cancel_button = Button(
            text="Cancel",
            on_press=self.app.utilities.on_custom_cash_cancel,
            size_hint=(0.8, 0.8),
        )
        keypad_layout.add_widget(confirm_button)
        keypad_layout.add_widget(cancel_button)

        self.custom_cash_popup_layout.add_widget(keypad_layout)
        self.custom_cash_popup = self.create_focus_popup(
            title="Custom Cash",
            content=self.custom_cash_popup_layout,
            size_hint=(0.4, 0.6),
            textinput=self.custom_cash_input,
        )
        self.custom_cash_popup.open()

    def show_payment_confirmation_popup(self):

        confirmation_layout = MDFloatLayout(size_hint=(1, 1))

        total_with_tax = self.app.order_manager.calculate_total_with_tax()
        order_details = self.app.order_manager.get_order_details()

        order_summary = "Order Complete:\n\n"
        for item_id, item_details in self.app.order_manager.items.items():
            item_name = item_details["name"]
            quantity = item_details["quantity"]
            order_summary += f"{item_name} x{quantity}\n"

        card = MDCard(
            orientation="vertical",
            size_hint=(0.8, 0.8),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            spacing=10,
            # padding=10xxx
        )

        card.add_widget(
            MDLabel(text=order_summary, halign="center", theme_text_color="Secondary")
        )

        card.add_widget(
            MDLabel(
                text=f"[b]${total_with_tax:.2f} Paid With {order_details['payment_method']}[/b]",
                halign="center",
                theme_text_color="Primary",
            )
        )

        button_layout = MDFloatLayout(size_hint_y=0.3)
        done_button = MDRaisedButton(
            text="[size=20][b]Done[/b][/size]",
            on_release=self.app.button_handler.on_done_button_press,
            pos_hint={"center_x": 0.25, "center_y": 0.5},
            size_hint=(0.45, 1),
        )

        receipt_button = MDRaisedButton(
            text="[size=20][b]Print Receipt[/b][/size]",
            on_release=self.app.button_handler.on_receipt_button_press,
            pos_hint={"center_x": 0.75, "center_y": 0.5},
            size_hint=(0.45, 1),
        )

        card.add_widget(button_layout)
        button_layout.add_widget(done_button)
        button_layout.add_widget(receipt_button)

        confirmation_layout.add_widget(card)

        self.payment_popup = Popup(
            title="Payment Confirmation",
            content=confirmation_layout,
            size_hint=(None, None),
            size=("500dp", "800dp"),
            auto_dismiss=False,
            separator_color="white",
            separator_height=0.5,
            title_align="center",
        )
        self.finalize_order_popup.dismiss()
        self.timeout_event = Clock.schedule_once(
            lambda dt: self.automatic_done_actions(), 60
        )
        self.payment_popup.open()

    def automatic_done_actions(self):
        order_details = self.app.order_manager.get_order_details()
        self.app.db_manager.send_order_to_history_database(
            order_details, self.app.order_manager, self.app.db_manager
        )
        self.app.order_manager.clear_order()
        self.payment_popup.dismiss()
        self.app.utilities.update_financial_summary()
        self.app.order_layout.clear_widgets()
        self.app.order_manager.delete_order_from_disk(order_details)

    def show_make_change_popup(self, change):
        change_layout = BoxLayout(orientation="vertical", spacing=10)
        change_layout.add_widget(
            MDLabel(
                text=f"[size=30]Change to return:\n [b]${change:.2f}[/b][/size]",
                halign="center",
            )
        )

        done_button = self.app.utilities.create_md_raised_button(
            f"[size=20][b]Done[/b][/size]", self.app.utilities.on_change_done, (1, 0.4)
        )
        change_layout.add_widget(done_button)

        self.change_popup = Popup(
            title="",
            content=change_layout,
            size_hint=(0.2, 0.4),
            separator_height=0,
            auto_dismiss=False,
        )
        self.change_popup.open()
        self.make_change_dismiss_event = Clock.schedule_once(
            self.make_change_popup_timeout, 60
        )

    def make_change_popup_timeout(self, *args):
        try:
            self.app.utilities.on_change_done(None)
        except Exception as e:
            logger.warn(f"Exception in popup_manager make_change_popup_timeout\n{e}")

    def handle_split_payment(self):
        self.dismiss_popups(
            "split_amount_popup", "split_cash_popup", "split_change_popup"
        )
        remaining_amount = self.app.order_manager.calculate_total_with_tax()
        remaining_amount = float(f"{remaining_amount:.2f}")
        self.split_payment_info = {
            "total_paid": 0.0,
            "remaining_amount": remaining_amount,
            "payments": [],
        }
        self.show_split_payment_numeric_popup()

    def split_cash_make_change(self, change, amount):
        split_change_layout = BoxLayout(orientation="vertical", spacing=10)
        split_change_layout.add_widget(
            MDLabel(text=f"[size=30]Change to return: [b]${change:.2f}[/b][/size]")
        )

        split_done_button = self.app.utilities.create_md_raised_button(
            f"[size=20][b]Done[/b][/size]",
            lambda x: self.app.utilities.split_cash_continue(amount),
            size_hint=(1, 0.4),
            height=50,
        )
        split_change_layout.add_widget(split_done_button)

        self.split_change_popup = Popup(
            title="Change Calculation",
            content=split_change_layout,
            size_hint=(0.4, 0.4),
        )
        self.split_change_popup.open()

    def show_split_cash_popup(self, amount):
        common_amounts = self.app.utilities.calculate_common_amounts(amount)
        other_buttons = BoxLayout(
            orientation="horizontal",
            spacing=5,
            size_hint=(1, 0.4),
        )
        self.split_cash_popup_layout = BoxLayout(orientation="vertical", spacing=10)
        self.split_cash_input = MoneyInput(
            text=str(amount),
            input_type="number",
            multiline=False,
            disabled=True,
            input_filter="float",
            font_size=30,
            size_hint_y=0.2,
            size_hint_x=0.3,
            height=50,
        )
        self.split_cash_popup_layout.add_widget(self.split_cash_input)

        split_cash_keypad_layout = GridLayout(cols=2, spacing=5)

        placeholder_amounts = [0] * 5
        for i, placeholder in enumerate(placeholder_amounts):

            btn_text = (
                f"[b][size=20]${common_amounts[i]}[/size][/b]"
                if i < len(common_amounts)
                else "-"
            )
            btn = MarkupButton(
                text=btn_text,
                on_press=self.app.button_handler.split_on_preset_amount_press,
            )

            btn.disabled = i >= len(common_amounts)
            split_cash_keypad_layout.add_widget(btn)

        split_custom_cash_button = Button(
            text="Custom",
            on_press=lambda x: self.split_open_custom_cash_popup(amount),
            size_hint=(0.8, 0.8),
        )

        split_cash_confirm_button = self.app.utilities.create_md_raised_button(
            "Confirm",
            lambda x: self.app.utilities.split_on_cash_confirm(amount),
            (0.8, 0.8),
        )

        split_cash_cancel_button = Button(
            text="Cancel",
            on_press=lambda x: self.app.utilities.split_on_cash_cancel(),
            size_hint=(0.8, 0.8),
        )

        other_buttons.add_widget(split_cash_confirm_button)
        other_buttons.add_widget(split_cash_cancel_button)
        other_buttons.add_widget(split_custom_cash_button)

        self.split_cash_popup_layout.add_widget(split_cash_keypad_layout)
        self.split_cash_popup_layout.add_widget(other_buttons)
        self.split_cash_popup = Popup(
            title="Amount Tendered",
            content=self.split_cash_popup_layout,
            size_hint=(0.4, 0.6),
        )

        self.split_cash_popup.open()

    def show_split_cash_confirm(self, amount):
        split_cash_confirm = BoxLayout(orientation="vertical")
        split_cash_confirm_text = Label(text=f"{amount} Cash Payment Confirmed")
        tolerance = 0.001

        if abs(self.split_payment_info["remaining_amount"]) <= tolerance:
            split_cash_confirm_next_btn = self.app.utilities.create_md_raised_button(
                "Done",
                lambda x: self.app.utilities.split_cash_continue(amount),
                (1, 0.4),
            )
        else:
            split_cash_confirm_next_btn = self.app.utilities.create_md_raised_button(
                "Next",
                lambda x: self.app.utilities.split_cash_continue(amount),
                (1, 0.4),
            )

        split_cash_confirm.add_widget(split_cash_confirm_text)
        split_cash_confirm.add_widget(split_cash_confirm_next_btn)
        self.split_cash_confirm_popup = Popup(
            title="Payment Confirmation",
            content=split_cash_confirm,
            size_hint=(0.4, 0.4),
        )
        self.split_cash_confirm_popup.open()

    def show_split_card_confirm(self, amount, method):
        open_cash_drawer()
        split_card_confirm = BoxLayout(orientation="vertical")
        split_card_confirm_text = Label(text=f"{amount} {method} Payment Confirmed")
        tolerance = 0.001

        if abs(self.split_payment_info["remaining_amount"]) <= tolerance:
            split_card_confirm_next_btn = self.app.utilities.create_md_raised_button(
                "Done",
                lambda x: self.app.utilities.split_card_continue(amount, method),
                (1, 0.4),
            )
        else:
            split_card_confirm_next_btn = self.app.utilities.create_md_raised_button(
                "Next",
                lambda x: self.app.utilities.split_card_continue(amount, method),
                (1, 0.4),
            )
        split_card_confirm.add_widget(split_card_confirm_text)
        split_card_confirm.add_widget(split_card_confirm_next_btn)
        self.split_card_confirm_popup = Popup(
            title="Payment Confirmation",
            content=split_card_confirm,
            size_hint=(0.4, 0.4),
        )
        self.split_card_confirm_popup.open()

    def show_split_payment_numeric_popup(self, subsequent_payment=False):
        self.dismiss_popups(
            "split_cash_confirm_popup",
            "split_cash_popup",
            "split_change_popup",
            "finalize_order_popup",
        )

        self.split_payment_numeric_popup_layout = BoxLayout(
            orientation="vertical", spacing=10
        )

        if subsequent_payment:
            self.split_payment_numeric_cash_input = TextInput(
                text=f"{self.split_payment_info['remaining_amount']:.2f}",
                # disabled=True,
                multiline=False,
                input_filter="float",
                font_size=20,
                size_hint_y=None,
                height=50,
            )
            self.split_payment_numeric_popup_layout.add_widget(
                self.split_payment_numeric_cash_input
            )

        else:
            self.split_payment_numeric_cash_input = TextInput(
                text="",
                hint_text="Enter first payment amount and then choose payment type below",
                # disabled=True,
                multiline=False,
                input_filter="float",
                font_size=20,
                size_hint_y=None,
                height=50,
            )
            self.split_payment_numeric_popup_layout.add_widget(
                self.split_payment_numeric_cash_input
            )

        self.split_payment_numeric_popup = self.create_focus_popup(
            title=f"Split Payment - Remaining Amount: {self.split_payment_info['remaining_amount']:.2f} ",
            content=self.split_payment_numeric_popup_layout,
            size_hint=(0.4, 0.6),
            textinput=self.split_payment_numeric_cash_input,
        )

        keypad_layout = GridLayout(cols=3, rows=4, spacing=10)

        numeric_buttons = [
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "",
            "0",
            "Clear",
        ]
        for button in numeric_buttons:
            if button == "":
                blank_space = Label(size_hint=(0.8, 0.8))
                keypad_layout.add_widget(blank_space)
            elif button == "Clear":
                clr_button = Button(
                    text=button,
                    on_press=lambda x: self.app.utilities.clear_split_numeric_input(),
                    size_hint=(0.8, 0.8),
                )
                keypad_layout.add_widget(clr_button)
            else:
                btn = Button(
                    text=button,
                    on_press=self.app.button_handler.on_split_payment_numeric_button_press,
                    size_hint=(0.8, 0.8),
                )
                keypad_layout.add_widget(btn)

        buttons_layout = GridLayout(cols=4, size_hint_y=1 / 7, spacing=5)
        cash_button = self.app.utilities.create_md_raised_button(
            "Cash",
            lambda x: self.app.utilities.handle_split_input(
                self.split_payment_numeric_cash_input.text, "Cash"
            ),
            (0.8, 0.8),
        )

        debit_button = self.app.utilities.create_md_raised_button(
            "Debit",
            lambda x: self.app.utilities.handle_split_input(
                self.split_payment_numeric_cash_input.text, "Debit"
            ),
            (0.8, 0.8),
        )
        credit_button = self.app.utilities.create_md_raised_button(
            "Credit",
            lambda x: self.app.utilities.handle_split_input(
                self.split_payment_numeric_cash_input.text, "Credit"
            ),
            (0.8, 0.8),
        )

        cancel_button = Button(
            text="Cancel",
            on_press=lambda x: self.app.utilities.split_cancel(),
            size_hint=(0.8, 0.8),
        )

        buttons_layout.add_widget(cash_button)
        buttons_layout.add_widget(debit_button)
        buttons_layout.add_widget(credit_button)
        buttons_layout.add_widget(cancel_button)

        self.split_payment_numeric_popup_layout.add_widget(keypad_layout)
        self.split_payment_numeric_popup_layout.add_widget(buttons_layout)

        self.split_payment_numeric_popup.open()

    def split_open_custom_cash_popup(self, amount):
        self.split_custom_cash_popup_layout = BoxLayout(
            orientation="vertical", spacing=10
        )
        self.split_custom_cash_input = TextInput(
            text="",
            multiline=False,
            input_filter="float",
            font_size=30,
            size_hint_y=None,
            height=50,
        )
        self.split_custom_cash_popup_layout.add_widget(self.split_custom_cash_input)

        keypad_layout = GridLayout(cols=3, spacing=10)

        numeric_buttons = [
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "0",
        ]
        for button in numeric_buttons:
            btn = self.app.utilities.create_md_raised_button(
                button,
                self.app.button_handler.on_split_custom_cash_payment_numeric_button_press,
                (0.8, 0.8),
            )
            keypad_layout.add_widget(btn)

        confirm_button = self.app.utilities.create_md_raised_button(
            "Confirm",
            lambda x: self.app.utilities.split_on_custom_cash_confirm(amount),
            (0.8, 0.8),
        )

        cancel_button = Button(
            text="Cancel",
            on_press=self.app.utilities.on_split_custom_cash_cancel,
            size_hint=(0.8, 0.8),
        )
        keypad_layout.add_widget(confirm_button)
        keypad_layout.add_widget(cancel_button)

        self.split_custom_cash_popup_layout.add_widget(keypad_layout)
        self.split_custom_cash_popup = Popup(
            title="Split Custom Cash",
            content=self.split_custom_cash_popup_layout,
            size_hint=(0.4, 0.6),
        )
        self.split_custom_cash_popup.open()

    def reboot_are_you_sure(self):
        arys_layout = BoxLayout()

        btn = self.app.utilities.create_md_raised_button(
            "Yes!",
            self.app.utilities.reboot,
            (0.9, 0.9),
        )
        btn2 = self.app.utilities.create_md_raised_button(
            "No!",
            lambda x: popup.dismiss(),
            (0.9, 0.9),
        )
        arys_layout.add_widget(Label(text=f"Are you sure?"))
        arys_layout.add_widget(btn)
        arys_layout.add_widget(btn2)
        popup = Popup(
            title="Reboot",
            content=arys_layout,
            size_hint=(0.9, 0.2),
            pos_hint={"top": 1},
            background_color=[1, 0, 0, 1],
        )

        popup.open()

    def dismiss_popups(self, *popups):
        for popup_attr in popups:
            if hasattr(self, popup_attr):
                try:
                    popup = getattr(self, popup_attr)
                    if popup._is_open:
                        popup.dismiss()
                except Exception as e:
                    logger.warn(e)

    def do_nothing(self, instance=None, *args, **kwargs):
        pass

    def create_focus_popup(
        self,
        title,
        content,
        textinput,
        size_hint,
        pos_hint={},
        on_dismiss=None,
        overlay_color=(0, 0, 0, 0),
        separator_height=1,
    ):
        if on_dismiss is None:
            on_dismiss = self.do_nothing
        popup = FocusPopup(
            title=title,
            content=content,
            size_hint=size_hint,
            pos_hint=pos_hint,
            on_dismiss=on_dismiss,
            overlay_color=overlay_color,
            separator_height=separator_height,
        )
        popup.focus_on_textinput(textinput)
        return popup

    def catch_label_printer_missing_barcode(self):
        layout = GridLayout(orientation="tb-lr", rows=2)
        error_text = Label(
            text=f"Error: It seems like this item has no barcode.\nPlease go back and generate one.",
            size_hint_y=0.5,
            pos_hint={"top": 1},
        )
        label_barcode_error_icon_button = MDRaisedButton(
            text="",
            on_press=lambda x: self.do_nothing(),
            size_hint_x=1,
        )
        label_barcode_error_button = MDRaisedButton(
            text="Dismiss",
            on_press=lambda x: self.label_barcode_error_popup.dismiss(),
            size_hint_x=1,
        )
        layout.add_widget(error_text)
        buttons_layout = GridLayout(
            orientation="lr-tb", cols=2, size_hint_y=0.1, spacing=5
        )
        buttons_layout.add_widget(label_barcode_error_button)
        buttons_layout.add_widget(label_barcode_error_icon_button)
        layout.add_widget(buttons_layout)
        self.label_barcode_error_popup = Popup(
            content=layout,
            size_hint=(0.4, 0.4),
            title="Error",
        )
        self.label_barcode_error_popup.open()


    def catch_label_printing_errors(self, e):
        if hasattr(self, "label_errors_popup") and self.label_errors_popup._is_open:
            self.label_errors_popup.dismiss()
        label_errors_layout = GridLayout(orientation="tb-lr", rows=2)
        label_errors_text = Label(
            text=f"Caught an error from the label printer:\n\n{e}\n\nMake sure it's plugged in and turned on.",
            size_hint_y=0.5,
            pos_hint={"top": 1},
        )
        label_errors_icon_button = MDRaisedButton(
            text="Try Again",
            on_press=lambda x: self.app.label_printer.process_queue(),
            size_hint_x=1,
        )
        label_errors_button = MDRaisedButton(
            text="Dismiss",
            on_press=lambda x: self.label_errors_popup.dismiss(),
            size_hint_x=1,
        )
        label_errors_layout.add_widget(label_errors_text)
        buttons_layout = GridLayout(
            orientation="lr-tb", cols=2, size_hint_y=0.1, spacing=5
        )
        buttons_layout.add_widget(label_errors_button)
        buttons_layout.add_widget(label_errors_icon_button)
        label_errors_layout.add_widget(buttons_layout)
        self.label_errors_popup = Popup(
            content=label_errors_layout,
            size_hint=(0.4, 0.4),
            title="Label Printer Error",
        )
        self.label_errors_popup.open()

    def catch_receipt_printer_errors(self, e, order_details):

        if hasattr(self, "receipt_errors_popup") and self.receipt_errors_popup._is_open:
            self.receipt_errors_popup.dismiss()
        receipt_errors_layout = GridLayout(orientation="tb-lr", rows=2)
        receipt_errors_text = Label(
            text=f"Caught an error from the receipt printer:\n\n{e}\n\nMake sure it's plugged in and turned on.",
            size_hint_y=0.5,
            pos_hint={"top": 1},
        )
        receipt_errors_icon_button = MDRaisedButton(
            text="Try Again",
            on_press=lambda x: self.app.receipt_printer.re_initialize_after_error(
                order_details
            ),
            size_hint_x=1,
        )
        receipt_errors_button = MDRaisedButton(
            text="Dismiss",
            on_press=lambda x: self.receipt_errors_popup.dismiss(),
            size_hint_x=1,
        )
        receipt_errors_layout.add_widget(receipt_errors_text)
        buttons_layout = GridLayout(
            orientation="lr-tb", cols=2, size_hint_y=0.1, spacing=5
        )
        buttons_layout.add_widget(receipt_errors_button)
        buttons_layout.add_widget(receipt_errors_icon_button)
        receipt_errors_layout.add_widget(buttons_layout)
        self.receipt_errors_popup = Popup(
            content=receipt_errors_layout,
            size_hint=(0.4, 0.4),
            title="Receipt Printer Error",
        )
        self.receipt_errors_popup.open()

    def unrecoverable_error(self):
        logger.warn("unrecoverable")
        error_layout = BoxLayout(orientation="vertical")
        error_text = Label(
            text=f"There has been an unrecoverable error\nand the system needs to reboot\nSorry!"
        )
        error_button = Button(text="Reboot", on_press=lambda x: self.app.reboot())
        error_layout.add_widget(error_text)
        error_layout.add_widget(error_button)
        error_popup = Popup(
            title="Uh-Oh",
            auto_dismiss=False,
            size_hint=(0.4, 0.4),
            content=error_layout,
        )
        error_popup.open()

    def open_inventory_item_popup(self, barcode=None, query=None):

        self.app.current_context = "inventory_item"

        content = BoxLayout(orientation="vertical", padding=10)
        name_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        name_input = TextInput(text=self.app.inventory_manager.name, font_size=20)
        name_layout.add_widget(Label(text="Name", size_hint_x=0.2))
        name_layout.add_widget(name_input)

        barcode_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        self.barcode_input = TextInput(
            input_filter="int", text=barcode if barcode else "", font_size=20
        )
        barcode_layout.add_widget(Label(text="Barcode", size_hint_x=0.2))
        barcode_layout.add_widget(self.barcode_input)

        price_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        price_input = TextInput(
            text=self.app.inventory_manager.price, input_filter="float", font_size=20
        )
        price_layout.add_widget(Label(text="Price", size_hint_x=0.2))
        price_layout.add_widget(price_input)

        cost_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        cost_input = TextInput(
            text=self.app.inventory_manager.cost, input_filter="float", font_size=20
        )
        cost_layout.add_widget(Label(text="Cost", size_hint_x=0.2))
        cost_layout.add_widget(cost_input)

        sku_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        sku_input = TextInput(text=self.app.inventory_manager.sku, font_size=20)
        sku_layout.add_widget(Label(text="SKU", size_hint_x=0.2))

        sku_layout.add_widget(sku_input)

        category_layout = BoxLayout(orientation="horizontal", size_hint_y=0.4)
        self.add_to_db_category_input_inv = TextInput(
            text=self.app.inventory_manager.category, disabled=True, font_size=20
        )
        category_layout.add_widget(Label(text="Category", size_hint_x=0.2))

        category_layout.add_widget(self.add_to_db_category_input_inv)

        content.add_widget(name_layout)
        content.add_widget(barcode_layout)
        content.add_widget(price_layout)
        content.add_widget(cost_layout)
        content.add_widget(sku_layout)
        content.add_widget(category_layout)

        button_layout = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=100,
            spacing=10,
            padding=10,
        )

        button_layout.add_widget(
            MDRaisedButton(
                text="[b][size=20]Confirm[/size][/b]",
                size_hint=(1, 1),
                on_press=lambda x: self.app.utilities.inventory_item_confirm_and_close(
                    self.barcode_input,
                    name_input,
                    price_input,
                    cost_input,
                    sku_input,
                    self.add_to_db_category_input_inv,
                    self.inventory_item_popup,
                    query=query,
                ),
            )
        )
        button_layout.add_widget(
            MDRaisedButton(
                text="[b][size=20]Generate Barcode[/size][/b]",
                size_hint=(1, 1),
                on_press=lambda x: self.app.utilities.set_generated_barcode(
                    self.barcode_input,
                ),
            )
        )
        button_layout.add_widget(
            MDRaisedButton(
                text="[b][size=20]Categories[/size][/b]",
                on_press=lambda x: self.open_category_button_popup_inv(),
                size_hint=(1, 1),
            )
        )
        button_layout.add_widget(
            MDRaisedButton(
                text="[b][size=20]Cancel[/size][/b]",
                on_press=lambda x: self.inventory_item_popup.dismiss(),
                size_hint=(1, 1),
            )
        )
        button_layout.add_widget(MDBoxLayout(size_hint=(1, 1)))

        content.add_widget(button_layout)

        self.inventory_item_popup = Popup(
            title="Item details",
            # pos_hint={"top": 1},
            content=content,
            size_hint=(0.8, 0.6),
        )

        self.inventory_item_popup.bind(
            on_dismiss=lambda x: self.on_inventory_item_dismiss(x)
        )
        # self.app.inventory_manager.refresh_inventory()
        self.inventory_item_popup.open()

    def on_inventory_item_dismiss(self, instance):
        self.app.inventory_manager.reset_inventory_context()
        # self.app.inventory_manager.detach_from_parent()

    def handle_duplicate_barcodes(self, barcode):
        try:
            logger.warn("in popups", barcode)
            items = self.app.db_manager.handle_duplicate_barcodes(barcode)

            if not isinstance(items, list):
                raise ValueError("Expected a list of items")

            for item in items:
                if not isinstance(item, dict):
                    raise ValueError("Expected item to be a dictionary")
                if "name" not in item or "price" not in item:
                    raise KeyError("Item dictionary missing required keys")

            layout = GridLayout(rows=10, cols=1, spacing=5, size_hint=(1, 1))
            for item in items:
                button = MDRaisedButton(
                    text=item["name"],
                    size_hint=(1, None),
                    on_press=lambda x, barcode=barcode, choice=item["name"], price=item[
                        "price"
                    ]: self.add_dupe_choice_to_order(
                        barcode=barcode, choice=choice, price=price
                    ),
                )
                layout.add_widget(button)

            self.handle_duplicate_barcodes_popup = Popup(
                title="Duplicate Barcode Detected!",
                content=layout,
                size_hint=(0.2, 0.6),
            )
            self.handle_duplicate_barcodes_popup.open()
        except Exception as e:
            logger.warn(f"Exception in handle_duplicate_barcodes\n{e}")

    def add_dupe_choice_to_order(self, barcode, choice, price):

        item_details = self.app.db_manager.get_item_details(
            barcode=barcode, name=choice, dupe=True, price=price
        )

        if item_details:

            item_name = item_details["name"]
            item_price = item_details["price"]
            self.app.order_manager.add_item(item_name, item_price)
            self.handle_duplicate_barcodes_popup.dismiss()
            self.app.utilities.update_display()
            self.app.utilities.update_financial_summary()


class MarkupLabel(Label):
    pass


class MarkupButton(Button):
    pass


class MoneyInput(TextInput):
    def insert_text(self, substring, from_undo=False):
        if not from_undo:
            current_text = self.text.replace(".", "") + substring
            current_text = current_text.zfill(3)
            new_text = current_text[:-2] + "." + current_text[-2:]
            new_text = (
                str(float(new_text)).rstrip("0").rstrip(".")
                if "." in new_text
                else new_text
            )
            self.text = ""
            self.text = new_text
        else:
            super(MoneyInput, self).insert_text(substring, from_undo=from_undo)


class FocusPopup(Popup):
    def focus_on_textinput(self, textinput):
        self.textinput_to_focus = textinput

    def on_open(self):
        if hasattr(self, "textinput_to_focus"):
            self.textinput_to_focus.focus = True


class FinancialSummaryWidget(MDFlatButton):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(FinancialSummaryWidget, cls).__new__(cls)
        return cls._instance

    def __init__(self, ref, **kwargs):
        if not hasattr(self, "_initialized"):
            self.app = ref
            super(FinancialSummaryWidget, self).__init__(**kwargs)
            # self.pos_hint = {'top':0.1,'right': 0.9}
            self.size_hint_y = None
            self.size_hint_x = None
            self.width = 350
            self.height = 200
            self.font = "images/VarelaRound-Regular.ttf"

            # self.padding = (100, 0, 0, 0)
            self._no_ripple_effect = True
            self.text = ""

            self.layout = BoxLayout(orientation="vertical", size_hint=(1, 1))

            self.subtotal_label = MDLabel(markup=True, halign="right")
            self.discount_label = MDLabel(markup=True, halign="right")
            self.tax_label = MDLabel(markup=True, halign="right")
            self.total_label = MDLabel(markup=True, font_style="H5", halign="right")
            self.blank = BoxLayout(size_hint_y=None, height=20)
            self.layout.add_widget(self.subtotal_label)
            self.layout.add_widget(self.discount_label)
            self.layout.add_widget(self.tax_label)
            self.layout.add_widget(self.blank)
            self.layout.add_widget(self.total_label)

            self.add_widget(self.layout)

            self._initialized = True
            self.update_summary(0, 0, 0, 0)

    def update_summary(self, subtotal, tax, total_with_tax, discount):
        self.subtotal_label.font_name = self.font
        self.discount_label.font_name = self.font
        self.tax_label.font_name = self.font
        self.total_label.font_name = self.font

        self.subtotal_label.text = f"[size=20]Subtotal: ${subtotal:.2f}[/size]"
        self.discount_label.text = f"[size=20]Discount: ${discount:.2f}[/size]"
        self.tax_label.text = f"[size=20]Tax: ${tax:.2f}[/size]"
        self.total_label.text = f"[size=42]Total: [b]${total_with_tax:.2f}[/b][/size]"
        # self.update_mirror_image()

    def on_press(self):
        self.open_order_modification_popup()

    def update_mirror_image(self, *args):
        try:
            snapshot_path = "mirror_snapshot.png"
            self.export_to_png(snapshot_path)
            cropped_img = self.crop_bottom_right_corner(
                "mirror_snapshot.png", "cropped_mirror_snapshot.png"
            )

            self.app.utilities.mirror_image.source = "cropped_mirror_snapshot.png"
            self.app.utilities.mirror_image.reload()
        except:
            pass

    def crop_bottom_right_corner(self, source_path, target_path, crop_size=(350, 50)):
        with PILImage.open(source_path) as img:
            original_width, original_height = img.size
            crop_width, crop_height = crop_size

            left = original_width - crop_width
            upper = original_height - crop_height
            right = original_width
            lower = original_height

            crop_rectangle = (left, upper, right, lower)
            cropped_img = img.crop(crop_rectangle)
            cropped_img.save(target_path)

    def clear_order(self):
        self.app.order_layout.clear_widgets()
        self.app.order_manager.clear_order()
        self.app.utilities.update_financial_summary()
        self.order_mod_popup.dismiss()

    def open_order_modification_popup(self):
        open_order_modification_popup_md_bg_color = (0.25, 0.25, 0.25, 0.75)
        order_mod_layout = MDBoxLayout(orientation="vertical", spacing=10, padding=10)
        if float(self.app.order_manager.order_discount) > 0:
            discount_order_button = MDFlatButton(
                text="[b][size=20]Remove Order Discount[/b][/size]",
                # pos_hint={"center_x": 0.5, "center_y": 1},
                size_hint=(None, None),
                _min_height=100,
                _min_width=100,
                md_bg_color=open_order_modification_popup_md_bg_color,
                on_press=lambda x: self.remove_order_discount(),
            )
        else:
            discount_order_button = MDFlatButton(
                text="[b][size=20]Add Order Discount[/b][/size]",
                # pos_hint={"center_x": 0.5, "center_y": 1},
                size_hint=(None, None),
                _min_height=100,
                _min_width=100,
                md_bg_color=open_order_modification_popup_md_bg_color,
                on_press=lambda x: self.app.popup_manager.add_order_discount_popup(),
            )
        clear_order_button = MDFlatButton(
            text="[b][size=20]Clear Order[/b][/size]",
            # pos_hint={"center_x": 0.5, "center_y": 1 - 0.2},
            size_hint=(None, None),
            _min_height=100,
            md_bg_color=open_order_modification_popup_md_bg_color,
            on_press=lambda x: self.clear_order(),
        )
        adjust_price_button = MDFlatButton(
            text="[b][size=20]Adjust Payment[/b][/size]",
            # pos_hint={"center_x": 0.5, "center_y": 1 - 0.4},
            size_hint=(None, None),
            _min_height=100,
            md_bg_color=open_order_modification_popup_md_bg_color,
            on_press=lambda x: self.adjust_price(),
        )
        medical_military_discount_button = MDFlatButton(
            text="[b][size=20]Medical/Military Discount[/b][/size]",
            # pos_hint={"center_x": 0.5, "center_y": 1 - 0.4},
            size_hint=(None, None),
            _min_height=100,
            _min_width=100,
            md_bg_color=open_order_modification_popup_md_bg_color,
            on_press=lambda x: self.app.popup_manager.apply_discount(10, military=True),
        )

        order_mod_layout.add_widget(clear_order_button)
        order_mod_layout.add_widget(adjust_price_button)

        order_mod_layout.add_widget(discount_order_button)
        order_mod_layout.add_widget(medical_military_discount_button)
        self.order_mod_popup = Popup(
            title="",
            content=order_mod_layout,
            size_hint=(0.2, 0.6),
            background="images/transparent.png",
            background_color=(0, 0, 0, 0),
            separator_height=0,
            pos_hint={"center_x": 0.825, "center_y": 0.43},
            # padding=(0,250,600,0),
            overlay_color=[0, 0, 0, 0],
        )
        self.order_mod_popup.open()

    def remove_order_discount(self):
        self.app.order_manager.remove_order_discount()
        self.order_mod_popup.dismiss()

    def save_order(self):
        self.app.order_manager.save_order_to_disk()
        self.add_saved_orders_to_clock_layout()
        # self.open_save_order_popup()
        toast("Saved!")
        self.app.order_manager.clear_order()
        try:
            self.order_mod_popup.dismiss()
        except Exception as e:
            logger.info(f"[Popups]: save_order expected errror\n{e}")
        self.app.utilities.update_display()
        self.app.utilities.update_financial_summary()

    def add_saved_orders_to_clock_layout(self):
        orders = self.app.order_manager.list_all_saved_orders()
        if len(orders) > 0:
            self.app.utilities.saved_order_title.text = "Saved Orders"
            self.app.utilities.saved_order_divider.md_bg_color = "blue"
        else:
            self.app.utilities.saved_order_title.text = ""
            self.app.utilities.saved_order_divider.md_bg_color = (0, 0, 0, 0)
        labels = [
            self.app.utilities.saved_order_button1_label,
            self.app.utilities.saved_order_button2_label,
            self.app.utilities.saved_order_button3_label,
            self.app.utilities.saved_order_button4_label,
            self.app.utilities.saved_order_button5_label,
        ]

        buttons = [
            self.app.utilities.saved_order_button1,
            self.app.utilities.saved_order_button2,
            self.app.utilities.saved_order_button3,
            self.app.utilities.saved_order_button4,
            self.app.utilities.saved_order_button5,
        ]

        for label in labels:
            label.text = ""

        for order, label, button in zip(orders, labels, buttons):
            items = str(order["items"])

            items_no_brackets = items.replace("[", "").replace("]", "").replace("'", "")
            if len(items_no_brackets) > 50:
                items_trunc = items_no_brackets[:50] + "..."
            else:
                items_trunc = items_no_brackets

            label.text = items_trunc
            button.on_press = lambda order=order, button=button: self.load_order(
                order=order, button=button
            )

    def delete_order(self, order):
        self.app.order_manager.delete_order_from_disk(order)
        try:
            self.list_saved_orders_popup.dismiss()
            self.open_list_saved_orders_popup()
        except:
            pass

    def load_order(self, order, button):
        self.app.order_manager.load_order_from_disk(order)
        button.md_bg_color = (0, 0, 0, 0)
        self.delete_order(order)
        self.add_saved_orders_to_clock_layout()

    def open_list_saved_orders_popup(self):
        content_layout = GridLayout(orientation="lr-tb", cols=3, rows=10)
        orders = self.app.order_manager.list_all_saved_orders()
        for order in orders:
            order_str = ""
            for item in order["items"]:
                order_str.join(item)
            items = str(order["items"])
            order_id = str(order["order_id"])
            entry = MDLabel(text=f"{order_id}\n{items}", size_hint_y=0.1)
            button = Button(
                text="Open",
                size_hint_y=0.1,
                on_press=lambda x, order=order: self.load_order(order=order),
            )
            del_button = Button(
                text="Delete",
                size_hint_y=0.1,
                on_press=lambda x, order=order: self.delete_order(order=order),
            )
            content_layout.add_widget(entry)
            content_layout.add_widget(button)
            content_layout.add_widget(del_button)
        self.list_saved_orders_popup = Popup(
            content=content_layout, size_hint=(0.8, 0.4)
        )
        self.list_saved_orders_popup.open()

    def open_save_order_popup(self):
        layout = GridLayout(orientation="tb-lr", rows=1, cols=1)
        label = Label(text="Saved!", size_hint=(1, 0.5))
        # button = MDRaisedButton(text="Dismiss", size_hint=(1, 0.5), on_press=lambda x: self.save_order_popup.dismiss())
        layout.add_widget(label)
        # layout.add_widget(button)
        self.save_order_popup = Popup(
            size_hint=(0.2, 0.2),
            content=layout,
            title="",
            background="images/transparent.png",
            background_color=(0, 0, 0, 0),
            separator_height=0,
        )
        self.save_order_popup.open()

        Clock.schedule_once(lambda dt: self.save_order_popup.dismiss(), 1)

    def adjust_price(self):
        self.app.popup_manager.show_adjust_price_popup()
        self.order_mod_popup.dismiss()


class Calculator:
    def __init__(self):
        self.operators = ["+", "-", "*", "/"]
        self.last_was_operator = None
        self.last_button = None
        self.calculation = ""

    def create_calculator_layout(self):
        main_layout = MDGridLayout(cols=1, spacing=5, size_hint=(1, 1))
        text_layout = MDBoxLayout(orientation="horizontal", size_hint_y=0.2)
        self.solution = MDTextField(
            multiline=False,
            readonly=True,
            halign="right",
            font_size=30,
            mode="rectangle",
            size_hint_x=1,
        )
        text_layout.add_widget(self.solution)
        main_layout.add_widget(text_layout)

        number_layout = MDGridLayout(cols=3, spacing=5, size_hint=(1, 0.6))

        buttons = ["1", "2", "3", "4", "5", "6", "7", "8", "9", ".", "0", "C"]

        for button in buttons:
            number_layout.add_widget(
                MDRaisedButton(
                    text=button,
                    font_style="H1",
                    size_hint=(1, 1),
                    on_press=self.on_button_press,
                )
            )
        main_layout.add_widget(number_layout)

        operation_button_layout = MDGridLayout(cols=5, spacing=5, size_hint=(1, 0.1))
        operation_buttons = ["+", "-", "*", "/", "="]
        for op_button in operation_buttons:
            if op_button == "=":
                operation_button_layout.add_widget(
                    MDRaisedButton(
                        text=op_button,
                        md_bg_color=get_color_from_hex("#4CAF50"),
                        size_hint=(1, 1),
                        font_style="H1",
                        on_press=self.on_solution,
                    )
                )
            else:
                operation_button_layout.add_widget(
                    MDRaisedButton(
                        text=op_button,
                        md_bg_color=get_color_from_hex("#2196F3"),
                        size_hint=(1, 1),
                        font_style="H1",
                        on_press=self.on_button_press,
                    )
                )
        main_layout.add_widget(operation_button_layout)

        return main_layout

    def on_button_press(self, instance):
        current = self.solution.text
        button_text = instance.text

        if button_text == "C":
            self.solution.text = ""
        else:
            if current and (self.last_was_operator and button_text in self.operators):
                return
            elif current == "" and button_text in self.operators:
                return
            else:
                new_text = current + button_text
                self.solution.text = new_text

        self.last_was_operator = button_text in self.operators
        self.last_button = button_text

    def on_solution(self, instance):
        text = self.solution.text
        if text:
            try:
                self.solution.text = str(eval(self.solution.text))
            except Exception:
                self.solution.text = "Error"

    def show_calculator_popup(self):
        calculator_layout = self.create_calculator_layout()
        calculator_popup = Popup(
            content=calculator_layout,
            size_hint=(0.4, 0.8),
            title="",
            background="images/transparent.png",
            background_color=(0, 0, 0, 0),
            separator_height=0,
        )
        calculator_popup.open()


class NonModalPopup(Popup):
    def on_touch_down(self, touch):
        super_result = super().on_touch_down(touch)
        return False

    def on_touch_move(self, touch):
        super_result = super().on_touch_move(touch)
        return False

    def on_touch_up(self, touch):
        super_result = super().on_touch_up(touch)
        return False


class ConditionalModalPopup(Popup):
    def on_touch_down(self, touch):
        if self.opacity == 0:
            return False
        return super(ConditionalModalPopup, self).on_touch_down(touch)

    def on_touch_move(self, touch):
        if self.opacity == 0:
            return False
        return super(ConditionalModalPopup, self).on_touch_move(touch)

    def on_touch_up(self, touch):
        if self.opacity == 0:
            return False
        return super(ConditionalModalPopup, self).on_touch_up(touch)


class TouchableMDBoxLayout(BoxLayout):
    def __init__(self, checkbox, **kwargs):
        super(TouchableMDBoxLayout, self).__init__(**kwargs)
        self.checkbox = checkbox

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.checkbox.active = not self.checkbox.active
            return True
        return super(TouchableMDBoxLayout, self).on_touch_down(touch)


class CustomCheckbox(MDCheckbox):
    active_color = ColorProperty([0, 0.5, 0.5, 1])

    def on_active(self, instance, value):
        if value:
            self.md_bg_color = self.active_color
        else:
            self.md_bg_color = self.theme_cls.primary_light


class AutoSaveTextInput(TextInput):
    def __init__(self, notes_dir, note_id, name, admin, **kwargs):
        super().__init__(**kwargs)
        self.notes_dir = notes_dir
        self.note_id = note_id
        self.note_name = name
        self.admin = admin
        self.bind(text=self.on_text)

    def on_text(self, instance, value):
        self.save_note_content({"name": self.note_name, "body": value})

    def save_note_content(self, content):
        content["last_modified"] = datetime.now().isoformat()
        content["admin"] = self.admin
        with open(os.path.join(self.notes_dir, f"{self.note_id}.json"), "w") as file:
            json.dump(content, file)

    def load_note_content(self):
        try:
            with open(
                os.path.join(self.notes_dir, f"{self.note_id}.json"), "r"
            ) as file:
                return json.load(file)
        except FileNotFoundError:
            return {"name": "", "body": "", "last_modified": "", "admin": False}
