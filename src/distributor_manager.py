from kivy.properties import StringProperty, NumericProperty
from kivy.uix.popup import Popup
from kivymd.uix.boxlayout import BoxLayout
from database_manager import DatabaseManager
from kivy.uix.gridlayout import GridLayout
from kivy.uix.textinput import TextInput
from kivymd.uix.button import MDRaisedButton, MDFlatButton, MDIconButton


class DistPopup(Popup):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DistPopup, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, **kwargs):
        if not hasattr(self, "_init"):
            self._init = True
            super(DistPopup, self).__init__(**kwargs)
            self.db_manager = DatabaseManager("db/inventory.db", self)
            # self.dist_view = DistView()

    def show_dist_reporting_popup(self, instance=None):
        order_dist = self.db_manager.get_all_distrib()
        container = BoxLayout(orientation="vertical")
        dist_view = DistView()

        dist_view.show_reporting_popup(order_dist)
        search_bar = GridLayout(orientation="lr-tb", size_hint_y=0.05, cols=3)
        dist_filter = TextInput(hint_text="dist", size_hint_x=40)
        item_filter = TextInput(hint_text="item", size_hint_x=40)
        price_filter = MDRaisedButton(text="price", size_hint_x=20)
        search_bar.add_widget(dist_filter)
        search_bar.add_widget(item_filter)
        search_bar.add_widget(price_filter)
        container.add_widget(search_bar)
        container.add_widget(dist_view)
        self.content = container
        self.size_hint = (0.9, 0.9)
        self.title = f"Order Dist"
        self.open()

    def dismiss_popup(self):
        self.dismiss()


class DistRow(BoxLayout):
    text = StringProperty()
    secondary_text = StringProperty()
    item_name = StringProperty()
    price = NumericProperty()
    price_str = str(price)
    price_str = StringProperty()
    notes = StringProperty()

    def __init__(self, **kwargs):

        super(DistRow, self).__init__(**kwargs)
        self.order_dist = None

    def do_nothin(self):
        pass


class DistView(BoxLayout):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(DistView, cls).__new__(cls)
        return cls._instance

    def __init__(self, ref=None, **kwargs):
        if not hasattr(self, "_init"):
            super(DistView, self).__init__(**kwargs)
            self._init = True
            self.order_dist = []
            self.orientation = "vertical"

        if ref is not None:
            self.app = ref

    def show_reporting_popup(self, order_dist):
        self.order_dist = order_dist
        try:
            self.rv_data = self.generate_data_for_rv()

            self.rv_data.reverse()
            self.ids.dist_rv.data = self.rv_data
        except Exception as e:
            print(f"[DistManager] show_reporting_popup\n{e}")

    def generate_data_for_rv(self):
        data_from_db = self.app.db_manager.get_all_distrib()
        formatted_data = [
            {
                #'viewclass': 'DistributorItem',
                "text": distrib["name"],
                "secondary_text": distrib["contact_info"],
                "item_name": distrib["item_name"],
                "price": str(distrib["price"]),
                "notes": distrib["notes"],
                #'height': 50,
            }
            for distrib in data_from_db.values()
        ]

        return formatted_data


#
# def create_dist_row(self, order):
#
#        try:
#            dist_row = DistRow()
#            dist_row.order_id = order[0]
#            dist_row.items = self.format_items(order[1])
#            dist_row.total = self.format_money(order[2])
#            dist_row.tax = self.format_money(order[3])
#            dist_row.discount = self.format_money(order[4])
#            dist_row.total_with_tax = self.format_money(order[5])
#            dist_row.timestamp = self.format_date(order[6])
#            dist_row.payment_method = order[7]
#            dist_row.amount_tendered = self.format_money(order[8])
#            dist_row.change_given = self.format_money(order[9])
#            dist_row.dist_view = self
#            return dist_row
#        except Exception as e:
#            print(f"[DistManager] create_dist_row\n{e}")
