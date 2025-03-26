import csv
import json
from datetime import datetime, timedelta

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import StringProperty, ObjectProperty
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivymd.uix.boxlayout import BoxLayout, MDBoxLayout
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.pickers import MDDatePicker
from kivy.uix.gridlayout import GridLayout
from database_manager import DatabaseManager
from receipt_printer import ReceiptPrinter
from rapidfuzz import process, fuzz
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
import inspect

import logging
logger = logging.getLogger('rigs_pos')


def log_caller_info(depths=1, to_file=False, filename="history_manager_dismiss_log.txt"):
    stack = inspect.stack()
    if isinstance(depths, int):
        depths = [depths]

    output_lines = []

    for depth in depths:
        if depth < len(stack):
            caller_frame = stack[depth]
            file_name = caller_frame.filename
            line_number = caller_frame.lineno
            function_name = caller_frame.function
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            line = f"{timestamp} - Called from {file_name}, line {line_number}, in {function_name}\n"
            output_lines.append(line)
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            line = f"{timestamp} - No caller information available for depth: {depth}\n"
            output_lines.append(line)

    if to_file:

        with open(filename, 'a') as f:
            f.writelines(output_lines)
    else:
        logger.warn(''.join(output_lines))

class NullableStringProperty(StringProperty):
    def __init__(self, *args, **kwargs):

        kwargs.setdefault("allownone", True)
        super(NullableStringProperty, self).__init__(*args, **kwargs)


class HistoryPopup(Popup):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(HistoryPopup, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, **kwargs):
        if not hasattr(self, "_init"):
            self._init = True
            super(HistoryPopup, self).__init__(**kwargs)
            self.db_manager = DatabaseManager("db/inventory.db", self)
            # self.history_view = HistoryView()


    def on_dismiss(self, *args, **kwargs):
        for i in range(10):
            log_caller_info(depths=i, to_file=True)
        super().on_dismiss(*args, **kwargs)

    def show_hist_reporting_popup(self, instance=None):
        order_history = self.db_manager.get_order_history()
        # print(order_history)
        history_view = HistoryView()

        history_view.show_reporting_popup(order_history)
        history_view.filter_today()
        self.content = history_view
        self.size_hint = (0.9, 0.9)
        self.title = f"Order History"
        Clock.schedule_once(self.open, 0.5)
        # self.open()

    def dismiss_popup(self):
        self.dismiss()


class HistoryRow(BoxLayout):
    order_id = NullableStringProperty()
    items = NullableStringProperty()
    total = NullableStringProperty()
    tax = NullableStringProperty()
    total_with_tax = NullableStringProperty()
    timestamp = NullableStringProperty()
    history_view = ObjectProperty()
    payment_method = NullableStringProperty()
    amount_tendered = NullableStringProperty()
    change_given = NullableStringProperty()

    def __init__(self, **kwargs):

        super(HistoryRow, self).__init__(**kwargs)
        self.order_history = None


class HistoryView(BoxLayout):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(HistoryView, cls).__new__(cls)
        return cls._instance

    def __init__(self, ref=None, **kwargs):
        if not hasattr(self, "_init"):
            super(HistoryView, self).__init__(**kwargs)
            self._init = True
            self.order_history = []
            self.orientation = "vertical"
            self.current_filter = "today"

        if ref is not None:
            self.app = ref
            self.receipt_printer = self.app.receipt_printer
            self.initialize_total_layout()
            self.initialize_buttons()
            self.add_widget(self.totals_layout)
            self.add_widget(self.button_layout)

            Clock.schedule_once(self.init_filter, 0.1)

    def initialize_total_layout(self):
        blank = BoxLayout()
        self.totals_layout = GridLayout(orientation="lr-tb", cols=5, size_hint=(1, 0.1))
        self.history_search = TextInput(hint_text="Search by item name")
        self.history_search.bind(text=self.on_search_text_changed)
        self.total_amount_label = MDLabel(text="Total: $0.00")
        self.current_filter_label = MDLabel(text="Current Filter: today")
        self.total_cash_label = MDLabel(text="Total Cash: $0.00")
        self.totals_layout.add_widget(self.history_search)
        self.totals_layout.add_widget(blank)
        self.totals_layout.add_widget(self.current_filter_label)
        self.totals_layout.add_widget(self.total_cash_label)
        self.totals_layout.add_widget(self.total_amount_label)

        self.button_layout = BoxLayout(orientation="horizontal", size_hint=(1, 0.4))

    def initialize_buttons(self):
        self.button_layout = BoxLayout(
            orientation="horizontal", spacing=5, size_hint=(1, 0.1)
        )
        self.button_layout.add_widget(
            MDRaisedButton(
                text="[b][size=20]Today[/size][/b]",
                size_hint=(1, 1),
                on_press=lambda x: self.filter_today(),
            )
        )
        self.button_layout.add_widget(
            MDRaisedButton(
                text="[b][size=20]Yesterday[/size][/b]",
                size_hint=(1, 1),
                on_press=lambda x: self.filter_yesterday(),
            )
        )

        # self.button_layout.add_widget(
        #     MDRaisedButton(
        #         text="This Week", size_hint=(1, 1), on_press=self.filter_this_week
        #     )
        # )
        # self.button_layout.add_widget(
        #     MDRaisedButton(
        #         text="This Month", size_hint=(1, 1), on_press=self.filter_this_month
        #     )
        # )
        self.button_layout.add_widget(
            MDRaisedButton(
                text="[b][size=20]Specific Day[/size][/b]",
                size_hint=(1, 1),
                on_press=self.show_specific_day_popup,
            )
        )
        self.button_layout.add_widget(
            MDRaisedButton(
                text="[b][size=20]Custom Range[/size][/b]",
                size_hint=(1, 1),
                on_press=self.show_custom_range_popup,
            )
        )
        self.button_layout.add_widget(
            MDRaisedButton(
                text="[b][size=20]Export CSV[/size][/b]",
                size_hint=(1, 1),
                on_press=self.export_history,
            )
        )
        return self.button_layout

    def init_filter(self, dt):
        self.filter_today()
        self.update_totals()

    def update_totals(self):

        total_amount = sum(float(order["total"]) for order in self.rv_data)
        total_tax = sum(float(order["tax"]) for order in self.rv_data)
        total_with_tax = sum(float(order["total_with_tax"]) for order in self.rv_data)
        total_tendered = sum(float(order["amount_tendered"]) for order in self.rv_data)
        total_change = sum(float(order["change_given"]) for order in self.rv_data)
        total_cash = sum(
            float(order["amount_tendered"]) - float(order["change_given"])
            for order in self.rv_data
        )

        self.total_amount_label.text = f"[size=20]Total: {total_amount:.2f} + {total_tax:.2f} tax = [b]${total_with_tax:.2f}[/b][/size]"

        self.total_cash_label.text = f"[size=20]Cash: {total_tendered:.2f} - {total_change:.2f} change = [b]${total_cash:.2f}[/b][/size]"
        self.current_filter_label.text = f"Current Filter: {self.current_filter}"

    def show_reporting_popup(self, order_history):
        self.order_history = order_history
        try:
            self.rv_data = [
                {
                    "order_id": order[0],
                    "items": self.format_items(order[1]),
                    "total": self.format_money(order[2]),
                    "tax": self.format_money(order[3]),
                    "discount": self.format_money(order[4]),
                    "total_with_tax": self.format_money(order[5]),
                    "timestamp": self.format_date(order[6]),
                    "payment_method": order[7],
                    "amount_tendered": self.format_money(order[8]),
                    "change_given": self.format_money(order[9]),
                    "history_view": self,
                }
                for order in order_history
            ]

            self.rv_data.reverse()
            self.ids.history_rv.data = self.rv_data
        except Exception as e:
            logger.warn(f"[HistoryManager] show_reporting_popup\n{e}")

    def create_history_row(self, order):

        try:
            history_row = HistoryRow()
            history_row.order_id = order[0]
            history_row.items = self.format_items(order[1])
            history_row.total = self.format_money(order[2])
            history_row.tax = self.format_money(order[3])
            history_row.discount = self.format_money(order[4])
            history_row.total_with_tax = self.format_money(order[5])
            history_row.timestamp = self.format_date(order[6])
            history_row.payment_method = order[7]
            history_row.amount_tendered = self.format_money(order[8])
            history_row.change_given = self.format_money(order[9])
            history_row.history_view = self
            return history_row
        except Exception as e:
            logger.warn(f"[HistoryManager] create_history_row\n{e}")

    def show_specific_day_popup(self, instance):
        specific_day_picker = MDDatePicker()
        specific_day_picker.bind(on_save=self.on_specific_day_selected)
        specific_day_picker.open()

    def on_specific_day_selected(self, instance, picker, date):
        self.current_filter = "specific_day"

        filtered_history = [
            order
            for order in self.order_history
            if datetime.strptime(order[6], "%Y-%m-%d %H:%M:%S.%f").date() == picker
        ]
        self.update_rv_data(filtered_history)
        self.update_totals()

    def show_custom_range_popup(self, instance):
        custom_range_picker = MDDatePicker(mode="range")
        custom_range_picker.bind(on_save=self.on_custom_range_selected)
        custom_range_picker.open()

    def on_custom_range_selected(self, instance, picker, date_range):
        self.current_filter = "custom_range"

        date_set = set(date_range)

        filtered_history = [
            order
            for order in self.order_history
            if datetime.strptime(order[6], "%Y-%m-%d %H:%M:%S.%f").date() in date_set
        ]
        self.update_rv_data(filtered_history)
        self.update_totals()

    def update_rv_data(self, filtered_history):
        try:
            self.rv_data = [
                {
                    "order_id": order[0],
                    "items": self.format_items(order[1]),
                    "total": self.format_money(order[2]),
                    "tax": self.format_money(order[3]),
                    "discount": self.format_money(order[4]),
                    "total_with_tax": self.format_money(order[5]),
                    "timestamp": self.format_date(order[6]),
                    "payment_method": order[7],
                    "amount_tendered": self.format_money(order[8]),
                    "change_given": self.format_money(order[9]),
                    "history_view": self,
                }
                for order in filtered_history
            ]
            self.rv_data.reverse()
            self.ids.history_rv.data = self.rv_data
        except Exception as e:
            logger.warn(f"[HistoryManager]: update_rv_data \n{e}")

    def is_today(self, date_obj):
        return date_obj.date() == datetime.today().date()

    def filter_today(self):
        # print("filtered today")
        self.current_filter = "today"
        filtered_history = [
            order
            for order in self.order_history
            if self.is_today(datetime.strptime(order[6], "%Y-%m-%d %H:%M:%S.%f"))
        ]
        self.update_rv_data(filtered_history)
        self.update_totals()

    def is_this_week(self, date_obj):
        today = datetime.today()
        start_week = today - timedelta(days=today.weekday())
        end_week = start_week + timedelta(days=6)
        return start_week.date() <= date_obj.date() <= end_week.date()

    def filter_this_week(self, instance):
        self.current_filter = "this_week"
        filtered_history = [
            order
            for order in self.order_history
            if self.is_this_week(datetime.strptime(order[6], "%Y-%m-%d %H:%M:%S.%f"))
        ]
        self.update_rv_data(filtered_history)
        self.update_totals()

    def is_this_month(self, date_obj):
        today = datetime.today()
        return date_obj.month == today.month and date_obj.year == today.year

    def filter_this_month(self, instance):
        self.current_filter = "this_month"

        filtered_history = [
            order
            for order in self.order_history
            if self.is_this_month(datetime.strptime(order[6], "%Y-%m-%d %H:%M:%S.%f"))
        ]
        self.update_rv_data(filtered_history)
        self.update_totals()

    def is_yesterday(self, date_obj):
        yesterday = datetime.today() - timedelta(days=1)
        return date_obj.date() == yesterday.date()

    def filter_yesterday(self):
        self.current_filter = "yesterday"
        filtered_history = [
            order
            for order in self.order_history
            if self.is_yesterday(datetime.strptime(order[6], "%Y-%m-%d %H:%M:%S.%f"))
        ]
        self.update_rv_data(filtered_history)
        self.update_totals()

    def set_order_history(self, order_history):
        self.order_history = order_history

    def on_search_text_changed(self, instance, value):
        if len(value) >= 1:
            self.current_filter = "search"
            self.search_order_by_item_name(value)

        else:
            self.current_filter = "today"
            self.filter_today()

    def search_order_by_item_name(self, search_term):
        search_term = search_term.lower()
        filtered_history = []

        for order in self.order_history:

            items_str = order[1]
            try:
                items = json.loads(items_str)
                for item in items:
                    if search_term in item["name"].lower():
                        filtered_history.append(order)
                        break
            except json.JSONDecodeError as e:
                logger.warn(f"[OrderManager]: search_order_by_item_name\n{e}")
                continue

        self.update_rv_data(filtered_history)
        self.update_totals()

    def display_order_details(
        self,
        order_id,
    ):
        order_id_str = str(order_id)
        try:
            specific_order = next(
                (
                    order
                    for order in self.order_history
                    if str(order[0]) == order_id_str
                ),
                None,
            )
        except Exception as e:
            logger.warn(f"[HistoryManager] display_order_details\n{e}")

        if specific_order:
            try:
                popup = OrderDetailsPopup(specific_order, self.receipt_printer)

                popup.open()
            except Exception as e:
                logger.warn(e)

    # def display_order_details_from_barcode_scan(self, barcode):
    #     try:
    #
    #         barcode_str = str(barcode)
    #         order_history = self.app.db_manager.get_order_history()
    #         specific_order = next(
    #             (
    #                 order
    #                 for order in order_history
    #                 if str(order[0]).startswith(barcode_str)
    #             ),
    #             None,
    #         )
    #
    #         if specific_order:
    #             popup = OrderDetailsPopup(specific_order, self.receipt_printer)
    #             popup.open()
    #         else:
    #             self.order_not_found_popup(barcode_str)  # needs testing
    #
    #     except Exception as e:
    #         print(f"[HistoryManager] display_order_details_from_barcode_scan\n{e}")

    def display_order_details_from_barcode_scan(self, barcode):
        try:
            barcode_str = str(barcode)
            order_history = self.app.db_manager.get_order_history()

            order_barcodes = [str(order[0]) for order in order_history]

            best_match, score, *_ = process.extractOne(
                barcode_str, order_barcodes, scorer=fuzz.partial_ratio, score_cutoff=80
            )

            if best_match:
                specific_order = next(
                    (order for order in order_history if str(order[0]) == best_match),
                    None,
                )

                if specific_order:
                    popup = OrderDetailsPopup(specific_order, self.receipt_printer)
                    popup.open()
                else:
                    self.order_not_found_popup(barcode_str)  # needs testing
            else:
                self.order_not_found_popup(barcode_str)

        except Exception as e:
            logger.warn(f"[HistoryManager] display_order_details_from_barcode_scan\n{e}")

    def order_not_found_popup(self, order):
        not_found_layout = BoxLayout(size_hint=(1, 1))
        not_found_label = Label(text=f"Order {order} Not Found")
        not_found_button = MDRaisedButton(
            text="Dismiss", on_press=lambda x: self.not_found_popup.dismiss()
        )
        not_found_layout.add_widget(not_found_label)
        not_found_layout.add_widget(not_found_button)
        self.not_found_popup = Popup(content=not_found_layout, size_hint=(0.4, 0.4))
        self.not_found_popup.open()

    def show_order_details(self, order_id):
        specific_order = next(
            (order for order in self.order_history if order[0] == order_id), None
        )
        if specific_order:
            # print(specific_order)
            self.clear_widgets()
            try:
                history_row = self.create_history_row(specific_order)
                self.add_widget(history_row)
            except Exception as e:
                logger.warn(f"[HistoryManager] show_order_details\n{e}")

    def format_items(self, items_str):
        try:

            parsed_data = json.loads(items_str)

            if isinstance(parsed_data, dict):
                items_list = [parsed_data]
            else:
                items_list = parsed_data

            all_item_names = ", ".join(
                item.get("name", "Unknown") for item in items_list
            )

            return self.truncate_text(all_item_names)
        except json.JSONDecodeError as e:
            logger.warn(f"JSON parsing error in format_items: {e}")
            return self.truncate_text("Error parsing items")

    def format_money(self, value):
        formatted_value = "{:.2f}".format(value)
        return formatted_value

    def format_date(self, date_str):
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S.%f")
            return date_obj.strftime("%d %b %Y, %H:%M")
        except Exception as e:
            logger.warn(e)

    def truncate_text(self, text, max_length=120):
        return text if len(text) <= max_length else text[: max_length - 3] + "..."

    def export_history(self, instance):
        filename = self.get_export_filename()

        csv_data = self.prepare_csv_data()

        with open(filename, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "Order ID",
                    "Items",
                    "Total",
                    "Tax",
                    "Discount",
                    "Total with Tax",
                    "Timestamp",
                    "Payment Method",
                    "Amount Tendered",
                    "Change Given",
                ]
            )
            for row in csv_data:
                writer.writerow(row)

    def get_export_filename(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if self.current_filter == "today":
            return f"Order_History_Today_{today}.csv"
        if self.current_filter == "this_week":
            return f"Order_History_This_Week_{today}.csv"
        if self.current_filter == "this_month":
            return f"Order_History_This_Month_{today}.csv"
        if self.current_filter == "custom_range":
            return f"Order_History_Custom_Range_{today}.csv"
        if self.current_filter == "specific_day":
            return f"Order_History_Custom_Range_{today}.csv"
        else:
            return f"Order_History_All_{today}.csv"

    def prepare_csv_data(self):
        return [
            [
                order["order_id"],
                order["items"],
                order["total"],
                order["tax"],
                order["discount"],
                order["total_with_tax"],
                order["timestamp"],
                order["payment_method"],
                order["amount_tendered"],
                order["change_given"],
            ]
            for order in self.rv_data
        ]


class OrderDetailsPopup(Popup):
    def __init__(self, order, receipt_printer, **kwargs):
        super(OrderDetailsPopup, self).__init__(**kwargs)
        self.title = f"Order Details - {order[0]}"
        self.history_view = HistoryView()
        self.history_popup = HistoryPopup()
        self.size_hint = (0.4, 0.8)
        self.receipt_printer = receipt_printer
        self.db_manager = DatabaseManager("db/inventory.db", self)

        content_layout = GridLayout(orientation="tb-lr", spacing=5, cols=1, rows=3)
        formatted_order_details = self.format_order_details(order)
        # print(formatted_order_details)

        # content_layout.add_widget(
        #     Label(text=self.format_order_details(order), valign="top", halign="left")
        # )
        top_layout = Label(
            halign="center",
            size_hint_y=0.1,
            text=f"\n{formatted_order_details['Timestamp']}",
        )
        items = formatted_order_details["Items"]
        items_split = items.split(",")
        formatted_items = "\n".join(items_split)
        if formatted_order_details["Payment Method"] == "Cash":
            middle_layout = Label(halign="center", text=f"{formatted_items}")
            bottom_layout = Label(
                halign="center",
                text=f"Subtotal: {formatted_order_details['Total']}\nDiscount: {formatted_order_details['Discount']}\nTax: {formatted_order_details['Tax']}\nTotal: {formatted_order_details['Total with Tax']}\n\nPaid with {formatted_order_details['Payment Method']}\nAmount Tendered: {formatted_order_details['Amount Tendered']}\nChange Given: {formatted_order_details['Change Given']}",
            )
            layout = MDCard(orientation="vertical")
            layout.add_widget(middle_layout)
            layout.add_widget(bottom_layout)
        # elif formatted_order_details['Payment Method'] == "Split":
        #     order_details = self.db_manager.get_order_by_id(order[0])
        #     print(order_details)
        else:
            middle_layout = Label(halign="center", text=f"{formatted_items}")
            bottom_layout = Label(
                halign="center",
                text=f"Subtotal: {formatted_order_details['Total']}\nDiscount: {formatted_order_details['Discount']}\nTax: {formatted_order_details['Tax']}\nTotal: {formatted_order_details['Total with Tax']}\n\nPaid with {formatted_order_details['Payment Method']}",
            )
            layout = MDCard(orientation="vertical")
            layout.add_widget(middle_layout)
            layout.add_widget(bottom_layout)

        button_layout = BoxLayout(size_hint=(1, 0.1), height=dp(50), spacing=5)

        button_layout.add_widget(
            MDRaisedButton(
                text="[b][size=20]Print Receipt[/size][/b]",
                on_press=lambda instance: self.print_receipt(instance, order=order),
                size_hint=(1, 1),
            )
        )
        button_layout.add_widget(
            MDRaisedButton(
                text="[b][size=20]Refund[/size][/b]",
                on_press=self.refund,
                size_hint=(1, 1),
            )
        )
        button_layout.add_widget(
            MDRaisedButton(
                text="[b][size=20]Edit[/size][/b]",
                on_press=lambda x: self.open_modify_order_popup(order[0]),
                size_hint=(1, 1),
            )
        )

        button_layout.add_widget(
            MDRaisedButton(
                text="[b][size=20]Close[/size][/b]",
                on_press=self.dismiss_popup,
                size_hint=(1, 1),
            )
        )
        content_layout.add_widget(top_layout)
        content_layout.add_widget(layout)
        content_layout.add_widget(button_layout)

        self.content = content_layout

    def open_modify_order_popup(self, order_id):
        order_details = self.db_manager.get_order_by_id(order_id)
        items_json = order_details[1]
        items = json.loads(items_json)
        modify_order_container = MDBoxLayout(
            orientation="vertical", size_hint=(1, 1), padding=5, spacing=5
        )
        modify_order_layout = GridLayout(
            rows=10, orientation="tb-lr", padding=5, spacing=5
        )
        item_name_inputs = []

        for item in items:
            text_input = TextInput(
                text=item["name"], multiline=False, size_hint_y=None, height=50
            )
            item_name_inputs.append(text_input)
            modify_order_layout.add_widget(text_input)

        def on_confirm(instance):
            for i in range(20):
                log_caller_info(depths=i, to_file=True)
            for item, name_input in zip(items, item_name_inputs):
                item["name"] = name_input.text

            updated_items_json = json.dumps(items)

            self.db_manager.modify_order(order_id, items=updated_items_json)
            self.dismiss()
            self.modify_order_popup.dismiss()
            logger.warn(self.history_view.current_filter)
            self.history_popup.dismiss_popup()
            Clock.schedule_once(self.history_popup.show_hist_reporting_popup, 0.2)

        buttons_layout = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=75, padding=5, spacing=5
        )
        confirm_button = MDRaisedButton(
            text="[b][size=20]Confirm Changes[/b][/size]",
            on_release=on_confirm,
            size_hint=(1, 1),
        )

        cancel_button = MDRaisedButton(
            text="[b][size=20]Cancel[/b][/size]",
            on_press=lambda instance: self.modify_order_popup.dismiss(),
            size_hint=(1, 1),
        )
        delete_button = MDFlatButton(
            md_bg_color="grey",
            text="Delete Order",
            on_press=lambda x: self.open_delete_order_confirmation_popup(
                order_id, admin=True
            ),
            size_hint=(0.5, 1),
        )
        _blank = MDBoxLayout(size_hint=(1, 1))
        buttons_layout.add_widget(confirm_button)
        buttons_layout.add_widget(cancel_button)
        buttons_layout.add_widget(_blank)
        buttons_layout.add_widget(delete_button)
        modify_order_container.add_widget(modify_order_layout)
        modify_order_container.add_widget(buttons_layout)

        self.modify_order_popup = Popup(
            size_hint=(0.8, 0.8),
            content=modify_order_container,
            title="",
            separator_height=0,
        )
        self.modify_order_popup.open()

    def open_delete_order_confirmation_popup(self, order_id, admin=False):  # TODO
        if admin:
            container = MDBoxLayout(orientation="vertical")
            layout = MDCard(orientation="vertical")
            message = MDLabel(
                text=f"Warning!\nOrder ID {order_id}\nWill Be Permanently Deleted!\nAre you sure?",
                halign="center",
            )
            layout.add_widget(message)
            btn_layout = MDBoxLayout(orientation="horizontal")
            confirm_button = MDFlatButton(
                text="Yes",
                on_press=lambda x: self.delete_order(order_id),
                size_hint=(1, 1),
            )
            _blank = MDBoxLayout(size_hint=(1, 0.4))
            cancel_button = MDFlatButton(
                text="No!",
                on_press=lambda x: self.delete_order_confirmation_popup.dismiss(),
                size_hint=(1, 1),
            )
            btn_layout.add_widget(confirm_button)
            btn_layout.add_widget(_blank)
            btn_layout.add_widget(cancel_button)
            container.add_widget(layout)
            container.add_widget(btn_layout)
            self.delete_order_confirmation_popup = Popup(
                size_hint=(0.2, 0.2), content=container, title="", separator_height=0
            )
            self.delete_order_confirmation_popup.open()

        else:
            self.do_nothing()

    def delete_order(self, order_id):
        self.db_manager.delete_order(order_id)
        self.delete_order_confirmation_popup.dismiss()
        self.modify_order_popup.dismiss()
        self.dismiss()
        self.history_popup.dismiss_popup()
        Clock.schedule_once(self.history_popup.show_hist_reporting_popup, 0.2)

    def do_nothing(self, *args, **kwargs):
        pass

    def format_order_details(self, order):

        formatted_order_dict = {
            "Order ID": order[0],
            "Items": self.format_items(order[1]),
            "Total": f"${self.history_view.format_money(order[2])}",
            "Tax": f"${self.history_view.format_money(order[3])}",
            "Discount": f"${self.history_view.format_money(order[4])}",
            "Total with Tax": f"${self.history_view.format_money(order[5])}",
            "Timestamp": self.history_view.format_date(order[6]),
            "Payment Method": order[7],
            "Amount Tendered": f"${self.history_view.format_money(order[8])}",
            "Change Given": f"${self.history_view.format_money(order[9])}",
        }

        return formatted_order_dict

    def print_receipt(self, instance, order):
        order_dict = self.convert_order_to_dict(order)
        self.receipt_printer.print_receipt(order_dict, reprint=True)

    def refund(self, instance):
        pass

    def dismiss_popup(self, instance):
        # print("called dismiss popup\n\n")
        # for i in range(20):
        #     log_caller_info(depths=i, to_file=True)
        self.dismiss()

    def format_items(self, items_str):

        try:
            parsed_data = json.loads(items_str)

            if isinstance(parsed_data, dict):
                items_list = [parsed_data]
            else:
                items_list = parsed_data

            all_item_names = ", ".join(
                f"{item.get('quantity', 'N/A')} {item.get('name', 'Unknown')}"
                for item in items_list
            )

            return all_item_names
        except json.JSONDecodeError as e:
            logger.warn(f"JSON parsing error in format_items: {e}")
            return "Error parsing items"

    def convert_order_to_dict(self, order):
        # print(order)

        (
            order_id,
            items_json,
            total,
            tax,
            discount,
            total_with_tax,
            timestamp,
            payment_method,
            amount_tendered,
            change_given,
        ) = order
        try:
            items = json.loads(items_json)
        except json.JSONDecodeError as e:
            logger.warn(f"[OrderDetailsPopup] convert_order_to_dict \n{e}")
            # items = ast.literal_eval(items_json)

        if isinstance(items, list):
            items_dict = {str(i): item for i, item in enumerate(items)}
        else:
            items_dict = items

        order_dict = {
            "order_id": order_id,
            "items": items_dict,
            "subtotal": total,
            "tax_amount": tax,
            "total_with_tax": total_with_tax,
            "timestamp": timestamp,
            "discount": discount,
            "payment_method": payment_method,
            "amount_tendered": amount_tendered,
            "change_given": change_given,
        }

        return order_dict
